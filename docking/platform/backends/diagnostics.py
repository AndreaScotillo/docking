"""Immutable, binding-free evidence from the last window tracking scan."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from docking.platform.applications.types import ApplicationMatch


@dataclass(frozen=True)
class WindowDiagnostic:
    """Shareable identity evidence and the actual scan decision for one window."""

    window_id: str | None = None
    identities: tuple[tuple[str, str], ...] = ()
    pid: int | None = None
    executable_path: str | None = None
    workspace: str | None = None
    outcome: Literal["matched", "unmatched", "excluded", "error"] = "unmatched"
    reason: str = "no-match"
    desktop_id: str | None = None
    match_method: str | None = None
    matched_identity: str | None = None
    desktop_file: str | None = None
    launcher_basename: str | None = None
    aliases: tuple[str, ...] = ()
    read_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class WindowTrackingDiagnostic:
    """Read-only snapshot; retrieving it never starts a tracking scan."""

    status: Literal[
        "unavailable", "unsupported", "pending", "stopped", "failed", "available"
    ] = "unavailable"
    scanned_at: datetime | None = None
    registry_generation: int | None = None
    windows: tuple[WindowDiagnostic, ...] = ()
    detail: str = "Detailed window capture is unavailable for this backend."


def with_match(
    record: WindowDiagnostic, match: ApplicationMatch | None
) -> WindowDiagnostic:
    """Copy only shareable launcher identity fields from a successful match."""
    if match is None:
        return record
    app = match.application
    basename = None
    if app is not None:
        try:
            argv = shlex.split(app.exec_line)
        except ValueError:
            argv = []
        basename = Path(argv[0]).name if argv else None
    return replace(
        record,
        outcome="matched",
        reason="included",
        desktop_id=match.desktop_id,
        match_method=match.evidence.method.value,
        matched_identity=match.evidence.raw_app_id,
        desktop_file=str(app.desktop_file) if app and app.desktop_file else None,
        launcher_basename=basename,
        aliases=app.aliases if app else (),
    )
