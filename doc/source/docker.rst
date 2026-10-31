.. _docker:

Running motley_cue in containers
================================

The repository contains a multi-target ``Dockerfile`` in ``container/``. The
build context is the repository root. Five images are available:

======================  =============================================  ===============
Target                  Purpose                                        Runs as
======================  =============================================  ===============
``api``                 API only, LDAP/bwidm backends                  ``motley_cue``
``allinone-pam``        motley_cue + ``local_unix`` + sshd + PAM       root
``allinone-oinit``      motley_cue + ``local_unix`` + sshd + oinit     root
``sshd-pam``            SSH host for an external API, PAM login        root
``sshd-oinit``          SSH host for an external API, oinit login      root
======================  =============================================  ===============

The all-in-one images are appliances: the container is the SSH host and
``local_unix`` creates accounts inside it. They run as root because
``shadow-utils`` manages those accounts. The API image has no account database
and runs as an unprivileged user.

Building
--------

Build the image that matches your deployment:

.. code-block:: bash

   docker build -f container/Dockerfile --target api \
       -t sshoidc/motley-cue:0.8.9 .

   docker build -f container/Dockerfile --target allinone-pam \
       -t sshoidc/motley-cue-allinone:0.8.9-pam .

   docker build -f container/Dockerfile --target allinone-oinit \
       -t sshoidc/motley-cue-allinone:0.8.9-oinit .

   docker build -f container/Dockerfile --target sshd-pam \
       -t sshoidc/motley-cue-sshd:0.8.9-pam .

   docker build -f container/Dockerfile --target sshd-oinit \
       -t sshoidc/motley-cue-sshd:0.8.9-oinit .

Build arguments:

``PYTHON_VERSION``
   Python base image version (default ``3.12``).

``DEBIAN_RELEASE``
   Debian release for the runtime images (default ``bookworm``).

``OINIT_REF``
   oinit git tag or branch built into the oinit images (default ``v1.3.2``).

``FEUDAL_ADAPTER_SPEC``
   Additional pip requirement for the adapter (default
   ``feudalAdapter==2.0.4``). Use this to install a patched build.

``KIT_REPO_URL`` / ``KIT_REPO_KEY_URL``
   Repository providing ``pam-ssh-oidc``.

API image
---------

The ``api`` image exposes port 8080 and runs gunicorn as the unprivileged
``motley_cue`` user. It refuses to start if ``feudal_adapter.conf`` selects
``backend = local_unix``, because accounts created in the API container would
not be visible to the SSH host.

Configuration is read from ``MOTLEY_CUE_CONFIG``,
``FEUDAL_ADAPTER_CONFIG``, ``FLAAT_CONFIG``, and ``BIND`` (default
``0.0.0.0:8080``). ``/var/lib/motley_cue`` must be writable; it contains the
``feudalAdapter`` log file. Mount a volume there if the root filesystem is
read-only.

The LDAP backend connects when the API starts. The LDAP server must be
reachable before the container is healthy.

All-in-one images
-----------------

The all-in-one images run motley_cue, sshd, and the selected login mechanism in
one container. All mutable state lives in ``/state``:

``/state/etc``
   Account database (``passwd``, ``group``, ``shadow``, ``gshadow``,
   ``subuid``, ``subgid``, ``login.defs``, ``shells``, ``default/useradd``,
   ``skel``).

``/state/home``
   Home directories. ``/home`` is a symlink to this directory.

``/state/ssh``
   SSH host keys.

``/state/motley_cue``
   motley_cue runtime data.

``/state/ssh/oinit``
   oinit user CA and host certificate (oinit variant only).

Mount ``/state`` as a volume. It is seeded from image templates on first start
and reused afterwards. The image installs wrappers for ``useradd``,
``usermod``, ``userdel``, ``groupadd``, ``groupmod``, and ``groupdel`` that
pass ``-P /state`` to the real tools (and ``-R /state`` for ``chage``), so
account changes go to the persistent volume.

The default configuration uses ``backend = local_unix`` and
``home_base = /home``. The API listens on ``127.0.0.1:8080`` inside the
container; do not publish it unless you intend to expose it.

PAM login
~~~~~~~~~

``allinone-pam`` configures sshd for ``keyboard-interactive`` authentication
through ``pam-ssh-oidc``. Adjust
``/etc/pam.d/pam-ssh-oidc-config.ini`` to point at the motley_cue API. Users
authenticate with an OIDC token from the configured provider.

oinit login
~~~~~~~~~~~

``allinone-oinit`` and ``sshd-oinit`` use certificate login through
``oinit-shell`` and ``oinit-switch``. The container generates
``/state/ssh/ssh_host_ed25519_key`` on first start. It then exits with an error
until the oinit files exist. To provision it:

#. Run the container once to generate the host key.
#. Sign the host public key with the host CA. If ``/state`` is a named volume,
   run this from a helper container with the volume mounted at ``/state``:

   .. code-block:: bash

      ssh-keygen -s host-ca -I motley-cue-host -h -n localhost \
          /state/ssh/ssh_host_ed25519_key.pub

#. Copy the certificate and the user CA public key:

   .. code-block:: bash

      cp /state/ssh/ssh_host_ed25519_key-cert.pub \
          /state/ssh/oinit/host-key-cert.pub
      cp user-ca.pub /state/ssh/oinit/user-ca.pub
      chmod 0644 /state/ssh/oinit/*

#. Start the container again.

The certificate principals must match the hostname clients use.

External-API SSH hosts
----------------------

``sshd-pam`` and ``sshd-oinit`` contain only sshd and the login mechanism. Users
are resolved through NSS/LDAP (``nslcd``), and motley_cue runs separately with
an LDAP backend.

Mount ``/state`` for host keys (and oinit files), ``/home`` for home
directories, and ``/etc/nslcd.conf`` for the LDAP bind configuration. Without
``/etc/nslcd.conf`` the image starts with an anonymous-bind template. A typical
configuration is:

.. code-block:: text

   uid nslcd
   gid nslcd
   uri ldap://ldap.example.org
   base dc=example,dc=org
   binddn cn=motley-cue,ou=services,dc=example,dc=org
   bindpw secret

``pam_mkhomedir`` creates home directories on first login.

Compose examples
----------------

``container/compose`` contains one example per deployment shape:

``api.yml``
   API only.

``allinone-pam.yml``
   All-in-one PAM appliance.

``allinone-oinit.yml``
   All-in-one oinit appliance.

``sshd-pam.yml``
   API and external SSH host with PAM login.

``sshd-oinit.yml``
   API and external SSH host with oinit login.

Replace the example configuration paths and credentials before deploying. The
oinit examples mount ``./oinit`` at ``/state/ssh/oinit``; create that directory
with ``user-ca.pub`` and ``host-key-cert.pub`` first.

.. code-block:: bash

   docker compose -f container/compose/allinone-pam.yml up -d

Health check
------------

The API image checks ``http://127.0.0.1:8080/`` and fails on connection errors
or 5xx responses. Set ``HEALTHCHECK_URL`` to check a different URL.

Limitations
-----------

- Host keys and the account database are state. Back up ``/state`` before
  replacing a container.
- The API image supports a read-only root filesystem; the all-in-one images do
  not, because they write through symlinks into ``/state``.
- ``pam-ssh-oidc`` is installed from the KIT Debian repository. Build with a
  compatible package source if that repository is unavailable.
- The images pin ``feudalAdapter==2.0.4``. Use ``FEUDAL_ADAPTER_SPEC`` to
  install a patched build.

See ``container/README.md`` for copy-paste ``docker run`` examples and the full
environment variable reference.
