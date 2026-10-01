#!/bin/sh
# Print a deb822 source for Debian, Ubuntu, or an Ubuntu derivative.
set -eu
. "${DOCKING_OS_RELEASE:-/etc/os-release}"
APT_DISTRO="$ID"
APT_SUITE="${VERSION_CODENAME:-}"
if [ -n "${UBUNTU_CODENAME:-}" ]; then
    APT_DISTRO=ubuntu
    APT_SUITE="$UBUNTU_CODENAME"
fi
case "$APT_DISTRO:$APT_SUITE" in
    ubuntu:jammy|ubuntu:noble|ubuntu:resolute|debian:bookworm|debian:trixie) ;;
    *) echo "Unsupported APT base: $APT_DISTRO/$APT_SUITE" >&2; exit 1 ;;
esac
cat <<EOF
Types: deb
URIs: https://dl.cloudsmith.io/public/docking/docking-apt/deb/${APT_DISTRO}
Suites: ${APT_SUITE}
Components: main
Architectures: amd64 arm64
Signed-By: /etc/apt/keyrings/docking-cloudsmith.asc
EOF
