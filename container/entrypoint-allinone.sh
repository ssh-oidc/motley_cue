#!/bin/sh
set -eu

: "${MOTLEY_CUE_CONFIG:=/etc/motley_cue/motley_cue.conf}"
: "${FEUDAL_ADAPTER_CONFIG:=/etc/motley_cue/feudal_adapter.conf}"
: "${FLAAT_CONFIG:=/etc/motley_cue/flaat.conf}"
: "${BIND:=127.0.0.1:8080}"
: "${STATE_DIR:=/state}"

export MOTLEY_CUE_CONFIG FEUDAL_ADAPTER_CONFIG FLAAT_CONFIG BIND

for file in "$MOTLEY_CUE_CONFIG" "$FEUDAL_ADAPTER_CONFIG" "$FLAAT_CONFIG"; do
    if [ ! -r "$file" ]; then
        echo "ERROR: required configuration file is not readable: $file" >&2
        exit 1
    fi
done

install -d -m 0755 "$STATE_DIR/etc" "$STATE_DIR/home"
install -d -m 0700 "$STATE_DIR/motley_cue" "$STATE_DIR/ssh"
install -d -m 0755 /run/sshd

# Seed the persistent account database from the image templates on first start.
for f in passwd group shadow gshadow subuid subgid; do
    template="/usr/share/motley-cue/state-templates/$f"
    if [ -e "$template" ] && [ ! -e "$STATE_DIR/etc/$f" ]; then
        cp -a "$template" "$STATE_DIR/etc/$f"
    fi
done

if [ ! -e "$STATE_DIR/etc/login.defs" ]; then
    cp -a /etc/login.defs "$STATE_DIR/etc/login.defs"
fi
if [ ! -e "$STATE_DIR/etc/shells" ]; then
    cp -a /etc/shells "$STATE_DIR/etc/shells"
fi
if [ ! -e "$STATE_DIR/etc/default" ]; then
    cp -a /etc/default "$STATE_DIR/etc/default"
fi
if [ ! -d "$STATE_DIR/etc/skel" ]; then
    cp -a /etc/skel "$STATE_DIR/etc/skel"
fi

chown root:shadow "$STATE_DIR/etc/shadow" "$STATE_DIR/etc/gshadow" 2>/dev/null || true
chmod 0640 "$STATE_DIR/etc/shadow" "$STATE_DIR/etc/gshadow" 2>/dev/null || true
chmod 0644 "$STATE_DIR/etc/passwd" "$STATE_DIR/etc/group" 2>/dev/null || true
chmod 0644 "$STATE_DIR/etc/subuid" "$STATE_DIR/etc/subgid" 2>/dev/null || true

# Host keys must survive restarts and must never be baked into the image.
if [ ! -f "$STATE_DIR/ssh/ssh_host_ed25519_key" ]; then
    ssh-keygen -q -t ed25519 -N '' \
        -f "$STATE_DIR/ssh/ssh_host_ed25519_key" \
        -C "motley-cue appliance"
fi

if [ "${MOTLEY_CUE_VARIANT:-pam}" = "oinit" ]; then
    install -d -m 0755 "$STATE_DIR/ssh/oinit"

    if ! getent passwd oinit >/dev/null 2>&1; then
        useradd --system \
            --shell /usr/bin/oinit-shell \
            --home-dir /var/oinit-shell \
            --no-create-home \
            --badname \
            oinit
    fi

    for file in "$STATE_DIR/ssh/oinit/user-ca.pub" \
                "$STATE_DIR/ssh/oinit/host-key-cert.pub"; do
        if [ ! -s "$file" ]; then
            echo "ERROR: oinit is not provisioned: missing $file" >&2
            echo "Mount the user CA public key and the host certificate into $STATE_DIR/ssh/oinit." >&2
            echo "See container/README.md for the oinit bootstrap steps." >&2
            exit 1
        fi
    done
fi

exec runsvdir /etc/service
