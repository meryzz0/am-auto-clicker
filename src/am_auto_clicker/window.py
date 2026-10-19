"""GTK 4 / Libadwaita interface and GNOME application integration."""
from __future__ import annotations

import logging
import os
import queue
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from . import APP_NAME, __version__
from .click_engine import ClickEngine, error_message
from .config import MAX_CLICKS_LIMIT, MAX_INTERVAL_MS, MIN_INTERVAL_MS, ConfigStore
from .shortcuts import describe_hotkey_error, format_binding, set_global_binding

LOGGER = logging.getLogger("am_auto_clicker")

CSS = """
.am-hero {
  background-color: #182438;
  border-radius: 20px;
  padding: 22px;
}
.am-hero-title { color: #f7f9fc; font-size: 25px; font-weight: 700; }
.am-hero-copy { color: #c6d1e1; font-size: 13px; }
.am-hero-kicker { color: #a8c7fa; font-size: 10px; font-weight: 800; letter-spacing: 1.3px; }
.am-count-caption {
  color: @dimmed_fg_color;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.1px;
}
.am-card {
  background-color: @card_bg_color;
  border: 1px solid alpha(@window_fg_color, 0.10);
  border-radius: 18px;
  padding: 18px;
}
.am-section-title { font-size: 15px; font-weight: 700; }
.am-field-title { font-weight: 600; }
.am-small { font-size: 12px; }
.am-status-dot { min-width: 9px; min-height: 9px; border-radius: 999px; }
.am-dot-ready { background-color: #8b95a7; }
.am-dot-running { background-color: #2ec27e; }
.am-dot-error { background-color: #e66100; }
.am-keycap {
  background-color: alpha(@accent_bg_color, 0.16);
  color: @accent_color;
  border: 1px solid alpha(@accent_color, 0.28);
  border-radius: 8px;
  padding: 5px 10px;
  font-weight: 700;
}
.am-count { font-size: 27px; font-weight: 700; }
.am-main-button { min-height: 46px; font-weight: 700; }
.am-hint {
  background-color: alpha(@accent_bg_color, 0.09);
  border-radius: 12px;
  padding: 12px;
}
.am-footer { font-size: 11px; }
"""

IGNORED_KEYS = {
    getattr(Gdk, name) for name in (
        "KEY_Shift_L", "KEY_Shift_R", "KEY_Control_L", "KEY_Control_R",
        "KEY_Alt_L", "KEY_Alt_R", "KEY_Super_L", "KEY_Super_R",
        "KEY_Meta_L", "KEY_Meta_R", "KEY_ISO_Level3_Shift",
        "KEY_Caps_Lock", "KEY_Num_Lock", "KEY_Shift_Lock",
    ) if hasattr(Gdk, name)
}

BUTTON_LABELS = {"left": "Left click", "right": "Right click", "middle": "Middle click"}
BUTTON_INDEX = {name: index for index, name in enumerate(BUTTON_LABELS)}


def install_css() -> None:
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


