"""
account_frame.py — Schermata profilo utente per Spryce
=======================================================
Mostra e permette di modificare le informazioni dell'utente loggato:
  - Foto profilo (upload locale)
  - Nome, cognome, data e luogo di nascita
  - Email (sola lettura, collegata all'account)
  - Cambio password
  - URL e-commerce personale
  - Settore merceologico (dropdown)
  - Upload CSV prodotti (salvato sul cloud via storage.upload_csv)
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps

import auth
import storage

# ── Stili condivisi con gui_app.py ────────────────────────────────────────
FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_SUBTLE = ("Segoe UI", 12)
FONT_NORMAL = ("Segoe UI", 13)
FONT_BOLD   = ("Segoe UI", 13, "bold")
FONT_SMALL  = ("Segoe UI", 11)

ACCENT_GREEN = "#1a8a7a"
ACCENT_RED   = "#e05555"
MUTED        = "#9a9a9a"

SETTORI = ["Alimentari", "Abbigliamento", "Calzature"]

AVATAR_SIZE = 96  # px, cerchio


def _make_circle_image(path: str | None, size: int) -> ctk.CTkImage:
    """
    Carica un'immagine, la ritaglia in cerchio e la restituisce come CTkImage.
    Se path è None restituisce un placeholder grigio con icona utente.
    """
    if path and os.path.exists(path):
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            img = None
    else:
        img = None

    if img is None:
        # Placeholder
        img = Image.new("RGBA", (size, size), (200, 200, 200, 255))
        draw = ImageDraw.Draw(img)
        # Cerchio più scuro al centro come silhouette
        draw.ellipse([size // 4, size // 5, size * 3 // 4, size * 3 // 5],
                     fill=(150, 150, 150, 255))
        draw.ellipse([size // 6, size // 2, size * 5 // 6, size],
                     fill=(150, 150, 150, 255))

    # Ritaglia quadrato centrale
    w, h = img.size
    m = min(w, h)
    img = img.crop(((w - m) // 2, (h - m) // 2, (w + m) // 2, (h + m) // 2))
    img = img.resize((size, size), Image.LANCZOS)

    # Maschera circolare
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, mask=mask)

    return ctk.CTkImage(light_image=result, dark_image=result, size=(size, size))


class AccountFrame(ctk.CTkFrame):
    """
    Schermata account utente. Va registrata in App.frames come "account".

    Uso in gui_app.py:
        self.frames["account"] = AccountFrame(container, self)
        self.frames["account"].grid(row=0, column=0, sticky="nsew")
    """

    def __init__(self, master, app):
        super().__init__(master, fg_color=("#f7fafa", "#1a1a1a"))
        self.app = app
        self._avatar_path: str | None = None

        self._build()

    # ── Costruzione UI ────────────────────────────────────────────────────

    def _build(self):
        # Scrollable per schermi piccoli
        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # ── Titolo pagina ─────────────────────────────────────────────────
        ctk.CTkLabel(scroll, text="Il mio account", font=FONT_TITLE).pack(
            anchor="w", padx=40, pady=(36, 2))
        ctk.CTkLabel(
            scroll,
            text="Gestisci le informazioni del tuo profilo e le preferenze.",
            font=FONT_SUBTLE, text_color=MUTED,
        ).pack(anchor="w", padx=40, pady=(0, 24))

        # ── Card principale ───────────────────────────────────────────────
        card = ctk.CTkFrame(scroll, fg_color=("white", "#2b2b2b"), corner_radius=14)
        card.pack(fill="x", padx=40, pady=(0, 16))

        # ── Sezione avatar ────────────────────────────────────────────────
        avatar_row = ctk.CTkFrame(card, fg_color="transparent")
        avatar_row.pack(fill="x", padx=28, pady=(28, 12))

        self.avatar_label = ctk.CTkLabel(avatar_row, text="", image=_make_circle_image(None, AVATAR_SIZE))
        self.avatar_label.pack(side="left")

        avatar_info = ctk.CTkFrame(avatar_row, fg_color="transparent")
        avatar_info.pack(side="left", padx=20)

        self.display_name_label = ctk.CTkLabel(
            avatar_info, text="", font=FONT_BOLD)
        self.display_name_label.pack(anchor="w")

        self.email_display_label = ctk.CTkLabel(
            avatar_info, text="", font=FONT_SMALL, text_color=MUTED)
        self.email_display_label.pack(anchor="w", pady=(2, 8))

        ctk.CTkButton(
            avatar_info,
            text="📷  Cambia foto",
            font=FONT_SMALL,
            height=32, width=140,
            fg_color="transparent",
            border_width=1,
            border_color=("#cccccc", "#555555"),
            text_color=("#222222", "#ffffff"),
            hover_color=("#f0f0f0", "#3a3a3a"),
            command=self._choose_avatar,
        ).pack(anchor="w")

        # ── Separatore ────────────────────────────────────────────────────
        ctk.CTkFrame(card, height=1, fg_color=("#e8e8e8", "#3a3a3a")).pack(
            fill="x", padx=28, pady=(8, 20))

        # ── Griglia campi anagrafica ──────────────────────────────────────
        fields_frame = ctk.CTkFrame(card, fg_color="transparent")
        fields_frame.pack(fill="x", padx=28, pady=(0, 8))
        fields_frame.columnconfigure(0, weight=1)
        fields_frame.columnconfigure(1, weight=1)

        # Nome
        self.nome_entry = self._field(fields_frame, "Nome", row=0, col=0)
        # Cognome
        self.cognome_entry = self._field(fields_frame, "Cognome", row=0, col=1)
        # Data di nascita
        self.dob_entry = self._field(
            fields_frame, "Data di nascita (gg/mm/aaaa)", row=1, col=0,
            placeholder="es. 15/03/1990")
        # Luogo di nascita
        self.luogo_entry = self._field(
            fields_frame, "Luogo di nascita", row=1, col=1)

        # Email (sola lettura)
        email_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
        email_frame.grid(row=2, column=0, columnspan=2, sticky="ew",
                         padx=4, pady=(0, 8))
        ctk.CTkLabel(email_frame, text="Email", font=FONT_SMALL,
                     text_color=MUTED).pack(anchor="w")
        self.email_entry = ctk.CTkEntry(
            email_frame, font=FONT_NORMAL, height=40,
            state="disabled",
            fg_color=("#f5f5f5", "#222222"),
            text_color=("#555555", "#888888"),
        )
        self.email_entry.pack(fill="x")

        # URL ecommerce
        url_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
        url_frame.grid(row=3, column=0, columnspan=2, sticky="ew",
                       padx=4, pady=(0, 8))
        ctk.CTkLabel(url_frame, text="URL del tuo e-commerce", font=FONT_SMALL,
                     text_color=MUTED).pack(anchor="w")
        self.url_entry = ctk.CTkEntry(
            url_frame, font=FONT_NORMAL, height=40,
            placeholder_text="https://mionegozio.myshopify.com")
        self.url_entry.pack(fill="x")

        # Settore merceologico
        settore_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
        settore_frame.grid(row=4, column=0, columnspan=2, sticky="ew",
                           padx=4, pady=(0, 8))
        ctk.CTkLabel(settore_frame, text="Settore merceologico", font=FONT_SMALL,
                     text_color=MUTED).pack(anchor="w")
        self.settore_var = ctk.StringVar(value=SETTORI[0])
        self.settore_menu = ctk.CTkOptionMenu(
            settore_frame,
            values=SETTORI,
            variable=self.settore_var,
            font=FONT_NORMAL,
            height=40,
            fg_color=("white", "#3a3a3a"),
            button_color=ACCENT_GREEN,
            button_hover_color="#0d6b5e",
            text_color=("#222222", "#ffffff"),
            dropdown_fg_color=("white", "#2b2b2b"),
            dropdown_text_color=("#222222", "#ffffff"),
            dropdown_hover_color=("#f0f0f0", "#3a3a3a"),
        )
        self.settore_menu.pack(fill="x")

        # ── Separatore ────────────────────────────────────────────────────
        ctk.CTkFrame(card, height=1, fg_color=("#e8e8e8", "#3a3a3a")).pack(
            fill="x", padx=28, pady=(12, 20))

        # ── Sezione cambio password ───────────────────────────────────────
        ctk.CTkLabel(card, text="Cambia password",
                     font=FONT_BOLD).pack(anchor="w", padx=28)
        ctk.CTkLabel(
            card,
            text="Lascia i campi vuoti se non vuoi cambiare la password.",
            font=FONT_SMALL, text_color=MUTED,
        ).pack(anchor="w", padx=28, pady=(2, 12))

        pwd_frame = ctk.CTkFrame(card, fg_color="transparent")
        pwd_frame.pack(fill="x", padx=28, pady=(0, 4))
        pwd_frame.columnconfigure(0, weight=1)
        pwd_frame.columnconfigure(1, weight=1)

        # Nuova password
        np_frame = ctk.CTkFrame(pwd_frame, fg_color="transparent")
        np_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
        ctk.CTkLabel(np_frame, text="Nuova password",
                     font=FONT_SMALL, text_color=MUTED).pack(anchor="w")
        self.new_pwd_entry = ctk.CTkEntry(
            np_frame, font=FONT_NORMAL, height=40, show="•",
            placeholder_text="Min. 8 caratteri")
        self.new_pwd_entry.pack(fill="x")

        # Conferma nuova password
        cp_frame = ctk.CTkFrame(pwd_frame, fg_color="transparent")
        cp_frame.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))
        ctk.CTkLabel(cp_frame, text="Conferma nuova password",
                     font=FONT_SMALL, text_color=MUTED).pack(anchor="w")
        self.confirm_pwd_entry = ctk.CTkEntry(
            cp_frame, font=FONT_NORMAL, height=40, show="•")
        self.confirm_pwd_entry.pack(fill="x")

        # ── Separatore ────────────────────────────────────────────────────
        ctk.CTkFrame(card, height=1, fg_color=("#e8e8e8", "#3a3a3a")).pack(
            fill="x", padx=28, pady=(12, 20))

        # ── Sezione CSV prodotti ──────────────────────────────────────────
        ctk.CTkLabel(card, text="CSV prodotti",
                     font=FONT_BOLD).pack(anchor="w", padx=28)
        ctk.CTkLabel(
            card,
            text="Carica il CSV esportato da Shopify per averlo sempre disponibile nel cloud.",
            font=FONT_SMALL, text_color=MUTED,
        ).pack(anchor="w", padx=28, pady=(2, 12))

        csv_row = ctk.CTkFrame(card, fg_color="transparent")
        csv_row.pack(fill="x", padx=28, pady=(0, 28))

        ctk.CTkButton(
            csv_row,
            text="📂  Scegli CSV...",
            font=FONT_BOLD,
            height=40, width=160,
            command=self._upload_csv,
        ).pack(side="left")

        self.csv_status_label = ctk.CTkLabel(
            csv_row, text="Nessun file caricato.",
            font=FONT_SMALL, text_color=MUTED)
        self.csv_status_label.pack(side="left", padx=16)

        # ── Footer card: feedback + salva ─────────────────────────────────
        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.pack(fill="x", padx=28, pady=(0, 24))

        self.feedback_label = ctk.CTkLabel(
            bottom, text="", font=FONT_SMALL, text_color=ACCENT_RED, wraplength=440)
        self.feedback_label.pack(side="left")

        ctk.CTkButton(
            bottom,
            text="💾  Salva profilo",
            font=FONT_BOLD,
            height=44, width=180,
            command=self._save,
        ).pack(side="right")

    # ── Helper costruzione campo ──────────────────────────────────────────

    def _field(self, parent, label: str, row: int, col: int,
               placeholder: str = "") -> ctk.CTkEntry:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=col, sticky="ew", padx=4, pady=(0, 8))
        ctk.CTkLabel(frame, text=label, font=FONT_SMALL,
                     text_color=MUTED).pack(anchor="w")
        entry = ctk.CTkEntry(frame, font=FONT_NORMAL, height=40,
                             placeholder_text=placeholder)
        entry.pack(fill="x")
        return entry

    # ── Refresh (chiama dopo login) ───────────────────────────────────────

    def refresh(self):
        """Popola i campi con i dati della sessione corrente."""
        session = auth.Session

        # Display name e email in cima
        name = session.full_name or session.email or "Utente"
        self.display_name_label.configure(text=name)
        self.email_display_label.configure(text=session.email or "")

        # Email nel campo (read-only)
        self.email_entry.configure(state="normal")
        self.email_entry.delete(0, "end")
        self.email_entry.insert(0, session.email or "")
        self.email_entry.configure(state="disabled")

        # Avatar dal profilo OAuth se disponibile, altrimenti placeholder
        avatar_url = session.avatar_url
        if avatar_url and not self._avatar_path:
            # Non scarichiamo l'immagine remota automaticamente;
            # mostriamo il placeholder finché l'utente non carica una foto locale.
            pass
        self._refresh_avatar(self._avatar_path)

        # Carica dati aggiuntivi dal cloud (user_profiles)
        threading.Thread(target=self._load_profile_data, daemon=True).start()

        # Pulisci password e feedback
        self.new_pwd_entry.delete(0, "end")
        self.confirm_pwd_entry.delete(0, "end")
        self.feedback_label.configure(text="")

    def _load_profile_data(self):
        try:
            client = auth._get_client()
            uid = auth.Session.user_id
            if not uid:
                return
            res = client.table("user_profiles") \
                .select("nome,cognome,data_nascita,luogo_nascita,url_ecommerce,settore,avatar_path") \
                .eq("user_id", uid) \
                .limit(1) \
                .execute()
            if res.data and len(res.data) > 0:
                self.after(0, lambda: self._populate_fields(res.data[0]))
        except Exception as e:
            print(f"[account] load_profile_data error: {e}")

    def _populate_fields(self, data: dict):
        def _set(entry: ctk.CTkEntry, value: str):
            entry.delete(0, "end")
            if value:
                entry.insert(0, value)

        _set(self.nome_entry,    data.get("nome", ""))
        _set(self.cognome_entry, data.get("cognome", ""))
        _set(self.dob_entry,     data.get("data_nascita", ""))
        _set(self.luogo_entry,   data.get("luogo_nascita", ""))
        _set(self.url_entry,     data.get("url_ecommerce", ""))

        settore = data.get("settore")
        if settore and settore in SETTORI:
            self.settore_var.set(settore)

        avatar = data.get("avatar_path")
        if avatar:
            self._avatar_path = avatar
            self._refresh_avatar(avatar)

    # ── Avatar ────────────────────────────────────────────────────────────

    def _choose_avatar(self):
        path = filedialog.askopenfilename(
            title="Scegli la tua foto profilo",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.webp *.gif"),
                       ("Tutti i file", "*.*")],
        )
        if path:
            self._avatar_path = path
            self._refresh_avatar(path)

    def _refresh_avatar(self, path: str | None):
        img = _make_circle_image(path, AVATAR_SIZE)
        self.avatar_label.configure(image=img)
        self.avatar_label._image = img  # mantieni riferimento

    # ── CSV upload ────────────────────────────────────────────────────────

    def _upload_csv(self):
        path = filedialog.askopenfilename(
            title="Seleziona il CSV prodotti",
            filetypes=[("File CSV", "*.csv"), ("Tutti i file", "*.*")],
        )
        if not path:
            return

        self.csv_status_label.configure(text="⏳  Caricamento in corso...", text_color=MUTED)

        def worker():
            ok, result = storage.upload_csv(path)
            if ok:
                filename = os.path.basename(path)
                self.after(0, lambda: self.csv_status_label.configure(
                    text=f"✔  {filename} caricato correttamente.",
                    text_color=ACCENT_GREEN,
                ))
            else:
                self.after(0, lambda: self.csv_status_label.configure(
                    text=f"Errore: {result}",
                    text_color=ACCENT_RED,
                ))

        threading.Thread(target=worker, daemon=True).start()

    # ── Salvataggio profilo ───────────────────────────────────────────────

    def _save(self):
        # Validazione password
        new_pwd     = self.new_pwd_entry.get()
        confirm_pwd = self.confirm_pwd_entry.get()

        if new_pwd or confirm_pwd:
            if new_pwd != confirm_pwd:
                self._set_feedback("Le password non coincidono.", error=True)
                return
            if len(new_pwd) < 8:
                self._set_feedback(
                    "La nuova password deve essere di almeno 8 caratteri.", error=True)
                return

        threading.Thread(target=self._save_worker,
                         args=(new_pwd,), daemon=True).start()

    def _save_worker(self, new_pwd: str):
        errors = []

        # ── 1. Aggiorna password (se richiesto) ──────────────────────────
        if new_pwd:
            try:
                client = auth._get_client()
                client.auth.update_user({"password": new_pwd})
            except Exception as e:
                errors.append(f"Password: {e}")

        # ── 2. Salva profilo su user_profiles ────────────────────────────
        try:
            client = auth._get_client()
            uid = auth.Session.user_id
            if uid:
                client.table("user_profiles").upsert({
                    "user_id":       uid,
                    "nome":          self.nome_entry.get().strip(),
                    "cognome":       self.cognome_entry.get().strip(),
                    "data_nascita":  self.dob_entry.get().strip(),
                    "luogo_nascita": self.luogo_entry.get().strip(),
                    "url_ecommerce": self.url_entry.get().strip(),
                    "settore":       self.settore_var.get(),
                    "avatar_path":   self._avatar_path or "",
                }, on_conflict="user_id").execute()
        except Exception as e:
            errors.append(f"Profilo: {e}")

        # ── 3. Feedback ───────────────────────────────────────────────────
        if errors:
            msg = "Errori durante il salvataggio:\n" + "\n".join(errors)
            self.after(0, lambda: self._set_feedback(msg, error=True))
        else:
            # Aggiorna il display name in cima
            nome    = self.nome_entry.get().strip()
            cognome = self.cognome_entry.get().strip()
            display = f"{nome} {cognome}".strip() or auth.Session.email or "Utente"
            self.after(0, lambda: self.display_name_label.configure(text=display))
            self.after(0, lambda: self._set_feedback("✔  Profilo salvato.", error=False))
            self.after(3000, lambda: self._set_feedback(""))

    # ── Helper UI ─────────────────────────────────────────────────────────

    def _set_feedback(self, text: str, error: bool = True):
        color = ACCENT_RED if error else ACCENT_GREEN
        self.feedback_label.configure(text=text, text_color=color)