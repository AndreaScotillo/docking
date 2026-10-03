"""Report what a live Wayland session actually offers.

Used by adapters for compositors where the answer decides which Docking backend
runs and cannot be known from configuration alone -- whether the compositor
implements layer-shell. Guessing would mean the harness asserts against a
backend the compositor never selects.

The probe connects as a plain GTK client to whatever session it is started in,
so it must run after the compositor is up and with WAYLAND_DISPLAY/GDK_BACKEND
already exported.

Usage:
    session_probe.py capabilities
"""

from __future__ import annotations

import json
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk


def capabilities() -> int:
    Gtk.init([])
    display = Gdk.Display.get_default()
    wayland = type(display).__name__ == "GdkWaylandDisplay"

    layer_shell = False
    if wayland:
        try:
            gi.require_version("GtkLayerShell", "0.1")
            from gi.repository import GtkLayerShell

            layer_shell = bool(GtkLayerShell.is_supported())
        except Exception:
            layer_shell = False

    json.dump(
        {
            "gtk_display_is_wayland": wayland,
            "gtk_display": type(display).__name__ if display else None,
            "layer_shell_supported": layer_shell,
        },
        sys.stdout,
        indent=2,
    )
    print()
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "capabilities":
        return capabilities()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
