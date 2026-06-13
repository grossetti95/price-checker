# -*- mode: python ; coding: utf-8 -*-
#
# Spec file PyInstaller per Competitor Price Checker.
#
# Uso (da terminale, sul PC Windows dove vuoi creare il .exe):
#     pyinstaller CompetitorPriceChecker.spec
#
# L'eseguibile finale si troverà in: dist/CompetitorPriceChecker/CompetitorPriceChecker.exe
#
# NOTA: usa --onedir (non --onefile). Con --onefile l'avvio è molto più lento
# perché ogni volta deve decomprimere tutte le librerie (pandas, selenium, ecc.)
# in una cartella temporanea. Con --onedir basta consegnare l'intera cartella
# "CompetitorPriceChecker" (anche zippata) ai colleghi.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

_ICON = "icon.ico" if os.path.exists("icon.ico") else None

datas = []

# Raccogli l'intera cartella di customtkinter (temi, font, immagini).
# collect_data_files a volte non riconosce customtkinter come "package"
# in alcuni ambienti (Anaconda): qui lo prendiamo direttamente dal modulo
# importato, che funziona sempre.
import customtkinter
_ctk_dir = os.path.dirname(customtkinter.__file__)
datas.append(("logo.png", "."))
datas.append((_ctk_dir, "customtkinter"))

hiddenimports = []
hiddenimports += collect_submodules("selenium")
hiddenimports += collect_submodules("webdriver_manager")
hiddenimports += [
    "bs4",
    "lxml",
    "lxml.etree",
    "anthropic",
]

excludes = [
    # Binding Qt: l'app usa CustomTkinter (basato su Tkinter), non Qt.
    # Se nell'ambiente Python sono installati sia PyQt5 che PySide6 (tipico
    # di un Anaconda "base" molto pieno), PyInstaller si blocca perché non
    # può includerli entrambi. Li escludiamo entrambi: non servono.
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    # Altri package tipici di un ambiente Anaconda "base" che non servono
    # a questa applicazione e che appesantiscono/allungano molto il build.
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
    name="CompetitorPriceChecker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # niente finestra nera del terminale
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICON,              # opzionale: metti un file icon.ico nella stessa cartella
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CompetitorPriceChecker",
)
