# Hostel Scheduler — Design Specification

**Date:** 2026-07-01
**Status:** Approved
**Project:** Windows desktop staff management app for a hostel in Florence, Italy

---

## 1. Overview

A single-user, offline Windows desktop application for a hostel manager to generate,
view, and maintain employee shift schedules. The app manages 16 employees (14
full-time, 2 part-time) across rolling 28-day scheduling cycles.

**Non-goals (MVP):**
- No login or multi-user access
- No cloud or internet dependency
- No split-shift tracking (post-MVP)
- No counters or HR dashboards (post-MVP)
- No web interface (distant maybe, not in scope)

---

## 2. Tech Stack

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Best fit for data-heavy scheduling logic; easy unit testing |
| UI framework | PyQt6 | Native Windows feel, built-in table widget, Qt translation system |
| Packaging | PyInstaller | Produces standalone `.exe`; battle-tested on Windows |
| Data storage | JSON files | Human-readable, copyable for backup, no database setup |
| Test framework | pytest | Standard Python testing |

---

## 3. Project Structure

```
hostel-scheduler/
├── main.py                        # entry point
├── core/
│   ├── models.py                  # Employee, Shift, Leave, Schedule dataclasses
│   ├── scheduler.py               # scheduling algorithm (pure Python, no UI imports)
│   ├── storage.py                 # JSON read/write
│   └── csv_io.py                  # CSV import/export
├── ui/
│   ├── app.py                     # QApplication setup, language switching
│   ├── main_window.py             # main window + navigation
│   ├── views/
│   │   ├── schedule_grid.py       # grid view (QTableWidget)
│   │   ├── schedule_calendar.py   # calendar view
│   │   ├── employees.py           # employee management screen
│   │   └── leave.py               # leave/absence management screen
│   └── i18n/
│       ├── it.json                # Italian strings (primary)
│       └── en.json                # English strings
├── data/                          # lives next to .exe at runtime
│   ├── employees.json
│   ├── leaves.json
│   └── schedules/                 # one JSON file per 28-day cycle
└── tests/
    └── test_scheduler.py          # pytest unit tests for all scheduling rules
```

**Key constraint:** `core/` has zero UI imports. The scheduler is testable without
launching the UI.

---

## 4. Employees (Current Data)

| Name | Type |
|---|---|
| Marco | Full-time |
| Linda | Full-time |
| Luca | Full-time |
| Varinia | Full-time |
| Emilia | Full-time |
| Leia | Full-time |
| Jo | Full-time |
| Denise | Full-time |
| Maurizio | Full-time |
| Pia | Full-time |
| Luisa | Full-time |
| Ivo | Full-time |
| Surbhi | Full-time |
| Julian | Full-time |
| Gioia | Part-time |
| Guido | Part-time |

---

## 5. Business Rules

### 5.1 Schedule Cycle

- **28-day rolling window.** The manager picks any start date; the app generates
  days 1–28 from that date with no forced alignment to Monday or month boundary.
- Day-of-week is derived from the real calendar date, so all weekday-specific rules
  apply correctly regardless of start date.

### 5.2 Shift Counts per 28-day Cycle

- **Full-time:** 20 working days, 8 rest days
- **Part-time:** 12–16 working days (flexible target)

### 5.3 Minimum Daily Staffing

| Day | Minimum workers |
|---|---|
| Sunday–Thursday | 8 |
| Friday–Saturday | 9 |

### 5.4 Rest Blocks — Full-time Employees

1. Each full-time employee has a **fixed rest block**: 2 consecutive rest days per
   7-day period ("blocco fisso").
2. The **Saturday–Sunday pair is excluded** as a fixed rest block.
3. If the fixed block includes Friday, Saturday may be the second day — but
   **maximum 2 times per cycle** (i.e., at most 2 of the 4 seven-day spans).
4. Each full-time employee is entitled to **1 free weekend per 28-day cycle**:
   either Fri–Sat or Sat–Sun (chosen to maximize fairness).
5. **Maximum 5 consecutive working days** per stretch.
   - Exception: may extend to **6 consecutive days** only during a rest-block
     transition (e.g., switching from fixed-block week to free-weekend week).

### 5.5 Fallback Rule (Infeasibility)

If the schedule cannot be satisfied with strict 2-day fixed blocks:
- Assign **1 fixed pivot day** + rotate the adjacent day week by week.
- Example: pivot = Tuesday → block alternates Mon–Tue / Tue–Wed each week.
- The engine records which employees were placed on fallback, visible to the manager.

### 5.6 Part-time Scheduling

Part-time employees are scheduled **after** full-time employees to fill remaining
staffing gaps. Their working days are distributed evenly across the cycle, targeting
14 days (midpoint of 12–16 range) unless gaps require more.

---

## 6. Data Model

