"""
core.py — Logica di business del Competitor Price Checker
============================================================
Contiene tutta la logica "motore" (CSV, Selenium, AI, estrazione prezzi,
generazione report) SENZA alcuna dipendenza da terminale/print/input.

Pensato per essere chiamato da una GUI (es. gui_app.py) in un thread
separato, comunicando lo stato tramite callback.
"""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from threading import Event
from typing import Callable, Optional
from urllib.parse import quote_plus

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# ── CONFIGURAZIONE DI DEFAULT ────────────────────────────────────────────────

DEFAULT_COMPETITOR_SITES = [
    "wildgear.it",
    "sicurmaxisrl.it",
    "sporttechs.it",
    "dimararmi.it",
]

SIMILARITY_THRESHOLD = 55
REQUEST_DELAY        = 0.8
PAGE_TIMEOUT         = 10

SEARCH_URLS = {
    "wildgear.it":     "https://www.wildgear.it/search?q={query}",
    "sicurmaxisrl.it": "https://www.sicurmaxisrl.it/search?q={query}",
    "sporttechs.it":   "https://www.sporttechs.it/search?q={query}",
    "dimararmi.it":    "https://www.dimararmi.it/search?q={query}",
}

SKIP_SEGMENTS = ["/categoria", "/category", "/brand", "/tag", "/cart", "/account", "/blog"]


# ── CSV ───────────────────────────────────────────────────────────────────────

def load_products(csv_path: str) -> pd.DataFrame:
    """Carica il CSV export di Shopify e restituisce solo i prodotti attivi."""
    df = pd.read_csv(csv_path, low_memory=False)
    df = df.drop_duplicates(subset="Handle")
    if "Status" in df.columns:
        df = df[df["Status"].str.lower() == "active"]
    df = df.dropna(subset=["Variant Price"])
    df["Variant Price"] = pd.to_numeric(df["Variant Price"], errors="coerce")
    df = df.dropna(subset=["Variant Price"])
    return df[["Handle", "Title", "Variant Price", "Vendor"]].reset_index(drop=True)


def get_brands(df: pd.DataFrame) -> list[str]:
    """Restituisce la lista ordinata (case-insensitive) dei brand/vendor presenti."""
    return sorted(df["Vendor"].dropna().unique(), key=lambda x: x.lower())


def filter_by_keyword(df: pd.DataFrame, keyword: str) -> pd.DataFrame:
    """Filtra i prodotti che contengono la parola chiave nel titolo."""
    mask = df["Title"].str.contains(keyword, case=False, na=False)
    return df[mask].reset_index(drop=True)


def filter_by_brands(df: pd.DataFrame, brands: list[str]) -> pd.DataFrame:
    """Filtra i prodotti appartenenti a uno o più brand/vendor."""
    return df[df["Vendor"].isin(brands)].reset_index(drop=True)


# ── AI: ESTRAZIONE QUERY DI RICERCA ──────────────────────────────────────────

_query_cache: dict[str, str] = {}


