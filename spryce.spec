# -*- mode: python ; coding: utf-8 -*-
#
# Spec file PyInstaller per Spryce.
#
# Uso (da terminale, con venv attivo):
#     pyinstaller Spryce.spec
#
# L'eseguibile finale si troverà in: dist/Spryce/Spryce.exe
#
# NOTA: usa --onedir (non --onefile). Con --onefile l'avvio è molto più lento
# perché ogni volta deve decomprimere tutte le librerie (pandas, selenium, ecc.)
# in una cartella temporanea. Con --onedir basta consegnare l'intera cartella
# "Spryce" (anche zippata) ai clienti.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

datas = []

# Asset grafici
datas.append(("logo.png",      "."))
datas.append(("icon.ico",      "."))
datas.append(("icon.png",      "."))

# logo_dark.png è opzionale: viene usato solo se presente
if os.path.exists("logo_dark.png"):
    datas.append(("logo_dark.png", "."))

# customtkinter: temi, font, immagini
import customtkinter
_ctk_dir = os.path.dirname(customtkinter.__file__)
datas.append((_ctk_dir, "customtkinter"))

hiddenimports = []
hiddenimports += collect_submodules("selenium")
hiddenimports += collect_submodules("webdriver_manager")
hiddenimports += collect_submodules("supabase")
hiddenimports += collect_submodules("gotrue")
hiddenimports += [
    "bs4",
    "lxml",
    "lxml.etree",
    "anthropic",
    "httpx",
    "httpx._transports.default",
]

excludes = [
    # Qt bindings: l'app usa CustomTkinter (Tkinter), non Qt.
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    # Package tipici di Anaconda base non necessari qui.
    "matplotlib", "scipy", "IPython", "ipykernel", "jupyter", "jupyter_client",
    "jupyter_core", "notebook", "nbformat", "nbconvert", "sphinx", "pytest",
    "black", "jedi", "parso", "zmq", "tornado", "docutils", "babel", "dask",
    "astroid", "pygments", "numba",
]

a = Analysis(
    ["gui_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Spryce",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Spryce",
)
