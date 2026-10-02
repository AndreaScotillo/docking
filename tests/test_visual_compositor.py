"""Regression tests for the compositor harness's independent assertions."""

from __future__ import annotations

import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from tools.visual_compositor import compare, scenarios


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    case = scenarios.PLACEMENT_CASES[0]
    output = {"name": "OUT-1", "x": 0, "y": 0, "width": 1280, "height": 720, "scale": 1}
    record = {
        "started": True,
        "stopped": True,
        "settled": True,
        "outputs": [output],
        "self_reported_anchor": "(true, 640, 700, 'bottom')",
        "dock_rect": {"x": 0, "y": 517, "width": 1280, "height": 163},
    }
    caps = {
        "compositor": "cinnamon",
        "expected_backend": "cinnamon-shell",
        "gtk_display_is_wayland": True,
        "placement": True,
        "native_geometry": True,
    }
    meta = {"image_id": "review-image", "panel": {"height": 0, "position": "bottom"}}
    image = Image.new("RGB", (1280, 720), "black")
    ImageDraw.Draw(image).rectangle((400, 660, 879, 719), fill="white")
    image.save(tmp_path / f"{case.name}.png")
    (tmp_path / f"{case.name}.log").write_text(
        "Selected session backend: cinnamon-shell (test)\n"
    )
    monkeypatch.setattr(compare, "BASELINE_DIR", tmp_path / "baselines")

    def evaluate(*, update=True):
        (tmp_path / f"{case.name}.json").write_text(json.dumps(record))
        return compare.evaluate(
            evidence_dir=tmp_path,
            cases=[case],
            out_dir=tmp_path / "diffs",
            update=update,
            compositor="cinnamon",
            capabilities=caps,
            run_meta=meta,
        )[0]

    return SimpleNamespace(
        case=case,
        record=record,
        caps=caps,
        meta=meta,
        path=tmp_path,
        evaluate=evaluate,
    )


@pytest.mark.parametrize(
    "failure",
    [
        "startup",
        "shutdown",
        "missing-start",
        "missing-stop",
        "backend",
        "backend-prefix",
        "missing-log",
    ],
)
def test_unsupported_placement_does_not_hide_session_failures(evidence, failure):
    evidence.caps["placement"] = False
    if failure in {"startup", "shutdown"}:
        evidence.record.update(status="fail", reason=f"{failure} failed")
    elif failure == "missing-start":
        evidence.record.pop("started")
    elif failure == "missing-stop":
        evidence.record.pop("stopped")
    elif failure == "backend":
        evidence.caps["expected_backend"] = "reduced"
    elif failure == "backend-prefix":
        evidence.caps["expected_backend"] = "cinnamon"
    else:
        (evidence.path / f"{evidence.case.name}.log").unlink()
    assert evidence.evaluate().status == "fail"


def test_negative_compatibility_checks_lifecycle_without_requiring_capture(evidence):
    evidence.caps["placement"] = False
    (evidence.path / f"{evidence.case.name}.png").unlink()
    result = evidence.evaluate()
    assert result.status == "unsupported"
    assert "startup, backend and shutdown verified" in result.detail


def test_cli_returns_failure_for_crash_on_unsupported_lane(evidence, monkeypatch):
    evidence.caps["placement"] = False
    evidence.record.update(status="fail", reason="docking did not start")
    evidence.evaluate()
    (evidence.path / "capabilities.json").write_text(json.dumps(evidence.caps))
    (evidence.path / "run-meta.json").write_text(json.dumps(evidence.meta))
    monkeypatch.setattr(scenarios, "select_cases", lambda **kwargs: [evidence.case])
    monkeypatch.setattr(
        "sys.argv",
        [
            "compare",
            "--compositor",
            "cinnamon",
            "--evidence",
            str(evidence.path),
            "--out",
            str(evidence.path / "diffs"),
        ],
    )
    assert compare.main() == 1


@pytest.mark.parametrize(
    "frame",
    [
        None,
        {"x": 0, "y": 517, "width": 5000, "height": 163},
        {"x": -100, "y": 517, "width": 1280, "height": 163},
        {"x": 0, "y": 700, "width": 1280, "height": 163},
        {"x": 0, "y": 517, "width": 0, "height": 163},
    ],
)
def test_native_frame_rejects_clipping_even_when_visible_pixels_match(evidence, frame):
    evidence.record["dock_rect"] = frame
    result = evidence.evaluate()
    assert result.status == "fail"
    assert "frame" in result.detail
    assert result.pending is None


