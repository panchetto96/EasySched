# EasySched - Hostel Scheduler

Applicazione desktop per Windows che genera automaticamente i turni del personale di un ostello su cicli rotanti di 28 giorni, rispettando vincoli di copertura, giorni consecutivi e weekend liberi. Funziona interamente offline.

## Funzionalità

- Gestione dipendenti (full-time e part-time), con attivazione/disattivazione e blocco di riposo settimanale fisso opzionale.
- Generazione automatica del turno su ciclo di 28 giorni (4 settimane), con navigazione tra cicli precedenti e successivi.
- Gestione assenze per giorno: ferie, malattia, permesso. Le assenze vengono rispettate dal generatore.
- Vista a griglia e vista calendario del turno.
- Segnalazione dei casi non fattibili: se la copertura minima non è raggiungibile, viene mostrato il dettaglio dei giorni scoperti.
- Import/export del turno e dei dipendenti in CSV.
- Interfaccia bilingue italiano/inglese, commutabile a runtime.
- Persistenza locale su file JSON, nessun server né connessione di rete.

## Stack tecnologico

- Python 3.12+
- PyQt6 (interfaccia grafica)
- pytest (test)
- PyInstaller (pacchetto eseguibile Windows)
- Persistenza su JSON, nessun database

## Architettura

Separazione netta tra logica di dominio (`core/`, senza dipendenze dalla GUI) e interfaccia (`ui/`).

- `core/models.py`: dataclass ed enum del dominio (`Employee`, `Leave`, `Schedule`, `ShiftStatus`, ...).
- `core/scheduler.py`: algoritmo di generazione.
- `core/storage.py`: lettura/scrittura JSON (dipendenti, assenze, un file per ciclo).
- `core/csv_io.py`: import/export CSV con validazione e errori puntuali (riga/colonna).
- `ui/`: finestra principale, viste (dipendenti, assenze, griglia, calendario) e traduzioni in `ui/i18n/{it,en}.json`.

Regole principali dell'algoritmo (`generate_schedule`, ciclo di 28 giorni):

- Copertura minima giornaliera: 9 persone al venerdì e al sabato, 8 negli altri giorni.
- Massimo 5 giorni lavorativi consecutivi (limite rigido, `MAX_CONSECUTIVE`).
- Ai full-time viene assegnato un blocco di riposo fisso di due giorni feriali consecutivi (lun-mar ... gio-ven); i blocchi non assegnati vengono distribuiti in modo bilanciato tra i dipendenti.
- Equità sui weekend: ogni full-time riceve un weekend libero per ciclo, alternando venerdì-sabato e sabato-domenica rispetto al ciclo precedente. La settimana del weekend libero viene scelta in modo da non superare il limite di giorni consecutivi.
- Se un dipendente non riesce a ottenere il weekend libero (`WEEKEND_MISSED`), nel ciclo successivo ha priorità e il generatore tenta di assegnargli un secondo weekend libero come recupero.
- Dopo la generazione dei full-time, un passaggio di ribilanciamento sposta giorni di lavoro dai giorni in esubero a quelli sotto organico, poi un passaggio di riparazione converte riposi in lavoro (senza violare il limite di giorni consecutivi).
- I part-time ricevono 14 giorni lavorativi per ciclo, assegnati in priorità ai giorni meno coperti.
- Se dopo tutti i passaggi restano giorni sotto la copertura minima, il risultato è non fattibile e l'elenco dei giorni scoperti viene restituito alla UI.

## Avvio in sviluppo

Requisiti: Python 3.12 o superiore. Comandi per PowerShell su Windows:

```powershell
git clone https://github.com/panchetto96/EasySched.git
cd EasySched
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python main.py
```

Test:

```powershell
pytest
```

In sviluppo i dati vengono salvati in `data/` nella root del progetto. Al primo avvio, se non esistono dipendenti, `main.py` crea un elenco iniziale di esempio (14 full-time e 2 part-time).

## Build dell'eseguibile

Con l'ambiente virtuale attivo e PyInstaller installato (`pip install pyinstaller`):

```powershell
.\build.bat
```

Equivale a `pyinstaller hostel_scheduler.spec --clean --noconfirm`. L'eseguibile (senza finestra console) viene generato in `dist\hostel_scheduler\`. Nella versione pacchettizzata i dati sono salvati nella cartella `data\` accanto all'eseguibile.

## Dati locali

I dati dei dipendenti risiedono in locale in `data/employees.json` (insieme a `leaves.json` e alla cartella `schedules/`). La cartella `data/` è esclusa dal repository tramite `.gitignore`: nessun dato reale è versionato.

## Struttura del progetto

```
.
├── main.py                  # entry point, seed iniziale, scelta cartella dati
├── core/
│   ├── models.py            # modelli di dominio
│   ├── scheduler.py         # generazione turni
│   ├── storage.py           # persistenza JSON
│   └── csv_io.py            # import/export CSV
├── ui/
│   ├── app.py               # QApplication, stile, cartella dati
│   ├── main_window.py       # finestra principale e toolbar
│   ├── views/               # dipendenti, assenze, griglia, calendario
│   └── i18n/                # traduzioni it.json / en.json
├── tests/                   # test pytest (scheduler, models, storage, csv)
├── docs/superpowers/        # specifica di design e piano di implementazione
├── hostel_scheduler.spec    # configurazione PyInstaller
├── build.bat                # script di build
└── pyproject.toml
```
