"""
gui_app.py — Competitor Price Checker (interfaccia grafica)
==============================================================
Applicazione desktop per confrontare i prezzi del catalogo Shopify
con quelli dei siti competitor. Pensata per essere usata anche da
colleghi senza esperienza tecnica.

Avvio:
    python gui_app.py
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import webbrowser
import customtkinter as ctk
import config
import core
from PIL import Image
from tkinter import filedialog, messagebox
from PIL import ImageTk
import auth
import login_frame  # ← aggiungi questa riga
import core

# ── Tema applicato all'avvio (verrà sovrascritto da App.__init__) ──────────
ctk.set_default_color_theme("blue")
ctk.ThemeManager.theme["CTkButton"]["fg_color"] = ["#1a8a7a", "#1a8a7a"]
ctk.ThemeManager.theme["CTkButton"]["hover_color"] = ["#00b4d8", "#00b4d8"]

FONT_TITLE   = ("Segoe UI", 20, "bold")
FONT_SUBTLE  = ("Segoe UI", 12)
FONT_NORMAL  = ("Segoe UI", 13)
FONT_BOLD    = ("Segoe UI", 13, "bold")
FONT_SMALL   = ("Segoe UI", 11)

ACCENT_GREEN  = "#1a8a7a"
ACCENT_RED    = "#e05555"
ACCENT_YELLOW = "#00b4d8"
MUTED         = "#9a9a9a"


def open_path(path: str):
    """Apre un file o una cartella con l'applicazione predefinita del sistema."""
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("Errore", f"Impossibile aprire:\n{path}\n\n{e}")


# ──────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────────────────────

