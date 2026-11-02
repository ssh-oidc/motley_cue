# syntax=docker/dockerfile:1.7

# motley_cue container images.
#
# Build context is the repository root, e.g.:
#   docker build -f container/Dockerfile --target api -t sshoidc/motley-cue .
#
# Targets:
#   api             API only, unprivileged, LDAP/bwidm backends
#   allinone-pam    appliance: local_unix + sshd + pam-ssh-oidc
#   allinone-oinit  appliance: local_unix + sshd + oinit
#   sshd-pam        SSH host for an external API (LDAP), PAM login
#
# The external SSH host with oinit login is provided by the oinit repository
# (target "oinit-sshd", image sshoidc/oinit-sshd).
# The appliance targets run as root because local_unix invokes shadow-utils.
# The api target runs as the unprivileged motley_cue user.

ARG PYTHON_VERSION=3.12
ARG DEBIAN_RELEASE=bookworm
ARG OINIT_REF=v1.3.2
ARG FEUDAL_ADAPTER_SPEC=feudalAdapter==2.0.4
ARG KIT_REPO_URL=https://repo.data.kit.edu/debian/bookworm
ARG KIT_REPO_KEY_URL=https://repo.data.kit.edu/repo-data-kit-edu-key.gpg

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_RELEASE} AS python-builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        libffi-dev \
        libldap2-dev \
        libsasl2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY container/requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

COPY . /src/motley_cue
RUN /opt/venv/bin/pip install --no-cache-dir --no-deps /src/motley_cue

# Optional replacement for the pinned feudalAdapter, e.g. a patched build:
#   --build-arg FEUDAL_ADAPTER_SPEC='feudalAdapter @ git+https://...@v2.0.4-f1'
ARG FEUDAL_ADAPTER_SPEC
RUN /opt/venv/bin/pip install --no-cache-dir --no-deps "${FEUDAL_ADAPTER_SPEC}"

# ---------------------------------------------------------------------------
# Runtime base shared by the Python images
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_RELEASE} AS python-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libldap-2.5-0 \
        libsasl2-2 \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-builder /opt/venv /opt/venv
COPY etc/gunicorn.conf.py /usr/lib/motley-cue/etc/gunicorn/gunicorn.conf.py
COPY etc/flaat.conf etc/privacystatement.md /usr/share/motley-cue/defaults/
COPY etc/motley_cue.conf etc/feudal_adapter.conf /usr/share/motley-cue/defaults/
COPY container/entrypoint-api.sh container/healthcheck.sh /usr/local/bin/
RUN chmod 0755 /usr/local/bin/entrypoint-api.sh /usr/local/bin/healthcheck.sh

# ---------------------------------------------------------------------------
# API only: LDAP/bwidm, no local account management
# ---------------------------------------------------------------------------
FROM python-runtime AS api

RUN groupadd --system --gid 999 motley_cue \
    && useradd --system --uid 999 --gid motley_cue \
        --home-dir /var/lib/motley_cue --shell /usr/sbin/nologin motley_cue \
    && install -d -m 0755 /etc/motley_cue \
    && install -d -m 0700 -o motley_cue -g motley_cue \
        /var/lib/motley_cue /var/log/motley_cue /run/motley_cue

COPY container/config/api/motley_cue.conf container/config/api/feudal_adapter.conf /etc/motley_cue/
COPY etc/flaat.conf etc/privacystatement.md /etc/motley_cue/

ENV MOTLEY_CUE_CONFIG=/etc/motley_cue/motley_cue.conf \
    FEUDAL_ADAPTER_CONFIG=/etc/motley_cue/feudal_adapter.conf \
    FLAAT_CONFIG=/etc/motley_cue/flaat.conf \
    BIND=0.0.0.0:8080 \
    ERROR_LOG=- \
    ACCESS_LOG=- \
    LOG_LEVEL_GUNICORN=info

USER motley_cue
EXPOSE 8080
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["/usr/local/bin/healthcheck.sh"]
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint-api.sh"]

# ---------------------------------------------------------------------------
# oinit server binaries
# ---------------------------------------------------------------------------
FROM golang:1.24-alpine AS oinit-builder

ARG OINIT_REF
RUN apk add --no-cache git
RUN git clone --depth 1 --branch "${OINIT_REF}" https://github.com/ssh-oidc/oinit.git /src/oinit
WORKDIR /src/oinit
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/oinit-shell ./cmd/oinit-shell \
    && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/oinit-switch ./cmd/oinit-switch

# ---------------------------------------------------------------------------
# Appliance base: the container is the SSH host
# ---------------------------------------------------------------------------
FROM python-runtime AS allinone-base

ARG DEBIAN_RELEASE
ARG KIT_REPO_URL
ARG KIT_REPO_KEY_URL

RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && chmod 0755 /usr/sbin/policy-rc.d

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        gpg \
        libcap2-bin \
        openssh-client \
        openssh-server \
        procps \
        runit \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL "${KIT_REPO_KEY_URL}" | gpg --dearmor -o /etc/apt/keyrings/kitrepo.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/kitrepo.gpg] ${KIT_REPO_URL} ./" \
        > /etc/apt/sources.list.d/kitrepo.list \
    && rm -f /usr/sbin/policy-rc.d \
    && apt-get purge -y --auto-remove curl gpg \
    && rm -rf /var/lib/apt/lists/*

# Do not bake host keys into a public image. Host keys live in /state.
RUN rm -f /etc/ssh/ssh_host_* \
    && sed -i 's|^HostKey /etc/ssh/|#HostKey /etc/ssh/|' /etc/ssh/sshd_config

# A dedicated range keeps deployed users away from image system users.
RUN sed -i \
        -e 's/^UID_MIN.*/UID_MIN 2000/' \
        -e 's/^UID_MAX.*/UID_MAX 60000/' \
        -e 's/^GID_MIN.*/GID_MIN 2000/' \
        -e 's/^GID_MAX.*/GID_MAX 60000/' \
        /etc/login.defs

RUN install -d -m 0755 /etc/motley_cue /etc/oinit /usr/share/motley-cue/state-templates \
    && install -d -m 0700 /var/lib/motley_cue /var/log/motley_cue /run/motley_cue \
    && rm -rf /home \
    && ln -s /state/home /home

# shadow-utils refuses to modify /etc/passwd when it is a symlink (which it is
# here, pointing into /state). Run the group/user tools against /state as a
# prefix (-P) instead of a chroot (-R): -P keeps the shell checks in the real
# root and creates homes through the /home symlink. NSS still reads the same
# files through the /etc symlinks. chage has no -P, so it uses -R.
RUN install -d -m 0755 /usr/local/sbin \
    && for tool in useradd usermod userdel groupadd groupmod groupdel; do \
        printf '#!/bin/sh\nexec /usr/sbin/%s -P /state "$@"\n' "$tool" \
            > "/usr/local/sbin/$tool"; \
        chmod 0755 "/usr/local/sbin/$tool"; \
    done \
    && printf '#!/bin/sh\nexec /usr/bin/chage -R /state "$@"\n' \
        > /usr/local/sbin/chage \
    && chmod 0755 /usr/local/sbin/chage

COPY etc/shells /etc/motley_cue/shells
COPY etc/templates /etc/motley_cue/templates
COPY etc/flaat.conf etc/privacystatement.md /etc/motley_cue/
COPY container/config/allinone/motley_cue.conf /etc/motley_cue/motley_cue.conf
COPY container/config/allinone/feudal_adapter.conf /etc/motley_cue/feudal_adapter.conf

COPY container/runit/motley-cue/run /etc/sv/motley-cue/run
RUN chmod 0755 /etc/sv/motley-cue/run \
    && ln -sf /etc/sv/motley-cue /etc/service/motley-cue \
    && sed -i '1i session required pam_mkhomedir.so skel=/etc/skel umask=0077' \
        /etc/pam.d/common-session

COPY container/entrypoint-allinone.sh /usr/local/bin/entrypoint-allinone.sh
RUN chmod 0755 /usr/local/bin/entrypoint-allinone.sh

# The account database is the appliance's state. Keep the image defaults as
# templates, then point /etc at the persistent volume. This is done last: any
# useradd/apt run after this point would write into the (not yet seeded) volume.
RUN for f in passwd group shadow gshadow subuid subgid; do \
        if [ -e "/etc/$f" ]; then \
            cp -a "/etc/$f" "/usr/share/motley-cue/state-templates/$f"; \
        fi; \
    done \
    && for f in passwd group shadow gshadow subuid subgid; do \
        if [ -e "/etc/$f" ]; then \
            rm -f "/etc/$f"; \
            ln -s "/state/etc/$f" "/etc/$f"; \
        fi; \
    done

EXPOSE 22 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint-allinone.sh"]

# ---------------------------------------------------------------------------
# Appliance with PAM token login
# ---------------------------------------------------------------------------
FROM allinone-base AS allinone-pam

