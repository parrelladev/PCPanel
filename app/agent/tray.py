from __future__ import annotations

import ctypes
import ipaddress
import socket
import sys
import threading
import webbrowser
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path

import pystray
from PIL import Image

from .telemetry import AgentTelemetrySource


SERVICE_NAME = "PCPanelTelemetry"
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


def asset_path(name: str) -> Path:
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return root / "assets" / name


def local_panel_url(host: str, port: int) -> str:
    display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{display_host}:{port}/"


def discover_lan_ipv4() -> str:
    """Choose the IPv4 used by the default route without sending network data."""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))
            candidate = probe.getsockname()[0]
            if _usable_lan_address(candidate):
                return candidate
        except OSError:
            pass

    candidates = sorted(
        {
            address
            for address in socket.gethostbyname_ex(socket.gethostname())[2]
            if _usable_lan_address(address)
        }
    )
    return candidates[0] if candidates else "127.0.0.1"


def lan_panel_url(port: int) -> str:
    return f"http://{discover_lan_ipv4()}:{port}/"


def telemetry_label(status: str) -> str:
    return {
        "running": "Online",
        "starting": "Service starting",
        "unavailable": "Offline",
        "failed": "Hardware unavailable",
    }.get(status, "Erro controlado")


def restart_telemetry_service() -> None:
    """Request UAC for one fixed SCM operation; no input reaches the command."""

    parameters = (
        '-NoProfile -WindowStyle Hidden -Command '
        '"Restart-Service -Name \'PCPanelTelemetry\' -ErrorAction Stop"'
    )
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "powershell.exe", parameters, None, 0
    )
    if result <= 32:
        raise OSError(f"Could not request telemetry service restart ({result})")


def copy_text(text: str) -> None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    encoded = (text + "\0").encode("utf-16-le")
    if not user32.OpenClipboard(None):
        raise ctypes.WinError()
    try:
        user32.EmptyClipboard()
        memory = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not memory:
            raise ctypes.WinError()
        pointer = kernel32.GlobalLock(memory)
        ctypes.memmove(pointer, encoded, len(encoded))
        kernel32.GlobalUnlock(memory)
        if not user32.SetClipboardData(CF_UNICODETEXT, memory):
            raise ctypes.WinError()
    finally:
        user32.CloseClipboard()


class AgentTray:
    def __init__(
        self,
        source: AgentTelemetrySource,
        host: str,
        port: int,
        request_exit: Callable[[], None],
    ) -> None:
        self._source = source
        self._local_url = local_panel_url(host, port)
        self._lan_url = lan_panel_url(port)
        self._request_exit = request_exit
        self._thread: threading.Thread | None = None
        image = Image.open(asset_path("pcpanel-tray.xpm")).convert("RGBA")
        self._icon = pystray.Icon(
            "PCPanelAgent",
            image,
            "PCPanel",
            menu=pystray.Menu(
                pystray.MenuItem(self._title, None, enabled=False),
                pystray.MenuItem("Abrir painel local", self._open_panel, default=True),
                pystray.MenuItem("Copiar endereço para celular", self._copy_address),
                pystray.MenuItem(self._telemetry_status, None, enabled=False),
                pystray.MenuItem("Reiniciar serviço de telemetria", self._restart_service),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", self._exit),
            ),
        )

    def start(self) -> None:
        self._thread = threading.Thread(target=self._icon.run, name="pcpanel-tray", daemon=False)
        self._thread.start()

    def stop(self) -> None:
        self._icon.stop()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _title(self, _item: object) -> str:
        return f"PCPanel ● {telemetry_label(self._source.get_status())}"

    def _telemetry_status(self, _item: object) -> str:
        return f"Telemetria: {telemetry_label(self._source.get_status())}"

    def _open_panel(self, _icon: object, _item: object) -> None:
        webbrowser.open(self._local_url)

    def _copy_address(self, icon: pystray.Icon, _item: object) -> None:
        copy_text(self._lan_url)
        icon.notify(self._lan_url, "Endereço do PCPanel copiado")

    def _restart_service(self, _icon: object, _item: object) -> None:
        restart_telemetry_service()

    def _exit(self, icon: pystray.Icon, _item: object) -> None:
        icon.stop()
        self._request_exit()


def _usable_lan_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return address.version == 4 and not address.is_loopback and not address.is_link_local
