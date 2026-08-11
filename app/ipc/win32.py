from __future__ import annotations

import ctypes
import os
import struct
import time
from ctypes import wintypes

from .protocol import (
    IPCProtocolError,
    IPCTimeoutError,
    IPCUnavailableError,
    IPCWin32Error,
    MAX_MESSAGE_BYTES,
)


PIPE_ACCESS_DUPLEX = 0x00000003
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
PIPE_UNLIMITED_INSTANCES = 255
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
ERROR_PIPE_CONNECTED = 535
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
SE_KERNEL_OBJECT = 6
DACL_SECURITY_INFORMATION = 0x00000004
TOKEN_QUERY = 0x0008
TOKEN_GROUPS = 2
TOKEN_USER = 1
TOKEN_RESTRICTED_SIDS = 11
THREAD_TERMINATE = 0x0001

# System and Administrators control the server; interactive users may only
# exchange telemetry. Network logons are denied and remote clients are also
# rejected by the pipe mode flag.
PIPE_SDDL = "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;IU)"


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]


class TOKEN_GROUPS_HEADER(ctypes.Structure):
    _fields_ = [("GroupCount", wintypes.DWORD)]


class TOKEN_USER_VALUE(ctypes.Structure):
    _fields_ = [("User", SID_AND_ATTRIBUTES)]


def _win32_error(operation: str) -> IPCWin32Error:
    return IPCWin32Error(operation, ctypes.get_last_error())


def _require_windows() -> None:
    if os.name != "nt":
        raise IPCUnavailableError("Windows named pipes require Windows")


def create_server_pipe(name: str) -> int:
    _require_windows()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.ULONG)
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    kernel32.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(SECURITY_ATTRIBUTES),
    ]
    kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    descriptor = wintypes.LPVOID()
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        PIPE_SDDL, 1, ctypes.byref(descriptor), None
    ):
        raise _win32_error("ConvertStringSecurityDescriptorToSecurityDescriptorW")
    attributes = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), descriptor, False)
    try:
        handle = kernel32.CreateNamedPipeW(
            name,
            PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
            PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
            PIPE_UNLIMITED_INSTANCES,
            65536,
            65536,
            0,
            ctypes.byref(attributes),
        )
        if handle == INVALID_HANDLE_VALUE:
            raise _win32_error("CreateNamedPipeW")
        return handle
    finally:
        kernel32.LocalFree(descriptor)


def connect_server(handle: int) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.ConnectNamedPipe(handle, None):
        error = ctypes.get_last_error()
        if error != ERROR_PIPE_CONNECTED:
            raise IPCWin32Error("ConnectNamedPipe", error)


def open_client(name: str, timeout_seconds: float) -> int:
    _require_windows()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise IPCUnavailableError("Telemetry service is unavailable")
        if kernel32.WaitNamedPipeW(name, max(1, int(remaining * 1000))):
            break
        error = ctypes.get_last_error()
        if error == 121:
            raise IPCTimeoutError("Timed out waiting for telemetry service")
        if error != 2:
            raise IPCWin32Error("WaitNamedPipeW", error)
        time.sleep(min(0.01, remaining))
    handle = kernel32.CreateFileW(
        name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None
    )
    if handle == INVALID_HANDLE_VALUE:
        raise _win32_error("CreateFileW")
    return handle


def close_handle(handle: int) -> None:
    ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)


def disconnect(handle: int) -> None:
    ctypes.WinDLL("kernel32", use_last_error=True).DisconnectNamedPipe(handle)


def flush_pipe(handle: int) -> None:
    """Wait until the client has consumed buffered response bytes."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    if not kernel32.FlushFileBuffers(handle):
        raise _win32_error("FlushFileBuffers")


def cancel_thread_io(thread_id: int) -> bool:
    """Cancel blocking synchronous pipe I/O owned by one server thread."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenThread.restype = wintypes.HANDLE
    kernel32.CancelSynchronousIo.argtypes = [wintypes.HANDLE]
    kernel32.CancelSynchronousIo.restype = wintypes.BOOL
    thread = kernel32.OpenThread(THREAD_TERMINATE, False, thread_id)
    if not thread:
        raise _win32_error("OpenThread")
    try:
        if not kernel32.CancelSynchronousIo(thread):
            error = ctypes.get_last_error()
            if error == 1168:  # ERROR_NOT_FOUND: no blocking I/O at that instant.
                return False
            raise IPCWin32Error("CancelSynchronousIo", error)
        return True
    finally:
        close_handle(thread)


def write_all(handle: int, data: bytes) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    offset = 0
    while offset < len(data):
        written = wintypes.DWORD()
        chunk = data[offset:]
        if not kernel32.WriteFile(handle, chunk, len(chunk), ctypes.byref(written), None):
            raise _win32_error("WriteFile")
        offset += written.value


