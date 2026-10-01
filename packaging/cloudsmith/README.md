# Cloudsmith APT maintenance

Stable releases publish their original amd64 and arm64 `.deb` assets to the public
[`docking/docking-apt`](https://cloudsmith.io/~docking/repos/docking-apt/setup/)
repository. GitHub Actions authenticates as `github-docking` through OIDC; no API
key is needed. Packages use `any-distro/any-version`, component `main`.

## Cloudsmith setup

- Keep the repository public, with **Broadcast** enabled. For free OSS hosting,
  retain the Cloudsmith attribution in the main README. Disable paid overage in
  workspace usage limits if required.
- Give service `github-docking` read and upload access to `docking-apt`.
- Add an OpenID provider with issuer `https://token.actions.githubusercontent.com`,
  allow that service, and require these claims:

  ```json
  {
    "repository": "edumucelli/docking",
    "sub": "repo:edumucelli/docking:environment:cloudsmith"
  }
  ```

  If restricting the audience, use `https://github.com/edumucelli`.

See [Cloudsmith's OIDC setup](https://docs.cloudsmith.com/authentication/setup-cloudsmith-to-authenticate-with-oidc-in-github-actions)
and [OSS hosting policy](https://docs.cloudsmith.com/resources/open-source-hosting-policy).

## GitHub activation

The `cloudsmith` environment must allow only `master`. Set these repository
Actions variables:

| Variable | Value |
| --- | --- |
| `CLOUDSMITH_WORKSPACE` | `docking` |
| `CLOUDSMITH_REPOSITORY` | `docking-apt` |
| `CLOUDSMITH_SERVICE_SLUG` | `github-docking` |
| `CLOUDSMITH_ENABLED` | `false` during setup; `true` after CI passes |

Keep the enable flag at repository scope: the calling job reads it before entering
the environment. These values and the signing fingerprint are public identifiers.

Before enabling, require the binary installation checks to pass on Ubuntu
22.04/24.04 and Debian 12/13 for both architectures. They verify runtime imports;
check desktop startup and X11/Wayland behavior separately on intended systems.

After activation, a successful CI release publishes automatically. The initial
release must include both versioned `.deb` assets; v2.13.7 has only amd64.

## Retry a publication

Open **Actions → Publish Cloudsmith → Run workflow**, choose `master`, and enter
the exact published stable tag, such as `v2.13.8`.

The publisher validates both packages before uploading, skips identical SHA-256
content, and waits for both architectures to be indexed and downloadable. For a
partial upload, retry the same tag and original assets. Conflicting bytes require
a new version or Debian revision; never replace an existing package.

Offline validation of a downloaded release pair:

```bash
python3 packaging/cloudsmith/publish.py --directory incoming --version 2.13.8 --validate-only
.venv/bin/python -m pytest tests/test_cloudsmith_publish.py -q
```

## Verify and announce

Use the repository's **Set Me Up / Debian** page to confirm these public settings
before publishing installation instructions:

| Setting | Value |
| --- | --- |
| APT URI | `https://dl.cloudsmith.io/public/docking/docking-apt/deb/any-distro` |
| Suite / component | `any-version` / `main` |
| Public key | `https://dl.cloudsmith.io/public/docking/docking-apt/gpg.key` |
| Signing fingerprint | `811B48CD4A69170DD98F4F49185CED80A7947754` |

1. Verify `apt update` accepts the signature and `apt-cache policy docking` shows
   Cloudsmith's expected version.
2. Install in a clean supported system and smoke-test the application.
3. Upgrade a previous `.deb` installation with
   `sudo apt install --only-upgrade docking`, and confirm its version changes.
4. Add the verified installation commands to the main README and remove its
   pending-publication notice. Keep direct release downloads available.

Retain previous packages for both architectures and monitor repository usage.
Signing-key changes require updating client instructions; the workflow never
rotates keys or deletes packages.
