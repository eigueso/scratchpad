package main

import (
	"encoding/base64"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
)

const (
	listenAddr = ":8080"
	targetURL  = "http://localhost:4000"
)

func loggingHandler(proxy http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		auth := r.Header.Get("Authorization")
		if encoded, ok := strings.CutPrefix(auth, "Bearer "); ok {
			log.Printf("encoded: %s", encoded)
			decoded, err := base64.StdEncoding.DecodeString(encoded)
			if err != nil {
				log.Printf("failed to decode token: %v", err)
				http.Error(w, "invalid token", http.StatusUnauthorized)
				return
			}
			token := string(decoded)
			log.Printf("token: %s", token)
			r.Header.Set("Authorization", "Bearer "+token)
		}
		for name, values := range r.Header {
			log.Printf("header %s: %s", name, strings.Join(values, ", "))
		}
		proxy.ServeHTTP(w, r)
	})
}

func main() {
	target, err := url.Parse(targetURL)
	if err != nil {
		log.Fatalf("invalid target URL: %v", err)
	}

	proxy := httputil.NewSingleHostReverseProxy(target)

	log.Printf("starting proxy on %s -> %s", listenAddr, targetURL)
	if err := http.ListenAndServe(listenAddr, loggingHandler(proxy)); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
