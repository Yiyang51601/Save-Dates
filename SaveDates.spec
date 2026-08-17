# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

datas = [
    ("save_dates/static", "save_dates/static"),
    ("assets/icon.ico", "assets"),
]
binaries = []
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "h11",
    "sniffio",
    "anyio",
    "anyio._backends._asyncio",
    "starlette",
    "starlette.routing",
    "starlette.responses",
    "starlette.staticfiles",
    "fastapi",
    "fastapi.routing",
    "httpx",
    "httpcore",
    "win32timezone",
    "pythoncom",
    "pywintypes",
    "win32com",
    "win32com.client",
    "webview",
    "pystray",
    "PIL",
    "lxml",
    "lxml.etree",
    "tzlocal",
    "bs4",
    "save_dates",
    "save_dates.server",
    "save_dates.desktop",
    "save_dates.watcher",
    "save_dates.outlook_client",
    "save_dates.extract",
    "save_dates.db",
    "save_dates.graph_auth",
    "save_dates.graph_client",
    "save_dates.graph_runtime",
    "save_dates.outlook_detect",
    "save_dates.greet",
    "save_dates.i18n",
    "msal",
]

for pkg in (
    "webview",
    "uvicorn",
    "pystray",
    "fastapi",
    "starlette",
    "anyio",
    "httpx",
    "httpcore",
    "msal",
    "bs4",
    "pydantic",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    ["save_dates/__main__.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SaveDates",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon="assets/icon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SaveDates",
)
