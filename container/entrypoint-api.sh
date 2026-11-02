#!/bin/sh
set -eu

: "${MOTLEY_CUE_CONFIG:=/etc/motley_cue/motley_cue.conf}"
: "${FEUDAL_ADAPTER_CONFIG:=/etc/motley_cue/feudal_adapter.conf}"
: "${FLAAT_CONFIG:=/etc/motley_cue/flaat.conf}"
: "${BIND:=0.0.0.0:8080}"

export MOTLEY_CUE_CONFIG FEUDAL_ADAPTER_CONFIG FLAAT_CONFIG BIND

for file in "$MOTLEY_CUE_CONFIG" "$FEUDAL_ADAPTER_CONFIG" "$FLAAT_CONFIG"; do
    if [ ! -r "$file" ]; then
        echo "ERROR: required configuration file is not readable: $file" >&2
        exit 1
    fi
done

# The api image has no shadow-utils and no host account database. Running the
# local_unix backend here would create accounts inside the container that the
# SSH host cannot see, so refuse to start instead of failing at first login.
if grep -Eq '^[[:space:]]*backend[[:space:]]*=[[:space:]]*local_unix[[:space:]]*$' \
        "$FEUDAL_ADAPTER_CONFIG"; then
    echo "ERROR: backend=local_unix is not supported by the API-only image." >&2
    echo "Use the allinone-pam or allinone-oinit image, or run motley_cue on the SSH host." >&2
    exit 1
fi

if [ ! -w /var/lib/motley_cue ]; then
    echo "ERROR: /var/lib/motley_cue is not writable by $(id -un)." >&2
    echo "Mount a writable volume there or fix its ownership." >&2
    exit 1
fi

exec gunicorn motley_cue.api:api \
    -k uvicorn.workers.UvicornWorker \
    --config /usr/lib/motley-cue/etc/gunicorn/gunicorn.conf.py