def test_native_frame_accepts_animation_headroom_and_valid_pixel_baseline(evidence):
    result = evidence.evaluate()
    assert result.status == "pass"
    assert result.pending is not None
    compare.commit_baseline(
        pending=result.pending, compositor="cinnamon", run_meta=evidence.meta
    )
    assert evidence.evaluate(update=False).status == "pass"


@pytest.mark.parametrize(
    "changed",
    ["panel-height", "panel-position", "workarea", "crop", "case-panel", "legacy"],
)
def test_baseline_requires_matching_scene_even_when_pixels_match(evidence, changed):
    result = evidence.evaluate()
    compare.commit_baseline(
        pending=result.pending, compositor="cinnamon", run_meta=evidence.meta
    )
    sidecar = compare.baseline_provenance_path(
        compositor="cinnamon", case_name=evidence.case.name
    )
    data = json.loads(sidecar.read_text())
    if changed == "legacy":
        data.pop("scene")
    elif changed == "panel-height":
        evidence.meta["panel"]["height"] = 40
    elif changed == "panel-position":
        evidence.meta["panel"]["position"] = "top"
    elif changed == "workarea":
        data["scene"]["workarea"]["height"] -= 40
    elif changed == "crop":
        data["scene"]["crop"]["y"] -= 40
    else:
        data["scene"]["case_panel"] = 40
    sidecar.write_text(json.dumps(data))
    result = evidence.evaluate(update=False)
    assert result.status == "fail"
    assert "baseline scene" in result.detail


@pytest.mark.parametrize("panel", [None, {}, {"height": 40}])
def test_missing_panel_metadata_cannot_produce_a_trusted_baseline(evidence, panel):
    evidence.meta["panel"] = panel
    result = evidence.evaluate()
    assert result.status == "fail"
    assert result.pending is None


def test_sway_selects_one_panel_implementation(tmp_path):
    scripts = compare.REPO_ROOT / "tools" / "visual_compositor" / "adapters"
    completed = subprocess.run(
        [
            "bash",
            "-c",
            """
set -euo pipefail
export XDG_RUNTIME_DIR="$1" XDG_CONFIG_HOME="$1/config" LAB_DIR="$1"
export LAB_PANEL_HEIGHT=40 LAB_PANEL_POSITION=bottom
source "$2/common.sh"
source "$2/sway.sh"
adapter_prepare
start_lab_panel
test -z "$ADAPTER_PANEL_PID"
grep -q 'height 40' "$SWAY_CONFIG"
""",
            "review",
            str(tmp_path),
            str(scripts),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(shutil.which("jq") is None, reason="adapter probe requires jq")
def test_cosmic_probe_matches_the_production_backend(tmp_path):
    from docking.platform.backends.wayland.cosmic_session import CosmicSessionBackend

    scripts = compare.REPO_ROOT / "tools" / "visual_compositor" / "adapters"
    completed = subprocess.run(
        [
            "bash",
            "-c",
            """
set -euo pipefail
export LAB_DIR="$1"
source "$2/common.sh"
source "$2/cosmic.sh"
session_probe_json() { echo '{"layer_shell_supported":true,"gtk_display_is_wayland":true}'; }
adapter_prepare
adapter_capabilities
""",
            "review",
            str(tmp_path),
            str(scripts),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    caps = json.loads(completed.stdout)
    backend = CosmicSessionBackend.__new__(CosmicSessionBackend)
    assert caps["expected_backend"] == backend.name


@pytest.mark.skipif(shutil.which("jq") is None, reason="adapter probe requires jq")
def test_niri_does_not_claim_a_native_dock_frame(tmp_path):
    scripts = compare.REPO_ROOT / "tools" / "visual_compositor" / "adapters"
    completed = subprocess.run(
        [
            "bash",
            "-c",
            """
set -euo pipefail
export LAB_DIR="$1"
source "$2/common.sh"
source "$2/niri.sh"
session_probe_json() { echo '{"layer_shell_supported":true,"gtk_display_is_wayland":true}'; }
adapter_capabilities
""",
            "review",
            str(tmp_path),
            str(scripts),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["native_geometry"] is False
