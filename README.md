# Spryce — Competitor Price Checker

Desktop application with a graphical interface for comparing Shopify catalog prices against competitor websites. Built with Python, CustomTkinter, and Selenium.

## Project Structure

```
Spryce/
├── core.py                     # business logic (CSV, Selenium, AI, reports)
├── config.py                   # local settings management
├── gui_app.py                  # GUI entry point
├── logo.png                    # shop logo displayed in the sidebar
├── icon.ico                    # app icon (titlebar + .exe)
├── icon.png                    # app icon (taskbar, runtime)
├── requirements.txt
├── Spryce.spec                 # PyInstaller configuration
```

---

## 1. Requirements (build machine)

- **Windows 10/11**
- **Python 3.11 or 3.12** ([python.org](https://www.python.org/downloads/) — check "Add Python to PATH" during install)
- **Google Chrome** installed (required both for testing and on end-user machines: the script drives it headlessly)

---

## 2. Environment Setup

⚠️ **Use a clean Python environment, NOT an Anaconda base env**. Anaconda base includes hundreds of libraries (Jupyter, matplotlib, PyQt5 *and* PySide6, sphinx, etc.) that PyInstaller tries to bundle, causing very slow builds, huge output, and errors like:

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

(If only Anaconda is installed and `python` isn't in PATH, use
`C:\Users\YOUR_USER\anaconda3\python.exe -m venv venv` to create the venv,
then activate normally with `venv\Scripts\activate`.)

---

## 3. Customizing for a New Shop

### Logo
Place the shop logo as `logo.png` in the project root. It must be a valid PNG file (re-export from any image editor if unsure). In `gui_app.py`, adjust the `size` parameter inside `Sidebar.__init__` to match the logo's proportions:

```python
logo_img = ctk.CTkImage(
    light_image=Image.open(resource_path("logo.png")),
    size=(160, 120)   # ← adjust width/height to your logo's proportions
)
```

Always use `resource_path()` when opening the logo — it ensures the file is found both during development and inside the compiled `.exe`.

### Colors
All UI colors are defined at the top of `gui_app.py` (lines 31–43):

```python
ctk.ThemeManager.theme["CTkButton"]["fg_color"]    = ["#1a8a7a", "#1a8a7a"]
ctk.ThemeManager.theme["CTkButton"]["hover_color"] = ["#00b4d8", "#00b4d8"]

ACCENT_GREEN  = "#1a8a7a"   # teal — confirm actions, success states
ACCENT_RED    = "#e05555"   # red  — alerts, stop button
ACCENT_YELLOW = "#00b4d8"   # cyan — highlights, warnings
MUTED         = "#9a9a9a"   # grey — subtle labels
```

The sidebar background is set in `Sidebar.__init__` (`fg_color`), and frame/card backgrounds are set per-frame as `fg_color` on each `CTkFrame`. Use `Ctrl+H` in VSCode to do bulk replacements when rebranding.

### App Name
- Window title: `self.title(...)` in `App.__init__` in `gui_app.py`
- Footer text: `text="Copyright 2026 ..."` in `App.__init__`
- Config folder: `APP_NAME = "Spryce"` in `config.py` (changing this moves the config file to `%APPDATA%\<new name>\`)
- Output exe name: `name='Spryce'` in the `.spec` file

### CSV Default Folder
The file picker opens by default in `C:\Program Files\Spryce\CSV` (set in `config.py`):

```python
"last_csv_dir": r"C:\Program Files\Spryce\CSV",
```

This folder is created automatically on first launch if it doesn't exist. Change this path to match the target machine's preferred location.

### Icons
- `icon.ico` — used by PyInstaller for the `.exe` icon and title bar (must include sizes 16, 32, 48, 256px)
- `icon.png` — used at runtime for the taskbar icon (256×256px recommended)

To generate a valid `.ico` from a PNG using Pillow:

```python
from PIL import Image
img = Image.open("logo.png").convert("RGBA")
img.save("icon.ico", format="ICO", sizes=[(16,16),(32,32),(48,48),(256,256)])
```

Both files must be listed in the `.spec` datas:

```python
datas.append(("logo.png", "."))
datas.append(("icon.ico", "."))
datas.append(("icon.png", "."))
```

---

## 4. Quick Test Before Building

Run the app locally to verify everything works:

```powershell
python gui_app.py
```

Go to the **⚙ Impostazioni** screen and:
- enter your Anthropic API key (used for AI-based title normalization)
- check/set the folder where reports will be saved
- review the competitor sites list (one per line)
- click **Salva impostazioni**

Settings are saved locally and never bundled into the `.exe`:

```
%APPDATA%\Spryce\config.json
```

---

## 5. Building the `.exe`

With the virtual environment active:

```powershell
pyinstaller Spryce.spec
```

The output will be in:

```
dist\Spryce\
```

That folder (which can be zipped) is the complete app: it contains `Spryce.exe` plus all required libraries, the logo, and the icons.

⚠️ **Important**: distribute the entire folder, not just the `.exe` — it won't launch otherwise.

---

## 6. Usage

1. Double-click the app icon
2. **1. Catalogo** → select the CSV exported from Shopify (Prodotti → Esporta)
3. **2. Selezione prodotti** → choose All, by keyword, or by brand
4. **3. Analisi** → click "Avvia analisi" and wait
5. **4. Risultati** → review flagged products and open the report

### Requirements on the end-user machine

- **Google Chrome** installed (standard version, nothing else needed)
- **Internet connection** (to scrape competitor sites and, on first run, to auto-download the matching ChromeDriver)

No Python or additional libraries required — everything is bundled in the `.exe`.

---

## 7. Updating the App

When you want to change logic or add competitor sites:

1. Edit `core.py` (logic) or `gui_app.py` (interface)
2. Re-run `pyinstaller Spryce.spec`
3. Replace the `dist\Spryce` folder on target machines (their settings in `%APPDATA%\Spryce` are untouched)

To add competitor sites **without rebuilding**, add them in Impostazioni → "Siti competitor da controllare", one per line. If a site uses a non-standard search URL (different from `/search?q=...`), update `SEARCH_URLS` in `core.py` and rebuild.

---

## 8. Performance & Limitations

- Chrome runs in headless mode — no visible browser windows.
- **Speed**: competitor sites are checked **in parallel** for each product (one browser instance per site, reused across the full catalog). Pages are considered ready as soon as the main content loads (`page_load_strategy = "eager"`). With 4 sites, each product takes ~3–8 seconds.
- If a site is slow or unreachable, it is skipped for that product after `PAGE_TIMEOUT` seconds (default: 10, configurable in `core.py`).
- The "Interrompi" button halts the analysis after the current product finishes and saves a partial report.
- The "% in meno" threshold hides negligible price differences (e.g. with 3%, a competitor only 1% cheaper won't trigger an alert).
- For large catalogs, filtering by brand or keyword before running the analysis is recommended.

---

*Spryce — developed by Giuseppe Rossetti · [kaindevelop.com](https://kaindevelop.com)*