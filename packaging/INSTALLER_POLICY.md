# PCPanel installer policy

- Binaries install under `%ProgramFiles%\PCPanel`.
- User data stays under `%LOCALAPPDATA%\PCPanel` and is never part of the installer payload.
- Service account is `LocalSystem`. Physical testing under `LocalService` exposed
  CPU temperature sensors but returned null values; the same installed binary
  returned a valid CPU temperature immediately under `LocalSystem`. The elevated
  process remains hardware-only and has no HTTP, Auth, Actions, tray, or SQLite.
- Service auto-start, Agent login startup, immediate launch, and private-LAN firewall access require explicit task selection.
- The firewall rule is inbound, Private profile only, executable-scoped, and limited to `LocalSubnet`.
- Upgrade gracefully signals the Agent, stops the Service, replaces binaries in place, preserves the data directory, then applies normal database migrations at Agent startup.
- Downgrade is unsupported. A binary older than the database schema fails with `UnsupportedSchemaVersionError` rather than mutating the database.
- Standard uninstall preserves user data. The uninstaller asks separately before deleting `%LOCALAPPDATA%\PCPanel`.
- Installer logs contain lifecycle command results only; tokens and pairing codes are never installer inputs.
