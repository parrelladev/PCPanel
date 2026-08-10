"""Local persistence infrastructure for PCPanel."""

from app.persistence.action_store import ActionStore, StoredAction
from app.persistence.database import Database
from app.persistence.device_store import DeviceStore, StoredDevice
from app.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    UnsupportedSchemaVersionError,
)
from app.persistence.sqlite_device_store import (
    CorruptStoredDeviceError,
    SQLiteDeviceStore,
    StoredDeviceNotFoundError,
)
from app.persistence.sqlite_action_store import (
    CorruptStoredActionError,
    SQLiteActionStore,
)

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "ActionStore",
    "Database",
    "DeviceStore",
    "CorruptStoredDeviceError",
    "CorruptStoredActionError",
    "SQLiteActionStore",
    "SQLiteDeviceStore",
    "StoredAction",
    "StoredDevice",
    "StoredDeviceNotFoundError",
    "UnsupportedSchemaVersionError",
]
