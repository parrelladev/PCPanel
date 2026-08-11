from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


MUTEX_NAME = r"Local\PCPanelAgent"
ERROR_ALREADY_EXISTS = 183
MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040


class AgentInstanceLock:
    """Keep at most one Agent in the current interactive Windows session."""

    def __init__(self, name: str = MUTEX_NAME) -> None:
        self._name = name
        self._handle: int | None = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        if self._handle is not None:
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, False, self._name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(self._handle)
        self._handle = None

    def __enter__(self) -> AgentInstanceLock:
        if not self.acquire():
            raise RuntimeError("PCPanel Agent is already running in this session")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


def notify_existing_instance() -> None:
    """Tell an interactive user why a duplicate launch exits."""

    if os.name != "nt":
        return
    ctypes.WinDLL("user32", use_last_error=True).MessageBoxW(
        None,
        "PCPanel Agent já está em execução nesta sessão.",
        "PCPanel",
        MB_OK | MB_ICONINFORMATION,
    )
