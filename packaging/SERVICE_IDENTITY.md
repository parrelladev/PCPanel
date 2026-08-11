# Telemetry Service identity decision

`PCPanelTelemetry` runs as `LocalSystem` because the less-privileged identity was
physically tested and did not provide the hardware access required by this host.

On 2026-08-11, the packaged Service running as `LocalService` exposed Intel CPU
temperature sensor records through the secure pipe, but their current, minimum,
and maximum values were all null. Restarting the Service did not recover them.
GPU temperature and non-privileged CPU readings remained available.

With the same installed binary reconfigured to `LocalSystem`, the first physical
validation returned `40.0 celsius` from `/intelcpu/0/temperature/16`. This is the
evidence required by M10.3 to reject `LocalService` for the final runtime.

The additional privilege is confined to the hardware boundary:

```text
LibreHardwareMonitor -> TelemetryManager -> raw snapshot -> local named pipe
```

The Service does not host HTTP, accept LAN traffic, read bearer tokens, access
SQLite, execute Actions, start user applications, or provide a generic command
primitive. The Agent remains a normal, non-elevated interactive-user process.
