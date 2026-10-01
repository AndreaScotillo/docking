# Cloudsmith APT publication

The publisher distributes the versioned GitHub Release `.deb` assets through a
public Cloudsmith repository. The repository is
[`docking/docking-apt`](https://cloudsmith.io/~docking/repos/docking-apt/setup/),
with CI service `github-docking`. Publication is disabled until package
compatibility checks pass and the first complete release is ready.

## 1. Create the Cloudsmith repository

1. Sign up at <https://app.cloudsmith.com/> and create a workspace. Choose a stable
   workspace slug; it becomes part of the APT URL.
2. Go to **Repositories → New repository**, name it `docking-apt`, enable
   **Broadcast**, and select **Open source** visibility.
3. Select `GPL-3.0-or-later` and provide
   `https://github.com/edumucelli/docking` as the project URL.
4. Accept the OSS hosting terms and create the repository. Keep the generated
   signing key for the initial setup and record its full public fingerprint.
5. In workspace **Usage limits**, disable paid overage if you want zero spending.
6. Reserve this repository for Docking's shared stable packages; the publisher
   uses `any-distro/any-version` and component `main`.

Cloudsmith's [OSS policy](https://docs.cloudsmith.com/resources/open-source-hosting-policy)
provides the current allowances and eligibility rules. It requires attribution
for free hosting; the main README credits Cloudsmith for this repository.

## 2. Configure OIDC for GitHub Actions

1. Under **Accounts and teams → Services**, create a service named
   `github-docking`. Record the actual service slug, which can differ from its
   display name.
2. Give the service read and upload access to `docking-apt`. It does not need
   repository administration or deletion privileges.
3. In workspace **Authentication → OpenID**, add a provider with issuer
   `https://token.actions.githubusercontent.com` and allow this service account.
4. Require these exact claims:

   | Claim | Value |
   | --- | --- |
   | `repository` | `edumucelli/docking` |
   | `sub` | `repo:edumucelli/docking:environment:cloudsmith` |

5. If configuring an audience claim too, the pinned CLI action's default is
   `https://github.com/edumucelli`.

The publisher uses the GitHub environment named `cloudsmith`, so an OIDC subject
containing `ref:refs/heads/master` would not match. Branch restriction is applied
on the GitHub environment instead. See the
[Cloudsmith OIDC guide](https://docs.cloudsmith.com/authentication/setup-cloudsmith-to-authenticate-with-oidc-in-github-actions).

If the workspace does not offer service accounts or OIDC, report that before
enabling publication; the committed workflow intentionally uses OIDC and stores
no Cloudsmith API key.

## 3. Configure the GitHub repository

In `edumucelli/docking`:

1. Create **Settings → Environments → cloudsmith**.
2. Restrict deployment branches to `master`. Reviewers are optional; this workflow
   does not require a manual approval for every release.
3. Under **Settings → Secrets and variables → Actions → Variables**, create these
   **repository variables**:

   | Variable | Value |
   | --- | --- |
   | `CLOUDSMITH_WORKSPACE` | `docking` |
   | `CLOUDSMITH_REPOSITORY` | `docking-apt` |
   | `CLOUDSMITH_SERVICE_SLUG` | `github-docking` |
   | `CLOUDSMITH_ENABLED` | `false` until step 4 passes |

These identifiers are not secrets. Use repository variables rather than putting
`CLOUDSMITH_ENABLED` only on the environment: the calling CI job must read it
before the publishing environment is entered.

## 4. Validate compatibility and enable publication

CI installs the existing amd64 and arm64 binaries in Ubuntu 22.04, Ubuntu 24.04,
Debian 12, and Debian 13 containers on native architecture runners. It imports the
installed application and weather dependencies. Where PyWayland is available, it
also imports the native client. These checks are required before a release.

The checks do not prove full desktop or compositor behavior. On intended systems,
also verify Docking starts in an actual desktop session, preserves settings, and
supports the expected X11/Wayland features. Live protocol features need
PyWayland; its vendored fallback only covers the builder's Python minor, so some
hosts must supply the distro package.

After the matrix is green and the intended support scope is confirmed, set
`CLOUDSMITH_ENABLED=true`. Never enable a shared repository solely because a
source-code test matrix passes.

Automatic publication runs after the existing CI workflow successfully creates
a new stable GitHub Release. It does not rely on a separate release event, which
GitHub suppresses for releases created with `GITHUB_TOKEN`.

Both versioned `.deb` assets must exist in the release. Older releases created
before the arm64 normalization fix cannot be bootstrapped unless the original
matching arm64 package is recovered and attached. Prefer the first complete
release after this change; do not silently rebuild or replace existing package
bytes under an already published version.

For bootstrap or repair: **Actions → Publish Cloudsmith → Run workflow**, select
`master`, and enter the exact stable tag, for example `v2.13.6`. The workflow
rejects drafts, prereleases, missing architectures, unexpected package names,
wrong versions, and mismatched Debian revisions.

The Cloudsmith CLI/action are pinned. The publisher checks all matching remote
packages before uploading either architecture, skips only identical SHA-256
content on a retry, and verifies both are processed, downloadable, and indexed.
It never uses `--republish`. A conflict requires a new Debian revision or project
version. For partial publication, rerun the same tag. Do not rebuild first.

## 5. Publish the user installation instructions

Open the live Cloudsmith repository's **Set Me Up / Debian setup** page. Use its
actual URI, suite, component, key URL, and full fingerprint, not a guessed URL.
Verify the configuration points to the shared `any-distro/any-version` packages.
Users of a public repository do not need a Cloudsmith account or download token.

The repository's public configuration was retrieved on 2026-10-01. Its APT URI is
`https://dl.cloudsmith.io/public/docking/docking-apt/deb/any-distro`, suite
`any-version`, and component `main`. The public key fingerprint is:

```text
811B48CD4A69170DD98F4F49185CED80A7947754
```

After the first packages are published and verified, users can configure
`/etc/apt/keyrings/docking-cloudsmith.asc` and
`/etc/apt/sources.list.d/docking.sources` with the following commands. Until
publication, these commands do not make Docking available through APT:

```bash
sudo apt update
sudo apt install curl ca-certificates gnupg
curl -fsSL 'https://dl.cloudsmith.io/public/docking/docking-apt/gpg.key' \
  -o /tmp/docking-cloudsmith.asc
gpg --show-keys --with-fingerprint /tmp/docking-cloudsmith.asc
# Compare with 811B48CD4A69170DD98F4F49185CED80A7947754 above.
sudo install -d -m 0755 /etc/apt/keyrings
sudo install -m 0644 /tmp/docking-cloudsmith.asc /etc/apt/keyrings/docking-cloudsmith.asc
sudo tee /etc/apt/sources.list.d/docking.sources > /dev/null <<'EOF'
Types: deb
URIs: https://dl.cloudsmith.io/public/docking/docking-apt/deb/any-distro
Suites: any-version
Components: main
Architectures: amd64 arm64
Signed-By: /etc/apt/keyrings/docking-cloudsmith.asc
EOF
sudo apt update
apt-cache policy docking
sudo apt install docking
```

An ASCII-armored public key uses `.asc`; if the downloaded key is binary, use a
`.gpg` filename instead. See
[Cloudsmith Debian setup](https://docs.cloudsmith.com/formats/debian-repository)
and [APT keyrings](https://manpages.debian.org/unstable/apt/apt-secure.8.en.html).

After live installation has been verified, add the concrete commands to the main
README and remove its pending-publication notice. Keep direct Release downloads
available as a fallback.

## 6. Verify upgrades and retain previous packages

In clean supported systems:

1. Verify `apt update` succeeds without bypassing signature verification.
2. Verify `apt-cache policy docking` shows the correct origin and version.
3. Install the published package and smoke-test the desktop application.
4. Starting from the previous package, run `sudo apt install --only-upgrade docking`
   after a newer package is published and confirm the installed version changes.
5. Repeat with a previously downloaded `.deb` installation; no uninstall is
   needed when the package name matches and the repository version is higher.

Subsequent updates use `sudo apt update` and `sudo apt upgrade`. Unattended updates
and graphical updater behavior depend on the user's origin policy.

Keep previous known-good versions of both architectures and monitor storage and
delivery usage. The workflow does not delete old packages or regenerate signing
keys. Key changes require an explicit client migration.

## Local verification

Validate a downloaded release pair without credentials or network access:

```bash
python3 packaging/cloudsmith/publish.py \
  --directory incoming --version 2.13.6 --validate-only
.venv/bin/python -m pytest tests/test_cloudsmith_publish.py -q
```
