import Gio from 'gi://Gio';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const XML = `<node><interface name="org.docking.VisualLab.Gnome1">
  <method name="GetGeometry"><arg type="s" direction="out"/></method>
  <method name="ListWindows"><arg type="s" direction="out"/></method>
</interface></node>`;

export default class VisualObserver extends Extension {
    enable() {
        // This session is disposable. Keep the canvas static and panel-free so
        // the independent pixel oracle can distinguish the dock from Shell UI.
        new Gio.Settings({schema_id: 'org.gnome.desktop.interface'})
            .set_boolean('enable-animations', false);
        const background = new Gio.Settings({schema_id: 'org.gnome.desktop.background'});
        background.set_string('picture-uri', '');
        background.set_string('picture-uri-dark', '');
        background.set_string('primary-color', '#000000');
        background.set_string('picture-options', 'none');
        Main.overview.hide();
        Main.panel.hide();
        this._dbus = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._dbus.export(Gio.DBus.session, '/org/docking/VisualLab/Gnome');
        this._owner = Gio.bus_own_name_on_connection(Gio.DBus.session,
            'org.docking.VisualLab.Gnome', Gio.BusNameOwnerFlags.NONE, null, null);
    }

    disable() {
        this._dbus?.unexport();
        if (this._owner)
            Gio.bus_unown_name(this._owner);
        Main.panel.show();
    }

    _windows() {
        return global.get_window_actors().map(actor => actor.meta_window);
    }

    ListWindows() {
        return JSON.stringify(this._windows().map(window => ({
            title: window.get_title(), app_id: window.get_wm_class(),
        })));
    }

    GetGeometry() {
        const outputs = [];
        for (let index = 0; index < global.display.get_n_monitors(); index++) {
            const rect = global.display.get_monitor_geometry(index);
            outputs.push({name: `output-${index}`, x: rect.x, y: rect.y,
                width: rect.width, height: rect.height,
                scale: global.display.get_monitor_scale(index)});
        }
        const docks = this._windows().filter(window => window.get_title() === 'Docking');
        const frame = docks.length === 1 ? docks[0].get_frame_rect() : null;
        return JSON.stringify({outputs, overview_visible: Main.overview.visible, dock_rect: frame ? {
            x: frame.x, y: frame.y, width: frame.width, height: frame.height,
        } : null});
    }
}
