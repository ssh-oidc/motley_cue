.. _development:

For developers
==============

Branching model
---------------

- ``prerel`` is the development branch. All day-to-day work lands here.
- Feature and fix branches branch off ``prerel`` and merge back into
  ``prerel``, preferably via pull request, with green CI.
- ``master`` is the release branch. It advances only via release pull
  requests ``prerel`` → ``master``, opened once a release is ready — never
  by direct pushes. (The last such release PR was ``v0.7.1``; ``master``
  has since advanced outside that flow, which is why this rule is now
  written down.)
- ``vX.Y.Z`` tags are created manually on ``master`` after the release PR
  is merged.

Releasing
---------

The version is tracked in three places, kept in sync by ``bump2version``
(configured in ``.bumpversion.cfg``):

- ``motley_cue/VERSION`` (Python package version)
- ``debian/changelog`` (top entry, Debian package version)
- ``rpm/motley-cue.spec`` (``Version:``, RPM package version)

When to bump
^^^^^^^^^^^^

The version on ``prerel`` always names the release under development:
``0.8.9~rcN`` snapshots are release candidates for ``0.8.9``. The bump
therefore happens once per release, on ``prerel``, **right after** the
previous release is tagged::

    git switch prerel
    bump2version patch

Use ``patch`` unless the scope of the next release is already known to
require ``minor`` (new backwards-compatible functionality) or ``major``
(breaking changes) — then bump straight to that level. If the scope only
becomes clear mid-cycle, bump again at release time, as the final commit
before (or the first commit inside) the release pull request;
``bump2version`` moves cleanly between levels (``0.8.9 → 0.9.0``).

Why after, not before: prerel snapshots are published to the ``prerel``
package repo as ``X.Y.Z~rcN``, where ``N`` counts the commits ahead of
``master`` and resets to 1 on every release merge. If ``prerel`` kept the
just-released version, the next snapshots would reuse filenames already
published from earlier commits (``0.8.8~rc1`` twice), and the repo rejects
them ("already published from a different commit"). Bumping right after
the tag keeps every snapshot filename unique and sorting after the
release it follows.

Do not bump when starting a feature branch: every branch would edit the
same single-line files and conflict on merge. The single post-release
bump above is the only routine exception.

Rules:

- Never hand-edit the version strings. Hand edits desynchronise
  ``.bumpversion.cfg`` and the tool stops working.
- The tool never tags (``tag = False``). ``vX.Y.Z`` tags are created
  manually on ``master`` when a release is published (see below).
- Prerelease numbering (``X.Y.Z~rcN``) is fully automatic: GitLab CI
  rewrites the version at build time via
  ``.gitlab-ci-scripts/set-prerelease-version.sh``. Nothing to do manually.

Release checklist
^^^^^^^^^^^^^^^^^

1. All feature pull requests merged to ``prerel``; the ``prerel``
   pipeline is green, **including the integration tests**. Do not advance to the next step
   on red integration.
2. If the release level differs from the version on ``prerel`` (e.g. the
   scope grew from patch to minor), ``bump2version [minor|major]`` on
   ``prerel``.
3. Open pull request ``prerel`` → ``master`` titled ``vX.Y.Z``, review,
   merge.
4. Check that the GitLab pipeline for the merge (step 3) is fully green
   on ``master``, **including the integration tests**. Do not
   proceed until it is — the next step cannot be undone cleanly.
5. Create a release on GitHub from the release (the merge commit on
   ``master``): enter ``vX.Y.Z`` as a new tag — publishing the release
   creates the tag, which triggers the PyPI publish. Add release notes
   describing the changes since the previous release.
6. Back on ``prerel``: ``bump2version patch`` (or the already-known next
   level) and push, so the following snapshots become candidates for the
   next release and publish cleanly (see "When to bump").

.. important::

   Never publish the release before the GitLab integration tests pass.
   Merging to ``master`` starts the GitLab pipeline automatically via the
   mirror, but publishing the release creates the tag, which triggers the
   PyPI publish, which cannot be undone cleanly — publishing a broken
   ``master`` publishes a broken release. Wait for builds *and*
   integration tests, then publish.

Documentation versions
----------------------

This documentation is published on `Read the Docs
<https://motley-cue.readthedocs.io/>`_, which builds each version
separately:

- ``/en/latest/`` tracks ``master`` (released documentation),
- ``/en/prerel/`` tracks ``prerel`` (upcoming documentation),
- ``/en/stable/`` tracks the latest ``vX.Y.Z`` tag.

Document new ``prerel`` features directly on ``prerel`` — they show up
under ``/en/prerel/`` before the release, while ``/en/latest/`` keeps
showing ``master``. Rebuilds happen automatically on every push; nothing
needs to be configured in this repository for that.


Docker for SSH-OIDC
-------------------

`motley_cue_docker <https://github.com/dianagudu/motley_cue_docker>`_ allows you to run the whole SSH-OIDC set-up in Docker containers.

.. warning::

    motley_cue_docker is not regularly maintained.
