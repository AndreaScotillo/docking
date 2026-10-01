"""Verify Debian/Ubuntu base selection against derivative os-release fields."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "packaging/deb/apt-source.sh"


@pytest.mark.parametrize(
    "fields,distro,suite",
    [
        (
            "ID=ubuntu\nVERSION_CODENAME=jammy\nUBUNTU_CODENAME=jammy\n",
            "ubuntu",
            "jammy",
        ),
        ("ID=ubuntu\nVERSION_CODENAME=resolute\n", "ubuntu", "resolute"),
        ("ID=debian\nVERSION_CODENAME=bookworm\n", "debian", "bookworm"),
        ("ID=debian\nVERSION_CODENAME=trixie\n", "debian", "trixie"),
        (
            'ID=linuxmint\nVERSION_CODENAME=zena\nID_LIKE="ubuntu debian"\nUBUNTU_CODENAME=noble\n',
            "ubuntu",
            "noble",
        ),
        (
            "ID=linuxmint\nVERSION_CODENAME=virginia\nUBUNTU_CODENAME=jammy\n",
            "ubuntu",
            "jammy",
        ),
        ("ID=pop\nVERSION_CODENAME=noble\nUBUNTU_CODENAME=noble\n", "ubuntu", "noble"),
    ],
)
def test_selects_distribution_base(tmp_path, fields, distro, suite):
    os_release = tmp_path / "os-release"
    os_release.write_text(fields)
    result = subprocess.run(
        ["sh", str(SCRIPT)],
        env={"DOCKING_OS_RELEASE": str(os_release)},
        text=True,
        capture_output=True,
        check=True,
    )
    assert f"/deb/{distro}\n" in result.stdout
    assert f"Suites: {suite}\n" in result.stdout
    assert "Signed-By: /etc/apt/keyrings/docking-cloudsmith.asc\n" in result.stdout


@pytest.mark.parametrize(
    "fields",
    [
        "ID=linuxmint\nVERSION_CODENAME=zena\n",
        "ID=ubuntu\nVERSION_CODENAME=focal\n",
        "ID=debian\n",
    ],
)
def test_rejects_unknown_or_unsupported_base(tmp_path, fields):
    os_release = tmp_path / "os-release"
    os_release.write_text(fields)
    result = subprocess.run(
        ["sh", str(SCRIPT)],
        env={"DOCKING_OS_RELEASE": str(os_release)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert not result.stdout
    assert "Unsupported APT base" in result.stderr
