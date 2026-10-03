#!/bin/bash
# KWin adapter: the virtual backend. No X, no GPU, no display server.
#
# VIABILITY IS UNRESOLVED. The separate kwin-wayland-backend-virtual package
# exists in Debian only up to 5.20, and trixie's kwin-wayland ships no backend
# plugin packages at all -- so `--virtual` may not work there. Rather than
# assert a flag we could not verify (two binary-inspection attempts gave
# contradictory answers), the adapter attempts the start and reports KWin's own
# error. Arch's kwin package is the likely home for this lane if trixie cannot.
#
# SCREENSHOT: KWin's virtual backend can write every rendered frame to a
# directory named by KWIN_WAYLAND_VIRTUAL_SCREENSHOTS. That is preferred over
# org.kde.KWin.ScreenShot2, which is subject to the X-KDE-DBUS-Restricted-Interfaces
# authorization the app's own preview path documents
# (docking/platform/backends/kwin/preview.py:18) and which a bare virtual
# backend does not necessarily honour for an arbitrary caller. The capability
# check below proves which mechanism actually works rather than assuming.

KWIN_FRAMES="${XDG_RUNTIME_DIR:-/tmp}/kwin-frames"

adapter_capabilities() {
    local screenshot=none probe
    if [ -n "$(ls -A "$KWIN_FRAMES" 2>/dev/null)" ]; then
        screenshot=virtual-frames
    fi
    probe="$(session_probe_json)"

    jq -n --argjson probe "$probe" --arg screenshot "$screenshot" '{
        compositor: "kwin",
        expected_backend: "kwin",
        native_geometry: false,
        pointer: false,
        placement: $probe.layer_shell_supported,
        screenshot_method: $screenshot,
        gtk_display_is_wayland: $probe.gtk_display_is_wayland,
        layer_shell_supported: $probe.layer_shell_supported
    }'
}

adapter_prepare() {
    COMPOSITOR_LOG="${LAB_DIR}/kwin.log"
    KWIN_LOG="$COMPOSITOR_LOG"
    local width="${LAB_WIDTH:-1280}"
    local height="${LAB_HEIGHT:-720}"

    export XDG_CURRENT_DESKTOP=KDE
    export XDG_SESSION_TYPE=wayland
    export GDK_BACKEND=wayland

    rm -rf "$KWIN_FRAMES"
    mkdir -p "$KWIN_FRAMES"
    export KWIN_WAYLAND_VIRTUAL_SCREENSHOTS="$KWIN_FRAMES"
}

adapter_start() {
    # kwin_wayland carries cap_sys_nice=ep, so it is invoked through the
    # distribution's wrapper, which is the supported entry point.
    #
    # Whether the virtual backend exists is NOT asserted here or at build time:
    # Debian trixie ships no kwin backend plugin packages, so this may simply
    # not work. Attempting the start and letting wait_for_wayland_socket surface
    # kwin's own error is the honest test -- a flag-existence check is a proxy
    # that already proved unreliable twice.
    kwin_wayland_wrapper \
        --virtual \
        --width "${LAB_WIDTH:-1280}" \
        --height "${LAB_HEIGHT:-720}" \
        --output-count "${LAB_OUTPUTS:-1}" \
        --no-lockscreen \
        >"$COMPOSITOR_LOG" 2>&1 &
    ADAPTER_COMPOSITOR_PID=$!
    wait_for_wayland_socket 120
}

adapter_wait_ready() {
    # Two gates: the socket, then an actual captured frame. KWin creates its
    # Wayland socket before the virtual output has produced anything, so a
    # socket-only check would let the first screenshot fail.
    local attempts="${1:-120}"
    for _ in $(seq "$attempts"); do
        kill -0 "$ADAPTER_COMPOSITOR_PID"
        if [ -n "$(ls -A "$KWIN_FRAMES" 2>/dev/null)" ]; then
            return 0
        fi
        sleep 0.5
    done
    log_adapter "kwin never wrote a frame to $KWIN_FRAMES"
    return 1
}

adapter_screenshot() {
    local dest="$1"
    local newest=""
    # Newest frame wins: the directory accumulates over the run and the last
    # write is the state the dock settled into. `|| true` because a glob with no
    # match makes ls fail, and under `set -e` that would abort the run instead of
    # reporting the real problem.
    newest="$(ls -t "$KWIN_FRAMES"/*.png 2>/dev/null | head -1 || true)"
    if [ -z "$newest" ]; then
        log_adapter "no frame available in $KWIN_FRAMES"
        return 1
    fi
    cp "$newest" "$dest"
}

adapter_geometry() {
    local probe="$XDG_RUNTIME_DIR/.geometry.png"
    adapter_screenshot "$probe" || return 1
    local dims width height
    dims="$(png_dimensions "$probe")"
    rm -f "$probe"
    width="${dims%x*}"
    height="${dims#*x}"

    jq -n --argjson w "$width" --argjson h "$height" \
        '{outputs: [{name: "Virtual-1", x: 0, y: 0, width: $w, height: $h, scale: 1}],
          dock_rect: null}'
}

adapter_pointer() {
    log_adapter "pointer injection is not implemented for kwin"
    return 1
}

adapter_stop() {
    if [ -n "$ADAPTER_COMPOSITOR_PID" ]; then
        terminate_pid "$ADAPTER_COMPOSITOR_PID"
        ADAPTER_COMPOSITOR_PID=""
    fi
}
