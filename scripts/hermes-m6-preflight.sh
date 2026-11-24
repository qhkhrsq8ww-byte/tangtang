#!/usr/bin/env bash
# Read-only Mac mini preflight for TangTang V2 / Hermes-Agent.
# Does not install software, change settings, read secrets, or contact the network.

set -u

section() {
  printf "\n== %s ==\n" "$1"
}

present() {
  if command -v "$1" >/dev/null 2>&1; then
    printf "%s: available\n" "$1"
  else
    printf "%s: not found\n" "$1"
  fi
}

configured() {
  if [ -n "$2" ]; then
    printf "%s: configured (value hidden)\n" "$1"
  else
    printf "%s: not configured\n" "$1"
  fi
}

section "Platform"
printf "OS: %s\n" "$(uname -s 2>/dev/null || echo unknown)"
printf "Architecture: %s\n" "$(uname -m 2>/dev/null || echo unknown)"
printf "macOS: %s\n" "$(sw_vers -productVersion 2>/dev/null || echo unavailable)"

section "Hardware and storage"
MEM_BYTES="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
awk -v bytes="$MEM_BYTES" 'BEGIN { if (bytes > 0) printf "Physical memory: %.1f GB\n", bytes/1024/1024/1024; else print "Physical memory: unavailable" }'
if command -v df >/dev/null 2>&1; then
  AVAIL_KB="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [ -n "${AVAIL_KB:-}" ]; then
    awk -v kb="$AVAIL_KB" 'BEGIN { printf "Free space on home volume: %.1f GB\n", kb/1024/1024 }'
  else
    printf "Free space: unavailable\n"
  fi
fi

section "Runtime prerequisites"
present python3
if command -v python3 >/dev/null 2>&1; then
  python3 --version 2>&1
  python3 -c 'import sys; print("Python version tuple: %d.%d.%d" % sys.version_info[:3])' 2>/dev/null || true
fi
present node
if command -v node >/dev/null 2>&1; then
  node --version 2>&1
fi
present brew
present hermes
if command -v hermes >/dev/null 2>&1; then
  hermes --version 2>&1 || true
fi

section "Local configuration presence (values are never displayed)"
if [ -f "$HOME/.hermes/config.yaml" ]; then printf "Hermes config: present\n"; else printf "Hermes config: absent\n"; fi
if [ -d "$HOME/Library/Application Support/Tangtang" ]; then printf "TangTang application data directory: present\n"; else printf "TangTang application data directory: absent\n"; fi
configured "API_SERVER_KEY" "${API_SERVER_KEY:-}"
configured "TANGTANG_HERMES_API_KEY" "${TANGTANG_HERMES_API_KEY:-}"
printf "TANGTANG_LLM_BACKEND: %s\n" "${TANGTANG_LLM_BACKEND:-direct (default)}"

section "Local Hermes API port"
if command -v nc >/dev/null 2>&1; then
  if nc -z 127.0.0.1 8642 >/dev/null 2>&1; then
    printf "127.0.0.1:8642: accepting TCP connections\n"
  else
    printf "127.0.0.1:8642: not listening (normal before Hermes API setup)\n"
  fi
else
  printf "nc not available; port check skipped\n"
fi

section "Safety"
printf "This script is read-only. It does not display credentials, serial numbers, usernames, or family data.\n"
printf "Node requirement must be checked against the pinned Hermes release (official docs currently recommend Node 26 or Node 24.22.1+).\n"
printf "TangTang V4 requires Python 3.10+; Python 3.11 is recommended.\n"
printf "Do not enable TANGTANG_LLM_BACKEND=hermes until the API toolset allowlist is verified.\n"