### 6.1 `employees.json`

```json
[
  {
    "id": "<uuid>",
    "name": "Marco",
    "type": "full_time",
    "fixed_rest_block": [1, 2],
    "active": true
  }
]
```

- `fixed_rest_block`: array of two integers, 0 = Monday … 6 = Sunday.
  `null` means the algorithm assigns the block.
- `active`: false means the employee is hidden from scheduling (soft delete).

### 6.2 `leaves.json`

```json
[
  {
    "employee_id": "<uuid>",
    "date": "2025-07-03",
    "type": "ferie"
  }
]
```

- `type` values: `ferie` (holiday), `malattia` (sick leave), `permesso` (permission).
- Absent employees are excluded from scheduling for those dates.
- No counters or totals tracked in MVP.

### 6.3 `schedules/<start-date>.json`

```json
{
  "start_date": "2025-07-01",
  "generated_at": "2025-06-28T14:00:00",
  "days": [
    {
      "date": "2025-07-01",
      "shifts": [
        { "employee_id": "<uuid>", "status": "work" }
      ]
    }
  ],
  "exceptions": [
    {
      "employee_id": "<uuid>",
      "type": "six_day_stretch",
      "date": "2025-07-05"
    }
  ]
}
```

- `status` values: `work`, `rest`, `ferie`, `malattia`, `permesso`, `override`.
- `override` marks any cell the manager edited manually after generation.
- `exceptions` carries forward to the next cycle so the same employee is not
  penalized twice (e.g., who already had a 6-day stretch).
- Each schedule file is self-contained; old files can be archived without impact.

---

## 7. Scheduling Engine (`core/scheduler.py`)

The engine is a pure function: given employees, leaves, and a start date, it returns
a `ScheduleResult`. No side effects, no UI calls.

### 7.1 Output Type

```python
@dataclass
class ScheduleResult:
    schedule: Schedule | None
    feasible: bool
    exceptions: list[ScheduleException]   # six-day stretches, fallback activations
    warnings: list[Warning]               # staffing close to minimum but met
    errors: list[StaffingShortfall]       # days that cannot be staffed
```

### 7.2 Algorithm Steps

1. **Pre-processing**
   - Mark leave days as unavailable per employee.
   - Load previous cycle's exceptions to inform fairness weighting.

2. **Fixed rest block assignment**
   - Employees with an explicit `fixed_rest_block` keep it.
   - Employees with `null` get one assigned: the algorithm distributes blocks
     across the week to avoid clustering, excluding Sat–Sun.

3. **Draft generation**
   - For each of the 28 days, derive day-of-week from the calendar date.
   - Divide the 28 days into 4 consecutive 7-day spans (days 1–7, 8–14, 15–21,
     22–28). Apply each full-time employee's fixed rest block (2 rest days) within
     each span; the specific days are determined by the employee's `fixed_rest_block`
     weekday pair mapped onto the real calendar dates in that span.
   - Apply free weekend entitlement (1 per cycle): assign Fri–Sat or Sat–Sun per
     employee. Which weekend type (Fri–Sat vs. Sat–Sun) is stored in the cycle's
     `exceptions` array and carried forward so the choice rotates fairly across
     cycles — no employee receives the same weekend type every cycle.
   - Mark all other available days as working days.

4. **Constraint validation**
   - Verify minimum staffing per day.
   - Verify consecutive working day limit (≤ 5, or ≤ 6 at rest-block transitions).
   - On violation, attempt local repair: swap a rest day between two employees
     who can absorb the change without creating a new violation.

5. **Fallback activation**
   - If local repair fails after a bounded number of attempts, activate the pivot-day
     fallback for the affected employee. Record in `exceptions`.

6. **Infeasibility report**
   - If minimum staffing cannot be met even with fallback (e.g., mass leave), return
     `feasible=False` with a `StaffingShortfall` per affected day.

7. **Part-time scheduling**
   - After full-time schedule is fixed, assign part-time employees to remaining
     under-staffed days, targeting 14 working days per cycle.

### 7.3 Test Coverage Requirements

Every rule gets an isolated pytest test with a minimal employee set:

- Fixed rest block exclusion (no Sat–Sun block)
- Free weekend assignment (1 per cycle)
- Consecutive day limit (5-day max, 6-day exception at transitions)
- Minimum staffing (Sun–Thu ≥ 8, Fri–Sat ≥ 9)
- Fallback rule activation
- Infeasibility detection and structured error output
- Part-time day count (12–16 range)
- Exceptions carry-over across cycles

---

## 8. UI Design

### 8.1 Main Window Structure

