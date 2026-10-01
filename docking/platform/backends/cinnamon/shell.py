"""Dock placement through Cinnamon's built-in shell API on older Muffin releases.

Cinnamon 6.4/6.6 lack layer-shell. Native GTK movement is ignored there, but
org.Cinnamon.Eval can ask Muffin to move our own window. A unique window title
identifies the dock: those releases do not expose native Wayland client PIDs.
"""

from __future__ import annotations

import json
from typing import cast
from uuid import uuid4

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from docking.log import get_logger
from docking.platform.backends.base import MonitorSnapshot, PlacementRequest, Rect
from docking.platform.backends.reduced.services import ReducedSurfaceService

log = get_logger(name="backend.cinnamon.shell")


class CinnamonShellClient:
    """Use the shell's existing API without installing a Cinnamon extension."""

    def __init__(self, *, proxy: Gio.DBusProxy) -> None:
        self._proxy = proxy

    @classmethod
    def connect(cls) -> CinnamonShellClient | None:
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                "org.Cinnamon",
                "/org/Cinnamon",
                "org.Cinnamon",
                None,
            )
            client = cls(proxy=proxy)
            if client._eval("typeof global.get_window_actors === 'function'") is True:
                return client
        except Exception as exc:
            log.info("Cinnamon shell positioning unavailable: %s", exc)
        return None

    def _eval(self, script: str) -> object:
        try:
            success, value = self._proxy.call_sync(
                "Eval",
                GLib.Variant("(s)", (script,)),
                Gio.DBusCallFlags.NO_AUTO_START,
                250,
                None,
            ).unpack()
            return json.loads(value) if success else None
        except Exception as exc:
            log.debug("Cinnamon shell request failed: %s", exc)
            return None

    def workarea(self, monitor: MonitorSnapshot) -> Rect | None:
        geometry = monitor.geometry
        wanted = json.dumps([geometry.x, geometry.y, geometry.width, geometry.height])
        # GDK's Wayland output order need not match Muffin's monitor indexes.
        result = self._eval(
            f"(() => {{ const wanted = {wanted}; let index = -1;"
            "for (let i = 0; i < global.display.get_n_monitors(); i++) {"
            "const g = global.display.get_monitor_geometry(i);"
            "if ([g.x, g.y, g.width, g.height].every((v, n) => v === wanted[n])) {"
            "index = i; break; }} if (index < 0) return null;"
            "const r = global.workspace_manager.get_active_workspace()"
            ".get_work_area_for_monitor(index);"
            "return [r.x, r.y, r.width, r.height]; })()"
        )
        if (
            isinstance(result, list)
            and len(result) == 4
            and all(type(part) is int for part in result)
        ):
            values = cast(list[int], result)
            if values[2] > 0 and values[3] > 0:
                return Rect(*values)
        return None

    def position_dock(
        self,
        *,
        title: str,
        request: PlacementRequest,
        current_workspace_only: bool,
    ) -> tuple[int, int] | None:
        # JSON encoding keeps window identifiers separate from JavaScript code.
        result = self._eval(
            "(() => { const w = global.get_window_actors()"
            ".map(a => a.meta_window)"
            f".find(w => w.get_title() === {json.dumps(title)});"
            "if (!w) return null;"
            f"w.{'unstick' if current_workspace_only else 'stick'}();"
            f"w.{'make_above' if request.keep_above else 'unmake_above'}();"
            "w.move_resize_frame(false, "
            f"{int(request.x)}, {int(request.y)}, "
            f"{int(request.size.width)}, {int(request.size.height)});"
            "const r = w.get_frame_rect(); return [r.x, r.y]; })()"
        )
        if (
            isinstance(result, list)
            and len(result) == 2
            and all(type(part) is int for part in result)
        ):
            values = cast(list[int], result)
            return values[0], values[1]
        return None


class CinnamonShellSurfaceService(ReducedSurfaceService):
    """Position the main dock through Muffin while retaining limited capabilities."""

    def __init__(self, *, client: CinnamonShellClient) -> None:
        super().__init__()
        self._client = client
        self._title = f"Docking [{uuid4().hex}]"
        self._current_workspace_only = False
        self._position: tuple[int, int] | None = None
        self._request: PlacementRequest | None = None
        self._retry_source = 0
        self._attempts_left = 0

    @property
    def popups_use_parent_relative_coordinates(self) -> bool:
        return True

    def configure_before_realize(self, window: object) -> None:
        super().configure_before_realize(window)
        set_title = getattr(window, "set_title", None)
        if callable(set_title):
            set_title(self._title)

    def set_workspace_scope(self, *, current_workspace_only: bool) -> None:
        self._current_workspace_only = current_workspace_only
        if self._request is not None:
            self.position_or_anchor(self._request)

    def external_workarea(self, monitor: MonitorSnapshot) -> Rect | None:
        return self._client.workarea(monitor)

    def get_surface_position(self) -> tuple[int, int] | None:
        return self._position

    def position_or_anchor(self, request: PlacementRequest) -> None:
        window = self._window
        if window is None:
            return
        for method_name in ("set_size_request", "resize"):
            method = getattr(window, method_name, None)
            if callable(method):
                method(request.size.width, request.size.height)
        self._request = request
        # The GTK realize callback precedes Muffin seeing the mapped window.
        # Retry across mapping and asynchronous Wayland resize/configure events.
        self._attempts_left = 20
        self._apply_position()
        if not self._retry_source:
            self._retry_source = GLib.timeout_add(100, self._retry_position)

    def _apply_position(self) -> None:
        if self._request is None:
            return
        position = self._client.position_dock(
            title=self._title,
            request=self._request,
            current_workspace_only=self._current_workspace_only,
        )
        if position is not None:
            self._position = position

    def _retry_position(self) -> bool:
        self._attempts_left -= 1
        self._apply_position()
        if self._attempts_left > 0:
            return True
        self._retry_source = 0
        if self._position is None:
            log.warning("Cinnamon could not position the dock window")
        return False

    def stop(self) -> None:
        if self._retry_source:
            GLib.source_remove(self._retry_source)
            self._retry_source = 0
        self._attempts_left = 0
        self._request = None
        self._position = None
        super().stop()
