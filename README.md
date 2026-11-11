# SmartSpend

SmartSpend is a Python-first personal finance web application for tracking transactions, planning around commitments, and understanding short-term spending capacity. Flask serves server-rendered pages; SQLite stores durable data; vanilla JavaScript and the locally bundled Chart.js library add small interactions and visual summaries. A C DLL implements the required data structures and algorithms and is called from Python with `ctypes` when built.

## Windows quick start

1. Install Python 3.10 or newer. Install Visual Studio Build Tools with the C++ workload, MSVC x64 compiler, and Windows SDK to build the C DLL.
2. Double-click `setup.bat` to create `.venv` and install Flask and Pillow.
3. Copy `.env.example` to `.env`. The app reads its simple `KEY=VALUE` settings at startup. `run.bat` enables local debug mode by default only when no `SMARTSPEND_DEBUG` setting exists. Before shared or deployed use, set a unique `SMARTSPEND_SECRET` and `SMARTSPEND_DEBUG=0`.
4. Open **x64 Native Tools Command Prompt for VS** and run `build_c.bat`. It builds `c_core\build\smartspend.dll` from the separate C modules, compiles and runs the C unit test executable. If `cl.exe` cannot be found, start the correct Developer Command Prompt and retry.
5. Run `seed_demo.bat` and enter a demo password of at least 10 characters, or create a new account through the website.
6. Run `run.bat`, then open `http://127.0.0.1:5000`.

Do not expose the debug server to a public network. For deployment, use HTTPS, a random secret, debug off, a protected database/upload directory, and a configured SMTP server for password recovery.

## Useful commands

```powershell
# Python application tests
python -m unittest discover -s tests -v

# C library build and C unit tests (from an MSVC x64 Developer prompt)
build_c.bat

# Create/refresh a local demo account; prompts without writing password to code
python scripts/seed_demo.py
```

## Project structure

```text
SmartSpend/
├── app/
│   ├── routes/                 Flask routes and request handling
│   ├── services/               Money calculations and C DLL bridge
│   ├── templates/              Server-rendered HTML pages
│   └── static/                 Shared CSS and JavaScript
├── c_core/
│   ├── include/                Public C interface
│   ├── src/                    Data structures and algorithms
│   ├── tests/                  Native C checks
│   └── build/                  Generated DLL and compiler outputs
├── database/
│   ├── schema.sql              Current SQLite schema
│   └── migrations/             Additive schema migrations
├── docs/                       Project, architecture and feature guides
├── instance/                   Local SQLite database and private avatars
├── scripts/                    Demo data utilities
├── tests/                      Python application and C bridge tests
├── config.py                   Environment-based configuration
├── run.py                      Flask application entry point
├── requirements.txt            Python dependencies
├── .env.example                Safe configuration template
├── build_c.bat                 MSVC x64 DLL build and native test
├── setup.bat / run.bat         Windows setup and launch
├── seed_demo.bat               Demo account/data setup
└── README.md
```

The repository keeps the generated DLL under `c_core/build` because the Python bridge loads it from there. Local `.venv`, SQLite data, uploaded avatars, Python bytecode caches, and compiler intermediates are runtime or generated files and are not source files.

## Motion and accessibility

The interface uses short purple-themed hover/focus transitions, a restrained entrance for page content and notices, exact-value count-ups for loaded INR summaries, animated progress indicators, and a live Before You Buy comparison. The primary CTA pointer response is capped to a few pixels and only runs on fine pointers. Authentication provides password visibility and brief submit feedback. Locally served Chart.js animates database-backed dashboard, insight, and report charts. Motion is disabled or reduced under `prefers-reduced-motion`; no additional animation library is required.

Set the same environment variables listed in `.env.example` before running commands if you need a custom database, secret, mail server, upload location, or DLL path. `SMARTSPEND_DEBUG=1` is for local development only. A `C DLL unavailable` notice means the app is running in transparent Python fallback mode; C integration is active only after the DLL is built and loadable by the same architecture of Python.

## Feature guide

- Sign up, sign in/out, request a one-use password reset, edit profile, change password, and upload/remove an avatar.
- Dashboard: manually maintained balance snapshot, monthly income/expenses, Safe-to-Spend, runway, budgets, goals, and upcoming commitments.
- Transactions: create, edit, delete, filter, search, and undo the last 50 transaction changes. Undo events are persisted with before/after images in SQLite and processed LIFO through the C stack when its DLL is available.
- Budgets: category-specific monthly limits and overspend/near-limit states.
- Safe-to-Spend: current funds plus scheduled income, less scheduled bills, planned savings and buffer over the selected inclusive horizon.
- Zero-Day Runway: fixed trailing-30-day posted expense average, plus dated scheduled bills/income. A manual daily burn override is accepted by the calculation service, with missing-data states explained in the UI.
- Before You Buy: preview balance, safe amount, category allowance and estimated runway effect; record now or put on a two-day cooling-off queue.
- Commitments: upcoming bills, income and savings; due dates, status and weekly/monthly recurrence occurrences.
- Insights: repeated small expenses, repeated descriptions, expensive categories, unusual high expenses, exceeded budgets and a transparent savings suggestion.
- Goals and challenges: contribution history, fixed-cadence/target challenge tracking, explicit daily no-spend check-ins, and a consecutive contribution streak.
- Reports: filtered income/expense totals, category breakdown, monthly budget performance, savings goal progress, largest expense ranking, weekly summary and user-scoped CSV export.
- Settings: financial assumptions, account/profile details, avatar, password, and user-scoped demo reset.

## Architecture and data handling

See [the project plan](docs/PROJECT_PLAN.md), [the architecture](docs/ARCHITECTURE.md), and [the UI/UX guidelines](docs/UI_UX_GUIDELINES.md). SQLite is authoritative and stores money as integer paise. Every user-owned query is scoped to the session's user ID. The C structures are transient and rebuildable, not persistence. Password reset tokens are hashed at rest; avatar files are re-encoded, stored outside static serving, and fetched only by their owner. CSV values are escaped against spreadsheet formula execution.

## Student demonstration notes

Show a user account, set a balance snapshot, add a few transactions and commitments, view the estimates and budget, run Before You Buy, complete an undo, record a goal contribution, inspect the report, and download a CSV. Then show the C header/source, run `build_c.bat`, and point out the application C status indicator. Test with two accounts to demonstrate data isolation. Demo data is clearly marked and can be reset from Settings.

## Known limitations

- The application is local single-currency INR software; it does not connect to banks or execute payments.
- Recurrent commitments are materialized as dated occurrences by the app; users should review the upcoming list for schedule changes.
- A no-spend challenge counts only days explicitly checked in; if the ledger already records spending in the selected category for a date, the app rejects a “met” check-in for that day.
- Password reset delivery outside local development requires SMTP configuration. The development reset link appears only when debug mode is on.
- Financial projections are deterministic estimates based on user-entered balances, ledger records, and known commitments, not guaranteed forecasts.