# pam-ssh-oidc exists only for amd64 in the KIT repository.
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && chmod 0755 /usr/sbin/policy-rc.d \
    && apt-get update \
    && apt-get install -y --no-install-recommends pam-ssh-oidc \
    && rm -f /usr/sbin/policy-rc.d \
    && rm -rf /var/lib/apt/lists/*

ENV MOTLEY_CUE_VARIANT=pam
COPY container/config/pam/pam-ssh-oidc-config.ini /etc/pam.d/pam-ssh-oidc-config.ini
COPY container/config/allinone/sshd-pam.conf /etc/ssh/sshd_config.d/10-motley-cue.conf
RUN sed -i '1i auth [success=done default=die] pam_oidc_token.so config=/etc/pam.d/pam-ssh-oidc-config.ini' \
        /etc/pam.d/sshd

# ---------------------------------------------------------------------------
# Appliance with oinit certificate login
# ---------------------------------------------------------------------------
FROM allinone-base AS allinone-oinit

ENV MOTLEY_CUE_VARIANT=oinit
COPY --from=oinit-builder /out/oinit-shell /usr/bin/oinit-shell
COPY --from=oinit-builder /out/oinit-switch /usr/bin/oinit-switch
RUN chmod 0755 /usr/bin/oinit-shell /usr/bin/oinit-switch \
    && setcap cap_chown=ep /usr/bin/oinit-switch

COPY container/config/oinit/oinit-switch.conf /etc/oinit/oinit-switch.conf
COPY container/config/oinit/sshd_config.append /etc/oinit/sshd_config.append
RUN sed -i 's|^HostKey /etc/ssh/|#HostKey /etc/ssh/|' /etc/ssh/sshd_config \
    && cat /etc/oinit/sshd_config.append >> /etc/ssh/sshd_config \
    && printf '%s\n%s\n' \
        'auth [success=ignore default=1] pam_succeed_if.so use_uid user = oinit' \
        'auth sufficient                 pam_succeed_if.so uid ne 0' \
        | cat - /etc/pam.d/su > /tmp/su \
    && mv /tmp/su /etc/pam.d/su \
    && chmod 0644 /etc/pam.d/su

# ---------------------------------------------------------------------------
# SSH host for an external motley_cue API (LDAP backend)
# ---------------------------------------------------------------------------
FROM debian:${DEBIAN_RELEASE}-slim AS sshd-base

ARG DEBIAN_RELEASE
ARG KIT_REPO_URL
ARG KIT_REPO_KEY_URL

ENV DEBIAN_FRONTEND=noninteractive

RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d \
    && chmod 0755 /usr/sbin/policy-rc.d

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        gpg \
        libcap2-bin \
        libnss-ldapd \
        nslcd \
        openssh-client \
        openssh-server \
        procps \
        runit \
        tini \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL "${KIT_REPO_KEY_URL}" | gpg --dearmor -o /etc/apt/keyrings/kitrepo.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/kitrepo.gpg] ${KIT_REPO_URL} ./" \
        > /etc/apt/sources.list.d/kitrepo.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends pam-ssh-oidc \
    && rm -f /usr/sbin/policy-rc.d \
    && apt-get purge -y --auto-remove curl gpg \
    && rm -rf /var/lib/apt/lists/*

RUN rm -f /etc/ssh/ssh_host_* /etc/nslcd.conf \
    && sed -i 's|^HostKey /etc/ssh/|#HostKey /etc/ssh/|' /etc/ssh/sshd_config \
    && install -d -m 0755 /etc/oinit \
    && install -d -m 0750 /home \
    && sed -i '1i session required pam_mkhomedir.so skel=/etc/skel umask=0077' \
        /etc/pam.d/common-session

COPY container/config/sshd/nsswitch.conf /etc/nsswitch.conf
COPY container/config/sshd/nslcd.conf.template /etc/nslcd.conf.template
COPY container/runit/nslcd/run /etc/sv/nslcd/run
RUN chmod 0755 /etc/sv/nslcd/run \
    && ln -sf /etc/sv/nslcd /etc/service/nslcd

COPY container/entrypoint-sshd.sh /usr/local/bin/entrypoint-sshd.sh
RUN chmod 0755 /usr/local/bin/entrypoint-sshd.sh

EXPOSE 22
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint-sshd.sh"]

FROM sshd-base AS sshd-pam

ENV MOTLEY_CUE_VARIANT=pam
COPY container/config/sshd/pam-ssh-oidc-config.ini /etc/pam.d/pam-ssh-oidc-config.ini
COPY container/config/sshd/sshd-pam.conf /etc/ssh/sshd_config.d/10-motley-cue.conf
RUN sed -i '1i auth [success=done default=die] pam_oidc_token.so config=/etc/pam.d/pam-ssh-oidc-config.ini' \
        /etc/pam.d/sshd

# The external SSH host with oinit certificate login is not built here
# anymore: it is provided by the oinit repository (container/Dockerfile
# target "oinit-sshd", image sshoidc/oinit-sshd). It provides the same
# sshd + oinit-shell/switch + nslcd setup without the pam-ssh-oidc package.