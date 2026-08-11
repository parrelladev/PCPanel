from pathlib import Path


ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "pcpanel_telemetry_service.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "libs" / "LibreHardwareMonitor"), "lhm")],
    hiddenimports=["clr", "pythonnet"],
    excludes=[
        "fastapi",
        "uvicorn",
        "app.api",
        "app.agent",
        "app.auth",
        "app.actions",
        "app.persistence",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PCPanelTelemetryService",
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PCPanelTelemetryService",
)
