from __future__ import annotations

import ctypes
import argparse
import logging
import threading
from ctypes import wintypes

from .composition import create_telemetry_service_runtime
from ..telemetry.providers.librehardwaremonitor import LibreHardwareMonitorProvider


SERVICE_NAME = "PCPanelTelemetry"
SERVICE_WIN32_OWN_PROCESS = 0x00000010
SERVICE_START_PENDING = 0x00000002
SERVICE_STOP_PENDING = 0x00000003
SERVICE_RUNNING = 0x00000004
SERVICE_STOPPED = 0x00000001
SERVICE_ACCEPT_STOP = 0x00000001
SERVICE_ACCEPT_SHUTDOWN = 0x00000004
SERVICE_CONTROL_STOP = 0x00000001
SERVICE_CONTROL_SHUTDOWN = 0x00000005
NO_ERROR = 0


logger = logging.getLogger(__name__)


class SERVICE_STATUS(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
    ]


HANDLER = ctypes.WINFUNCTYPE(
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID
)
SERVICE_MAIN = ctypes.WINFUNCTYPE(None, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR))


class SERVICE_TABLE_ENTRY(ctypes.Structure):
    _fields_ = [("lpServiceName", wintypes.LPWSTR), ("lpServiceProc", SERVICE_MAIN)]


def run_service_dispatcher() -> None:
    """Connect this process to SCM; installation/configuration is handled later."""

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.StartServiceCtrlDispatcherW.argtypes = [
        ctypes.POINTER(SERVICE_TABLE_ENTRY)
    ]
    advapi32.StartServiceCtrlDispatcherW.restype = wintypes.BOOL
    main_callback = SERVICE_MAIN(_service_main)
    table = (SERVICE_TABLE_ENTRY * 2)(
        SERVICE_TABLE_ENTRY(SERVICE_NAME, main_callback),
        SERVICE_TABLE_ENTRY(None, SERVICE_MAIN()),
    )
    if not advapi32.StartServiceCtrlDispatcherW(table):
        raise ctypes.WinError(ctypes.get_last_error())


def _service_main(_argc: int, _argv: ctypes.POINTER(wintypes.LPWSTR)) -> None:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.RegisterServiceCtrlHandlerExW.argtypes = [
        wintypes.LPCWSTR, HANDLER, wintypes.LPVOID
    ]
    advapi32.RegisterServiceCtrlHandlerExW.restype = wintypes.HANDLE
    advapi32.SetServiceStatus.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(SERVICE_STATUS)
    ]
    advapi32.SetServiceStatus.restype = wintypes.BOOL
    stop_requested = threading.Event()

    @HANDLER
    def handler(
        control: int,
        _event_type: int,
        _event_data: wintypes.LPVOID,
        _context: wintypes.LPVOID,
    ) -> int:
        if control in {SERVICE_CONTROL_STOP, SERVICE_CONTROL_SHUTDOWN}:
            stop_requested.set()
        return NO_ERROR

    status_handle = advapi32.RegisterServiceCtrlHandlerExW(
        SERVICE_NAME, handler, None
    )
    if not status_handle:
        return

    def report(state: int, *, exit_code: int = NO_ERROR, wait_hint: int = 0) -> None:
        accepted = (
            SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN
            if state == SERVICE_RUNNING
            else 0
        )
        status = SERVICE_STATUS(
            SERVICE_WIN32_OWN_PROCESS,
            state,
            accepted,
            exit_code,
            0,
            0,
            wait_hint,
        )
        if not advapi32.SetServiceStatus(status_handle, ctypes.byref(status)):
            raise ctypes.WinError(ctypes.get_last_error())

    runtime = None
    try:
        report(SERVICE_START_PENDING, wait_hint=10_000)
        runtime = create_telemetry_service_runtime()
        runtime.start()
        report(SERVICE_RUNNING)
        stop_requested.wait()
        report(SERVICE_STOP_PENDING, wait_hint=10_000)
        runtime.stop()
        report(SERVICE_STOPPED)
    except Exception:
        logger.exception("PCPanel telemetry service failed")
        if runtime is not None:
            runtime.stop()
        report(SERVICE_STOPPED, exit_code=1)


def main() -> None:
    parser = argparse.ArgumentParser(description="PCPanel Telemetry Windows Service")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        provider = LibreHardwareMonitorProvider()
        dll_path = provider._resolve_dll_path()
        import pythonnet

        computer_type = provider._get_computer_type()
        print(f"PCPanelTelemetryService smoke test passed: {dll_path}")
        print(f"pythonnet: {pythonnet.__file__}")
        print(f"LHM type: {computer_type}")
        return
    logging.basicConfig(level=logging.INFO)
    run_service_dispatcher()


if __name__ == "__main__":
    main()
