from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

from .single_instance import MUTEX_NAME


SHUTDOWN_EVENT_NAME = r"Local\PCPanelAgentShutdown"
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF


class AgentShutdownMonitor:
    """Receive one local, fixed-name graceful shutdown signal."""

    def __init__(self, request_exit: Callable[[], None]) -> None:
        self._request_exit = request_exit
        self._handle: int | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateEventW.argtypes = [
            wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR
        ]
        kernel32.CreateEventW.restype = wintypes.HANDLE
        handle = kernel32.CreateEventW(None, False, False, SHUTDOWN_EVENT_NAME)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handle = handle
        self._thread = threading.Thread(
            target=self._wait,
            name="pcpanel-agent-shutdown",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        handle = self._handle
        if handle is None:
            return
        _set_event(handle)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
        self._handle = None
        self._thread = None

    def _wait(self) -> None:
        handle = self._handle
        if handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject(handle, INFINITE)
        self._request_exit()


def request_existing_agent_shutdown(timeout_ms: int = 10_000) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenMutexW.restype = wintypes.HANDLE
    event_handle = kernel32.OpenEventW(
        EVENT_MODIFY_STATE | SYNCHRONIZE, False, SHUTDOWN_EVENT_NAME
    )
    if not event_handle:
        return False
    try:
        _set_event(event_handle)
        elapsed_ms = 0
        while elapsed_ms < timeout_ms:
            mutex_handle = kernel32.OpenMutexW(SYNCHRONIZE, False, MUTEX_NAME)
            if not mutex_handle:
                return True
            kernel32.CloseHandle(mutex_handle)
            kernel32.Sleep(100)
            elapsed_ms += 100
        return False
    finally:
        kernel32.CloseHandle(event_handle)


def _set_event(handle: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.SetEvent.restype = wintypes.BOOL
    if not kernel32.SetEvent(handle):
        raise ctypes.WinError(ctypes.get_last_error())