def resource_path(relative_path: str) -> str:
    """Returns the correct path both in dev and when bundled by PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


class Sidebar(ctk.CTkFrame):
    STEPS = [
        ("catalogo",     "1.  Catalogo"),
        ("selezione",    "2.  Selezione prodotti"),
        ("analisi",      "3.  Analisi"),
        ("risultati",    "4.  Risultati"),
        ("impostazioni", "⚙  Impostazioni"),
    ]

    def __init__(self, master, on_select):
        super().__init__(master, width=210, corner_radius=0, fg_color=("#f0fafa", "#1f1f1f"))
        self.on_select = on_select
        self.buttons: dict[str, ctk.CTkButton] = {}

        logo_img = ctk.CTkImage(
            light_image=Image.open(resource_path("logo.png")),
            size=(160, 155)
        )
        self.logo_label = ctk.CTkLabel(self, image=logo_img, text="")
        self.logo_label.pack(anchor="w", padx=20, pady=(28, 24))
        self.logo_label._image = logo_img  # mantieni riferimento

        for key, label in self.STEPS:
            btn = ctk.CTkButton(
                self, text=label, anchor="w", height=40,
                font=FONT_NORMAL, fg_color="transparent",
                text_color="#1a8a7a", hover_color="#d0f0ec",
                corner_radius=8,
                command=lambda k=key: self.on_select(k),
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.buttons[key] = btn

        self.set_active("catalogo")

    def set_active(self, key: str):
        for k, btn in self.buttons.items():
            if k == key:
                btn.configure(fg_color="#1a8a7a", text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color="#1a8a7a")

    def set_enabled(self, key: str, enabled: bool):
        self.buttons[key].configure(state="normal" if enabled else "disabled")

    def update_logo(self, theme: str):
        """Cambia il logo in base al tema (light/dark)."""
        logo_file = "logo_dark.png" if theme == "dark" else "logo.png"
        try:
            logo_img = ctk.CTkImage(
                light_image=Image.open(resource_path(logo_file)),
                size=(160, 155)
            )
            self.logo_label.configure(image=logo_img)
            self.logo_label._image = logo_img
        except FileNotFoundError:
            pass  # se logo_dark.png non esiste ancora, non fa nulla


# ──────────────────────────────────────────────────────────────────────────
# STEP 1 — CATALOGO
# ──────────────────────────────────────────────────────────────────────────

class CatalogoFrame(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=("#f7fafa", "#1a1a1a"))
        self.app = app

        ctk.CTkLabel(self, text="1. Carica il catalogo", font=FONT_TITLE).pack(
            anchor="w", padx=40, pady=(36, 4))
        ctk.CTkLabel(
            self,
            text="Seleziona il file CSV esportato da Shopify (Prodotti → Esporta).",
            font=FONT_SUBTLE, text_color=MUTED,
        ).pack(anchor="w", padx=40, pady=(0, 24))

        box = ctk.CTkFrame(self, fg_color=("white", "#2b2b2b"), corner_radius=12)
        box.pack(fill="x", padx=40, pady=10)

        ctk.CTkButton(
            box, text="📂  Scegli file CSV...", font=FONT_BOLD, height=44,
            command=self.choose_file,
        ).pack(padx=24, pady=24, anchor="w")

        self.status_label = ctk.CTkLabel(
            box, text="Nessun file selezionato.", font=FONT_NORMAL, text_color=MUTED
        )
        self.status_label.pack(padx=24, pady=(0, 24), anchor="w")

        self.next_btn = ctk.CTkButton(
            self, text="Avanti  →", font=FONT_BOLD, height=44, width=160,
            state="disabled", command=lambda: app.show("selezione"),
        )
        self.next_btn.pack(anchor="e", padx=40, pady=30)

    def choose_file(self):
        initial = self.app.cfg.get("last_csv_dir") or os.path.expanduser("~")
        path = filedialog.askopenfilename(
            title="Seleziona il file CSV del catalogo",
            initialdir=initial,
            filetypes=[("File CSV", "*.csv"), ("Tutti i file", "*.*")],
        )
        if not path:
            return

        try:
            df = core.load_products(path)
        except Exception as e:
            messagebox.showerror(
                "Errore nel file",
                f"Non sono riuscito a leggere il file CSV.\n\n"
                f"Assicurati che sia un export prodotti di Shopify valido.\n\nDettagli: {e}",
            )
            return

        if df.empty:
            messagebox.showwarning(
                "Catalogo vuoto",
                "Il file è stato letto correttamente ma non contiene prodotti attivi con prezzo.",
            )
            return

        self.app.df = df
        self.app.csv_path = path
        self.app.cfg = config.update_config(last_csv_dir=os.path.dirname(path))

        self.status_label.configure(
            text=f"✔  {os.path.basename(path)}   —   {len(df)} prodotti attivi caricati",
            text_color=ACCENT_GREEN,
        )
        self.next_btn.configure(state="normal")
        self.app.sidebar.set_enabled("selezione", True)

        self.app.selected_df = None
        self.app.on_catalog_loaded()


# ──────────────────────────────────────────────────────────────────────────
# STEP 2 — SELEZIONE PRODOTTI
# ──────────────────────────────────────────────────────────────────────────

class SelezioneFrame(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=("#f7fafa", "#1a1a1a"))
        self.app = app
        self.checkbox_vars: dict[int, ctk.BooleanVar] = {}
        self.current_pool = None

        ctk.CTkLabel(self, text="2. Seleziona i prodotti da analizzare",
                      font=FONT_TITLE).pack(anchor="w", padx=40, pady=(36, 4))
        self.subtitle = ctk.CTkLabel(self, text="", font=FONT_SUBTLE, text_color=MUTED)
        self.subtitle.pack(anchor="w", padx=40, pady=(0, 16))

        self.mode_var = ctk.StringVar(value="tutti")
        mode_bar = ctk.CTkSegmentedButton(
            self,
            values=["Tutti i prodotti", "Per parola chiave", "Per brand"],
            command=self.on_mode_change,
            fg_color="#1a8a7a",
            selected_color="#00b4d8",
            selected_hover_color="#0099bb",
            unselected_color="#1a8a7a",
            unselected_hover_color="#00b4d8",
            text_color="#ffffff",
            text_color_disabled="#9a9a9a",
        )
        mode_bar.set("Tutti i prodotti")
        mode_bar.pack(anchor="w", padx=40, pady=(0, 16))
        self.mode_bar = mode_bar

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=40, pady=0)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=40, pady=20)

        self.count_label = ctk.CTkLabel(bottom, text="", font=FONT_BOLD)
        self.count_label.pack(side="left")

        self.next_btn = ctk.CTkButton(
            bottom, text="Avanti  →", font=FONT_BOLD, height=44, width=160,
            state="disabled", command=self.confirm_selection,
        )
        self.next_btn.pack(side="right")

    def reset(self):
        df = self.app.df
        self.subtitle.configure(
            text=f"Catalogo caricato: {len(df)} prodotti attivi."
        )
        self.mode_bar.set("Tutti i prodotti")
        self.on_mode_change("Tutti i prodotti")

    def on_mode_change(self, value):
        for w in self.content.winfo_children():
            w.destroy()
        self.checkbox_vars = {}

        if value == "Tutti i prodotti":
            self._build_tutti()
        elif value == "Per parola chiave":
            self._build_keyword()
        else:
            self._build_brand()

    def _build_tutti(self):
        df = self.app.df
        info = ctk.CTkFrame(self.content, fg_color=("white", "#2b2b2b"), corner_radius=12)
        info.pack(fill="x", pady=10)
        ctk.CTkLabel(
            info,
            text=f"Verranno analizzati tutti i {len(df)} prodotti attivi del catalogo.",
            font=FONT_NORMAL,
        ).pack(padx=24, pady=20, anchor="w")
        ctk.CTkLabel(
            info,
            text="⚠  Con cataloghi molto grandi l'analisi può richiedere parecchio tempo.",
            font=FONT_SMALL, text_color=ACCENT_YELLOW,
        ).pack(padx=24, pady=(0, 20), anchor="w")

        self.app.selected_df = df
        self._update_count()

    def _build_keyword(self):
        search_row = ctk.CTkFrame(self.content, fg_color="transparent")
        search_row.pack(fill="x", pady=(0, 10))

        self.kw_entry = ctk.CTkEntry(
            search_row, placeholder_text="Es. trabaldo, nocpix, scarpon...",
            font=FONT_NORMAL, height=40,
        )
        self.kw_entry.pack(side="left", fill="x", expand=True)
        self.kw_entry.bind("<Return>", lambda e: self._do_keyword_search())

        ctk.CTkButton(
            search_row, text="Cerca", width=100, height=40, font=FONT_BOLD,
            command=self._do_keyword_search,
        ).pack(side="left", padx=(10, 0))

        sel_row = ctk.CTkFrame(self.content, fg_color="transparent")
        sel_row.pack(fill="x")
        self.sel_all_btn = ctk.CTkButton(
            sel_row, text="Seleziona tutti", width=140, height=30, font=FONT_SMALL,
            fg_color="#00b4d8", hover_color="#1a8a7a", border_width=1, text_color="#ffffff",
            command=lambda: self._set_all_checks(True),
        )
        self.desel_all_btn = ctk.CTkButton(
            sel_row, text="Deseleziona tutti", width=140, height=30, font=FONT_SMALL,
            fg_color="#00b4d8", hover_color="#1a8a7a", border_width=1, text_color="#ffffff",
            command=lambda: self._set_all_checks(False),
        )

        self.results_frame = ctk.CTkScrollableFrame(
            self.content, fg_color=("white", "#2b2b2b"), corner_radius=12, height=320,
        )
        self.results_frame.pack(fill="both", expand=True, pady=10)

        self.placeholder = ctk.CTkLabel(
            self.results_frame, text="Digita una parola chiave e premi Cerca o Invio.",
            font=FONT_NORMAL, text_color=MUTED,
        )
        self.placeholder.pack(pady=30)

        self.app.selected_df = None
        self._update_count()

    def _do_keyword_search(self):
        keyword = self.kw_entry.get().strip()
        for w in self.results_frame.winfo_children():
            w.destroy()
        self.checkbox_vars = {}

        if not keyword:
            ctk.CTkLabel(self.results_frame, text="Inserisci una parola chiave.",
                          font=FONT_NORMAL, text_color=MUTED).pack(pady=30)
            self.app.selected_df = None
            self._update_count()
            self.sel_all_btn.pack_forget()
            self.desel_all_btn.pack_forget()
            return

        found = core.filter_by_keyword(self.app.df, keyword)
        self.current_pool = found

        if found.empty:
            ctk.CTkLabel(
                self.results_frame, text=f"Nessun prodotto trovato per '{keyword}'.",
                font=FONT_NORMAL, text_color=MUTED,
            ).pack(pady=30)
            self.app.selected_df = None
            self._update_count()
            self.sel_all_btn.pack_forget()
            self.desel_all_btn.pack_forget()
            return

        self.sel_all_btn.pack(side="left", pady=(2, 6))
        self.desel_all_btn.pack(side="left", padx=(8, 0), pady=(2, 6))

        MAX_SHOW = 300
        shown = found.head(MAX_SHOW)
        if len(found) > MAX_SHOW:
            ctk.CTkLabel(
                self.results_frame,
                text=f"Trovati {len(found)} risultati — mostrati i primi {MAX_SHOW}. "
                     f"Affina la ricerca per restringere.",
                font=FONT_SMALL, text_color=ACCENT_YELLOW,
            ).pack(anchor="w", padx=10, pady=(4, 8))

        for idx, row in shown.iterrows():
            var = ctk.BooleanVar(value=True)
            self.checkbox_vars[idx] = var
            price_str = f"€ {row['Variant Price']:.2f}"
            vendor    = f"  ·  {row['Vendor']}" if pd_notna(row.get("Vendor")) else ""
            text = f"{row['Title']}   —   {price_str}{vendor}"
            cb = ctk.CTkCheckBox(
                self.results_frame, text=text, variable=var, font=FONT_SMALL,
                text_color="#1a8a7a", command=self._update_count,
            )
            cb.pack(anchor="w", padx=10, pady=4)

        self._apply_keyword_selection()
        self._update_count()

    def _set_all_checks(self, value: bool):
        for var in self.checkbox_vars.values():
            var.set(value)
        self._apply_keyword_selection()
        self._update_count()

    def _apply_keyword_selection(self):
        if self.current_pool is None:
            self.app.selected_df = None
            return
        selected_idx = [idx for idx, var in self.checkbox_vars.items() if var.get()]
        self.app.selected_df = self.current_pool.loc[selected_idx].reset_index(drop=True)

    def _build_brand(self):
        brands = core.get_brands(self.app.df)

        if not brands:
            ctk.CTkLabel(
                self.content, text="Nessun brand/vendor trovato nel catalogo. "
                                    "Usa la ricerca per parola chiave.",
                font=FONT_NORMAL, text_color=MUTED,
            ).pack(pady=30)
            self.app.selected_df = None
            self._update_count()
            return

        sel_row = ctk.CTkFrame(self.content, fg_color="transparent")
        sel_row.pack(fill="x")
        ctk.CTkButton(
            sel_row, text="Seleziona tutti", width=140, height=30, font=FONT_SMALL,
            fg_color="#00b4d8", hover_color="#1a8a7a", border_width=1, text_color="#ffffff",
            command=lambda: self._set_all_brand_checks(True),
        ).pack(side="left", pady=(2, 6))
        ctk.CTkButton(
            sel_row, text="Deseleziona tutti", width=140, height=30, font=FONT_SMALL,
            fg_color="#00b4d8", hover_color="#1a8a7a", border_width=1, text_color="#ffffff",
            command=lambda: self._set_all_brand_checks(False),
        ).pack(side="left", padx=(8, 0), pady=(2, 6))

        scroll = ctk.CTkScrollableFrame(
            self.content, fg_color=("white", "#2b2b2b"), corner_radius=12, height=320,
        )
        scroll.pack(fill="both", expand=True, pady=10)

        self.brand_vars: dict[str, ctk.BooleanVar] = {}
        for brand in brands:
            count = (self.app.df["Vendor"] == brand).sum()
            var = ctk.BooleanVar(value=False)
            self.brand_vars[brand] = var
            cb = ctk.CTkCheckBox(
                scroll, text=f"{brand}   ({count})", variable=var, font=FONT_SMALL,
                text_color="#1a8a7a", command=self._apply_brand_selection,
            )
            cb.pack(anchor="w", padx=10, pady=3)

        self.app.selected_df = None
        self._update_count()

    def _set_all_brand_checks(self, value: bool):
        for var in self.brand_vars.values():
            var.set(value)
        self._apply_brand_selection()

    def _apply_brand_selection(self):
        chosen = [b for b, v in self.brand_vars.items() if v.get()]
        if not chosen:
            self.app.selected_df = None
        else:
            self.app.selected_df = core.filter_by_brands(self.app.df, chosen)
        self._update_count()

    def _update_count(self):
        if self.mode_bar.get() == "Per parola chiave":
            self._apply_keyword_selection()

        df = self.app.selected_df
        n = 0 if df is None else len(df)
        self.count_label.configure(
            text=f"{n} prodotti selezionati" if n else "Nessun prodotto selezionato",
            text_color="#222" if n else MUTED,
        )
        self.next_btn.configure(state="normal" if n else "disabled")

    def confirm_selection(self):
        self.app.show("analisi")


def pd_notna(value) -> bool:
    try:
        import pandas as pd
        return pd.notna(value)
    except Exception:
        return value is not None


# ──────────────────────────────────────────────────────────────────────────
# STEP 3 — ANALISI
# ──────────────────────────────────────────────────────────────────────────

class AnalisiFrame(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=("#f7fafa", "#1a1a1a"))
        self.app = app
        self.stop_event = None
        self.msg_queue: "queue.Queue" = queue.Queue()
        self.running = False

        ctk.CTkLabel(self, text="3. Avvia l'analisi", font=FONT_TITLE).pack(
            anchor="w", padx=40, pady=(36, 4))

        self.summary_label = ctk.CTkLabel(self, text="", font=FONT_SUBTLE, text_color=MUTED)
        self.summary_label.pack(anchor="w", padx=40, pady=(0, 16))

        opts = ctk.CTkFrame(self, fg_color=("white", "#2b2b2b"), corner_radius=12)
        opts.pack(fill="x", padx=40, pady=(0, 16))

        row1 = ctk.CTkFrame(opts, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=(18, 6))

        self.ai_var = ctk.BooleanVar(value=True)
        self.ai_switch = ctk.CTkSwitch(
            row1, text="Pulizia automatica titoli con AI (consigliata)",
            variable=self.ai_var, font=FONT_NORMAL,
        )
        self.ai_switch.pack(side="left")

        row2 = ctk.CTkFrame(opts, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(6, 18))
        ctk.CTkLabel(row2, text="Segnala solo se il competitor costa almeno il",
                      font=FONT_NORMAL).pack(side="left")
        self.soglia_entry = ctk.CTkEntry(row2, width=60, font=FONT_NORMAL)
        self.soglia_entry.insert(0, "0")
        self.soglia_entry.pack(side="left", padx=8)
        ctk.CTkLabel(row2, text="% in meno", font=FONT_NORMAL).pack(side="left")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=40, pady=(0, 10))

        self.start_btn = ctk.CTkButton(
            btn_row, text="▶  Avvia analisi", font=FONT_BOLD, height=46, width=200,
            command=self.start_analysis,
        )
        self.start_btn.pack(side="left")

        self.stop_btn = ctk.CTkButton(
            btn_row, text="■  Interrompi", font=FONT_BOLD, height=46, width=160,
            fg_color=ACCENT_RED, hover_color="#b53a3a",
            command=self.stop_analysis, state="disabled",
        )
        self.stop_btn.pack(side="left", padx=10)

        prog_box = ctk.CTkFrame(self, fg_color=("white", "#2b2b2b"), corner_radius=12)
        prog_box.pack(fill="x", padx=40, pady=10)

        self.progress_bar = ctk.CTkProgressBar(prog_box, height=14)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(20, 8))

        self.progress_label = ctk.CTkLabel(
            prog_box, text="In attesa di avvio...", font=FONT_NORMAL, text_color=MUTED,
        )
        self.progress_label.pack(anchor="w", padx=20, pady=(0, 6))

        stats_row = ctk.CTkFrame(prog_box, fg_color="transparent")
        stats_row.pack(anchor="w", padx=20, pady=(0, 18))
        self.stat_alerts = ctk.CTkLabel(stats_row, text="⚠ Alert: 0", font=FONT_BOLD,
                                          text_color=ACCENT_RED)
        self.stat_alerts.pack(side="left", padx=(0, 24))
        self.stat_no_match = ctk.CTkLabel(stats_row, text="Senza riscontro: 0",
                                            font=FONT_NORMAL, text_color=MUTED)
        self.stat_no_match.pack(side="left")

        ctk.CTkLabel(self, text="Prodotti più cari trovati durante l'analisi:",
                      font=FONT_BOLD).pack(anchor="w", padx=40, pady=(6, 6))
        self.live_alerts = ctk.CTkScrollableFrame(self, fg_color=("white", "#2b2b2b"),
                                                     corner_radius=12, height=160)
        self.live_alerts.pack(fill="both", expand=True, padx=40, pady=(0, 20))

    def refresh(self):
        df = self.app.selected_df
        n = 0 if df is None else len(df)
        sites = ", ".join(self.app.cfg.get("competitor_sites", []))
        self.summary_label.configure(
            text=f"{n} prodotti da analizzare  ·  Siti competitor: {sites}"
        )

        has_key = bool(self.app.cfg.get("anthropic_api_key"))
        if has_key:
            self.ai_var.set(self.app.cfg.get("use_ai", True))
            self.ai_switch.configure(state="normal")
        else:
            self.ai_var.set(False)
            self.ai_switch.configure(state="disabled")

        if not self.running:
            self.progress_bar.set(0)
            self.progress_label.configure(text="In attesa di avvio...")
            self.stat_alerts.configure(text="⚠ Alert: 0")
            self.stat_no_match.configure(text="Senza riscontro: 0")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            for w in self.live_alerts.winfo_children():
                w.destroy()

    def start_analysis(self):
        df = self.app.selected_df
        if df is None or df.empty:
            messagebox.showwarning("Nessun prodotto", "Torna alla selezione prodotti.")
            return

        try:
            soglia = float(self.soglia_entry.get().strip() or "0")
        except ValueError:
            soglia = 0.0
            self.soglia_entry.delete(0, "end")
            self.soglia_entry.insert(0, "0")

        use_ai  = self.ai_var.get() and bool(self.app.cfg.get("anthropic_api_key"))
        api_key = self.app.cfg.get("anthropic_api_key") or None
        sites   = self.app.cfg.get("competitor_sites", core.DEFAULT_COMPETITOR_SITES)
        out_dir = self.app.cfg.get("output_dir") or os.path.expanduser("~")
        self.running = True
        self.stop_event = threading.Event()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)
        self.stat_alerts.configure(text="⚠ Alert: 0")
        self.stat_no_match.configure(text="Senza riscontro: 0")
        self.progress_label.configure(text="Avvio dei browser in background (uno per sito)...")
        for w in self.live_alerts.winfo_children():
            w.destroy()

        self.app.sidebar.set_enabled("catalogo", False)
        self.app.sidebar.set_enabled("selezione", False)

        def progress_cb(current, total, label):
            self.msg_queue.put(("progress", current, total, label))

        def alert_cb(entry):
            self.msg_queue.put(("alert", entry))

        def log_cb(msg):
            self.msg_queue.put(("log", msg))

        def worker():
            result = core.run_analysis(
                df, sites, use_ai, api_key, out_dir,
                progress_cb=progress_cb, alert_cb=alert_cb, log_cb=log_cb,
                stop_event=self.stop_event, min_discount_pct=soglia,
            )
            self.msg_queue.put(("done", result))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_queue)

    def stop_analysis(self):
        if self.stop_event:
            self.stop_event.set()
        self.stop_btn.configure(state="disabled")
        self.progress_label.configure(text="Interruzione in corso... attendi il prodotto in corso.")

    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                kind = msg[0]

                if kind == "progress":
                    _, current, total, label = msg
                    self.progress_bar.set(current / total if total else 0)
                    short = (label[:60] + "…") if len(label) > 60 else label
                    self.progress_label.configure(text=f"{current}/{total}  —  {short}")

                elif kind == "alert":
                    _, entry = msg
                    self._add_alert_card(entry)
                    n = int(self.stat_alerts.cget("text").split(":")[1].strip()) + 1
                    self.stat_alerts.configure(text=f"⚠ Alert: {n}")

                elif kind == "log":
                    self.progress_label.configure(text=msg[1])

                elif kind == "done":
                    self._on_done(msg[1])
                    return

        except queue.Empty:
            pass

        if self.running:
            self.after(100, self._poll_queue)

    def _add_alert_card(self, entry: dict):
        cheaper  = entry["cheaper_results"]
        cheapest = min(cheaper, key=lambda x: x["price"])
        diff_pct = (entry["my_price"] - cheapest["price"]) / entry["my_price"] * 100

        card = ctk.CTkFrame(self.live_alerts, fg_color=("#f7fafa", "#1a1a1a"), corner_radius=8)
        card.pack(fill="x", padx=6, pady=4)

        title = entry["title"]
        title = (title[:70] + "…") if len(title) > 70 else title
        ctk.CTkLabel(card, text=title, font=FONT_BOLD, anchor="w").pack(
            fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            card,
            text=(f"Tuo prezzo: € {entry['my_price']:.2f}    →    "
                  f"{cheapest['site']}: € {cheapest['price']:.2f}  "
                  f"(-{diff_pct:.1f}%)"),
            font=FONT_SMALL, text_color=ACCENT_RED, anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

    def _on_done(self, result: "core.AnalysisResult"):
        self.running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.app.sidebar.set_enabled("catalogo", True)
        self.app.sidebar.set_enabled("selezione", True)

        self.stat_no_match.configure(text=f"Senza riscontro: {result.no_match}")

        if result.errore:
            self.progress_label.configure(text=f"Errore: {result.errore}")
            messagebox.showerror("Errore durante l'analisi", result.errore)
            return

        if result.interrotto:
            self.progress_label.configure(text="Analisi interrotta dall'utente.")
        else:
            self.progress_bar.set(1)
            self.progress_label.configure(text="Analisi completata.")

        self.app.last_result = result
        self.app.sidebar.set_enabled("risultati", True)
        self.app.refresh_results()
        self.app.show("risultati")


# ──────────────────────────────────────────────────────────────────────────
# STEP 4 — RISULTATI
# ──────────────────────────────────────────────────────────────────────────

class RisultatiFrame(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=("#f7fafa", "#1a1a1a"))
        self.app = app

        ctk.CTkLabel(self, text="4. Risultati", font=FONT_TITLE).pack(
            anchor="w", padx=40, pady=(36, 4))

        self.summary_label = ctk.CTkLabel(self, text="", font=FONT_SUBTLE, text_color=MUTED)
        self.summary_label.pack(anchor="w", padx=40, pady=(0, 16))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=40, pady=(0, 16))

        self.open_report_btn = ctk.CTkButton(
            btn_row, text="📄  Apri report (.txt)", font=FONT_BOLD, height=42,
            fg_color="#00b4d8", hover_color="#1a8a7a", border_width=1, text_color="#ffffff",
            command=self._open_report,
        )
        self.open_report_btn.pack(side="left")

        self.open_folder_btn = ctk.CTkButton(
            btn_row, text="📁  Apri cartella report", font=FONT_BOLD, height=42,
            fg_color="#00b4d8", hover_color="#1a8a7a", border_width=1, text_color="#ffffff",
            command=self._open_folder,
        )
        self.open_folder_btn.pack(side="left", padx=10)

        ctk.CTkButton(
            btn_row, text="↺  Nuova analisi", font=FONT_BOLD, height=42,
            fg_color="#00b4d8", hover_color="#1a8a7a", border_width=1, text_color="#ffffff",
            command=lambda: app.show("selezione"),
        ).pack(side="right")

        self.export_csv_btn = ctk.CTkButton(
            btn_row, text="💾  Esporta CSV modificato", font=FONT_BOLD, height=42,
            fg_color="#1a8a7a", hover_color="#00b4d8", text_color="#ffffff",
            command=self._export_modified_csv,
            state="disabled",
        )
        self.export_csv_btn.pack(side="left", padx=10)

        ctk.CTkLabel(self, text="Dettaglio prodotti più cari della concorrenza:",
                      font=FONT_BOLD).pack(anchor="w", padx=40, pady=(6, 6))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=("white", "#2b2b2b"), corner_radius=12)
        self.scroll.pack(fill="both", expand=True, padx=40, pady=(0, 30))
        self.price_updates: dict[str, float] = {}

    def refresh(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.price_updates = {}
        self.export_csv_btn.configure(state="disabled")

        result = self.app.last_result
        if result is None:
            self.summary_label.configure(text="Nessuna analisi eseguita.")
            self.open_report_btn.configure(state="disabled")
            self.open_folder_btn.configure(state="disabled")
            return

        m, s = divmod(int(result.elapsed), 60)
        ok = result.total - result.no_match - len(result.alerts_data)
        self.summary_label.configure(
            text=(f"Prodotti analizzati: {result.total}   ·   "
                  f"Prezzi competitivi: {ok}   ·   "
                  f"Da rivedere: {len(result.alerts_data)}   ·   "
                  f"Senza riscontro: {result.no_match}   ·   "
                  f"Tempo: {m:02d}:{s:02d}")
        )

        has_report = bool(result.report_path)
        self.open_report_btn.configure(state="normal" if has_report else "disabled")
        self.open_folder_btn.configure(state="normal" if has_report else "disabled")

        if not result.alerts_data:
            ctk.CTkLabel(
                self.scroll, text="🎉  Nessun prodotto risulta più caro della concorrenza. Ottimo!",
                font=FONT_BOLD, text_color=ACCENT_GREEN,
            ).pack(padx=20, pady=30)
            return

        for entry in sorted(
            result.alerts_data,
            key=lambda e: min(r["price"] for r in e["cheaper_results"]) - e["my_price"],
        ):
            self._build_card(entry)

    def _build_card(self, entry: dict):
        cheaper   = entry["cheaper_results"]
        cheapest  = min(cheaper, key=lambda x: x["price"])
        diff_pct  = (entry["my_price"] - cheapest["price"]) / entry["my_price"] * 100
        suggested = round(cheapest["price"] * 0.99, 2)

        card = ctk.CTkFrame(self.scroll, fg_color=("#f7fafa", "#1a1a1a"), corner_radius=10)
        card.pack(fill="x", padx=6, pady=6)

        ctk.CTkLabel(card, text=entry["title"], font=FONT_BOLD, anchor="w",
                      wraplength=720, justify="left").pack(
            fill="x", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            card, text=f"Tuo prezzo: € {entry['my_price']:.2f}",
            font=FONT_NORMAL, anchor="w",
        ).pack(fill="x", padx=16)

        for r in sorted(cheaper, key=lambda x: x["price"]):
            delta = entry["my_price"] - r["price"]
            crown = "👑 " if r["price"] == cheapest["price"] else "    "
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=1)
            ctk.CTkLabel(
                row,
                text=(f"{crown}{r['site']}: € {r['price']:.2f}  "
                      f"(-€ {delta:.2f}, match {r['match_score']}%)"),
                font=FONT_SMALL, text_color=ACCENT_RED, anchor="w",
            ).pack(side="left")

        ctk.CTkLabel(
            card,
            text=f"→  Prezzo consigliato: € {suggested:.2f}   (-{diff_pct:.1f}% sul tuo)",
            font=FONT_BOLD, text_color=ACCENT_GREEN, anchor="w",
        ).pack(fill="x", padx=16, pady=(6, 4))

        link = ctk.CTkLabel(
            card, text=cheapest["url"], font=FONT_SMALL, text_color="#1a4fd6",
            anchor="w", cursor="hand2",
        )
        link.pack(fill="x", padx=16, pady=(0, 14))
        link.bind("<Button-1>", lambda e, url=cheapest["url"]: open_path(url))

        confirm_var = ctk.BooleanVar(value=False)
        confirm_row = ctk.CTkFrame(card, fg_color="transparent")
        confirm_row.pack(fill="x", padx=16, pady=(4, 14))

        price_entry = ctk.CTkEntry(confirm_row, width=90, font=FONT_NORMAL)
        price_entry.insert(0, str(suggested))
        price_entry.pack(side="left", padx=(0, 10))

        def on_confirm(var=confirm_var, e=price_entry, h=entry["title"], entry=entry):
            if var.get():
                try:
                    new_price = float(e.get().replace(",", "."))
                    self.price_updates[h] = new_price
                except ValueError:
                    var.set(False)
                    messagebox.showerror("Errore", "Prezzo non valido.")
                    return
            else:
                self.price_updates.pop(h, None)
            self.export_csv_btn.configure(
                state="normal" if self.price_updates else "disabled"
            )

        ctk.CTkCheckBox(
            confirm_row, text="Conferma modifica prezzo",
            variable=confirm_var, font=FONT_SMALL,
            text_color="#1a8a7a", command=on_confirm,
        ).pack(side="left")

    def _open_report(self):
        result = self.app.last_result
        if result and result.report_path:
            open_path(result.report_path)

    def _open_folder(self):
        result = self.app.last_result
        if result and result.report_path:
            open_path(os.path.dirname(os.path.abspath(result.report_path)))

    def _export_modified_csv(self):
        if not self.price_updates:
            return
        if not self.app.csv_path:
            messagebox.showerror("Errore", "CSV originale non trovato.")
            return
        try:
            out = core.export_modified_csv(
                self.app.csv_path,
                self.price_updates,
                self.app.cfg.get("output_dir", os.path.expanduser("~")),
            )
            messagebox.showinfo("Esportazione completata", f"CSV salvato in:\n{out}")
            open_path(os.path.dirname(out))
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile esportare il CSV:\n{e}")


# ──────────────────────────────────────────────────────────────────────────
# STEP 5 — IMPOSTAZIONI
# ──────────────────────────────────────────────────────────────────────────

class ImpostazioniFrame(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=("#f7fafa", "#1a1a1a"))
        self.app = app

        ctk.CTkLabel(self, text="⚙  Impostazioni", font=FONT_TITLE).pack(
            anchor="w", padx=40, pady=(36, 4))
        ctk.CTkLabel(
            self, text="Queste impostazioni vengono salvate sul computer e restano "
                       "attive per tutti gli avvii successivi del programma.",
            font=FONT_SUBTLE, text_color=MUTED,
        ).pack(anchor="w", padx=40, pady=(0, 24))

        # ── API key ──────────────────────────────────────────────────────────
        box1 = ctk.CTkFrame(self, fg_color=("white", "#2b2b2b"), corner_radius=12)
        box1.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(box1, text="Chiave API Anthropic (per la pulizia AI dei titoli)",
                      font=FONT_BOLD).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            box1, text="Necessaria solo per migliorare la precisione della ricerca. "
                       "Senza chiave, il programma funziona comunque con un metodo di fallback.",
            font=FONT_SMALL, text_color=MUTED, wraplength=640, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 8))

        key_row = ctk.CTkFrame(box1, fg_color="transparent")
        key_row.pack(fill="x", padx=20, pady=(0, 18))
        self.api_key_entry = ctk.CTkEntry(key_row, width=420, show="•", font=FONT_NORMAL)
        self.api_key_entry.pack(side="left")
        self.show_key_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            key_row, text="Mostra", variable=self.show_key_var, font=FONT_SMALL,
            command=self._toggle_key_visibility,
        ).pack(side="left", padx=10)

        # ── Cartella report ──────────────────────────────────────────────────
        box2 = ctk.CTkFrame(self, fg_color=("white", "#2b2b2b"), corner_radius=12)
        box2.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(box2, text="Cartella dove salvare i report",
                      font=FONT_BOLD).pack(anchor="w", padx=20, pady=(18, 4))

        folder_row = ctk.CTkFrame(box2, fg_color="transparent")
        folder_row.pack(fill="x", padx=20, pady=(0, 18))
        self.folder_label = ctk.CTkLabel(folder_row, text="", font=FONT_NORMAL,
                                           text_color=MUTED)
        self.folder_label.pack(side="left")
        ctk.CTkButton(
            folder_row, text="Cambia...", width=110, height=32, font=FONT_SMALL,
            fg_color="transparent", border_width=1, text_color="#222",
            command=self._choose_folder,
        ).pack(side="left", padx=10)

        # ── Siti competitor ──────────────────────────────────────────────────
        box3 = ctk.CTkFrame(self, fg_color=("white", "#2b2b2b"), corner_radius=12)
        box3.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(box3, text="Siti competitor da controllare",
                      font=FONT_BOLD).pack(anchor="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            box3, text="Un sito per riga, senza https:// (es. wildgear.it)",
            font=FONT_SMALL, text_color=MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 6))
        self.sites_text = ctk.CTkTextbox(box3, height=100, font=FONT_NORMAL)
        self.sites_text.pack(fill="x", padx=20, pady=(0, 18))

        # ── Tema ─────────────────────────────────────────────────────────────
        box4 = ctk.CTkFrame(self, fg_color=("white", "#2b2b2b"), corner_radius=12)
        box4.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(box4, text="Tema dell'interfaccia",
                      font=FONT_BOLD).pack(anchor="w", padx=20, pady=(18, 4))

        self.theme_var = ctk.StringVar(value="light")
        theme_row = ctk.CTkFrame(box4, fg_color="transparent")
        theme_row.pack(anchor="w", padx=20, pady=(0, 18))
        ctk.CTkRadioButton(
            theme_row, text="☀  Chiaro", variable=self.theme_var,
            value="light", font=FONT_NORMAL,
        ).pack(side="left", padx=(0, 24))
        ctk.CTkRadioButton(
            theme_row, text="🌙  Scuro", variable=self.theme_var,
            value="dark", font=FONT_NORMAL,
        ).pack(side="left")

        # ── Salvataggio ──────────────────────────────────────────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=40, pady=20)
        self.saved_label = ctk.CTkLabel(bottom, text="", font=FONT_SMALL,
                                          text_color=ACCENT_GREEN)
        self.saved_label.pack(side="left")
        ctk.CTkButton(
            bottom, text="💾  Salva impostazioni", font=FONT_BOLD, height=44, width=200,
            command=self._save,
        ).pack(side="right")

    def refresh(self):
        cfg = self.app.cfg
        self.api_key_entry.delete(0, "end")
        self.api_key_entry.insert(0, cfg.get("anthropic_api_key", ""))
        self.folder_label.configure(text=cfg.get("output_dir", ""))
        self.sites_text.delete("1.0", "end")
        self.sites_text.insert("1.0", "\n".join(cfg.get("competitor_sites", [])))
        self.theme_var.set(cfg.get("theme", "light"))
        self.saved_label.configure(text="")

    def _toggle_key_visibility(self):
        self.api_key_entry.configure(show="" if self.show_key_var.get() else "•")

    def _choose_folder(self):
        folder = filedialog.askdirectory(
            title="Scegli la cartella dove salvare i report",
            initialdir=self.app.cfg.get("output_dir") or os.path.expanduser("~"),
        )
        if folder:
            self.folder_label.configure(text=folder)

    def _save(self):
        sites = [s.strip() for s in self.sites_text.get("1.0", "end").splitlines() if s.strip()]
        if not sites:
            sites = core.DEFAULT_COMPETITOR_SITES

        theme = self.theme_var.get()

        self.app.cfg = config.update_config(
            anthropic_api_key=self.api_key_entry.get().strip(),
            output_dir=self.folder_label.cget("text") or self.app.cfg.get("output_dir"),
            competitor_sites=sites,
            theme=theme,
        )

        # Applica il tema immediatamente su tutta l'app
        ctk.set_appearance_mode(theme)
        # Aggiorna il logo in base al tema
        self.app.sidebar.update_logo(theme)

        self.saved_label.configure(text="✔  Impostazioni salvate")
        self.after(2500, lambda: self.saved_label.configure(text=""))


# ──────────────────────────────────────────────────────────────────────────
# APP PRINCIPALE
# ──────────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Spryce - E il miglior prezzo è il tuo!")
        self.geometry("1100x760")
        self.minsize(900, 620)

        self.cfg = config.load_config()

        # Applica il tema salvato prima di costruire l'interfaccia
        ctk.set_appearance_mode(self.cfg.get("theme", "light"))

        self.df = None
        self.csv_path = None
        self.selected_df = None
        self.last_result = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(self, on_select=self.show)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        container = ctk.CTkFrame(self, fg_color=("#f7fafa", "#1a1a1a"), corner_radius=0)
        container.grid(row=0, column=1, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {
            "catalogo":     CatalogoFrame(container, self),
            "selezione":    SelezioneFrame(container, self),
            "analisi":      AnalisiFrame(container, self),
            "risultati":    RisultatiFrame(container, self),
            "impostazioni": ImpostazioniFrame(container, self),
        }
        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        for key in ("selezione", "analisi", "risultati"):
            self.sidebar.set_enabled(key, False)

        self.frames["impostazioni"].refresh()

        # ── Schermata di login ────────────────────────────────────────────
        # Copre l'intera finestra finché l'utente non si autentica.
        self.login_frame = login_frame.LoginFrame(self, on_login_success=self._on_logged_in)
        self.login_frame.grid(row=0, column=0, columnspan=2, rowspan=3, sticky="nsew")
        self.login_frame.tkraise()

        # Icon setting
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass
        try:
            icon_image = ImageTk.PhotoImage(file=resource_path("icon.png"))
            self.wm_iconphoto(True, icon_image)
            self._icon_image = icon_image
        except Exception:
            pass

        footer = ctk.CTkFrame(self, fg_color=("#e0f4f1", "#1f2f2f"), height=28, corner_radius=0)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        footer.grid_propagate(False)

        self.user_label = ctk.CTkLabel(
            footer, text="", font=("Segoe UI", 11), text_color="#888888")
        self.user_label.pack(side="right", padx=16)

        ctk.CTkButton(
            footer, text="Esci", font=("Segoe UI", 11),
            height=20, width=60,
            fg_color="transparent", text_color=MUTED,
            hover_color=("#d0f0ec", "#1f2f2f"),
            command=self._logout,
        ).pack(side="right", padx=(0, 4))

        ctk.CTkLabel(
            footer,
            text="Copyright 2026 Giuseppe Rossetti - Spryce",
            font=("Segoe UI", 11),
            text_color="#888888",
        ).pack(side="left", padx=16)

        link = ctk.CTkLabel(
            footer,
            text="kaindevelop.com",
            font=("Segoe UI", 11, "underline"),
            text_color="#4a9eff",
            cursor="hand2",
        )
        link.pack(side="left", padx=(0, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open("https://kaindevelop.com"))

        # Applica il logo corretto in base al tema salvato
        self.sidebar.update_logo(self.cfg.get("theme", "light"))

    def _on_logged_in(self, session):
        """Chiamato da LoginFrame dopo autenticazione riuscita."""
        self.session = session
        self.login_frame.grid_forget()
        self.show("catalogo")
        # Mostra il nome utente nel footer
        try:
            name = session.full_name or session.email or ""
            self.user_label.configure(text=f"👤  {name}")
        except Exception:
            pass

    def on_catalog_loaded(self):
        self.frames["selezione"].reset()
        for key in ("analisi", "risultati"):
            self.sidebar.set_enabled(key, False)

    def refresh_results(self):
        self.frames["risultati"].refresh()

    def show(self, key: str):
        if key == "analisi":
            self.frames["analisi"].refresh()
        if key == "impostazioni":
            self.frames["impostazioni"].refresh()
        if key == "risultati":
            self.frames["risultati"].refresh()

        self.frames[key].tkraise()
        self.sidebar.set_active(key)


    def _logout(self):
        auth.logout()
        self.user_label.configure(text="")
        self.login_frame = login_frame.LoginFrame(self, on_login_success=self._on_logged_in)
        self.login_frame.grid(row=0, column=0, columnspan=2, rowspan=3, sticky="nsew")
        self.login_frame.tkraise()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()