def ai_search_query(title: str, api_key: str) -> str:
    """
    Usa Claude per estrarre dal titolo del prodotto la query di ricerca ottimale:
    solo brand + modello, senza parole SEO generiche.
    Usa una cache per non ripetere la chiamata sullo stesso titolo.
    """
    if title in _query_cache:
        return _query_cache[title]

    import anthropic

    # Pre-pulizia: rimuovi suffissi promozionali/logistici prima di mandare all'AI
    title_clean = re.sub(
        r"\s*[-–|]\s*(preordine|promo|kit|set|bundle|offerta|usato|ricondizionato|"
        r"spedizione gratuita|garanzia|ricaricabile|con custodia|con borsa).*$",
        "", title, flags=re.IGNORECASE
    ).strip()

    prompt = (
        "Sei un assistente per un negozio outdoor italiano specializzato in prodotti "
        "di caccia, trekking, ottica termica, GPS per cani e abbigliamento tecnico.\n\n"
        "Ti do il titolo di un prodotto del catalogo Shopify. Devi restituire SOLO "
        "la query di ricerca ottimale da usare sui siti competitor, seguendo queste regole:\n\n"
        "REGOLA FONDAMENTALE — Il risultato DEVE iniziare con il BRAND (prima parola "
        "riconoscibile come marchio). Non restituire mai solo parole generiche di categoria.\n\n"
        "REGOLA 1 — PRODOTTI TECNOLOGICI (visori termici, monoculari, binocoli, "
        "cannocchiali, GPS, clip-on, collari, palmari, torce, ottiche, red dot, "
        "fotocamere, tosatici professionali, ecc.):\n"
        "  - Marchi di riferimento: Hikmicro, Nocpix, RIX, Pulsar, ATN, Infiray, "
        "Pard, ThermTec, Garmin, Dogtrace, Bitrabi, TR-Dog, Canicom, Sportdog, "
        "Aimpoint, Vortex, Nikon, Konus, Bushnell, Holosun, Fenix, Nextorch, "
        "Wahl, Moser, Umarex, Shotkam, Tactacam, ecc.\n"
        "  - Mantieni ESATTAMENTE il brand e il codice/sigla del modello "
        "(es. 'TH35C', 'VS50R', 'Alpha 200', 'X30T', 'RAPTOR RH50L').\n"
        "  - Rimuovi solo le parole generiche di categoria "
        "(es. 'monocolo termico', 'visore notturno', 'cannocchiale termico', "
        "'palmare', 'collare GPS', 'kit', 'ottica da puntamento', 'torcia LED', "
        "'promo', 'preordine', 'set', 'ricaricabile').\n"
        "  - Non alterare o abbreviare la sigla del modello.\n\n"
        "REGOLA 2 — ABBIGLIAMENTO E CALZATURE (giacche, pantaloni, gilet, maglie, "
        "scarponi, scarpe, stivali, calze, guanti, cappelli, cinture, ecc.):\n"
        "  - Marchi di riferimento: Trabaldo, Noan, Crispi, AKU, Gronell, Garsport, "
        "Garmont, Zamberlan, Beretta, Bitrabi, Cofra, Chiruca, Kayland, Meindl, "
        "Le Chameau, Aigle, Armond, Diotto, Blatex, Univers, Riserva, Capone, "
        "Red Jack, Masseria, Follow Me, ecc.\n"
        "  - Mantieni brand + nome del modello specifico.\n"
        "  - Rimuovi le parole generiche di categoria "
        "(es. 'pantaloni', 'pantalone', 'giacca', 'gilet', 'maglia', 'pile', "
        "'scarponi', 'scarpe', 'stivale', 'calze', 'guanti', 'cappello', "
        "'da caccia', 'da trekking', 'da montagna', 'impermeabile', "
        "'softshell', 'antispino', 'antistrappo', 'antipioggia', "
        "'con rinforzi in kevlar', 'full kevlar', 'anti rovo', 'imbottita', "
        "'in pile', 'termica', 'estiva', 'invernale', 'alti', 'bassi', 'mid').\n\n"
        "REGOLA 3 — ALTRI PRODOTTI (munizioni, richiami, accessori, coltelli, "
        "canne da pesca, mulinelli, ami, ecc.):\n"
        "  - Mantieni brand + nome/codice specifico del prodotto.\n"
        "  - Rimuovi solo le parole di categoria più generiche.\n\n"
        "ESEMPI CORRETTI:\n"
        "  'Crispi Titan GTX Scarponi Alti - Preordine'  →  Crispi Titan GTX\n"
        "  'Trabaldo Warrior Evo Pro Pantalone da caccia'  →  Trabaldo Warrior Evo Pro\n"
        "  'Monocolo termico Nocpix Vista VS50R con telemetro'  →  Nocpix Vista VS50R\n"
        "  'Gronell Wild Trek Scarpe Caccia e Trekking'  →  Gronell Wild Trek\n\n"
        "OUTPUT: restituisci UNICAMENTE la query di ricerca, senza spiegazioni, "
        "senza virgolette, senza punteggiatura finale.\n\n"
        f"Titolo: {title_clean}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        query = msg.content[0].text.strip().strip('"').strip("'")
    except Exception:
        # Fallback: ultime 4 parole se sembrano generiche
        words = title.split()
        query = " ".join(words[-4:]) if len(words) > 4 else title

    _query_cache[title] = query
    return query


def make_search_query(title: str, use_ai: bool, api_key: Optional[str] = None) -> str:
    """Wrapper: usa AI se disponibile e richiesta, altrimenti fallback semplice."""
    if use_ai and api_key:
        return ai_search_query(title, api_key)
    # Fallback: ultime 4 parole (tendenzialmente brand + modello)
    words = title.strip().split()
    return " ".join(words[-4:]) if len(words) > 4 else title


# ── SELENIUM SETUP ────────────────────────────────────────────────────────────

def create_driver(headless: bool = True, driver_path: Optional[str] = None) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    prefs = {"profile.managed_default_content_settings.images": 2}
    opts.add_experimental_option("prefs", prefs)

    # "eager" = considera la pagina pronta non appena il DOM è costruito,
    # senza aspettare immagini/script/pubblicità/tracker secondari.
    # È il guadagno di velocità più grande: senza questo, driver.get() può
    # restare "appeso" a lungo su siti con script di terze parti lenti.
    opts.page_load_strategy = "eager"

    if driver_path is None:
        driver_path = ChromeDriverManager().install()

    service = Service(driver_path)
    driver  = webdriver.Chrome(service=service, options=opts)

    # Timeout duro: se una pagina non è pronta entro PAGE_TIMEOUT secondi,
    # Selenium interrompe il caricamento invece di aspettare all'infinito.
    driver.set_page_load_timeout(PAGE_TIMEOUT)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


# ── ESTRAZIONE PREZZO ─────────────────────────────────────────────────────────

def extract_price_from_html(html: str) -> float | None:
    soup = BeautifulSoup(html, "lxml")

    # 1. JSON-LD schema.org
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data  = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") in ("Product", "product"):
                    offers    = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0]
                    price_raw = offers.get("price") or offers.get("lowPrice")
                    if price_raw:
                        return float(str(price_raw).replace(",", "."))
        except Exception:
            pass

    # 2. Meta og:price
    meta = soup.find("meta", property="product:price:amount")
    if meta and meta.get("content"):
        try:
            return float(meta["content"].replace(",", "."))
        except ValueError:
            pass

    # 3. Selettori CSS comuni
    for sel in [
        "[itemprop='price']", ".woocommerce-Price-amount", ".product-price",
        ".price", ".our_price_display", ".special-price", ".current-price",
        "[class*='price']", "[class*='prezzo']", "[id*='price']",
    ]:
        for tag in soup.select(sel)[:4]:
            price = _parse_price_text(tag.get_text(separator=" ", strip=True))
            if price:
                return price

    # 4. Regex grezza
    full_text = soup.get_text(separator=" ")
    matches   = re.findall(r"€\s*(\d[\d.,]+)|\b(\d[\d.,]+)\s*€", full_text)
    prices    = [p for g1, g2 in matches for p in [_parse_price_text(g1 or g2)] if p]
    if prices:
        from collections import Counter
        return Counter(prices).most_common(1)[0][0]

    return None


