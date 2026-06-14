"""
storage.py — Storage cloud dei dati utente su Supabase
=======================================================
Gestisce il salvataggio e il recupero dei dati personali
dell'utente loggato: impostazioni, storico ricerche e CSV importati.

Tutte le funzioni sono no-op silenziosee se l'utente non è loggato,
in modo da non rompere l'app in modalità offline o non autenticata.

Uso tipico:
    import storage

    # Salva impostazioni dopo che l'utente clicca "Salva"
    storage.save_settings(cfg)

    # Carica impostazioni all'avvio (dopo il login)
    cloud_cfg = storage.load_settings()
    if cloud_cfg:
        cfg.update(cloud_cfg)

    # Salva una ricerca completata
    storage.save_search(
        csv_filename="catalogo.csv",
        competitor_sites=["example.com"],
        results=result_list,
    )

    # Recupera lo storico
    history = storage.get_history()

    # Carica un CSV sul cloud
    storage.upload_csv("/path/to/file.csv")
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import auth


# ── Helper interno ────────────────────────────────────────────────────────

def _client():
    """Ritorna il client Supabase, o None se non disponibile."""
    try:
        return auth._get_client()
    except Exception:
        return None


def _user_id() -> Optional[str]:
    """Ritorna lo user_id dell'utente loggato, o None."""
    return auth.Session.user_id


def _ok() -> bool:
    """True se l'utente è loggato e il client è disponibile."""
    return bool(_user_id() and _client())


# ── Impostazioni ──────────────────────────────────────────────────────────

def save_settings(cfg: dict) -> bool:
    """
    Salva le impostazioni dell'utente su Supabase (upsert).
    Ritorna True in caso di successo, False altrimenti.
    cfg è il dizionario restituito da config.load_config().
    """
    if not _ok():
        return False
    try:
        client = _client()
        client.table("user_settings").upsert({
            "user_id":           _user_id(),
            "theme":             cfg.get("theme", "light"),
            "anthropic_api_key": cfg.get("anthropic_api_key", ""),
            "output_dir":        cfg.get("output_dir", ""),
            "competitor_sites":  cfg.get("competitor_sites", []),
            "updated_at":        datetime.utcnow().isoformat(),
        }, on_conflict="user_id").execute()
        return True
    except Exception as e:
        print(f"[storage] save_settings error: {e}")
        return False


def load_settings() -> Optional[dict]:
    if not _ok():
        return None
    try:
        client = _client()
        res = client.table("user_settings") \
            .select("theme, anthropic_api_key, output_dir, competitor_sites") \
            .eq("user_id", _user_id()) \
            .limit(1) \
            .execute()
        if res.data and len(res.data) > 0:
            d = res.data[0]
            return {
                "theme":             d.get("theme", "light"),
                "anthropic_api_key": d.get("anthropic_api_key", ""),
                "output_dir":        d.get("output_dir", ""),
                "competitor_sites":  d.get("competitor_sites", []),
            }
        return None
    except Exception as e:
        print(f"[storage] load_settings error: {e}")
        return None


# ── Storico ricerche ──────────────────────────────────────────────────────

def save_search(
    results: list,
    csv_filename: str = "",
    competitor_sites: list | None = None,
) -> bool:
    """
    Salva una ricerca completata nello storico cloud.

    results: lista di dict con i risultati (es. output di core.run_analysis)
    csv_filename: nome del file CSV usato
    competitor_sites: lista dei siti competitor analizzati
    """
    if not _ok():
        return False
    try:
        client = _client()

        # Serializza i risultati in formato JSON-safe
        serializable = _make_serializable(results)

        client.table("search_history").insert({
            "user_id":          _user_id(),
            "csv_filename":     csv_filename,
            "competitor_sites": competitor_sites or [],
            "total_products":   len(results),
            "results":          serializable,
        }).execute()
        return True
    except Exception as e:
        print(f"[storage] save_search error: {e}")
        return False


def get_history(limit: int = 50) -> list:
    """
    Recupera lo storico delle ricerche dell'utente.
    Ritorna una lista di dict ordinata dalla più recente.
    Ogni elemento ha: id, created_at, csv_filename, total_products, results.
    """
    if not _ok():
        return []
    try:
        client = _client()
        res = client.table("search_history") \
            .select("id, created_at, csv_filename, competitor_sites, total_products, results") \
            .eq("user_id", _user_id()) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return res.data or []
    except Exception as e:
        print(f"[storage] get_history error: {e}")
        return []


def delete_search(search_id: str) -> bool:
    """Elimina una voce dallo storico ricerche."""
    if not _ok():
        return False
    try:
        _client().table("search_history") \
            .delete() \
            .eq("id", search_id) \
            .eq("user_id", _user_id()) \
            .execute()
        return True
    except Exception as e:
        print(f"[storage] delete_search error: {e}")
        return False


# ── CSV importati ─────────────────────────────────────────────────────────