def read_exact(handle: int, size: int) -> bytes:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    result = bytearray()
    while len(result) < size:
        chunk_size = size - len(result)
        buffer = ctypes.create_string_buffer(chunk_size)
        read = wintypes.DWORD()
        if not kernel32.ReadFile(handle, buffer, chunk_size, ctypes.byref(read), None):
            raise _win32_error("ReadFile")
        if read.value == 0:
            raise IPCUnavailableError("Named pipe connection closed")
        result.extend(buffer.raw[:read.value])
    return bytes(result)


def read_frame(handle: int) -> bytes:
    header = read_exact(handle, 4)
    (size,) = struct.unpack("<I", header)
    if size > MAX_MESSAGE_BYTES:
        raise IPCProtocolError("IPC message exceeds maximum size")
    return header + read_exact(handle, size)


def security_descriptor_sddl(handle: int) -> str:
    """Read back the DACL applied by the kernel to an open pipe handle."""

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.GetSecurityInfo.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.LPVOID, wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPVOID),
    ]
    advapi32.GetSecurityInfo.restype = wintypes.DWORD
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.ULONG),
    ]
    descriptor = wintypes.LPVOID()
    result = advapi32.GetSecurityInfo(
        handle, SE_KERNEL_OBJECT, DACL_SECURITY_INFORMATION,
        None, None, None, None, ctypes.byref(descriptor),
    )
    if result:
        raise IPCWin32Error("GetSecurityInfo", result)
    text = wintypes.LPWSTR()
    length = wintypes.ULONG()
    try:
        if not advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, DACL_SECURITY_INFORMATION, ctypes.byref(text), ctypes.byref(length)
        ):
            raise _win32_error("ConvertSecurityDescriptorToStringSecurityDescriptorW")
        return text.value
    finally:
        if text:
            kernel32.LocalFree(text)
        kernel32.LocalFree(descriptor)


def current_token_diagnostics() -> dict[str, object]:
    """Report effective and restricting SIDs for the calling process token."""

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
    ]
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)
    ]
    advapi32.IsTokenRestricted.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise _win32_error("OpenProcessToken")
    try:
        return {
            "is_restricted": bool(advapi32.IsTokenRestricted(token)),
            "groups": _token_sids(token, TOKEN_GROUPS),
            "restricted_sids": _token_sids(token, TOKEN_RESTRICTED_SIDS),
        }
    finally:
        close_handle(token)


def current_user_sid() -> str:
    """Return the SID of the effective Windows process user."""

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
    ]
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)
    ]
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise _win32_error("OpenProcessToken")
    try:
        required = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(required))
        buffer = ctypes.create_string_buffer(required.value)
        if not advapi32.GetTokenInformation(
            token, TOKEN_USER, buffer, required, ctypes.byref(required)
        ):
            raise _win32_error("GetTokenInformation")
        user = ctypes.cast(buffer, ctypes.POINTER(TOKEN_USER_VALUE)).contents
        sid_text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(user.User.Sid, ctypes.byref(sid_text)):
            raise _win32_error("ConvertSidToStringSidW")
        try:
            return sid_text.value
        finally:
            kernel32.LocalFree(sid_text)
    finally:
        close_handle(token)


def _token_sids(token: int, information_class: int) -> list[dict[str, object]]:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)
    ]
    required = wintypes.DWORD()
    advapi32.GetTokenInformation(token, information_class, None, 0, ctypes.byref(required))
    buffer = ctypes.create_string_buffer(required.value)
    if not advapi32.GetTokenInformation(
        token, information_class, buffer, required, ctypes.byref(required)
    ):
        raise _win32_error("GetTokenInformation")
    count = ctypes.cast(buffer, ctypes.POINTER(TOKEN_GROUPS_HEADER)).contents.GroupCount
    offset = ctypes.sizeof(wintypes.DWORD)
    alignment = ctypes.alignment(SID_AND_ATTRIBUTES)
    offset = (offset + alignment - 1) & ~(alignment - 1)
    entries = ctypes.cast(ctypes.addressof(buffer) + offset, ctypes.POINTER(SID_AND_ATTRIBUTES))
    result: list[dict[str, object]] = []
    for index in range(count):
        sid_text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(entries[index].Sid, ctypes.byref(sid_text)):
            raise _win32_error("ConvertSidToStringSidW")
        try:
            result.append({"sid": sid_text.value, "attributes": entries[index].Attributes})
        finally:
            ctypes.WinDLL("kernel32", use_last_error=True).LocalFree(sid_text)
    return result