def _parse_price_text(text: str) -> float | None:
    text = text.strip()
    for pattern, transform in [
        (r"(\d{1,3}(?:\.\d{3})*,\d{2})", lambda s: s.replace(".", "").replace(",", ".")),
        (r"(\d+),(\d{2})$",              lambda s: s.replace(",", ".")),
        (r"(\d+\.\d{2})",               lambda s: s),
        (r"\b(\d{2,5})\b",              lambda s: s),
    ]:
        m = re.search(pattern, text)
        if m:
            try:
                v = float(transform(m.group(0)))
                if 10 < v < 50000:
                    return v
            except ValueError:
                pass
    return None


# ── RICERCA SUI COMPETITOR ────────────────────────────────────────────────────

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100


def search_on_site(driver, site: str, query: str, original_title: str) -> list[dict]:
    """
    Cerca sul motore interno del sito usando la query pulita (AI o fallback).
    Il match di similarità usa comunque il titolo originale per confronto corretto.
    """
    url = SEARCH_URLS.get(site, f"https://www.{site}/search?q={{query}}").format(
        query=quote_plus(query)
    )
    try:
        driver.get(url)
        WebDriverWait(driver, PAGE_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(0.6)
    except Exception:
        return []

    soup       = BeautifulSoup(driver.page_source, "lxml")
    candidates = []
    seen_urls  = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if href.startswith("/"):
            href = f"https://www.{site}{href}"
        if not href.startswith("http") or site not in href:
            continue
        if len(text) < 5 or href in seen_urls:
            continue
        if any(s in href.lower() for s in SKIP_SEGMENTS):
            continue

        # Similarità rispetto alla query AI (più precisa) E al titolo originale
        score = max(similarity(query, text), similarity(original_title, text))
        if score >= SIMILARITY_THRESHOLD:
            seen_urls.add(href)
            candidates.append({"title": text, "url": href, "score": score})

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:3]


