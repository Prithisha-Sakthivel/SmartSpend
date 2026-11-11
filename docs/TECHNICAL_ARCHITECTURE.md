# SmartSpend Technical Architecture

## Runtime layout

- `run.py` creates and starts the Flask application through `app.create_app`.
- `app/routes/__init__.py` contains the server-rendered routes and validates request data before calling calculation helpers or SQLite.
- `app/services/money.py` implements integer-paise conversion, snapshot-based funds, scheduled commitments, Safe-to-Spend, and the daily Zero-Day Runway simulation.
- `app/services/c_bridge.py` owns the `ctypes` declarations and calls. If the configured DLL is missing, supported pages use explicit Python implementations and show a status message. This is a development fallback, not a claim of native integration.
- `app/db.py` opens one SQLite connection per Flask request context, enables foreign keys and WAL, and initializes the schema from `database/schema.sql`.
- `c_core/include/smartspend.h` defines the exported ABI; separate files in `c_core/src/` implement the transaction list, undo stack, cooling queue, category array, and transaction algorithms; `c_core/tests/test_smartspend.c` is the native C test harness.
- `app/templates`, `app/static/css`, and `app/static/js` contain server-rendered pages, the purple design system, mobile behavior, and Chart.js report visualization.

## Financial calculations

Balance is an explicit user snapshot at the close of the selected local date. Current funds add posted income and subtract posted expenses whose effective `occurred_on` date is later than that snapshot date. If the snapshot is missing, calculations that need current funds are unavailable.

For a horizon of `H` days from today `D`, inclusive end date `E = D + H - 1`:

```text
SafeToSpend = max(0,
    current funds
  + scheduled income due in [D,E]
  - scheduled bills due in [D,E]
  - planned savings due in [D,E]
  - configured safety buffer)
```

Only active unpaid scheduled entries count. Completing bill/income creates a linked transaction in the same database transaction and marks the commitment complete, preventing double counting. Negative un-clamped capacity is retained for the explanation and shown as a separate shortfall.

Runway uses the trailing 30 calendar dates ending today. Historical daily burn is `floor(ordinary posted expenses in those dates / 30)` paise/day; transactions created by completing a scheduled commitment are excluded because that dated commitment is projected separately. Starting cash is simulated day by day, subtracting this fixed burn and that day’s scheduled bills while adding that day’s scheduled income. The first end-of-day balance at or below zero determines the runway. A missing balance or no usable history returns an explanatory unavailable state; a user can enter a manual daily burn. A starting nonpositive balance returns zero days. No zero-burn division is used; projections are capped at ten years.

## Undo and C state

Transaction create/edit/delete and its versioned before/after undo payload are committed atomically in SQLite under `BEGIN IMMEDIATE`. Events also retain an optional scheduled-commitment or cooling-off parent reference. On undo, the latest eligible user event IDs are pushed in order to the C stack and the stack top selects the event to process. Python validates the current row against the stored expected after-image, applies the inverse and restores a linked parent item's workflow status in the same SQLite transaction. It marks the event consumed atomically and leaves it unconsumed if rollback occurs. Undo is user-scoped, survives restarts and workers, and is bounded to the latest 50 unconsumed actions.

The C linked list is constructed from the current user’s transaction rows; the queue orders that user’s cooling-off entries; category arrays aggregate report expenses; Quick Sort ranks expenses by amount descending then ID ascending; binary search checks the transaction array sorted by ID. These C values are request-level working data and SQLite remains authoritative.

## Windows native build

Use Visual Studio Build Tools or Visual Studio 2022 with the MSVC x64 compiler and Windows SDK. From **x64 Native Tools Command Prompt for VS**, run `build_c.bat`. It compiles C11 as a `__cdecl` DLL (`smartspend.dll`) with exported fixed-width C ABI functions, compiles the native C unit executable, and runs that test executable. Python must have the same bitness as the DLL. The binding loads with `ctypes.CDLL`, declares argument and return types, uses pointer handles, and pairs allocations with C release functions. The compiled DLL is ignored by Git and is reproducibly built from source.

## Security boundaries

Every private repository query includes the authenticated user ID. Passwords use Werkzeug's password hash helpers; reset tokens are random, hashed, short-lived and single use. Forms include a session CSRF token. Avatar uploads are format-decoded, size-limited, re-encoded as JPEG, assigned random names, saved outside the static directory, and served only after owner checks. CSV formula-leading text is prefixed safely before export. Production requires a non-default secret, debug disabled, HTTPS, and configured reset email.
