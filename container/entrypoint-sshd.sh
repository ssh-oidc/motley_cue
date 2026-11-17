#!/bin/sh
set -eu

: "${STATE_DIR:=/state}"

install -d -m 0700 "$STATE_DIR/ssh"
install -d -m 0755 /run/sshd
install -d -m 0755 -o nslcd -g nslcd /run/nslcd

if [ ! -f "$STATE_DIR/ssh/ssh_host_ed25519_key" ]; then
    ssh-keygen -q -t ed25519 -N '' \
        -f "$STATE_DIR/ssh/ssh_host_ed25519_key" \
        -C "motley-cue ssh host"
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
            exit 1
        fi
    done
fi

if [ ! -e /etc/nslcd.conf ]; then
    install -m 0600 -o nslcd -g nslcd /etc/nslcd.conf.template /etc/nslcd.conf
fi

exec runsvdir /etc/service
