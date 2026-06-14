"""
login_frame.py — Schermata di login/registrazione per Spryce
==============================================================
Frame iniziale dell'app che appare prima del resto dell'interfaccia.
Permette login con email/password e con provider OAuth.
Una volta autenticato, chiama on_login_success() passando la Session.
"""

from __future__ import annotations

import threading
import customtkinter as ctk
from tkinter import messagebox

import auth

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_NORMAL = ("Segoe UI", 13)
FONT_BOLD   = ("Segoe UI", 13, "bold")
FONT_SMALL  = ("Segoe UI", 11)
FONT_SUBTLE = ("Segoe UI", 12)

ACCENT_GREEN  = "#1a8a7a"
ACCENT_RED    = "#e05555"
MUTED         = "#9a9a9a"


class LoginFrame(ctk.CTkFrame):
    """
    Frame di login/registrazione. Va inserito nella finestra principale
    prima di mostrare il resto dell'app.

    Uso in App.__init__:
        self.login_frame = LoginFrame(self, on_login_success=self._on_logged_in)
        self.login_frame.pack(fill="both", expand=True)
    """

    def __init__(self, master, on_login_success):
        super().__init__(master, fg_color=("white", "#1a1a1a"))
        self.on_login_success = on_login_success
        self._mode = "login"   # "login" | "register" | "reset"

        self._build()

    # ── Costruzione UI ────────────────────────────────────────────────────

    def _build(self):
        # Colonna centrale con larghezza fissa
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        card = ctk.CTkFrame(self, fg_color=("white", "#2b2b2b"),
                             corner_radius=16, width=420)
        card.grid(row=0, column=1, pady=60, padx=20, sticky="n")
        card.grid_propagate(False)
        card.configure(width=420)

        # Titolo
        self.title_label = ctk.CTkLabel(
            card, text="Accedi a Spryce", font=FONT_TITLE)
        self.title_label.pack(padx=40, pady=(40, 4))

        self.subtitle_label = ctk.CTkLabel(
            card, text="Inserisci le tue credenziali per continuare.",
            font=FONT_SUBTLE, text_color=MUTED)
        self.subtitle_label.pack(padx=40, pady=(0, 28))

        # ── Campi email / password ────────────────────────────────────────
        self.email_entry = ctk.CTkEntry(
            card, placeholder_text="Email", font=FONT_NORMAL,
            height=42, width=340)
        self.email_entry.pack(padx=40, pady=(0, 12))

        self.password_entry = ctk.CTkEntry(
            card, placeholder_text="Password", font=FONT_NORMAL,
            height=42, width=340, show="•")
        self.password_entry.pack(padx=40, pady=(0, 6))
        self.password_entry.bind("<Return>", lambda e: self._on_submit())

        # Conferma password (solo registrazione)
        self.confirm_entry = ctk.CTkEntry(
            card, placeholder_text="Conferma password", font=FONT_NORMAL,
            height=42, width=340, show="•")
        # non è visibile in login mode

        # ── Pulsante principale ───────────────────────────────────────────
        self.submit_btn = ctk.CTkButton(
            card, text="Accedi", font=FONT_BOLD, height=44, width=340,
            command=self._on_submit)
        self.submit_btn.pack(padx=40, pady=(16, 0))

        # ── Feedback ─────────────────────────────────────────────────────
        self.feedback_label = ctk.CTkLabel(
            card, text="", font=FONT_SMALL, text_color=ACCENT_RED,
            wraplength=340)
        self.feedback_label.pack(padx=40, pady=(8, 0))

        # ── Separatore ───────────────────────────────────────────────────
        sep_row = ctk.CTkFrame(card, fg_color="transparent")
        sep_row.pack(fill="x", padx=40, pady=(20, 0))
        ctk.CTkFrame(sep_row, height=1, fg_color=("#e0e0e0", "#3a3a3a")).pack(
            side="left", fill="x", expand=True)
        ctk.CTkLabel(sep_row, text="  oppure  ", font=FONT_SMALL,
                     text_color=MUTED).pack(side="left")
        ctk.CTkFrame(sep_row, height=1, fg_color=("#e0e0e0", "#3a3a3a")).pack(
            side="left", fill="x", expand=True)

        # ── Pulsanti OAuth ────────────────────────────────────────────────
        oauth_frame = ctk.CTkFrame(card, fg_color="transparent")
        oauth_frame.pack(padx=40, pady=(16, 0))

        ctk.CTkButton(
            oauth_frame, text="G  Google", font=FONT_BOLD,
            height=40, width=100,
            fg_color=("white", "#2b2b2b"),
            border_width=1,
            border_color=("#cccccc", "#555555"),
            text_color=("#222222", "#ffffff"),
            hover_color=("#f0f0f0", "#3a3a3a"),
            command=lambda: self._on_oauth("google"),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            oauth_frame, text="⊞  Microsoft", font=FONT_BOLD,
            height=40, width=120,
            fg_color=("white", "#2b2b2b"),
            border_width=1,
            border_color=("#cccccc", "#555555"),
            text_color=("#222222", "#ffffff"),
            hover_color=("#f0f0f0", "#3a3a3a"),
            command=lambda: self._on_oauth("azure"),
        ).pack(side="left")



  # ── Link inferiori ────────────────────────────────────────────────
        links_frame = ctk.CTkFrame(card, fg_color="transparent")
        links_frame.pack(pady=(24, 32))

        self.toggle_btn = ctk.CTkLabel(
            links_frame, text="Non hai un account? Registrati",
            font=FONT_SMALL, text_color=ACCENT_GREEN, cursor="hand2",
        )
        self.toggle_btn.pack()
        self.toggle_btn.bind("<Button-1>", lambda e: self._toggle_mode())

        reset_lbl = ctk.CTkLabel(
            links_frame, text="Password dimenticata?",
            font=FONT_SMALL, text_color=MUTED, cursor="hand2",
        )
        reset_lbl.pack(pady=(4, 0))
        reset_lbl.bind("<Button-1>", lambda e: self._show_reset())

    # ── Logica modal ──────────────────────────────────────────────────────

    def _toggle_mode(self):
        if self._mode in ("login", "reset"):
            self._set_mode("register")
        else:
            self._set_mode("login")

    def _set_mode(self, mode: str):
        self._mode = mode
        self.feedback_label.configure(text="")

        if mode == "login":
            self.title_label.configure(text="Accedi a Spryce")
            self.subtitle_label.configure(
                text="Inserisci le tue credenziali per continuare.")
            self.submit_btn.configure(text="Accedi")
            self.toggle_btn.configure(text="Non hai un account? Registrati")
            self.confirm_entry.pack_forget()
            self.password_entry.pack(padx=40, pady=(0, 6),
                                      before=self.submit_btn)

        elif mode == "register":
            self.title_label.configure(text="Crea un account")
            self.subtitle_label.configure(
                text="Registrati per salvare i tuoi dati nel cloud.")
            self.submit_btn.configure(text="Registrati")
            self.toggle_btn.configure(text="Hai già un account? Accedi")
            self.confirm_entry.pack(padx=40, pady=(0, 6),
                                     before=self.submit_btn)

        elif mode == "reset":
            self.title_label.configure(text="Reset password")
            self.subtitle_label.configure(
                text="Inserisci la tua email per ricevere il link di reset.")
            self.submit_btn.configure(text="Invia link di reset")
            self.toggle_btn.configure(text="Torna al login")
            self.password_entry.pack_forget()
            self.confirm_entry.pack_forget()

    def _show_reset(self):
        self._set_mode("reset")

    # ── Submit ────────────────────────────────────────────────────────────

    def _on_submit(self):
        email    = self.email_entry.get().strip()
        password = self.password_entry.get()

        if not email:
            self._set_feedback("Inserisci la tua email.", error=True)
            return

        if self._mode == "reset":
            self._do_reset(email)
            return

        if not password:
            self._set_feedback("Inserisci la password.", error=True)
            return

        if self._mode == "register":
            confirm = self.confirm_entry.get()
            if password != confirm:
                self._set_feedback("Le password non coincidono.", error=True)
                return
            if len(password) < 8:
                self._set_feedback(
                    "La password deve essere di almeno 8 caratteri.", error=True)
                return
            self._do_register(email, password)
        else:
            self._do_login(email, password)

    def _do_login(self, email: str, password: str):
        self._set_loading(True)

        def worker():
            ok, err = auth.login_email(email, password)
            self.after(0, lambda: self._handle_auth_result(ok, err))

        threading.Thread(target=worker, daemon=True).start()

    def _do_register(self, email: str, password: str):
        self._set_loading(True)

        def worker():
            ok, err = auth.register(email, password)
            if ok:
                self.after(0, lambda: self._set_feedback(
                    "✔  Registrazione completata! Controlla la tua email "
                    "per confermare l'account, poi accedi.",
                    error=False,
                ))
                self.after(0, lambda: self._set_mode("login"))
            else:
                self.after(0, lambda: self._handle_auth_result(False, err))

        threading.Thread(target=worker, daemon=True).start()

    def _do_reset(self, email: str):
        self._set_loading(True)

        def worker():
            ok, err = auth.reset_password(email)
            if ok:
                self.after(0, lambda: self._set_feedback(
                    "✔  Email inviata! Controlla la tua casella di posta.",
                    error=False,
                ))
            else:
                self.after(0, lambda: self._set_feedback(err, error=True))
            self.after(0, lambda: self._set_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _on_oauth(self, provider: str):
        self._set_loading(True)
        self._set_feedback(
            f"Apertura browser per il login con {provider.title()}...\n"
            f"Dopo aver completato l'accesso, torna qui.",
            error=False,
        )

        def worker():
            ok, err = auth.login_oauth(provider)
            if ok:
                self.after(0, lambda: self.on_login_success(auth.Session))
            else:
                self.after(0, lambda: self._set_feedback(err, error=True))
            self.after(0, lambda: self._set_loading(False))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_auth_result(self, ok: bool, err: str):
        self._set_loading(False)
        if ok:
            self.on_login_success(auth.Session)
        else:
            self._set_feedback(err, error=True)

    # ── Helper UI ─────────────────────────────────────────────────────────

    def _set_loading(self, loading: bool):
        state = "disabled" if loading else "normal"
        self.submit_btn.configure(state=state)
        self.email_entry.configure(state=state)
        self.password_entry.configure(state=state)
        if loading:
            self.submit_btn.configure(text="...")
        else:
            texts = {"login": "Accedi", "register": "Registrati",
                     "reset": "Invia link di reset"}
            self.submit_btn.configure(text=texts.get(self._mode, "Accedi"))

    def _set_feedback(self, text: str, error: bool = True):
        color = ACCENT_RED if error else ACCENT_GREEN
        self.feedback_label.configure(text=text, text_color=color)