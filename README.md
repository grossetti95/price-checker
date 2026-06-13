# Competitor Price Checker — Versione Desktop (GUI)

Applicazione desktop con interfaccia grafica per confrontare i prezzi del
catalogo Shopify con quelli dei siti competitor, pensata per essere usata
anche da chi non ha esperienza di terminale (titolare, colleghi).

## Struttura del progetto

```
CompetitorPriceChecker/
├── core.py                     # logica di business (CSV, Selenium, AI, report)
├── config.py                   # gestione impostazioni salvate localmente
├── gui_app.py                  # interfaccia grafica (avvio del programma)
├── requirements.txt
├── CompetitorPriceChecker.spec # configurazione PyInstaller
└── icon.ico                    # (opzionale) icona dell'app
```

I vecchi file `price_checker.py` e `ui.py` (versione da terminale) non sono
più necessari: tutta la logica è stata spostata in `core.py` e collegata
alla nuova interfaccia.

---

## 1. Requisiti sul PC dove crei il `.exe`

- **Windows 10/11**
- **Python 3.11 o 3.12** installato (https://www.python.org/downloads/ —
  durante l'installazione spunta "Add Python to PATH")
- **Google Chrome** installato (serve sempre, sia per testare sia per i PC
  dei colleghi: lo script lo pilota in background)

## 2. Preparazione ambiente

⚠️ **Usa un ambiente Python "pulito", NON l'Anaconda "base"**. Un ambiente
Anaconda base contiene centinaia di librerie (Jupyter, matplotlib, PyQt5 *e*
PySide6, sphinx, ecc.) che PyInstaller cerca di analizzare tutte, causando
build lentissimi, file enormi, e talvolta errori come:

```
ERROR: Aborting build process due to attempt to collect multiple Qt
bindings packages: ... PyQt5 ... PySide6 ...
```

Lo `.spec` aggiornato esclude già queste librerie come misura di sicurezza,
ma è comunque molto meglio partire da un ambiente dedicato e leggero:

Apri PowerShell nella cartella del progetto e crea un ambiente virtuale:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

(Se hai solo Anaconda installato e `python` non è nel PATH, usa
`C:\Users\TUO_UTENTE\anaconda3\python.exe -m venv venv` per creare il venv,
poi attivalo normalmente con `venv\Scripts\activate`.)

## 3. Test rapido prima del build

Avvia l'app in locale per controllare che tutto funzioni:

```powershell
python gui_app.py
```

Vai nella schermata **⚙ Impostazioni** e:
- inserisci la tua chiave API Anthropic (per la pulizia AI dei titoli)
- controlla/modifica la cartella dove salvare i report
- controlla l'elenco dei siti competitor (uno per riga)
- premi **Salva impostazioni**

Questa configurazione viene scritta in un file locale (NON nel codice, quindi
non finirà mai nel `.exe`):

```
%APPDATA%\CompetitorPriceChecker\config.json
```

## 4. Creazione del `.exe`

Sempre con l'ambiente virtuale attivo:

```powershell
pyinstaller CompetitorPriceChecker.spec
```

Al termine troverai tutto in:

```
dist\CompetitorPriceChecker\
```

Quella cartella (puoi anche zipparla) è l'app completa: contiene
`CompetitorPriceChecker.exe` + tutte le librerie necessarie.

⚠️ **Importante**: consegna ai colleghi l'intera cartella, non solo il
`.exe` — altrimenti non si avvia.

---

## 5. Configurazione sui PC dei colleghi

### La prima volta (la fai tu)

1. Copia la cartella `dist\CompetitorPriceChecker` sul PC del collega
   (es. sul Desktop, o in `C:\Programmi\CompetitorPriceChecker`).
2. Crea un collegamento a `CompetitorPriceChecker.exe` sul Desktop.
3. Avvia l'app **una volta** e vai in **⚙ Impostazioni**: inserisci la
   stessa chiave API Anthropic (o lasciala vuota se non vuoi che usino la
   pulizia AI — funzionerà comunque con il metodo di fallback), controlla i
   siti competitor e la cartella di salvataggio report (es. il Desktop del
   collega), poi **Salva**.

A questo punto il collega deve solo:

1. Doppio click sull'icona
2. **1. Catalogo** → scegliere il file CSV esportato da Shopify
3. **2. Selezione prodotti** → scegliere "Tutti", per parola chiave o per
   brand
4. **3. Analisi** → premere "Avvia analisi" e aspettare
5. **4. Risultati** → vedere i prodotti da rivedere e aprire il report

### Requisiti sul PC del collega

- **Google Chrome installato** (la versione normale, non serve altro)
- **Connessione internet** (per cercare sui siti competitor e, la prima
  volta, per scaricare automaticamente il driver di Chrome compatibile)

Non serve installare Python, né altre librerie: tutto è incluso nel `.exe`.

---

## 6. Aggiornare l'app in futuro

Quando vuoi aggiungere nuovi siti competitor o modificare la logica:

1. Modifica `core.py` (logica) o `gui_app.py` (interfaccia)
2. Rilancia `pyinstaller CompetitorPriceChecker.spec`
3. Sostituisci la cartella `dist\CompetitorPriceChecker` sui PC dei
   colleghi (le loro impostazioni in `%APPDATA%` non vengono toccate)

Per aggiungere nuovi siti competitor **senza ricompilare**, basta che tu
(o anche il titolare) li scriva nella schermata Impostazioni → "Siti
competitor da controllare", uno per riga. Se il sito ha un motore di ricerca
interno diverso da `/search?q=...`, però, ti serve modificare anche
`SEARCH_URLS` in `core.py` e rifare il build.

---

## 7. Note su prestazioni e limiti

- Il browser viene avviato in modalità invisibile ("headless"): i colleghi
  non vedranno finestre di Chrome che si aprono.
- **Velocità**: per ogni prodotto, i siti competitor vengono controllati
  TUTTI IN PARALLELO (un browser separato per ciascun sito, riutilizzato
  per tutto il catalogo). Le pagine vengono considerate "pronte" non appena
  il contenuto principale è caricato (`page_load_strategy = "eager"`), senza
  aspettare pubblicità, tracker o script secondari — questo è il fattore che
  in precedenza causava le attese più lunghe. Con 4 siti, un prodotto richiede
  ora circa 3-8 secondi (anziché 1-3+ minuti).
- Se un sito è particolarmente lento o irraggiungibile, dopo `PAGE_TIMEOUT`
  secondi (10 di default, modificabile in `core.py`) viene saltato per quel
  prodotto, senza bloccare gli altri siti.
- Il pulsante "Interrompi" ferma l'analisi al termine del prodotto in corso
  (non istantaneamente) e salva comunque un report parziale.
- La soglia "% in meno" in fase di analisi permette di nascondere differenze
  di prezzo trascurabili (es. impostando 3%, un competitor che costa solo
  l'1% in meno non genera un alert).
- Con cataloghi molto grandi conviene comunque usare la selezione per brand
  o parola chiave, per analizzare solo i prodotti di interesse.
