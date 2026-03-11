from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hermit.companion.appbundle import (
    app_path,
    disable_login_item,
    enable_login_item,
    install_app_bundle,
    login_item_enabled,
    open_app_bundle,
)
from hermit.companion.control import (
    config_path,
    ensure_base_dir,
    ensure_config_file,
    hermit_base_dir,
    hermit_log_dir,
    open_in_textedit,
    open_path,
    reload_service,
    run_hermit_command,
    service_status,
    start_service,
    stop_service,
)
from hermit.config import get_settings
from hermit.i18n import resolve_locale, tr

try:
    import rumps
except Exception as exc:  # pragma: no cover - runtime dependency on macOS only
    rumps = None
    _IMPORT_ERROR = exc
else:  # pragma: no cover - exercised manually on macOS
    _IMPORT_ERROR = None


def _t(key: str, **kwargs: object) -> str:
    settings = get_settings()
    locale = resolve_locale(getattr(settings, "locale", None))
    return tr(key, locale=locale, **kwargs)


if rumps is not None:  # pragma: no branch - class only exists when dependency is available
    class HermitMenuApp(rumps.App):  # pragma: no cover - macOS UI exercised manually
        def __init__(self, *, adapter: str, profile: str | None = None, base_dir: Path | None = None) -> None:
            super().__init__(_t("menubar.title"), quit_button=None)
            self.adapter = adapter
            self.profile = profile
            self.base_dir = base_dir or hermit_base_dir()
            self.status_item = rumps.MenuItem(_t("menubar.status.checking"))
            self.profile_item = rumps.MenuItem(_t("menubar.profile.pending"))
            self.provider_item = rumps.MenuItem(_t("menubar.provider.pending"))
            self.model_item = rumps.MenuItem(_t("menubar.model.pending"))
            self.start_item = rumps.MenuItem(_t("menubar.action.start"), callback=self._start_service)
            self.stop_item = rumps.MenuItem(_t("menubar.action.stop"), callback=self._stop_service)
            self.reload_item = rumps.MenuItem(_t("menubar.action.reload"), callback=self._reload_service)
            self.menu_login_item = rumps.MenuItem(_t("menubar.action.enable_login_item"), callback=self._enable_menu_login_item)
            self.install_app_item = rumps.MenuItem(_t("menubar.action.install_or_open"), callback=self._install_or_open_menu_app)
            self.menu = [
                self.status_item,
                self.profile_item,
                self.provider_item,
                self.model_item,
                None,
                self.start_item,
                self.stop_item,
                self.reload_item,
                None,
                rumps.MenuItem(_t("menubar.action.enable_autostart"), callback=self._enable_autostart),
                rumps.MenuItem(_t("menubar.action.disable_autostart"), callback=self._disable_autostart),
                self.menu_login_item,
                self.install_app_item,
                None,
                rumps.MenuItem(_t("menubar.action.open_config"), callback=self._open_config),
                rumps.MenuItem(_t("menubar.action.open_logs"), callback=self._open_logs),
                rumps.MenuItem(_t("menubar.action.open_home"), callback=self._open_base_dir),
            ]
            self.refresh_status(None)

        def _notify(self, title: str, message: str) -> None:
            rumps.notification(title, "", message)

        def _show_result(self, title: str, fn, *args, **kwargs) -> None:
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                self._notify(title, str(exc))
            else:
                self._notify(title, str(result))
                self.refresh_status(None)

        @rumps.timer(5)
        def refresh_status(self, _sender) -> None:
            get_settings.cache_clear()
            settings = get_settings()
            state = service_status(self.adapter, base_dir=self.base_dir)
            running_text = _t("menubar.status.running") if state.running else _t("menubar.status.stopped")
            if state.running and state.pid is not None:
                running_text = _t("menubar.status.pid", text=running_text, pid=state.pid)
            autostart = _t("menubar.status.launchd_on") if state.autostart_loaded else _t("menubar.status.launchd_off")
            self.status_item.title = _t("menubar.status.summary", running=running_text, autostart=autostart)
            resolved_profile = self.profile or settings.resolved_profile or _t("menubar.profile.default")
            self.profile_item.title = _t("menubar.profile.title", profile=resolved_profile)
            self.provider_item.title = _t("menubar.provider.title", provider=settings.provider)
            self.model_item.title = _t("menubar.model.title", model=settings.model)
            if state.autostart_loaded:
                self.start_item.title = _t("menubar.action.start.managed")
                self.start_item.set_callback(None)
                self.stop_item.title = _t("menubar.action.stop.disable_autostart")
                self.stop_item.set_callback(None)
            elif state.running:
                self.start_item.title = _t("menubar.action.start.running")
                self.start_item.set_callback(None)
                self.stop_item.title = _t("menubar.action.stop")
                self.stop_item.set_callback(self._stop_service)
            else:
                self.start_item.title = _t("menubar.action.start")
                self.start_item.set_callback(self._start_service)
                self.stop_item.title = _t("menubar.action.stop.not_running")
                self.stop_item.set_callback(None)
            self.reload_item.title = _t("menubar.action.reload") if state.running else _t("menubar.action.reload.not_running")
            self.reload_item.set_callback(self._reload_service if state.running else None)
            if login_item_enabled():
                self.menu_login_item.title = _t("menubar.action.disable_login_item")
                self.menu_login_item.set_callback(self._disable_menu_login_item)
                self.install_app_item.title = _t("menubar.action.open_menu_app")
            else:
                self.menu_login_item.title = _t("menubar.action.enable_login_item")
                self.menu_login_item.set_callback(self._enable_menu_login_item)
                self.install_app_item.title = _t("menubar.action.install_or_open")

        def _start_service(self, _sender) -> None:
            self._show_result(_t("menubar.title"), start_service, self.adapter, base_dir=self.base_dir, profile=self.profile)

        def _stop_service(self, _sender) -> None:
            self._show_result(_t("menubar.title"), stop_service, self.adapter, base_dir=self.base_dir)

        def _reload_service(self, _sender) -> None:
            self._show_result(_t("menubar.title"), reload_service, self.adapter, base_dir=self.base_dir, profile=self.profile)

        def _enable_autostart(self, _sender) -> None:
            self._show_result(
                _t("menubar.title"),
                lambda: run_hermit_command(
                    ["autostart", "enable", "--adapter", self.adapter],
                    base_dir=self.base_dir,
                    profile=self.profile,
                ).stdout.strip(),
            )

        def _disable_autostart(self, _sender) -> None:
            self._show_result(
                _t("menubar.title"),
                lambda: run_hermit_command(
                    ["autostart", "disable", "--adapter", self.adapter],
                    base_dir=self.base_dir,
                    profile=self.profile,
                ).stdout.strip(),
            )

        def _enable_menu_login_item(self, _sender) -> None:
            bundle = install_app_bundle(adapter=self.adapter, profile=self.profile, base_dir=self.base_dir)
            self._show_result(_t("menubar.title"), enable_login_item, bundle)

        def _disable_menu_login_item(self, _sender) -> None:
            self._show_result(_t("menubar.title"), disable_login_item)

        def _install_or_open_menu_app(self, _sender) -> None:
            bundle = app_path()
            if not bundle.exists():
                bundle = install_app_bundle(adapter=self.adapter, profile=self.profile, base_dir=self.base_dir)
                self._notify(_t("menubar.title"), _t("menubar.notify.installed_menu_app", bundle=bundle))
            open_app_bundle(bundle)

        def _open_config(self, _sender) -> None:
            ensure_base_dir(self.base_dir)
            target = config_path(self.base_dir)
            if not target.exists():
                target = ensure_config_file(self.base_dir)
                self._notify(_t("menubar.title"), _t("menubar.notify.config_missing", base_dir=self.base_dir))
            open_in_textedit(target)

        def _open_logs(self, _sender) -> None:
            open_path(hermit_log_dir(self.base_dir))

        def _open_base_dir(self, _sender) -> None:
            open_path(self.base_dir)

        def _quit_app(self, _sender) -> None:
            rumps.quit_application()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=_t("menubar.argparse.description"))
    parser.add_argument("--adapter", default="feishu", help=_t("menubar.argparse.adapter"))
    parser.add_argument("--profile", default=None, help=_t("menubar.argparse.profile"))
    parser.add_argument("--base-dir", default=None, help=_t("menubar.argparse.base_dir"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if sys.platform != "darwin":
        print(_t("menubar.error.mac_only"), file=sys.stderr)
        return 1
    if rumps is None:
        print(_t("menubar.error.missing_rumps"), file=sys.stderr)
        if _IMPORT_ERROR is not None:
            print(str(_IMPORT_ERROR), file=sys.stderr)
        return 1
    args = _parse_args(argv or sys.argv[1:])
    base_dir = Path(args.base_dir).expanduser() if args.base_dir else None
    app = HermitMenuApp(adapter=args.adapter, profile=args.profile, base_dir=base_dir)
    app.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