class MainWindowController:
    """Own the application window and coordinate UI controls with the click engine."""

    def __init__(self, application: Adw.Application) -> None:
        self.application = application
        self.config = ConfigStore()
        self.engine_events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.engine = ClickEngine(self._emit_engine_event)
        self.window: Adw.ApplicationWindow | None = None
        self.toast_overlay: Adw.ToastOverlay | None = None
        self._is_starting = False
        self._is_clicking = False
        self._minimize_when_started = False
        self._quit_after_stop = False
        self._input_access = False
        self._shortcut_dialog: Gtk.Window | None = None
        self._about_dialog: Gtk.Window | None = None
        self._status_title: Gtk.Label | None = None
        self._status_detail: Gtk.Label | None = None
        self._status_dot: Gtk.Box | None = None
        self._count_label: Gtk.Label | None = None
        self._main_button: Gtk.Button | None = None
        self._hotkey_label: Gtk.Label | None = None
        self._access_label: Gtk.Label | None = None
        self._access_detail: Gtk.Label | None = None
        self._interval_spin: Gtk.SpinButton | None = None
        self._button_dropdown: Gtk.DropDown | None = None
        self._limit_spin: Gtk.SpinButton | None = None
        self._shortcut_detail: Gtk.Label | None = None

    @property
    def is_open(self) -> bool:
        """Whether the application window has been created and not closed."""
        return self.window is not None

    @property
    def is_busy(self) -> bool:
        """Whether the click engine is preparing or sending events."""
        return self._is_starting or self._is_clicking

    def show(self) -> None:
        """Create the main window if needed and present it."""
        self._present_window()

    def toggle(self) -> None:
        """Start or stop the click engine using the current UI settings."""
        self._toggle_clicking()

    def request_quit(self) -> None:
        """Stop an active click worker before asking GTK to shut down."""
        if self.is_busy:
            self._quit_after_stop = True
            self._stop_clicking()
        else:
            self.application.quit()

    def _ensure_window(self) -> None:
        if self.window is not None:
            return
        install_css()
        window = Adw.ApplicationWindow(application=self.application)
        window.set_title(APP_NAME)
        window.set_default_size(610, 720)
        window.set_size_request(420, 520)
        window.connect("close-request", self._on_close_request)

        header = Adw.HeaderBar()
        title = Gtk.Label(label=APP_NAME)
        title.add_css_class("heading")
        header.set_title_widget(title)
        about_button = Gtk.Button.new_from_icon_name("help-about-symbolic")
        about_button.set_tooltip_text(f"About {APP_NAME}")
        about_button.connect("clicked", lambda *_: self._show_about())
        header.pack_end(about_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.append(header)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        clamp = Adw.Clamp()
        clamp.set_maximum_size(650)
        clamp.set_tightening_threshold(480)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page.set_margin_top(22)
        page.set_margin_bottom(22)
        page.set_margin_start(20)
        page.set_margin_end(20)
        self._build_hero(page)
        self._build_status_card(page)
        self._build_settings_card(page)
        self._build_shortcut_card(page)
        self._build_hint(page)
        footer = Gtk.Label(label=f"Version {__version__} · Built for GNOME and Wayland")
        footer.add_css_class("dim-label")
        footer.add_css_class("am-footer")
        footer.set_xalign(0.5)
        footer.set_margin_top(1)
        page.append(footer)
        clamp.set_child(page)
        scroller.set_child(clamp)
        root.append(scroller)

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(root)
        window.set_content(self.toast_overlay)
        self.window = window
        self._refresh_input_access()
        self._update_shortcut_label()
        self._set_status(
            "ready",
            "Ready when you are. Use the shortcut while your target application is focused.",
        )
        GLib.timeout_add(50, self._drain_engine_events)

    @staticmethod
    def _new_card() -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("am-card")
        return card

    @staticmethod
    def _label(text: str, css: str | None = None, wrap: bool = False) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_wrap(wrap)
        if css:
            for item in css.split():
                label.add_css_class(item)
        return label

    def _build_hero(self, page: Gtk.Box) -> None:
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        hero.add_css_class("am-hero")
        eyebrow = Gtk.Label(label="A SMALL DESKTOP TOOL")
        eyebrow.set_xalign(0)
        eyebrow.add_css_class("am-hero-kicker")
        hero.append(eyebrow)

        heading = Gtk.Label(label="Click at your own pace.")
        heading.set_xalign(0)
        heading.set_wrap(True)
        heading.add_css_class("am-hero-title")
        hero.append(heading)

        copy = Gtk.Label(
            label=(
                "A lightweight autoclicker for Linux, with a global shortcut "
                "and straightforward controls."
            )
        )
        copy.set_xalign(0)
        copy.set_wrap(True)
        copy.add_css_class("am-hero-copy")
        hero.append(copy)
        page.append(hero)

    def _build_status_card(self, page: Gtk.Box) -> None:
        card = self._new_card()
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_row.set_valign(Gtk.Align.CENTER)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        state_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        state_row.set_valign(Gtk.Align.CENTER)
        self._status_dot = Gtk.Box()
        self._status_dot.set_size_request(9, 9)
        self._status_dot.add_css_class("am-status-dot")
        self._status_dot.add_css_class("am-dot-ready")
        state_row.append(self._status_dot)
        self._status_title = self._label("Ready", "title-3")
        state_row.append(self._status_title)
        left.append(state_row)
        self._status_detail = self._label("Ready when you are.", "dim-label am-small", wrap=True)
        left.append(self._status_detail)
        left.set_hexpand(True)
        header_row.append(left)

        count_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        count_column.set_halign(Gtk.Align.END)
        count_caption = self._label("CLICKS SENT", "am-count-caption")
        count_caption.set_xalign(1)
        count_column.append(count_caption)
        self._count_label = Gtk.Label(label="0")
        self._count_label.add_css_class("am-count")
        self._count_label.set_xalign(1)
        count_column.append(self._count_label)
        header_row.append(count_column)
        card.append(header_row)

        self._main_button = Gtk.Button()
        self._main_button.add_css_class("suggested-action")
        self._main_button.add_css_class("am-main-button")
        button_contents = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        button_contents.set_halign(Gtk.Align.CENTER)
        self._button_icon = Gtk.Image.new_from_icon_name("media-playback-start-symbolic")
        self._button_label = Gtk.Label(label="Start clicking")
        button_contents.append(self._button_icon)
        button_contents.append(self._button_label)
        self._main_button.set_child(button_contents)
        self._main_button.set_hexpand(True)
        self._main_button.connect("clicked", lambda *_: self._toggle_clicking())
        card.append(self._main_button)
        page.append(card)

    def _build_settings_card(self, page: Gtk.Box) -> None:
        card = self._new_card()
        card.append(self._label("Click settings", "am-section-title"))
        saved = self.config.data

        interval_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        interval_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        interval_text.set_hexpand(True)
        interval_text.append(self._label("Click interval", "am-field-title"))
        initial_cps = 1000.0 / saved["interval_ms"]
        initial_cps_text = (
            f"{initial_cps:g} clicks per second"
            if initial_cps.is_integer()
            else f"{initial_cps:.1f} clicks per second"
        )
        self._cps_label = self._label(initial_cps_text, "dim-label am-small")
        interval_text.append(self._cps_label)
        interval_row.append(interval_text)
        interval_control = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._interval_spin = Gtk.SpinButton.new_with_range(MIN_INTERVAL_MS, MAX_INTERVAL_MS, 10)
        self._interval_spin.set_digits(0)
        self._interval_spin.set_numeric(True)
        self._interval_spin.set_value(saved["interval_ms"])
        self._interval_spin.set_size_request(100, -1)
        self._interval_spin.set_tooltip_text("Time between clicks, in milliseconds")
        interval_control.append(self._interval_spin)
        unit = Gtk.Label(label="ms")
        unit.add_css_class("dim-label")
        interval_control.append(unit)
        interval_row.append(interval_control)
        card.append(interval_row)
        self._interval_spin.connect("value-changed", self._on_interval_changed)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        card.append(separator)

        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        button_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        button_text.set_hexpand(True)
        button_text.append(self._label("Mouse button", "am-field-title"))
        button_text.append(self._label("Which button to repeat", "dim-label am-small"))
        button_row.append(button_text)
        self._button_dropdown = Gtk.DropDown.new_from_strings(list(BUTTON_LABELS.values()))
        self._button_dropdown.set_selected(BUTTON_INDEX.get(saved["button"], 0))
        self._button_dropdown.set_size_request(145, -1)
        self._button_dropdown.set_tooltip_text("Choose the mouse button to click")
        button_row.append(self._button_dropdown)
        card.append(button_row)
        self._button_dropdown.connect("notify::selected", self._on_button_changed)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        limit_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        limit_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        limit_text.set_hexpand(True)
        limit_text.append(self._label("Click limit", "am-field-title"))
        limit_text.append(self._label("Set to 0 for unlimited clicks", "dim-label am-small"))
        limit_row.append(limit_text)
        self._limit_spin = Gtk.SpinButton.new_with_range(0, MAX_CLICKS_LIMIT, 1)
        self._limit_spin.set_digits(0)
        self._limit_spin.set_numeric(True)
        self._limit_spin.set_value(saved["limit"])
        self._limit_spin.set_size_request(145, -1)
        self._limit_spin.set_tooltip_text(
            "Stop automatically after this many clicks; zero means no limit"
        )
        limit_row.append(self._limit_spin)
        card.append(limit_row)
        self._limit_spin.connect("value-changed", self._on_limit_changed)

        card.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        access_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        access_icon = Gtk.Image.new_from_icon_name("input-mouse-symbolic")
        access_row.append(access_icon)
        access_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        access_text.set_hexpand(True)
        self._access_label = self._label("Checking input access…", "am-field-title")
        self._access_detail = self._label(
            "The clicker uses a virtual Linux mouse device.", "dim-label am-small", wrap=True
        )
        access_text.append(self._access_label)
        access_text.append(self._access_detail)
        access_row.append(access_text)
        card.append(access_row)
        page.append(card)

    def _build_shortcut_card(self, page: Gtk.Box) -> None:
        card = self._new_card()
        card.append(self._label("Global shortcut", "am-section-title"))
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        details.set_hexpand(True)
        details.append(self._label("Start or stop from any app", "am-field-title"))
        self._shortcut_detail = self._label(
            "Keep AM Auto Clicker open in the background while you play.",
            "dim-label am-small", wrap=True,
        )
        details.append(self._shortcut_detail)
        row.append(details)
        self._hotkey_label = Gtk.Label(label=format_binding(self.config.data["hotkey"]))
        self._hotkey_label.add_css_class("am-keycap")
        self._hotkey_label.set_valign(Gtk.Align.CENTER)
        row.append(self._hotkey_label)
        card.append(row)

        change_button = Gtk.Button(label="Change shortcut…")
        change_button.set_halign(Gtk.Align.START)
        change_button.connect("clicked", lambda *_: self._capture_shortcut())
        card.append(change_button)
        page.append(card)

    def _build_hint(self, page: Gtk.Box) -> None:
        hint = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hint.add_css_class("am-hint")
        hint.set_valign(Gtk.Align.CENTER)
        info_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        info_icon.set_valign(Gtk.Align.START)
        hint.append(info_icon)
        copy = Gtk.Label(
            label=(
                "Open your target application and place the pointer where you want to click. "
                "The global shortcut lets you start or stop without switching windows."
            ),
        )
        copy.set_xalign(0)
        copy.set_wrap(True)
        copy.add_css_class("am-small")
        hint.append(copy)
        page.append(hint)

    def _present_window(self) -> None:
        self._ensure_window()
        assert self.window is not None
        self.window.present()

    def _show_about(self) -> None:
        if self.window is None:
            return
        if self._about_dialog is not None:
            self._about_dialog.present()
            return
        dialog = Gtk.Window(transient_for=self.window, modal=True, resizable=False)
        dialog.set_title(f"About {APP_NAME}")
        dialog.set_default_size(360, 300)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(28)
        content.set_margin_bottom(24)
        content.set_margin_start(26)
        content.set_margin_end(26)
        content.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name("com.am.autoclicker")
        icon.set_pixel_size(68)
        content.append(icon)
        name = Gtk.Label(label=APP_NAME)
        name.add_css_class("title-2")
        content.append(name)
        content.append(self._label(f"Version {__version__}", "dim-label"))
        description = Gtk.Label(
            label=(
                "A simple, native-feeling autoclicker for Linux desktops.\n"
                "Uses the Linux uinput interface for mouse events."
            )
        )
        description.set_justify(Gtk.Justification.CENTER)
        description.set_wrap(True)
        content.append(description)
        close_button = Gtk.Button(label="Close")
        close_button.add_css_class("suggested-action")
        close_button.set_halign(Gtk.Align.CENTER)
        close_button.connect("clicked", lambda *_: dialog.close())
        content.append(close_button)
        dialog.set_child(content)
        dialog.connect("close-request", lambda *_: self._clear_about_dialog())
        self._about_dialog = dialog
        dialog.present()

    def _clear_about_dialog(self) -> bool:
        self._about_dialog = None
        return False

    def _set_status(self, kind: str, detail: str) -> None:
        title = {
            "ready": "Ready",
            "starting": "Starting…",
            "running": "Clicking",
            "stopping": "Stopping…",
            "error": "Needs attention",
            "done": "Finished",
        }.get(kind, "Ready")
        if self._status_title is not None:
            self._status_title.set_text(title)
        if self._status_detail is not None:
            self._status_detail.set_text(detail)
        if self._status_dot is not None:
            for css_class in ("am-dot-ready", "am-dot-running", "am-dot-error"):
                self._status_dot.remove_css_class(css_class)
            if kind in {"starting", "running"}:
                dot_class = "am-dot-running"
            elif kind == "error":
                dot_class = "am-dot-error"
            else:
                dot_class = "am-dot-ready"
            self._status_dot.add_css_class(dot_class)
        if self._main_button is not None:
            if kind in {"starting", "running", "stopping"}:
                self._button_label.set_text(
                    "Stopping…" if kind == "stopping" else "Stop clicking"
                )
                self._button_icon.set_from_icon_name("media-playback-stop-symbolic")
                self._main_button.remove_css_class("suggested-action")
                self._main_button.add_css_class("destructive-action")
                self._main_button.set_sensitive(kind != "stopping")
            else:
                self._button_label.set_text("Start clicking")
                self._button_icon.set_from_icon_name("media-playback-start-symbolic")
                self._main_button.remove_css_class("destructive-action")
                self._main_button.add_css_class("suggested-action")
                self._main_button.set_sensitive(True)

    def _refresh_input_access(self) -> None:
        path = Path("/dev/uinput")
        exists = path.exists()
        self._input_access = exists and os.access(path, os.W_OK)
        if self._access_label is None or self._access_detail is None:
            return
        if self._input_access:
            self._access_label.set_text("Input access available")
            self._access_detail.set_text(
                "Permissions look good. The virtual mouse will be created when you start clicking."
            )
            self._access_label.remove_css_class("error")
        elif exists:
            self._access_label.set_text("Input permission needed")
            self._access_detail.set_text(
                "Run install.sh, then sign out of Zorin and sign back in. "
                "Do not run the app with sudo."
            )
        else:
            self._access_label.set_text("Input device not found")
            self._access_detail.set_text(
                "Run install.sh to enable the Linux uinput device, then sign out and back in."
            )

    def _update_shortcut_label(self) -> None:
        binding = self.config.data["hotkey"]
        if self._hotkey_label is not None:
            self._hotkey_label.set_text(format_binding(binding))
        if self._shortcut_detail is not None:
            self._shortcut_detail.set_text(
                f"{format_binding(binding)} toggles clicking. Leave this app open in the "
                "background while using your target application."
            )

    def _on_interval_changed(self, spin: Gtk.SpinButton) -> None:
        interval = int(spin.get_value())
        cps = 1000.0 / interval
        value = f"{cps:g} clicks per second" if cps.is_integer() else f"{cps:.1f} clicks per second"
        self._cps_label.set_text(value)
        self._save_settings(interval_ms=interval)

    def _on_button_changed(self, dropdown: Gtk.DropDown, _property: Any) -> None:
        selected = int(dropdown.get_selected())
        button = list(BUTTON_LABELS)[selected] if selected < len(BUTTON_LABELS) else "left"
        self._save_settings(button=button)

    def _on_limit_changed(self, spin: Gtk.SpinButton) -> None:
        self._save_settings(limit=int(spin.get_value()))

    def _save_settings(self, **changes: Any) -> None:
        try:
            self.config.update(**changes)
        except OSError as exc:
            LOGGER.exception("Could not save settings")
            self._notify(f"Settings could not be saved: {exc}")

    def _toggle_clicking(self) -> None:
        if self._is_starting or self._is_clicking:
            self._stop_clicking()
        else:
            self._start_clicking()

    def _start_clicking(self) -> None:
        if self._is_starting or self._is_clicking:
            return
        assert self._interval_spin is not None
        assert self._button_dropdown is not None
        assert self._limit_spin is not None
        interval = int(self._interval_spin.get_value())
        selected = int(self._button_dropdown.get_selected())
        button = list(BUTTON_LABELS)[selected] if selected < len(BUTTON_LABELS) else "left"
        limit = int(self._limit_spin.get_value())
        try:
            self.config.update(interval_ms=interval, button=button, limit=limit)
        except OSError as exc:
            LOGGER.exception("Could not save settings before starting")
            self._notify(f"Settings could not be saved: {exc}")
            return

        self._is_starting = True
        self._minimize_when_started = bool(self.window and self.window.is_active())
        if self._count_label is not None:
            self._count_label.set_text("0")
        self._set_status("starting", "Preparing the virtual mouse…")
        try:
            self.engine.start(interval, button, limit)
        except Exception as exc:
            self._is_starting = False
            LOGGER.exception("Could not start the click engine")
            self._set_status("error", error_message(exc))
            self._notify(error_message(exc))

    def _stop_clicking(self) -> None:
        if not (self._is_starting or self._is_clicking):
            return
        self._set_status("stopping", "Releasing the mouse button and stopping safely…")
        self.engine.stop()

    def _emit_engine_event(self, kind: str, payload: Any) -> None:
        self.engine_events.put((kind, payload))

    def _drain_engine_events(self) -> bool:
        try:
            while True:
                kind, payload = self.engine_events.get_nowait()
                if kind == "started":
                    self._is_starting = False
                    self._is_clicking = True
                    self._set_status(
                        "running",
                        f"Active. Press {format_binding(self.config.data['hotkey'])} to stop.",
                    )
                    # Delay the first click briefly so the window can minimize.
                    if self._minimize_when_started and self.window is not None:
                        GLib.timeout_add(80, self._minimize_window)
                elif kind == "count":
                    if self._count_label is not None:
                        self._count_label.set_text(f"{payload:,}")
                elif kind == "finished":
                    self._is_starting = False
                    self._is_clicking = False
                    clicks = int(payload.get("clicks", 0))
                    error = payload.get("error")
                    if self._count_label is not None:
                        self._count_label.set_text(f"{clicks:,}")
                    if error is not None:
                        LOGGER.error(
                            "Click engine stopped with an error",
                            exc_info=(type(error), error, error.__traceback__),
                        )
                        message = error_message(error)
                        self._set_status("error", message)
                        self._notify(message)
                        if self.window is not None:
                            self.window.present()
                    else:
                        limit = self.config.data["limit"]
                        if limit and clicks >= limit:
                            self._set_status("done", f"Limit reached. {clicks:,} click(s) sent.")
                        else:
                            self._set_status("done", f"Stopped. {clicks:,} click(s) sent.")
                    if self._quit_after_stop:
                        self.application.quit()
        except queue.Empty:
            pass
        return self.window is not None

    def _minimize_window(self) -> bool:
        if self.window is not None and self._is_clicking and self._minimize_when_started:
            self.window.minimize()
        return GLib.SOURCE_REMOVE

    def _notify(self, message: str) -> None:
        if self.toast_overlay is not None:
            try:
                toast = Adw.Toast.new(message)
                toast.set_timeout(6)
                self.toast_overlay.add_toast(toast)
                return
            except Exception:
                LOGGER.debug("Toast unavailable", exc_info=True)
        LOGGER.info("%s", message)

    def _capture_shortcut(self) -> None:
        if self.window is None or self._shortcut_dialog is not None:
            return
        dialog = Gtk.Window(transient_for=self.window, modal=True, resizable=False)
        dialog.set_title("Change global shortcut")
        dialog.set_default_size(390, 235)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(22)
        content.set_margin_bottom(22)
        content.set_margin_start(22)
        content.set_margin_end(22)
        title = Gtk.Label(label="Press your new shortcut")
        title.add_css_class("title-2")
        title.set_xalign(0)
        content.append(title)
        hint = Gtk.Label(
            label="Use a key such as -, F6 or Ctrl + F6. Press Esc to cancel."
        )
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        content.append(hint)
        capture = Gtk.Label(label="Waiting for a key…")
        capture.add_css_class("am-keycap")
        capture.set_margin_top(6)
        capture.set_margin_bottom(6)
        content.append(capture)
        cancel = Gtk.Button(label="Cancel")
        cancel.set_halign(Gtk.Align.END)
        cancel.connect("clicked", lambda *_: dialog.close())
        content.append(cancel)
        dialog.set_child(content)
        dialog.connect("close-request", lambda *_: self._clear_shortcut_dialog())

        controller = Gtk.EventControllerKey.new()
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        controller.connect("key-pressed", self._on_shortcut_key, dialog, capture)
        dialog.add_controller(controller)
        self._shortcut_dialog = dialog
        dialog.present()

    def _clear_shortcut_dialog(self) -> bool:
        self._shortcut_dialog = None
        return False

    def _on_shortcut_key(
        self, _controller: Gtk.EventControllerKey, keyval: int,
        _keycode: int, state: Gdk.ModifierType, dialog: Gtk.Window,
        capture: Gtk.Label,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            dialog.close()
            return True
        if keyval in IGNORED_KEYS:
            return True
        modifiers = state & Gtk.accelerator_get_default_mod_mask()
        try:
            binding = Gtk.accelerator_name(keyval, modifiers)
        except Exception as exc:
            LOGGER.debug("Could not encode shortcut", exc_info=True)
            self._notify(f"That key could not be used: {exc}")
            return True
        if not binding:
            self._notify("That key cannot be used as a shortcut. Try another key.")
            return True

        capture.set_text(format_binding(binding))
        previous_binding = self.config.data["hotkey"]
        try:
            self.config.update(hotkey=binding)
            set_global_binding(binding)
        except Exception as exc:
            try:
                self.config.update(hotkey=previous_binding)
            except OSError:
                LOGGER.exception("Could not restore the previous shortcut setting")
            LOGGER.warning("Could not save global shortcut: %s", exc)
            message = describe_hotkey_error(exc)
            if self._shortcut_detail is not None:
                self._shortcut_detail.set_text(message)
            self._notify(message)
            return True

        self._update_shortcut_label()
        if self._is_clicking:
            self._set_status(
                "running",
                f"Shortcut changed. Press {format_binding(binding)} to stop clicking.",
            )
        elif self._is_starting:
            self._set_status("starting", "Shortcut changed. Preparing the virtual mouse…")
        else:
            self._set_status("ready", f"Shortcut changed to {format_binding(binding)}.")
        self._notify(f"Global shortcut set to {format_binding(binding)}.")
        dialog.close()
        return True

    def _on_close_request(self, *_args: Any) -> bool:
        # Stop the worker before the final window and application are torn down.
        if self._is_starting or self._is_clicking:
            self.engine.stop_and_wait(0.8)
        return False

    def shutdown(self) -> None:
        """Stop the worker and detach the closed window during application shutdown."""
        self.engine.stop_and_wait(0.8)
        self.window = None
