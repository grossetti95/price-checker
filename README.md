# Spryce — Competitor Price Checker

Desktop application with a graphical interface for comparing Shopify catalog prices against competitor websites. Built with Python, CustomTkinter, and Selenium. Supports cloud authentication via Supabase (Google, Apple, Microsoft login).

## Project Structure

```
Spryce/
├── core.py                     # business logic (CSV, Selenium, AI, reports)
├── config.py                   # local settings management
├── gui_app.py                  # GUI entry point
├── auth.py                     # Supabase authentication (login/register/OAuth)
├── logo.png                    # sidebar logo (light mode)
├── logo_dark.png               # sidebar logo (dark mode) — optional
├── icon.ico                    # app icon (titlebar + .exe)
├── icon.png                    # app icon (taskbar, runtime)
├── requirements.txt
├── Spryce.spec                 # PyInstaller configuration
```

---

## 1. Requirements (build machine)

- **Windows 10/11**
- **Python 3.11 or 3.12** ([python.org](https://www.python.org/downloads/) — check "Add Python to PATH" during install)
- **Google Chrome** installed (required both for testing and on end-user machines)

---

## 2. Environment Setup

⚠️ **Use a clean Python environment, NOT an Anaconda base env**. Anaconda base includes hundreds of libraries that PyInstaller tries to bundle, causing very slow builds, huge output, and errors like:

```
ERROR: Aborting build process due to attempt to collect multiple Qt
bindings packages: ... PyQt5 ... PySide6 ...
```

Open PowerShell in the project folder and create a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Supabase Setup (Authentication)

Spryce uses [Supabase](https://supabase.com) for cloud authentication (email/password, Google, Apple, Microsoft).

### Create a project
1. Sign up at [supabase.com](https://supabase.com) and create a new project
2. Go to **Project Settings → API** and copy:
   - `Project URL`
   - `anon / public key`
3. Create a file `.env` in the project root (never commit this):

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
```

### Enable OAuth providers
In Supabase dashboard → **Authentication → Providers**, enable the ones you want (Google, Azure/Microsoft, Apple) and follow the setup guide for each. Each provider requires you to register a developer app on their platform and paste the client ID + secret into Supabase.

---

## 4. Customizing for a New Shop

### Logo
Place the shop logo as `logo.png` in the project root. Optionally add `logo_dark.png` for dark mode — if not present, `logo.png` is used for both themes.

In `gui_app.py`, adjust the `size` parameter inside `Sidebar.__init__`:

```python
logo_img = ctk.CTkImage(
    light_image=Image.open(resource_path("logo.png")),
    size=(160, 120)   # ← adjust to your logo's proportions
)
```

### Colors
All UI colors are defined at the top of `gui_app.py`:

```python
ctk.ThemeManager.theme["CTkButton"]["fg_color"]    = ["#1a8a7a", "#1a8a7a"]
ctk.ThemeManager.theme["CTkButton"]["hover_color"] = ["#00b4d8", "#00b4d8"]

ACCENT_GREEN  = "#1a8a7a"
ACCENT_RED    = "#e05555"
ACCENT_YELLOW = "#00b4d8"
MUTED         = "#9a9a9a"
```

Adaptive colors (light/dark) use tuples: `fg_color=("white", "#2b2b2b")`.

### App Name
- Window title: `self.title(...)` in `App.__init__` in `gui_app.py`
- Footer text: `text="Copyright 2026 ..."` in `App.__init__`
- Config folder: `APP_NAME = "Spryce"` in `config.py`
- Output exe name: `name='Spryce'` in the `.spec` file

---

## 5. Quick Test Before Building

```powershell
python gui_app.py
```

Go to **⚙ Impostazioni** and:
- enter your Anthropic API key
- set the report output folder
- review competitor sites
- choose light/dark theme
- click **Salva impostazioni**

Settings are saved locally at `%APPDATA%\Spryce\config.json`.

---

## 6. Building the `.exe`

With the virtual environment active:

```powershell
pyinstaller Spryce.spec
```

Output in `dist\Spryce\`. Distribute the **entire folder**, not just the `.exe`.

⚠️ If `logo_dark.png` exists in the project root, it is automatically included in the build.

---

## 7. Usage

1. Double-click the app icon
2. **Login / Registrazione** → sign in or create an account (email or OAuth)
3. **1. Catalogo** → import via CSV or Shopify API
4. **2. Selezione prodotti** → All, by keyword, or by brand
5. **3. Analisi** → click "Avvia analisi" and wait
6. **4. Risultati** → review alerts, update prices, export

### Requirements on the end-user machine
- **Google Chrome** installed
- **Internet connection**

No Python or additional libraries required.

---

## 8. Performance & Limitations

- Chrome runs in **headless mode** — no visible browser windows.
- Competitor sites are checked **in parallel** (one browser per site). With 4 sites, each product takes ~3–8 seconds.
- Slow/unreachable sites are skipped after `PAGE_TIMEOUT` seconds (default: 10).
- The **Interrompi** button halts after the current product and saves a partial report.
- For large catalogs, filtering by brand or keyword before running is recommended.

---

*Spryce — developed by Giuseppe Rossetti · [kaindevelop.com](https://kaindevelop.com)*