```
┌─────────────────────────────────────────────────────────────┐
│  [Turni]  [Dipendenti]  [Assenze]                [IT | EN] │  ← nav bar
├─────────────────────────────────────────────────────────────┤
│  Ciclo: 01 Lug – 28 Lug 2025    [← Prec]  [Succ →]       │
│  [Genera Turni]  [Esporta CSV]  [Importa CSV]              │
│  [Vista Griglia]  [Vista Calendario]                       │
│  ─────────────────────────────────────────────────────     │
│  < active view >                                           │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Grid View (Vista Griglia)

- Rows = employees; columns = days 1–28 with headers showing date + weekday
  abbreviation (e.g., "1 Lun", "2 Mar").
- Cell color codes:
  - **L** (Lavoro) — green
  - **R** (Riposo) — grey
  - **F** (Ferie) — blue
  - **M** (Malattia) — orange
  - **P** (Permesso) — yellow
  - **O** (Override) — purple border on the cell
- Click any cell → dropdown to override status manually.
- Row right-margin: "Giorni lavorati: 20/20"
- Column bottom margin: staffing count per day, highlighted red if below minimum.

### 8.3 Calendar View (Vista Calendario)

- Standard monthly calendar grid (or 28-day equivalent if cycle spans two months).
- Each day cell lists working employees (green text) and absent employees (grey).
- Days below minimum staffing are tinted red.
- Read-only; edits are made in the grid view.

### 8.4 Employee Management Screen

- Sortable list of employees with **Aggiungi / Modifica / Disattiva** buttons.
- Edit dialog fields: name, type (full-time / part-time), fixed rest block
  (dropdown of valid Mon–Sun consecutive pairs, or "Algoritmo").

### 8.5 Leave Management Screen

- Left column: employee list.
- Right column: date-range picker + absence type selector + "Aggiungi assenza" button.
- Existing absences shown in a table below with a delete button per row.

### 8.6 Infeasibility / Exception Panel

- Dismissible banner at top of schedule view when the scheduler reports problems.
- Lists affected days and employees clearly in the active language.
- Exceptions (6-day stretches, fallback activations) shown as a collapsible section.

### 8.7 Visual Style

- Flat design, muted blue/white palette.
- Qt stylesheets applied globally for consistent look.
- Large click targets; all controls labelled with text (no icon-only buttons).

---

## 9. CSV Import / Export

### 9.1 Schedule Export (`turni_YYYY-MM-DD.csv`)

```
# start_date=2025-07-01,generated_at=2025-06-28T14:00:00
employee,2025-07-01,2025-07-02,...,2025-07-28
Marco,L,R,...,L
Linda,F,L,...,R
```

- Status codes: `L` (work), `R` (rest), `F` (ferie), `M` (malattia), `P` (permesso),
  `O` (override). Language-neutral by design.

### 9.2 Employee Export (`dipendenti.csv`)

```
id,name,type,fixed_rest_block,active
<uuid>,Marco,full_time,"1,2",true
```

### 9.3 Import Rules

1. Validate columns and values before touching any stored data.
2. On validation failure: show a clear error naming the offending row/column. No partial import.
3. On success: prompt the manager to confirm before overwriting existing data.
4. Round-trip guarantee: export → import → export produces identical CSV bytes
   (same column order, same date format, same status codes).

---

## 10. Bilingual Support

- All user-visible strings keyed in `ui/i18n/it.json` (Italian, primary) and
  `ui/i18n/en.json` (English).
- Global `tr(key)` function used by all UI components.
- Language toggle (`IT | EN`) in the nav bar switches instantly without restart.
  All visible labels and messages re-render immediately.
- Date display respects locale:
  - Italian: `1 luglio 2025`
  - English: `1 July 2025`
- CSV files use ISO dates and language-neutral status codes regardless of active language.

---

## 11. Packaging

- PyInstaller produces a single-folder distribution containing `hostel_scheduler.exe`
  and all dependencies.
- The `data/` folder is created next to the `.exe` on first run if it does not exist.
  Seed data (the 16 employees) is written on first launch.
- Target: Windows 10 and Windows 11, x64, no Python installation required.
- Estimated binary size: 30–50 MB.

---

## 12. Post-MVP (Out of Scope Now — Design for Extensibility)

- Manual assignment of fixed rest blocks per employee (UI already supports this via
  the "Algoritmo" dropdown; backend is wired for it)
- Override minimum staffing for individual days (Christmas, New Year's Eve)
- Split shifts: morning / evening tracking
- Counters: days worked, free weekends earned, mornings/evenings worked
- Employee history / fairness tracking dashboard
- Web interface (distant plan; Python core logic would need a REST wrapper)

---

## 13. Success Criteria

1. A non-technical manager can use the app without a manual.
2. Schedule generation always respects all business rules, or explains clearly why it cannot.
3. CSV round-trip: export → re-import produces byte-identical data.
4. All core scheduling logic covered by automated pytest tests.
5. App runs offline on a stock Windows 10/11 machine with no installation dependencies.