def find_competitor_price(driver, site: str, query: str, original_title: str,
                          my_price: float = 0.0) -> dict | None:
    candidates = search_on_site(driver, site, query, original_title)
    time.sleep(REQUEST_DELAY)
    for cand in candidates:
        # Scarta URL che sembrano pagine di categoria, non di prodotto singolo
        if _is_category_url(cand["url"]):
            continue

        try:
            driver.get(cand["url"])
        except Exception:
            # Pagina troppo lenta o non raggiungibile: passa al prossimo candidato
            continue

        time.sleep(0.4)
        price = extract_price_from_html(driver.page_source)
        time.sleep(REQUEST_DELAY)

        if not price:
            continue

        # Scarta prezzi fuori da un range plausibile rispetto al tuo prezzo
        # Accetta solo prezzi tra il 30% e il 200% del tuo prezzo
        if my_price > 0:
            ratio = price / my_price
            if ratio < 0.30 or ratio > 2.00:
                continue

        return {
            "site":        site,
            "title":       cand["title"],
            "price":       price,
            "url":         cand["url"],
            "match_score": round(cand["score"], 1),
        }
    return None


def _is_category_url(url: str) -> bool:
    """
    Rileva URL di pagine categoria/lista (da scartare) vs pagine prodotto singolo.
    """
    url_lower = url.lower()
    category_patterns = [
        r"/collections/[^/]+$",        # Shopify: /collections/scarpe
        r"/categoria/[^/]+$",           # WooCommerce: /categoria/scarponi
        r"/category/[^/]+$",
        r"/c/[^/]+$",
        r"/reparto/[^/]+$",
        r"/-[0-9]+$",                   # Prestashop: /scarpe-trekking-226
        r"/scarpe-[a-z]+-[a-z]+/$",    # URL generici tipo /scarpe-trekking-donna/
        r"/[a-z-]+-[0-9]{2,4}/?$",     # path che finisce con codice categoria numerico
    ]
    path = url.split("//")[-1].split("?")[0]
    segments = [s for s in path.split("/") if s]
    if len(segments) <= 2 and url_lower.endswith("/"):
        return True
    for pat in category_patterns:
        if re.search(pat, url_lower):
            return True
    return False


# ── REPORT TXT ────────────────────────────────────────────────────────────────

def write_txt_report(alerts_data: list[dict], total: int, no_match: int, output_path: str) -> str:
    now   = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = []

    lines.append("=" * 65)
    lines.append("  COMPETITOR PRICE CHECKER — Outdoor Ecommerce")
    lines.append(f"  Report generato il: {now}")
    lines.append("=" * 65)
    lines.append("")
    lines.append(f"  Prodotti analizzati   : {total}")
    lines.append(f"  Senza corrispondenza  : {no_match}  (prodotti esclusivi)")
    lines.append(f"  Prezzi da rivedere    : {len(alerts_data)}")
    lines.append("")
    lines.append("=" * 65)
    lines.append("  PRODOTTI PIU' CARI DELLA CONCORRENZA")
    lines.append("=" * 65)
    lines.append("")

    for i, entry in enumerate(alerts_data, 1):
        title     = entry["title"]
        my_price  = entry["my_price"]
        cheaper   = entry["cheaper_results"]
        query     = entry.get("search_query", "")
        cheapest  = min(cheaper, key=lambda x: x["price"])
        diff_pct  = ((my_price - cheapest["price"]) / my_price) * 100
        suggested = round(cheapest["price"] * 0.99, 2)

        lines.append(f"[{i}] {title}")
        if query and query.lower() != title.lower():
            lines.append(f"    Query usata       : {query}")
        lines.append(f"    Tuo prezzo        : €{my_price:.2f}")
        lines.append("")

        for r in sorted(cheaper, key=lambda x: x["price"]):
            delta = my_price - r["price"]
            crown = "*** " if r["price"] == cheapest["price"] else "    "
            lines.append(f"  {crown}{r['site']}: €{r['price']:.2f}  (-€{delta:.2f} rispetto a te)")
            lines.append(f"       {r['url']}")

        lines.append("")
        lines.append(f"    CONSIGLIO: abbassa a €{suggested:.2f}  (-{diff_pct:.1f}% sul tuo prezzo)")
        lines.append("")
        lines.append("-" * 65)
        lines.append("")

    if not alerts_data:
        lines.append("  Nessun prodotto risulta piu' caro della concorrenza. Ottimo!")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


