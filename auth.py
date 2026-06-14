"""
auth.py — Autenticazione Supabase per Spryce
==============================================
Gestisce registrazione, login (email/password),
login OAuth (Google, Microsoft) e sessione utente.

Le credenziali Supabase vengono lette da:
  1. Variabili d'ambiente SUPABASE_URL e SUPABASE_ANON_KEY
  2. File .env nella cartella del progetto (utile in sviluppo)

In produzione (exe PyInstaller) le credenziali devono essere
impostate come variabili d'ambiente oppure hardcodate qui sotto
nella sezione CONFIGURAZIONE — mai distribuire il file .env.
"""

from __future__ import annotations

import os
import threading
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

# ── Carica .env se presente (sviluppo locale) ─────────────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ── CONFIGURAZIONE ─────────────────────────────────────────────────────────
SUPABASE_URL      = os.environ.get("SUPABASE_URL",      "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

OAUTH_CALLBACK_PORT = 7123
OAUTH_CALLBACK_URL  = f"http://localhost:{OAUTH_CALLBACK_PORT}/auth/callback"

# ── Client Supabase ────────────────────────────────────────────────────────
_client = None

def _get_client():
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise RuntimeError(
                "Credenziali Supabase mancanti.\n"
                "Imposta SUPABASE_URL e SUPABASE_ANON_KEY nel file .env "
                "oppure direttamente in auth.py."
            )
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _client


# ── Stato sessione corrente ────────────────────────────────────────────────

class Session:
    """Contiene i dati dell'utente loggato. None se non autenticato."""
    user_id:    Optional[str] = None
    email:      Optional[str] = None
    full_name:  Optional[str] = None
    avatar_url: Optional[str] = None
    token:      Optional[str] = None

    @classmethod
    def from_supabase(cls, response) -> "Session":
        user = response.user
        cls.user_id   = user.id
        cls.email     = user.email
        meta          = user.user_metadata or {}
        cls.full_name = meta.get("full_name") or meta.get("name") or cls.email
        cls.avatar_url = meta.get("avatar_url")
        cls.token     = response.session.access_token if response.session else None
        return cls

    @classmethod
    def clear(cls):
        cls.user_id = cls.email = cls.full_name = cls.avatar_url = cls.token = None

    @classmethod
    def is_logged_in(cls) -> bool:
        return cls.user_id is not None


# ── Funzioni di autenticazione ─────────────────────────────────────────────

def register(email: str, password: str) -> tuple[bool, str]:
    """Registra un nuovo utente con email e password."""
    try:
        client = _get_client()
        res = client.auth.sign_up({"email": email, "password": password})
        if res.user:
            return True, ""
        return False, "Registrazione fallita. Riprova."
    except Exception as e:
        return False, _friendly_error(str(e))


def login_email(email: str, password: str) -> tuple[bool, str]:
    """Login con email e password."""
    try:
        client = _get_client()
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            Session.from_supabase(res)
            return True, ""
        return False, "Credenziali non valide."
    except Exception as e:
        return False, _friendly_error(str(e))


def login_oauth(provider: str) -> tuple[bool, str]:
    """
    Avvia il flusso OAuth per Google o Azure (Microsoft).
    Apre il browser, aspetta il callback su localhost e scambia il code.
    """
    try:
        client = _get_client()
        result: dict = {}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)

                # Ignora favicon e altre richieste spurie
                if parsed.path != "/auth/callback":
                    self.send_response(204)
                    self.end_headers()
                    return

                params = urllib.parse.parse_qs(parsed.query)

                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style='font-family:sans-serif;text-align:center;padding-top:80px'>
                    <h2>&#10003; Login completato!</h2>
                    <p>Puoi chiudere questa scheda e tornare a Spryce.</p>
                    </body></html>
                """)

                if "code" in params:
                    result["code"] = params["code"][0]
                elif "error" in params:
                    result["error"] = params.get("error_description", ["Errore OAuth"])[0]

                threading.Thread(target=server.shutdown, daemon=True).start()

            def log_message(self, *args):
                pass

        # Avvia il server in un thread separato
        server = HTTPServer(("localhost", OAUTH_CALLBACK_PORT), CallbackHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print(f"[DEBUG] Server avviato su localhost:{OAUTH_CALLBACK_PORT}")

        # Genera URL OAuth
        res = client.auth.sign_in_with_oauth({
            "provider": provider,
            "options": {
                "redirect_to": OAUTH_CALLBACK_URL,
                "skip_browser_open": True,
            }
        })

        if not res.url:
            server.shutdown()
            return False, f"Impossibile avviare il login con {provider.title()}."

        print(f"[DEBUG] Apertura browser: {res.url}")
        webbrowser.open(res.url)

        # Aspetta il callback (max 3 minuti)
        server_thread.join(timeout=180)

        if "error" in result:
            return False, result["error"]
        if "code" not in result:
            return False, "Login annullato o scaduto."

        print(f"[DEBUG] Code ricevuto, scambio con sessione...")

        # Scambia il code con la sessione
        session_res = client.auth.exchange_code_for_session({"auth_code": result["code"]})

        if session_res.user:
            Session.from_supabase(session_res)
            return True, ""

        return False, "Impossibile completare il login OAuth."

    except Exception as e:
        print(f"[DEBUG] Eccezione: {e}")
        return False, _friendly_error(str(e))


def logout() -> None:
    """Disconnette l'utente corrente e pulisce la sessione."""
    try:
        _get_client().auth.sign_out()
    except Exception:
        pass
    finally:
        Session.clear()


def reset_password(email: str) -> tuple[bool, str]:
    """Invia l'email di reset password."""
    try:
        _get_client().auth.reset_password_email(email)
        return True, ""
    except Exception as e:
        return False, _friendly_error(str(e))


# ── Helper ────────────────────────────────────────────────────────────────

def _friendly_error(raw: str) -> str:
    """Converte i messaggi di errore Supabase in testo leggibile."""
    raw_lower = raw.lower()
    if "invalid login" in raw_lower or "invalid credentials" in raw_lower:
        return "Email o password non corretti."
    if "email not confirmed" in raw_lower:
        return "Controlla la tua email e clicca il link di conferma prima di accedere."
    if "user already registered" in raw_lower:
        return "Esiste già un account con questa email. Prova ad accedere."
    if "password" in raw_lower and "weak" in raw_lower:
        return "Password troppo debole. Usa almeno 8 caratteri."
    if "network" in raw_lower or "connection" in raw_lower:
        return "Errore di connessione. Controlla la tua connessione internet."
    if "credenziali supabase mancanti" in raw_lower:
        return raw
    return f"Errore: {raw}"