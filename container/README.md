# motley_cue container images

This directory contains a multi-target `Dockerfile` for running motley_cue as
a container. The build context is the repository root.

| Target | Purpose | Runs as |
| --- | --- | --- |
| `api` | motley_cue API only, LDAP/bwidm backends | `motley_cue` (UID 999) |
| `allinone-pam` | motley_cue + `local_unix` + sshd + PAM token login | root |
| `allinone-oinit` | motley_cue + `local_unix` + sshd + oinit login | root |
| `sshd-pam` | SSH host for an external motley_cue API, PAM token login | root |

The external SSH host with oinit certificate login is provided by the
[oinit repository](https://github.com/ssh-oidc/oinit): its
`container/Dockerfile` target `oinit-sshd` publishes `sshoidc/oinit-sshd` with
the same sshd + `oinit-shell`/`oinit-switch` + nslcd setup (and without the
unused `pam-ssh-oidc` package).

The all-in-one images are appliances: the container is the SSH host and the
`local_unix` backend creates real accounts inside it. They must run as root
because `shadow-utils` is used to manage those accounts.

## Building

```bash
docker build -f container/Dockerfile --target api            -t sshoidc/motley-cue:0.8.9            .
docker build -f container/Dockerfile --target allinone-pam   -t sshoidc/motley-cue-allinone:0.8.9-pam   .
docker build -f container/Dockerfile --target allinone-oinit -t sshoidc/motley-cue-allinone:0.8.9-oinit .
docker build -f container/Dockerfile --target sshd-pam       -t sshoidc/motley-cue-sshd:0.8.9-pam       .
# For the external SSH host with oinit login, use sshoidc/oinit-sshd from the
# oinit repository (see the table above).
```

Useful build arguments:

| Argument | Default | Meaning |
| --- | --- | --- |
| `PYTHON_VERSION` | `3.12` | Python base image version |
| `DEBIAN_RELEASE` | `bookworm` | Debian release for the runtime images |
| `OINIT_REF` | `v1.3.2` | oinit git tag/branch used to build the oinit binaries |
| `FEUDAL_ADAPTER_SPEC` | `feudalAdapter==2.0.4` | pip requirement installed in addition to `container/requirements.txt` |
| `KIT_REPO_URL` | KIT bookworm repository | Repository providing `pam-ssh-oidc` |
| `KIT_REPO_KEY_URL` | KIT repository key | Key used for that repository |

The oinit binaries are built from `https://github.com/ssh-oidc/oinit`. To build
from a local checkout instead, change the `oinit-builder` stage or pass a
different `OINIT_REF`.

## API image

The `api` image exposes port 8080 and runs `gunicorn` as the unprivileged
`motley_cue` user. It has no `shadow-utils`, no SSH server, and no local account
database. It refuses to start if `feudal_adapter.conf` selects
`backend = local_unix`; use an all-in-one image, or run the API on the SSH host,
for that backend.

Configuration is read from:

| Variable | Default |
| --- | --- |
| `MOTLEY_CUE_CONFIG` | `/etc/motley_cue/motley_cue.conf` |
| `FEUDAL_ADAPTER_CONFIG` | `/etc/motley_cue/feudal_adapter.conf` |
| `FLAAT_CONFIG` | `/etc/motley_cue/flaat.conf` |
| `BIND` | `0.0.0.0:8080` |
| `ERROR_LOG` / `ACCESS_LOG` | `-` (stderr) |
| `LOG_LEVEL_GUNICORN` | `info` |

`/var/lib/motley_cue` must be writable. It contains the `feudalAdapter` log
file, so mount a volume there when the container filesystem is read-only:

```bash
docker run -d --name motley-cue \
  -p 8080:8080 \
  -v "$PWD/container/config/api/motley_cue.conf:/etc/motley_cue/motley_cue.conf:ro" \
  -v "$PWD/container/config/api/feudal_adapter.conf:/etc/motley_cue/feudal_adapter.conf:ro" \
  -v "$PWD/container/config/api/flaat.conf:/etc/motley_cue/flaat.conf:ro" \
  -v motley-cue-state:/var/lib/motley_cue \
  sshoidc/motley-cue:0.8.9
```

The `feudalAdapter` LDAP backend connects when the API starts, so the LDAP
server must be reachable before the container is considered healthy.

## All-in-one images

The all-in-one images start motley_cue, sshd, and (for PAM) `pam-ssh-oidc`
inside one container. They persist all mutable account and SSH state in
`/state`:

| Path | Contents |
| --- | --- |
| `/state/etc` | `passwd`, `group`, `shadow`, `gshadow`, `subuid`, `subgid`, `login.defs`, `shells`, `default/useradd`, `skel` |
| `/state/home` | user home directories; `/home` is a symlink to this directory |
| `/state/ssh` | SSH host keys |
| `/state/motley_cue` | motley_cue runtime data |
| `/state/ssh/oinit` | oinit user CA and host certificate (oinit variant only) |

Mount `/state` as a volume. The account database is seeded from image templates
on first start; later starts reuse it. Because `/etc/passwd` and friends are
symlinks into `/state`, the image installs wrappers for `useradd`, `usermod`,
`userdel`, `groupadd`, `groupmod`, and `groupdel` that pass `-P /state` to the
real tools (and `-R /state` for `chage`), so account changes go to the
persistent volume.

Configuration is read from the same variables as the API image. The defaults in
the image use `backend = local_unix` and `home_base = /home`.

```bash
docker run -d --name motley-cue \
  -p 2222:22 \
  -v "$PWD/container/config/allinone/motley_cue.conf:/etc/motley_cue/motley_cue.conf:ro" \
  -v "$PWD/container/config/allinone/feudal_adapter.conf:/etc/motley_cue/feudal_adapter.conf:ro" \
  -v "$PWD/container/config/allinone/flaat.conf:/etc/motley_cue/flaat.conf:ro" \
  -v motley-cue-state:/state \
  sshoidc/motley-cue-allinone:0.8.9-pam
```

The API listens on `127.0.0.1:8080` inside the container and is intended to be
reached through the SSH host or a sidecar, not published directly.

### PAM login

`allinone-pam` installs `pam-ssh-oidc` and configures sshd for
`keyboard-interactive` authentication. Edit
`container/config/pam/pam-ssh-oidc-config.ini` (or mount your own over
`/etc/pam.d/pam-ssh-oidc-config.ini`) and point it at the motley_cue API. Users
authenticate with an OIDC token issued by the configured provider.

### oinit login

`allinone-oinit` uses certificate login through `oinit-shell` and
`oinit-switch`. Before the container can start, `oinit` must be provisioned:

1. Start the container once. It generates
   `/state/ssh/ssh_host_ed25519_key` and then exits with an error if the oinit
   files are missing.
2. Sign the host public key with the host CA. If `/state` is a named volume,
   run the helper container below; if it is a bind mount, run the same
   `ssh-keygen` command directly on the host:

   ```bash
   docker run --rm \
     -v motley-cue-state:/state \
     -v "$PWD/oinit:/oinit" \
     -v "$PWD/host-ca:/keys/host-ca:ro" \
     --entrypoint sh \
     sshoidc/motley-cue-allinone:0.8.9-oinit -c '
       ssh-keygen -s /keys/host-ca -I motley-cue-host -h -n localhost \
         /state/ssh/ssh_host_ed25519_key.pub
       cp /state/ssh/ssh_host_ed25519_key-cert.pub /oinit/host-key-cert.pub
     '
   ```

3. Put the user CA public key in place:

   ```bash
   cp user-ca.pub /state/ssh/oinit/user-ca.pub
   chmod 0644 /state/ssh/oinit/*
   ```

   In the named-volume example, `$PWD/oinit` contains
   `host-key-cert.pub`; copy `user-ca.pub` there as well and mount it at
   `/state/ssh/oinit`.
4. Start the container again. `sshd` uses
   `/state/ssh/oinit/host-key-cert.pub` and trusts
   `/state/ssh/oinit/user-ca.pub`.

The certificate's principals must match the hostname users connect to.

## External-API SSH hosts

`sshd-pam` provides only sshd with PAM token login. It looks up users through
NSS/LDAP (`nslcd`) and expects an external motley_cue API with an LDAP backend.
For oinit certificate login, use the `sshoidc/oinit-sshd` image from the oinit
repository (see its `container/README.md` for provisioning and the oinit file
layout, which differs slightly: the host key lives at `/state/ssh/host-key`).

Mount:

| Path | Contents |
| --- | --- |
| `/state` | SSH host keys, and oinit files for the oinit variant |
| `/home` | home directories (`pam_mkhomedir` creates them on first login) |
| `/etc/nslcd.conf` | LDAP bind configuration, readable by user `nslcd` |

If `/etc/nslcd.conf` is not mounted, the image installs an anonymous-bind
template at first start. A typical configuration is:

```text
uid nslcd
gid nslcd
uri ldap://ldap.example.org
base dc=example,dc=org
binddn cn=motley-cue,ou=services,dc=example,dc=org
bindpw secret
```

The PAM image uses the API configured in
`/etc/pam.d/pam-ssh-oidc-config.ini`; the oinit SSH host image uses the
certificates in `/state/ssh/oinit` as described above.

## Health check

The API image has a `HEALTHCHECK` that requests `http://127.0.0.1:8080/` and
fails on connection errors or 5xx responses. Override the URL with
`HEALTHCHECK_URL`.

## Compose examples

`container/compose` contains one example per deployment shape:

| File | Services |
| --- | --- |
| `api.yml` | API only |
| `allinone-pam.yml` | all-in-one PAM appliance |
| `allinone-oinit.yml` | all-in-one oinit appliance |
| `sshd-pam.yml` | API + external SSH host, PAM login |
| `sshd-oinit.yml` | API + external SSH host, oinit login (`sshoidc/oinit-sshd`) |

The compose files mount the example configuration from `container/config`.
Replace those paths and credentials with your own before deploying. The oinit
examples mount `./oinit` (relative to the compose file) at
`/state/ssh/oinit`; create that directory with `user-ca.pub` and
`host-key-cert.pub` before starting.

```bash
docker compose -f container/compose/allinone-pam.yml up -d
```

## Notes and limitations

- Host keys and the account database are state. Back up `/state` before
  replacing the container.
- The API image is compatible with a read-only root filesystem; mount a volume
  at `/var/lib/motley_cue`.
- The all-in-one images write to `/etc` through symlinks into `/state` and are
  not intended to run with a read-only root filesystem.
- `pam-ssh-oidc` is installed from the KIT Debian repository. If that repository
  is unavailable, build with a compatible package source and adjust the
  `apt` steps.
- The images pin `feudalAdapter==2.0.4`. Use `FEUDAL_ADAPTER_SPEC` to install a
  patched build without editing `requirements.txt`.
