import json
import os

import redis
from fastapi import Request
from litellm.proxy._types import UserAPIKeyAuth, LitellmUserRoles, ProxyException
from litellm.proxy.utils import hash_token
from litellm.proxy import proxy_server

_REDIS = redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), port=6379, decode_responses=True)


async def user_api_key_auth(request: Request, api_key: str) -> UserAPIKeyAuth:

    client_ip = get_client_ip(request)
    path = request.url.path
    key_preview = (api_key or "None")[:8]
    print(f"Client IP: {client_ip} | Path: {path} | Key: {key_preview}...")

    foo_signature = request.headers.get("x-foo-signature")
    print(f"Headers: {dict(request.headers)}")
    print(f"x-foo-signature: received={foo_signature!r}")

    if api_key == os.environ.get("LITELLM_MASTER_KEY"):
        raise Exception("Master key detected — falling back to regular LiteLLM auth")

    raw = _REDIS.get(api_key)
    if raw is not None:
        cached = json.loads(raw)
        if cached.get("verified") is True:
            cached_owner = cached.get("owner")
            print(f"Cache hit - authorized key on {path}: owner={cached_owner!r}")
            return UserAPIKeyAuth(api_key=api_key)
        print(f"Cache hit - rejected key on {path}: verified=False")
        raise ProxyException(message="Authentication failed: token not verified", type="auth_error", param="api_key", code=401)

    exists, metadata = await get_key_metadata(api_key)

    if not exists:
        print(f"Rejected key on {path}: not found in DB")
        raise ProxyException(message="Authentication failed: key not found", type="auth_error", param="api_key", code=401)

    # Empty metadata means a LiteLLM-generated session/system key (e.g. dashboard login)
    # Do not cache these — they are managed by LiteLLM internally
    if not metadata:
        print(f"System key authorized on {path}")
        return UserAPIKeyAuth(
            api_key=api_key,
            user_role=LitellmUserRoles.PROXY_ADMIN,
        )

    owner = metadata.get("owner")
    if owner != "malmonte":
        print(f"Rejected key on {path}: owner={owner!r}, expected 'malmonte'")
        raise ProxyException(message="Authentication failed: unauthorized owner", type="auth_error", param="api_key", code=401)

    _REDIS.set(api_key, json.dumps({**metadata, "verified": True}))
    print(f"Authorized key on {path}: owner={owner!r}")
    return UserAPIKeyAuth(api_key=api_key)


async def get_key_metadata(api_key: str) -> tuple[bool, dict]:
    """Returns (exists_in_db, metadata)."""
    if proxy_server.prisma_client is None:
        return False, {}
    try:
        hashed = hash_token(api_key)
        record = await proxy_server.prisma_client.db.litellm_verificationtoken.find_unique(
            where={"token": hashed}
        )
        if record is None:
            return False, {}
        meta = getattr(record, "metadata", None) or getattr(record, "metadata_", None)
        return True, (meta if isinstance(meta, dict) else {})
    except Exception as e:
        print(f"Metadata lookup failed: {e}")
    return False, {}

def get_client_ip(request):
    headers = request.headers

    # Cloudflare
    if headers.get("cf-connecting-ip"):
        return headers.get("cf-connecting-ip")

    # Standard proxy header
    if headers.get("x-forwarded-for"):
        return headers.get("x-forwarded-for").split(",")[0].strip()

    # AWS / other proxies
    if headers.get("x-real-ip"):
        return headers.get("x-real-ip")

    return request.client.host