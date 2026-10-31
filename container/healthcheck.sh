#!/bin/sh
set -eu

: "${HEALTHCHECK_URL:=http://127.0.0.1:8080/}"

exec python - "$HEALTHCHECK_URL" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=3) as response:
        sys.exit(0 if response.status < 500 else 1)
except Exception:
    sys.exit(1)
PY