def upload_csv(file_path: str) -> tuple[bool, str]:
    """
    Carica un file CSV sul bucket Supabase Storage e registra i metadati.
    Ritorna (True, storage_path) in caso di successo, (False, errore) altrimenti.

    Richiede che il bucket 'csvs' esista su Supabase Storage.
    Puoi crearlo da: Storage → New bucket → nome: 'csvs' → Private.
    """
    if not _ok():
        return False, "Utente non autenticato."
    try:
        client  = _client()
        uid     = _user_id()
        path    = Path(file_path)
        ts      = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        storage_path = f"{uid}/{ts}_{path.name}"

        with open(file_path, "rb") as f:
            client.storage.from_("csvs").upload(
                storage_path,
                f,
                {"content-type": "text/csv"},
            )

        # Conta le righe (escluso header)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                row_count = max(0, sum(1 for _ in f) - 1)
        except Exception:
            row_count = 0

        # Salva metadati
        client.table("imported_csvs").insert({
            "user_id":      uid,
            "filename":     path.name,
            "storage_path": storage_path,
            "row_count":    row_count,
        }).execute()

        return True, storage_path

    except Exception as e:
        print(f"[storage] upload_csv error: {e}")
        return False, str(e)


def get_imported_csvs() -> list:
    """
    Recupera la lista dei CSV importati dall'utente.
    Ritorna una lista di dict con: id, filename, storage_path, row_count, imported_at.
    """
    if not _ok():
        return []
    try:
        res = _client().table("imported_csvs") \
            .select("id, filename, storage_path, row_count, imported_at") \
            .eq("user_id", _user_id()) \
            .order("imported_at", desc=True) \
            .execute()
        return res.data or []
    except Exception as e:
        print(f"[storage] get_imported_csvs error: {e}")
        return []


def download_csv(storage_path: str, dest_dir: str) -> tuple[bool, str]:
    """
    Scarica un CSV dal bucket Supabase Storage nella cartella dest_dir.
    Ritorna (True, percorso_locale) o (False, errore).
    """
    if not _ok():
        return False, "Utente non autenticato."
    try:
        client   = _client()
        filename = Path(storage_path).name
        dest     = Path(dest_dir) / filename

        data = client.storage.from_("csvs").download(storage_path)
        with open(dest, "wb") as f:
            f.write(data)

        return True, str(dest)
    except Exception as e:
        print(f"[storage] download_csv error: {e}")
        return False, str(e)


def delete_csv(csv_id: str, storage_path: str) -> bool:
    """Elimina un CSV dal bucket e dai metadati."""
    if not _ok():
        return False
    try:
        client = _client()
        client.storage.from_("csvs").remove([storage_path])
        client.table("imported_csvs") \
            .delete() \
            .eq("id", csv_id) \
            .eq("user_id", _user_id()) \
            .execute()
        return True
    except Exception as e:
        print(f"[storage] delete_csv error: {e}")
        return False

def get_profile_csv(dest_dir: str) -> tuple[bool, str]:
    """
    Scarica il CSV più recente caricato dall'utente nel profilo.
    Ritorna (True, percorso_locale) oppure (False, messaggio_errore).
    """
    if not _ok():
        return False, "Utente non autenticato."
    try:
        client = _client()
        res = client.table("imported_csvs") \
            .select("filename, storage_path, imported_at") \
            .eq("user_id", _user_id()) \
            .order("imported_at", desc=True) \
            .limit(1) \
            .execute()

        if not res.data or len(res.data) == 0:
            return False, "Nessun CSV trovato nel profilo. Caricane uno dalla schermata Account."

        row          = res.data[0]
        storage_path = row["storage_path"]
        filename     = row["filename"]

        import os
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)

        data = client.storage.from_("csvs").download(storage_path)
        with open(dest, "wb") as f:
            f.write(data)

        return True, dest

    except Exception as e:
        print(f"[storage] get_profile_csv error: {e}")
        return False, f"Errore durante il download: {e}"

# ── Admin ─────────────────────────────────────────────────────────────────

def is_admin() -> bool:
    """True se l'utente corrente ha ruolo 'admin'."""
    if not _ok():
        return False
    try:
        res = _client().table("user_roles") \
            .select("role") \
            .eq("user_id", _user_id()) \
            .single() \
            .execute()
        return res.data.get("role") == "admin" if res.data else False
    except Exception:
        return False


def get_all_users_summary() -> list:
    """
    Solo admin: ritorna un riepilogo di tutti gli utenti
    con numero di ricerche e CSV importati.
    """
    if not is_admin():
        return []
    try:
        client = _client()
        searches = client.table("search_history") \
            .select("user_id, id") \
            .execute().data or []
        csvs = client.table("imported_csvs") \
            .select("user_id, id") \
            .execute().data or []

        # Aggrega per user_id
        summary: dict[str, dict] = {}
        for row in searches:
            uid = row["user_id"]
            summary.setdefault(uid, {"user_id": uid, "searches": 0, "csvs": 0})
            summary[uid]["searches"] += 1
        for row in csvs:
            uid = row["user_id"]
            summary.setdefault(uid, {"user_id": uid, "searches": 0, "csvs": 0})
            summary[uid]["csvs"] += 1

        return list(summary.values())
    except Exception as e:
        print(f"[storage] get_all_users_summary error: {e}")
        return []


# ── Utility interna ───────────────────────────────────────────────────────

def _make_serializable(obj):
    """Converte ricorsivamente oggetti non-JSON-serializable in tipi base."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(i) for i in obj]
    if isinstance(obj, float):
        import math
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if hasattr(obj, "item"):      # numpy scalars
        return obj.item()
    if hasattr(obj, "isoformat"): # datetime
        return obj.isoformat()
    return obj