# Competitor Price Checker — Desktop GUI

Desktop application with a graphical interface for comparing Shopify catalog prices against competitor websites.

## Project Structure

```
CompetitorPriceChecker/
├── core.py                     # business logic (CSV, Selenium, AI, reports)
├── config.py                   # local settings management
├── gui_app.py                  # GUI entry point
├── logo.png                    # shop logo displayed in the sidebar
├── requirements.txt
├── CompetitorPriceChecker.spec # PyInstaller configuration
└── icon.ico                    # (optional) app icon
```

The old `price_checker.py` and `ui.py` (terminal version) are no longer needed — all logic has been moved to `core.py` and wired to the new interface.

---

## 1. Requirements (build machine)

- **Windows 10/11**
- **Python 3.11 or 3.12** ([python.org](https://www.python.org/downloads/) — check "Add Python to PATH" during install)
- **Google Chrome** installed (required both for testing and on end-user machines: the script drives it headlessly)

## 2. Environment Setup

⚠️ **Use a clean Python environment, NOT an Anaconda base env**. Anaconda base includes hundreds of libraries (Jupyter, matplotlib, PyQt5 *and* PySide6, sphinx, etc.) that PyInstaller tries to bundle, causing very slow builds, huge output, and errors like:

```
ERROR: Aborting build process due to attempt to collect multiple Qt
bindings packages: ... PyQt5 ... PySide6 ...
```

The updated `.spec` already excludes these libraries as a safeguard, but it's much better to start from a dedicated, lean environment.

Open PowerShell in the project folder and create a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

(If only Anaconda is installed and `python` isn't in PATH, use
`C:\Users\YOUR_USER\anaconda3\python.exe -m venv venv` to create the venv,
then activate it normally with `venv\Scripts\activate`.)

## 3. Logo Setup

The sidebar displays a shop logo loaded from `logo.png` in the project root. To customise it for a different shop:

1. Place the new logo as `logo.png` in the same folder as `gui_app.py`. The file must be a valid PNG (if in doubt, re-export it from any image editor as PNG).

2. In `gui_app.py`, find the `CTkImage` call inside `Sidebar.__init__` and adjust the `size` parameter to match the logo's aspect ratio:

```python
logo_img = ctk.CTkImage(
    light_image=Image.open(resource_path("logo.png")),
    size=(160, 101)   # ← width, height in pixels — adjust to your logo's proportions
)
```

3. The `resource_path()` helper (defined just above the `Sidebar` class) ensures the logo is found both during development and inside the compiled `.exe`. Do not replace it with a plain `open("logo.png")`.

4. The `.spec` file already contains the line that tells PyInstaller to bundle the logo:

```python
datas.append(("logo.png", "."))
```

If you rename the file, update this line and the `Image.open(...)` call accordingly.

⚠️ **`Pillow` must be in `requirements.txt`** — it is used to load the logo image. If it is missing, add it:

```
Pillow>=10.0.0
```

---

## 4. Quick Test Before Building

Run the app locally to verify everything works:

```powershell
python gui_app.py
```

Go to the **⚙ Settings** screen and:
- enter your Anthropic API key (used for AI-based title normalization)
- check/set the folder where reports will be saved
- review the competitor sites list (one per line)
- click **Save settings**

This configuration is written to a local file (NOT embedded in the code, so it will never end up in the `.exe`):

```
%APPDATA%\CompetitorPriceChecker\config.json
```

## 5. Building the `.exe`

With the virtual environment still active:

```powershell
pyinstaller CompetitorPriceChecker.spec
```

The output will be in:

```
dist\CompetitorPriceChecker\
```

That folder (which can be zipped) is the complete app: it contains `CompetitorPriceChecker.exe` plus all required libraries and the logo.

⚠️ **Important**: distribute the entire folder, not just the `.exe` — it won't launch otherwise.

---

## 6. Usage

1. Double-click the app icon
2. **1. Catalog** → select the CSV exported from Shopify
3. **2. Product Selection** → choose All, by keyword, or by brand
4. **3. Analysis** → click "Start analysis" and wait
5. **4. Results** → review flagged products and open the report

### Requirements on the end-user machine

- **Google Chrome** installed (standard version, nothing else needed)
- **Internet connection** (to scrape competitor sites and, on first run, to auto-download the matching ChromeDriver)

No Python or additional libraries required — everything is bundled in the `.exe`.

---

## 7. Updating the App

When you want to add new competitor sites or change the logic:

1. Edit `core.py` (logic) or `gui_app.py` (interface)
2. Re-run `pyinstaller CompetitorPriceChecker.spec`
3. Replace the `dist\CompetitorPriceChecker` folder on target machines (their settings in `%APPDATA%` are untouched)

To add new competitor sites **without rebuilding**, just add them in Settings → "Competitor sites to check", one per line. If a site uses a non-standard search URL (different from `/search?q=...`), you'll need to update `SEARCH_URLS` in `core.py` and rebuild.

---

## 8. Performance & Limitations

- Chrome runs in headless mode — no visible browser windows.
- **Speed**: competitor sites are checked **in parallel** for each product (one browser instance per site, reused across the full catalog). Pages are considered ready as soon as the main content loads (`page_load_strategy = "eager"`), skipping ads, trackers, and secondary scripts — previously the main source of delays. With 4 sites, each product now takes ~3–8 seconds (down from 1–3+ minutes).
- If a site is slow or unreachable, it's skipped for that product after `PAGE_TIMEOUT` seconds (default: 10, configurable in `core.py`), without blocking the other sites.
- The "Stop" button halts the analysis after the current product finishes (not immediately) and still saves a partial report.
- The "% cheaper" threshold hides negligible price differences (e.g. with 3%, a competitor that's only 1% cheaper won't trigger an alert).
- For large catalogs, filtering by brand or keyword before running the analysis is recommended.