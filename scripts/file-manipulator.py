import os
import uuid
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

# Same file as https://gitlab.com/almontem/file-manipulator/-/raw/main/foo.yaml
# (the web raw URL redirects to sign-in for non-browser clients; API is reliable).
GITLAB_API_BASE = "https://gitlab.com/api/v4"
GITLAB_PROJECT_PATH = "almontem/file-manipulator"
GITLAB_DEFAULT_BRANCH = "main"
REPO_FILE_PATH = "foo.yaml"
GITLAB_FILE_URL = (
    f"{GITLAB_API_BASE}/projects/{quote(GITLAB_PROJECT_PATH, safe='')}/"
    f"repository/files/{quote(REPO_FILE_PATH, safe='')}/raw?ref={GITLAB_DEFAULT_BRANCH}"
)
TMP_YAML_PATH = Path("/tmp/foo.yaml")
# Prefix for branches created by push_tmp_yaml_and_open_mr (unique suffix per run).
SYNC_MR_SOURCE_BRANCH_PREFIX = "sync-foo-yaml-"


def _gitlab_token() -> str:
    token = os.environ.get("GITLAB_TOKEN")
    if token:
        return token
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.is_file():
        raise FileNotFoundError(
            f"Set GITLAB_TOKEN or create {env_file}"
        )
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith("GITLAB_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise ValueError("GITLAB_TOKEN not found in .env")


def _gitlab_api_headers() -> dict[str, str]:
    return {"PRIVATE-TOKEN": _gitlab_token()}


def _project_api_root() -> str:
    return f"{GITLAB_API_BASE}/projects/{quote(GITLAB_PROJECT_PATH, safe='')}"


def fetch_gitlab(url: str) -> requests.Response:
    """GET a GitLab URL using a personal access token from the environment or .env."""
    headers = _gitlab_api_headers()
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    return response


def print_yaml_content(response: requests.Response) -> None:
    """Parse the response body as YAML and print it in a readable form."""
    data = yaml.safe_load(response.text)
    print(yaml.dump(data, default_flow_style=False, sort_keys=False))


def read_yaml_from_tmp(path: Path | str = TMP_YAML_PATH) -> object:
    """Load and parse YAML from a file (default: /tmp/foo.yaml)."""
    p = Path(path)
    text = p.read_text()
    return yaml.safe_load(text)


def tmp_yaml_matches_gitlab(response: requests.Response) -> bool:
    """True if parsed YAML in /tmp/foo.yaml equals parsed YAML from GitLab."""
    local = read_yaml_from_tmp()
    remote = yaml.safe_load(response.text)
    return local == remote


def create_gitlab_branch(name: str, ref: str = GITLAB_DEFAULT_BRANCH) -> dict:
    """Create a new branch from ref (e.g. main)."""
    url = f"{_project_api_root()}/repository/branches"
    response = requests.post(
        url,
        headers=_gitlab_api_headers(),
        json={"branch": name, "ref": ref},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def update_gitlab_file_on_branch(
    branch: str,
    content: str,
    commit_message: str,
    file_path: str = REPO_FILE_PATH,
) -> dict:
    """Commit updated file content on the given branch."""
    enc = quote(file_path, safe="")
    url = f"{_project_api_root()}/repository/files/{enc}"
    response = requests.put(
        url,
        headers=_gitlab_api_headers(),
        json={
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def create_gitlab_merge_request(
    source_branch: str,
    title: str,
    target_branch: str = GITLAB_DEFAULT_BRANCH,
    description: str = "",
) -> dict:
    """Open an MR from source_branch into target_branch."""
    url = f"{_project_api_root()}/merge_requests"
    response = requests.post(
        url,
        headers=_gitlab_api_headers(),
        json={
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def fetch_repo_file_raw_on_branch(branch: str, file_path: str = REPO_FILE_PATH) -> str:
    """Return the raw file text at file_path on branch, or empty string if missing (404)."""
    enc = quote(file_path, safe="")
    url = f"{_project_api_root()}/repository/files/{enc}/raw"
    response = requests.get(
        url,
        headers=_gitlab_api_headers(),
        params={"ref": branch},
        timeout=60,
    )
    if response.status_code == 404:
        return ""
    response.raise_for_status()
    return response.text


def has_open_mr_with_same_foo_yaml_as_local() -> bool:
    """
    True if some open MR into main already has the same parsed foo.yaml on its source
    branch as /tmp/foo.yaml. Different proposed content (e.g. one MR deletes, another
    adds) allows multiple open MRs; we only skip duplicate proposals.
    """
    local_text = TMP_YAML_PATH.read_text()
    local_parsed = yaml.safe_load(local_text)
    page = 1
    while True:
        response = requests.get(
            f"{_project_api_root()}/merge_requests",
            headers=_gitlab_api_headers(),
            params={
                "state": "opened",
                "target_branch": GITLAB_DEFAULT_BRANCH,
                "per_page": 100,
                "page": page,
            },
            timeout=60,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            return False
        for mr in batch:
            src = mr.get("source_branch")
            if not src:
                continue
            src_pid = mr.get("source_project_id")
            tgt_pid = mr.get("project_id")
            if src_pid is not None and tgt_pid is not None and src_pid != tgt_pid:
                continue
            remote_text = fetch_repo_file_raw_on_branch(src)
            remote_parsed = yaml.safe_load(remote_text)
            if remote_parsed == local_parsed:
                return True
        if len(batch) < 100:
            return False
        page += 1


def push_tmp_yaml_and_open_mr() -> dict:
    """
    Push `/tmp/foo.yaml` contents to a new branch and open a merge request to main.
    """
    body = TMP_YAML_PATH.read_text()
    branch = f"{SYNC_MR_SOURCE_BRANCH_PREFIX}{uuid.uuid4().hex[:12]}"
    create_gitlab_branch(branch)
    update_gitlab_file_on_branch(
        branch,
        body,
        "Update foo.yaml from local /tmp/foo.yaml",
    )
    return create_gitlab_merge_request(
        branch,
        "Update foo.yaml from /tmp/foo.yaml",
        description="Proposes changes from local `/tmp/foo.yaml` to `foo.yaml` on `main`.",
    )


if __name__ == "__main__":
    resp = fetch_gitlab(GITLAB_FILE_URL)
    print_yaml_content(resp)
    match = tmp_yaml_matches_gitlab(resp)
    print(match)
    if not match:
        if has_open_mr_with_same_foo_yaml_as_local():
            print(
                "Skipped: an open merge request already proposes the same "
                "foo.yaml as /tmp/foo.yaml."
            )
        else:
            mr = push_tmp_yaml_and_open_mr()
            print(mr.get("web_url", mr))
