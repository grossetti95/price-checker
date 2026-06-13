"""
config.py — Gestione configurazione locale dell'applicazione
================================================================
Salva impostazioni persistenti (API key Anthropic, cartella output,
ultima cartella CSV usata, siti competitor, soglia) in un file JSON
nella cartella dati utente, in modo che restino tra una sessione e l'altra
e che non finiscano nel codice/eseguibile.

Percorso del file:
    Windows : %APPDATA%/CompetitorPriceChecker/config.json
    macOS   : ~/Library/Application Support/CompetitorPriceChecker/config.json
    Linux   : ~/.config/CompetitorPriceChecker/config.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from core import DEFAULT_COMPETITOR_SITES

APP_NAME = "CompetitorPriceChecker"


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", str(Path.home()))
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".config" / APP_NAME


CONFIG_DIR  = _config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "anthropic_api_key": "",
    "use_ai": True,
    "competitor_sites": DEFAULT_COMPETITOR_SITES,
    "output_dir": str(Path.home() / "Desktop"),
    "last_csv_dir": str(Path.home()),
}


def load_config() -> dict:
    """Carica la configurazione, creando i valori di default se assenti."""
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except Exception:
            pass

    # Se la cartella di output salvata non esiste più, torna al Desktop/Home
    if not os.path.isdir(cfg.get("output_dir", "")):
        cfg["output_dir"] = str(Path.home() / "Desktop") if (Path.home() / "Desktop").exists() else str(Path.home())

    return cfg


def save_config(cfg: dict) -> None:
    """Salva la configurazione su disco (crea la cartella se necessario)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    to_save = {k: cfg.get(k, v) for k, v in DEFAULTS.items()}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2, ensure_ascii=False)


def update_config(**kwargs) -> dict:
    """Aggiorna solo alcune chiavi della configurazione e la salva."""
    cfg = load_config()
    cfg.update({k: v for k, v in kwargs.items() if k in DEFAULTS})
    save_config(cfg)
    return cfg
