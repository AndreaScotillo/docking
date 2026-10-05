"""Bounded, diagnostic-only reads of X11 application identity properties."""

from __future__ import annotations

import ctypes

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11

from docking.platform.backends.diagnostics import (
    IdentityHintStatus,
    WindowIdentityHint,
)

IDENTITY_PROPERTIES = ("_GTK_APPLICATION_ID", "_KDE_NET_WM_DESKTOP_FILE")
MAX_PROPERTY_BYTES = 4096


class X11IdentityHintReader:
    """Use GTK's X connection; never open or close a separate display."""

    def __init__(self) -> None:
        self._xlib: ctypes.CDLL | None = None
        self._display: GdkX11.X11Display | None = None
        self._xdisplay: ctypes.c_void_p | None = None
        self._atoms: dict[str, int] = {}

    def read(self, xid: int) -> tuple[WindowIdentityHint, ...]:
        try:
            available = self._initialize()
        except Exception:
            available = False
        if not available:
            return tuple(
                WindowIdentityHint(name, IdentityHintStatus.UNAVAILABLE)
                for name in IDENTITY_PROPERTIES
            )
        hints: list[WindowIdentityHint] = []
        for name in IDENTITY_PROPERTIES:
            try:
                hint = self._read_property(xid, name)
            except Exception:
                # Extra evidence must never abort a real tracking scan.
                hint = WindowIdentityHint(name, IdentityHintStatus.READ_ERROR)
            hints.append(hint)
        return tuple(hints)

    def _initialize(self) -> bool:
        if self._xlib is not None:
            return True
        display = Gdk.Display.get_default()
        if not isinstance(display, GdkX11.X11Display):
            return False
        try:
            xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
            xdisplay = ctypes.c_void_p(hash(display.get_xdisplay()))
        except (OSError, TypeError, ValueError):
            return False
        xlib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        xlib.XInternAtom.restype = ctypes.c_ulong
        xlib.XGetWindowProperty.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_long,
            ctypes.c_long,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        xlib.XGetWindowProperty.restype = ctypes.c_int
        xlib.XFree.argtypes = [ctypes.c_void_p]
        xlib.XFree.restype = ctypes.c_int
        self._display = display
        self._xdisplay = xdisplay
        self._xlib = xlib
        return True

    def _atom(self, name: str) -> int:
        assert self._xlib is not None and self._xdisplay is not None
        # Do not cache missing atoms: an application may create one later.
        if name not in self._atoms:
            atom = int(self._xlib.XInternAtom(self._xdisplay, name.encode(), 1))
            if atom:
                self._atoms[name] = atom
            return atom
        return self._atoms[name]

    def _read_property(self, xid: int, name: str) -> WindowIdentityHint:
        assert self._xlib is not None and self._xdisplay is not None
        assert self._display is not None
        atom = self._atom(name)
        if not atom:
            return WindowIdentityHint(name, IdentityHintStatus.ABSENT)
        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        item_count = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        data = ctypes.POINTER(ctypes.c_ubyte)()
        try:
            self._display.error_trap_push()
            try:
                status = self._xlib.XGetWindowProperty(
                    self._xdisplay,
                    xid,
                    atom,
                    0,
                    MAX_PROPERTY_BYTES // 4,
                    0,
                    0,
                    ctypes.byref(actual_type),
                    ctypes.byref(actual_format),
                    ctypes.byref(item_count),
                    ctypes.byref(bytes_after),
                    ctypes.byref(data),
                )
            finally:
                x_error = self._display.error_trap_pop()
            if status or x_error:
                return WindowIdentityHint(name, IdentityHintStatus.READ_ERROR)
            if not actual_type.value:
                return WindowIdentityHint(name, IdentityHintStatus.ABSENT)
            if actual_format.value != 8 or actual_type.value not in (
                self._atom("UTF8_STRING"),
                self._atom("STRING"),
            ):
                return WindowIdentityHint(name, IdentityHintStatus.MALFORMED)
            if bytes_after.value or item_count.value > MAX_PROPERTY_BYTES:
                return WindowIdentityHint(name, IdentityHintStatus.OVERSIZED)
            if item_count.value and not data:
                return WindowIdentityHint(name, IdentityHintStatus.MALFORMED)
            raw = ctypes.string_at(data, item_count.value) if data else b""
            encoding = (
                "utf-8" if actual_type.value == self._atom("UTF8_STRING") else "latin-1"
            )
            try:
                value = raw.rstrip(b"\0").decode(encoding)
            except UnicodeDecodeError:
                return WindowIdentityHint(name, IdentityHintStatus.MALFORMED)
            if "\0" in value:
                return WindowIdentityHint(name, IdentityHintStatus.MALFORMED)
            return WindowIdentityHint(name, IdentityHintStatus.PRESENT, value)
        finally:
            if data:
                self._xlib.XFree(data)
