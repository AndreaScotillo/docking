"""Read native foreign toplevels from the private compositor, without Docking."""

from __future__ import annotations

import json

from pywayland.client import Display
from pywayland.protocol.ext_foreign_toplevel_list_v1 import ExtForeignToplevelListV1


def main() -> None:
    display = Display()
    windows = {}
    proxies = []

    def toplevel(manager, handle):
        windows[handle] = {"app_id": "", "title": ""}
        handle.dispatcher["app_id"] = lambda h, value: windows[h].update(app_id=value)
        handle.dispatcher["title"] = lambda h, value: windows[h].update(title=value)
        handle.dispatcher["closed"] = lambda h: windows.pop(h, None)

    def global_added(registry, name, interface, version):
        if interface == ExtForeignToplevelListV1.name:
            manager = registry.bind(name, ExtForeignToplevelListV1, 1)
            manager.dispatcher["toplevel"] = toplevel
            proxies.append(manager)

    try:
        display.connect()
        registry = display.get_registry()
        registry.dispatcher["global"] = global_added
        # Registry, handle announcements, then each handle's initial properties.
        for _ in range(3):
            display.roundtrip()
        if not proxies:
            raise RuntimeError("compositor does not advertise foreign toplevel listing")
        print(json.dumps(list(windows.values())))
    finally:
        display.disconnect()


if __name__ == "__main__":
    main()
