from pathlib import Path


ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "pcpanel_agent.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "web"), "web"),
        (str(ROOT / "assets"), "assets"),
    ],
    hiddenimports=[],
    excludes=[
        "app.service",
        "app.telemetry.providers.librehardwaremonitor",
        "pythonnet",
        "clr",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PCPanelAgent",
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PCPanelAgent",
)