# ── ANALISI PRINCIPALE ────────────────────────────────────────────────────────

@dataclass
class AnalysisResult:
    alerts_data: list[dict] = field(default_factory=list)
    no_match:    int = 0
    total:       int = 0
    elapsed:     float = 0.0
    report_path: Optional[str] = None
    interrotto:  bool = False
    errore:      Optional[str] = None


def run_analysis(
    df: pd.DataFrame,
    competitor_sites: list[str],
    use_ai: bool,
    api_key: Optional[str],
    output_dir: str,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    alert_cb: Optional[Callable[[dict], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
    stop_event: Optional[Event] = None,
    min_discount_pct: float = 0.0,
) -> AnalysisResult:
    """
    Esegue l'analisi completa dei prodotti sui siti competitor.

    Per velocità, viene avviato un browser Chrome separato per ciascun sito
    competitor, e tutti i siti vengono interrogati IN PARALLELO per ogni
    prodotto (invece che uno dopo l'altro).

    Callback:
        progress_cb(current, total, label)  — chiamata dopo ogni prodotto analizzato
        alert_cb(entry_dict)                 — chiamata quando un prodotto risulta più caro
        log_cb(message)                      — messaggi di stato generici

    stop_event: se impostato (set()), interrompe l'analisi al prossimo ciclo.
    """
    result = AnalysisResult(total=len(df))
    stop_event = stop_event or Event()

    if log_cb:
        log_cb("Scarico/verifico il driver di Chrome...")

    try:
        driver_path = ChromeDriverManager().install()
    except Exception as e:
        result.errore = f"Impossibile scaricare/individuare ChromeDriver: {e}"
        return result

    if log_cb:
        log_cb(f"Avvio Chrome per {len(competitor_sites)} siti competitor...")

    drivers: dict[str, webdriver.Chrome] = {}
    for site in competitor_sites:
        try:
            drivers[site] = create_driver(headless=True, driver_path=driver_path)
        except Exception as e:
            if log_cb:
                log_cb(f"Impossibile avviare Chrome per {site}: {e}")

    if not drivers:
        result.errore = "Impossibile avviare Chrome per nessun sito competitor."
        return result

    if log_cb:
        log_cb("Chrome avviato correttamente. Analisi in corso...")

    start_time = time.time()

    try:
        with ThreadPoolExecutor(max_workers=len(drivers)) as executor:
            for i, row in df.iterrows():
                if stop_event.is_set():
                    result.interrotto = True
                    break

                original_title = row["Title"]
                my_price       = float(row["Variant Price"])

                search_query = make_search_query(original_title, use_ai, api_key)

                futures = {
                    executor.submit(
                        find_competitor_price, drv, site, search_query, original_title, my_price
                    ): site
                    for site, drv in drivers.items()
                }

                competitor_results = []
                for future in as_completed(futures):
                    try:
                        r = future.result()
                    except Exception:
                        r = None
                    if r:
                        competitor_results.append(r)

                if stop_event.is_set():
                    result.interrotto = True
                    break

                is_no_match = not competitor_results
                if is_no_match:
                    result.no_match += 1

                cheaper = [
                    r for r in competitor_results
                    if r["price"] < my_price
                    and ((my_price - r["price"]) / my_price * 100) >= min_discount_pct
                ]

                if progress_cb:
                    progress_cb(i + 1, result.total, original_title)

                if cheaper:
                    entry = {
                        "title":           original_title,
                        "my_price":        my_price,
                        "cheaper_results": cheaper,
                        "search_query":    search_query,
                    }
                    result.alerts_data.append(entry)
                    if alert_cb:
                        alert_cb(entry)

    except Exception as e:
        result.errore = str(e)

    finally:
        for drv in drivers.values():
            try:
                drv.quit()
            except Exception:
                pass

    result.elapsed = time.time() - start_time

    # Report
    ts          = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = os.path.join(output_dir, f"report_prezzi_{ts}.txt")
    try:
        write_txt_report(result.alerts_data, result.total, result.no_match, output_path)
        result.report_path = output_path
    except Exception as e:
        if log_cb:
            log_cb(f"Errore durante il salvataggio del report: {e}")

    return result
