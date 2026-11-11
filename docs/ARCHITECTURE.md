# SmartSpend Architecture

## System architecture

SmartSpend is a modular, Python-first Flask application. Flask routes handle HTTP concerns and call Python services. Services validate requests, enforce ownership, run financial calculations, and use repositories for SQLite access. Python also calls the C library for the required data-structure and algorithm operations. SQLite is the durable source of truth; the C library holds transient working structures and can be reconstructed from records. The browser uses server-rendered HTML, CSS, vanilla JavaScript, and Chart.js.

```text
Browser (HTML/CSS/JS + Chart.js)
       | HTTP forms / JSON requests
Flask routes and authentication
       | validated user-scoped service calls
Python services and financial calculations
       |                         |
SQLite repositories             ctypes wrapper
       |                         |
SQLite database             compiled C library
                             list / stack / queue /
                             arrays / quick sort / binary search
```

## Folder structure

```text
smartspend/
├── app/
│   ├── __init__.py              # Flask app factory, CSRF guard and template context
│   ├── db.py                     # connection, schema initialization and upgrades
│   ├── routes/__init__.py        # route groups and user-scoped workflows
│   ├── services/
│   │   ├── money.py              # currency conversion and finance calculations
│   │   └── c_bridge.py           # ctypes ABI, memory and error handling
│   ├── templates/                # server-rendered pages
│   └── static/
│       ├── css/app.css            # purple design system and responsive layouts
│       └── js/                    # progressive enhancements and Chart.js
├── config.py                     # environment-based settings
├── c_core/
│   ├── include/smartspend.h      # exported ABI declarations and fixed-width structs
│   ├── src/                      # separate linked-list, stack, queue, arrays, algorithm modules
│   ├── tests/test_smartspend.c    # native C tests
│   └── build/                    # generated DLL and native test binary (ignored)
├── database/
│   ├── schema.sql                # initial versioned SQLite schema
│   └── migrations/               # additive schema upgrades
├── tests/
│   ├── test_app.py                # routes, auth, DB and finance flows
│   ├── test_c_bridge.py           # Python fallback contract
│   └── test_c_integration.py      # calls through compiled DLL
├── instance/                     # local SQLite DB and instance-only secrets (ignored)
├── scripts/                      # demo seed and maintenance scripts
├── docs/                         # project plan, architecture, design and feature docs
├── run.py                        # local development entry point
├── requirements.txt              # Python dependencies
├── .env.example                  # configuration names, no secrets
├── setup.bat / run.bat / build_c.bat / seed_demo.bat
├── DEVELOPMENT_STATUS.md
└── README.md                     # setup, C build, run, tests, demo
```

## Frontend/backend communication

Flask serves public registration/login pages and authenticated server-rendered pages. Standard form submissions handle core create/edit/delete workflows and remain usable without JavaScript. Small vanilla JavaScript modules provide progressive enhancements such as interactive purchase estimates, date/filter controls, accessible confirmation prompts, and Chart.js visualizations. JSON endpoints may support calculations or chart data where useful; all such routes use the same authentication, validation, ownership checks, and domain services as HTML routes. Templates never contain business calculations or direct database logic.

Forms include CSRF protection, clear field-level errors, and preserve valid inputs after a validation failure. Mutations use POST/redirect/GET where appropriate. Chart data is produced by Python from the signed-in user's filtered records and rendered with labels, units, date ranges, and a text/table alternative.

## Python and C integration

The C library implements and exercises the required structures and algorithms; it does not own durable application state or perform HTTP/database work. Python remains authoritative for business rules, user scoping, validation, paise semantics, and persistence.

Python's `ctypes` wrapper declares every exported function's `argtypes` and `restype`, uses fixed-width integer fields, and centralizes library loading and error conversion. The ABI uses opaque handles where possible. Exported operations return explicit status codes; C-owned allocations have paired release functions, and Python-owned buffers are kept alive for each call. Avoid returning pointers to temporary stack memory or passing compiler-dependent structures without explicit layout checks.

### Windows DLL build and compatibility

- Target 64-bit Windows and 64-bit Python by default. Install the Visual Studio Build Tools C++ workload with the MSVC x64/x86 C compiler and Windows SDK; no C++ implementation is required. Build from the matching **x64 Native Tools Command Prompt** or **Developer PowerShell for VS** so `cl.exe` and the SDK linker are configured.
- From that configured prompt, run the root `build_c.bat`; it creates `c_core\build`, compiles the separate C translation units, builds the native test executable, and runs the tests. Its DLL command is equivalent to:

  ```bat
  cl /nologo /TC /std:c11 /W4 /O2 /LD /DSMARTSPEND_BUILD /I c_core\include c_core\src\transaction_list.c c_core\src\undo_stack.c c_core\src\cooling_queue.c c_core\src\category_array.c c_core\src\transaction_algorithms.c /link /OUT:c_core\build\smartspend.dll
  ```

  The source/header export macro must mark the public API for DLL export while building. Keep a small C test executable build separate from the DLL build. Rebuild when C headers or modules change.
- Compile the C modules as a DLL with `/LD`, the public include directory, and an explicit output path under `c_core/build/`; compile C translation units as C (`/TC`) and export functions using a shared header macro (`__declspec(dllexport)` while building, `dllimport` for consumers if needed). Keep the public function declarations inside `extern "C"` guards for compatibility with a C++ consumer. The root build script and README document this command; generated binaries are not source files.
- Match DLL machine type to Python (`x64` DLL for 64-bit Python, `x86` for 32-bit). Load with `ctypes.CDLL` for the documented `__cdecl` ABI; use `ctypes.WinDLL` only if the whole ABI explicitly uses `__stdcall`. Define `argtypes`/`restype` for every export and use `ctypes.c_int64`/`c_uint64` and other fixed-width equivalents matching the header. Use `ctypes.sizeof`/layout checks for any public structure. An architecture mismatch, missing dependent runtime, or missing DLL must produce an actionable application startup/build error, not a silent Python fallback.
- MSVC is the primary supported Windows toolchain. MinGW-w64/GCC may be documented as an alternative only after confirming calling convention, symbol export, integer layout, and Python/DLL bitness; do not mix incompatible runtime-owned allocations across the boundary. Prefer caller-provided buffers or C allocation/free pairs.

### C module responsibilities

- **Singly linked list:** Maintain an ordered in-memory transaction working set; support append/insert, remove, lookup, traversal, and destruction. SQLite transaction IDs provide stable keys.
- **Stack:** Implement push, peek, pop, and clear for transaction undo. The stack is a per-user in-memory execution structure hydrated from that user's eligible SQLite undo events in ascending sequence order (oldest pushed first, newest at the top). Python performs every inverse operation and owns the database transaction; C determines last-in-first-out ordering only.
- **Queue:** Represent cooling-off purchases ordered by review/creation sequence, with enqueue, peek, dequeue, and removal/update operations. SQLite stores queue entries and status; hydrate the user's active entries at request/service initialization and persist every transition through Python.
- **Arrays:** Aggregate paise totals by stable category identifier or defined category index and provide category-wise expense calculations. Python validates IDs and handles categories not in the fixed built-in set.
- **Quick sort:** Rank expense records by amount (with deterministic tie-breaks such as date and ID) for largest expense/report views. Define sort direction explicitly and test empty/single/equal-value inputs.
- **Binary search:** Search a transaction array sorted by a documented key (for example, stable transaction ID). The Python wrapper or C API must ensure the input is sorted before search; duplicate key behavior is defined and tested.

### Reliable transaction undo

Undo applies to successful create, edit, and delete operations on ledger transactions. In the same SQLite `BEGIN IMMEDIATE` transaction as each mutation, insert an `undo_events` row containing the user, monotonically increasing per-user sequence, operation kind, transaction ID, versioned JSON before-image and after-image (nullable for create/delete as appropriate), creation time, and nullable `undone_at`. The immutable images contain validated transaction fields, including category, description, amount paise, occurred date, and notes. The mutation and undo event commit atomically. Keep a configured bounded number of unconsumed events per user (for example, the latest 50); pruning may remove only older eligible events and must be documented in the UI as the undo limit.

For an undo request, start `BEGIN IMMEDIATE`, query that user's newest non-undone event, and hydrate/push the ordered event IDs into the C stack for that user/request. Peek the top through C and use its ID to load and validate the payload from SQLite. Apply the inverse in Python: undo create by deleting the currently matching created row, undo edit by restoring the before-image, and undo delete by reinserting the before-image with the original ID when available. Check the live row still matches the event's expected after-image (or expected absence) to reject stale/conflicting undo rather than overwrite later changes. Mark the event undone and commit atomically with the inverse. Only after commit pop/refresh the C stack; if the DB operation fails, roll back and leave/rebuild the stack from SQLite. Undo events are not themselves pushed as ordinary undoable mutations. A stale or already-undone request returns a clear conflict and refreshes state. New edits after undo create new events; redo is outside initial scope. Sequence allocation, newest-event selection, and mutation are serialized by `BEGIN IMMEDIATE`; ownership is checked at every query. This persists undo across requests, restarts, and workers, while the C stack remains a working LIFO index and is never the authority.

### Synchronization and lifecycle

SQLite commits happen before the application reports a durable success. After a commit, Python updates the relevant C working structure; if an in-memory update fails, it marks that structure stale and rebuilds it from a user-scoped query rather than rolling back a committed database change. On startup or library reload, C state is empty and rebuilt on demand. Every synchronization query is filtered by authenticated user ID. No C pointer or structure is shared across processes; each Flask worker has independent transient state. Correctness never depends on a specific worker retaining state.

## Financial calculation rules

All rules use integer paise and one explicit local calendar date (`as_of_date`) in the user's configured timezone. Date ranges below are inclusive. Date-only scheduled entries due today count as due today. Python implements canonical formulas; C arrays may accelerate aggregation but must match the exact inputs and results.

### Balance basis

Store a user-entered `available_balance_paise` and `balance_as_of_date` snapshot in settings (or a dedicated balance snapshot table if history is needed). The date means the observed balance at the close of that local calendar day; it is not a bank feed. `current_funds_paise = snapshot_balance_paise + sum(posted income amount_paise - posted expense amount_paise where transaction.occurred_on > balance_as_of_date)`. Only transactions with a later effective date are added, preventing double-counting history already reflected in the snapshot; transactions on or before the snapshot date are assumed included. If no snapshot is set, current funds are unknown; calculations requiring it return unavailable with an onboarding prompt, not an inferred verified balance. Amounts are signed in calculations; no hidden zero clamp on current funds.

### Safe-to-Spend

For as-of date `D` and horizon `H` days (default from settings, minimum 1), let `E = D + H - 1` (inclusive). Define:

`safe_to_spend_paise = max(0, current_funds_paise + scheduled_income(D..E) - scheduled_bills(D..E) - planned_savings_contributions(D..E) - safety_buffer_paise)`.

Scheduled income/bills include only active, unpaid commitments whose due date is in `[D,E]`. A planned savings contribution is an active scheduled commitment classified as savings; do not also subtract a savings goal's historical contribution. The safety buffer is the user's configured nonnegative paise amount, defaulting to zero until set. Include the full amount for each commitment in the interval; do not prorate. Exclude posted ledger transactions from future commitments, and when a commitment is marked paid/received, atomically mark it complete and create the corresponding transaction so it is counted once. If commitments recur, materialize one occurrence per due date or calculate occurrences deterministically without duplicates. Negative raw result is displayed as ₹0 available and separately show the deficit/commitment breakdown. All components and the exact period are visible. Proposed purchases are compared against this amount; a simulation subtracts the proposed amount once and does not persist it.

### Zero-Day Runway

Use the same `current_funds_paise` basis. Define trailing period as the 30 calendar dates `[D-29,D]`. `base_daily_burn_paise = floor(sum(posted expense amount_paise in that period) / 30)`. Posted income is not netted into burn; future income is applied on its scheduled date. Ignore scheduled bills when estimating base burn because they are added separately; this avoids double counting a bill after it posts. Simulate one day at a time beginning with `cash_0 = current_funds_paise`; for each offset `k = 0,1,...`, calculate end-of-day `cash_(k+1) = cash_k - base_daily_burn + scheduled_income_due(D+k) - scheduled_bills_due(D+k)`. The runway is the smallest `k+1` whose end-of-day cash is `<= 0`, and estimated zero date is `D+k`. Include due-today items in the first projected day. Search up to a documented maximum horizon (3650 days); if funds never reach zero within it, report “more than 10 years at this rate,” not an exact infinite runway.

If starting funds are `<= 0`, return 0 days and “at/under zero now.” If trailing history contains no posted expenses, or average burn floors to zero, do not divide by zero or claim infinite days: show “not enough expense history to estimate” and allow a clearly labelled optional user-entered daily burn override. With an override, require a nonnegative integer paise/day; zero burn still simulates scheduled commitments/income, and if those never take cash below zero report the capped horizon. Missing balance snapshot always makes runway unavailable. Explain that the projection assumes a fixed historical burn and only known scheduled items; it is not a forecast guarantee.

## Database schema

Use SQLite foreign keys, `NOT NULL` constraints, check constraints for enumerations/nonnegative amounts, indexes for user/date/category lookups, and UTC ISO-8601 timestamps. Use integer paise for every monetary value, never floating-point storage. All user-owned rows include `user_id`; repositories require the authenticated user ID and include it in reads, updates, and deletes. Enable foreign-key enforcement on every connection.

### Tables

- **users:** `id`, normalized unique `email`, `password_hash`, `display_name`, nullable `avatar_storage_key`, `created_at`, `updated_at`, `is_active`.
- **password_reset_tokens:** `id`, `user_id`, unique `token_hash` (never raw token), `created_at`, `expires_at`, nullable `used_at`. Generate a cryptographically random one-time token; store its hash, use constant-time verification, set a short expiry (for example 30 minutes), and atomically mark used while replacing the password hash. Responses must not reveal whether an email exists. Delivery uses a configured email adapter in deployed environments; local development exposes links only through a clearly development-only mail sink, never production logs.
- **user_settings:** `user_id` (PK/FK), currency code (initially INR), default buffer paise, planning horizon days, nullable user-entered available balance paise and balance snapshot local date, timezone, and preference timestamps.
- **scheduled_commitments:** `id`, `user_id`, `kind` (`bill`/`income`/`savings`), `description`, positive `amount_paise`, `due_on`, nullable category, `status` (`scheduled`/`completed`/`cancelled`), nullable `recurrence_rule` and `series_id` (recurring items materialize one dated row per occurrence with a stable series ID), nullable linked transaction ID, created/updated timestamps. Index `(user_id,status,due_on)`. A completed bill/income links to exactly one posted transaction; completion and transaction creation are one database transaction. Savings commitments reduce safe-to-spend but do not create income/expense ledger transactions automatically.
- **categories:** `id`, `user_id` nullable for built-ins, `name`, `kind`/expense classification, `is_active`, timestamps. Enforce uniqueness per owner and built-in namespace.
- **transactions:** `id`, `user_id`, `type` (`income`/`expense`), `amount_paise` positive integer, `description`, nullable `category_id`, `occurred_on`, optional `notes`, `source`/demo marker, timestamps. Index `(user_id, occurred_on, id)` and `(user_id, category_id, occurred_on)`.
- **budgets:** `id`, `user_id`, `category_id`, `period_type`, `period_start`, `period_end`, `limit_paise`, timestamps. Uniqueness by user/category/period and positive limit constraint.
- **cooling_off_purchases:** `id`, `user_id`, description, `amount_paise`, nullable category, created/review timestamps, status (`pending`/`proceeded`/`cancelled`), optional linked transaction ID, timestamps. Index by user/status/review date.
- **savings_goals:** `id`, `user_id`, name, `target_paise`, `target_date`, status (`active`/`completed`/`archived`), created/updated timestamps.
- **savings_challenges:** `id`, `user_id`, name, `challenge_type` (`target_by_end`/`fixed_cadence`/`no_spend`), `target_paise` (total goal), nullable `installment_paise` (required for fixed cadence), `start_on`, `end_on`, `cadence` (`once`/`daily`/`weekly`/`monthly`), optional `goal_id` and `category_id`, status (`scheduled`/`active`/`completed`/`cancelled`), timestamps. A target-by-end challenge has a total amount; a fixed-cadence challenge has an installment and total target. A no-spend challenge names the category to avoid. Validate target/date ordering, owner consistency, and cadence parameters.
- **goal_contributions:** `id`, `user_id`, nullable `goal_id`, nullable `challenge_id`, positive `amount_paise`, `contributed_on`, optional note, source (`manual`/`challenge`), created timestamp, nullable `reversed_at`, and demo marker. Require at least one of goal/challenge; if both are present they must belong to the same user. One contribution linked to both contributes to each target but is one event in activity. Derive goal and challenge progress from non-reversed scoped events and inclusive challenge date range.
- **challenge_checkins:** `id`, `user_id`, `challenge_id`, `check_on`, result (`met`/`missed`), created timestamp, unique `(user_id,challenge_id,check_on)`. No-spend progress counts explicit check-ins only; unreported days are not inferred as successful.
- **undo_events:** `id`, `user_id`, per-user `sequence_no`, `entity_type` (`transaction`), `entity_id`, `operation` (`create`/`edit`/`delete`), optional related entity type/ID (scheduled commitment or cooling-off purchase), `payload_version`, JSON before-image and after-image, `created_at`, nullable `undone_at`. Unique `(user_id,sequence_no)` and index `(user_id,undone_at,sequence_no DESC)`. Store events atomically with transaction mutations and keep a bounded unconsumed history as described above. Undo also restores a linked commitment or cooling-off item to its prior workflow state.
- **avatar files:** Store bytes under a non-public, non-executable upload root using random opaque storage keys (outside static serving); persist only the key in `users.avatar_storage_key`. Enforce size limit, allow-listed image formats, signature and decode validation, safe generated filenames, and per-user authorization on retrieval/deletion. Never trust the supplied filename or MIME header.
- **schema_migrations:** version and applied timestamp. `database/schema.sql` provides the initial schema and additive updates are tracked under `database/migrations/` and applied by the initialization layer.

Database constraints and repository checks both enforce user ownership. Deletes should follow an explicit retention/foreign-key policy; linked records must not silently become inconsistent.

## Data flow

1. Browser submits a form or requests a page with the session cookie and CSRF token where applicable. Password reset uses a random single-use expiring token delivered through the configured mail adapter; only its hash is persisted.
2. Flask authenticates the session and obtains the current user ID.
3. Route validates request shape, then calls a service with the user ID and typed values.
4. Service checks domain invariants and reads/writes through a repository using parameterized SQL and an explicit transaction. Transaction writes and versioned undo event images commit atomically; scheduled commitment completion and linked ledger creation are likewise atomic.
5. For C-backed operations, Python obtains only that user's relevant records, converts monetary fields to integer paise/fixed-width ABI values, and calls the C wrapper. Results return to the service for display/report use.
6. On mutation, SQLite is committed first; Python then updates or rebuilds transient C state. A rebuild query is always user-scoped.
7. Service returns a typed result; Flask renders a template or JSON response. Chart.js receives formatted, user-scoped aggregates and never accesses SQLite directly.

## Security and privacy considerations

- Hash passwords using a password hashing function from a well-maintained library (Werkzeug's supported password hash helpers or an equivalent reviewed choice); never store or log plaintext passwords. Reset tokens are random, hashed at rest, one-use, short-lived, and responses do not disclose account existence.
- Use secure, HTTP-only, same-site session cookies; enable `Secure` when deployed behind HTTPS; use CSRF protection for state-changing forms and regenerate/clear session state on authentication transitions.
- Keep secrets and production database paths in environment/configuration outside source control. Disable debug mode outside local development.
- Use parameterized SQL, strict input validation, output escaping, request size limits where appropriate, and safe CSV quoting/formula-injection mitigation. Avatar upload validates size and actual decoded image format, uses a random storage key outside the public static directory, and checks owner access for retrieval/removal.
- Apply ownership predicates at every repository boundary, not only in route navigation. Avoid exposing sequential IDs as authorization. Test cross-user reads, edits, deletes, exports, and C synchronization.
- Validate amounts and conversions in Python before narrowing to C integer widths; reject overflow and malformed ABI data. Never trust browser calculations.
- Use transactions for related writes, especially contributions, purchase-to-transaction conversion, demo-data removal, and other linked state changes.
- Insights and estimates should expose assumptions and source periods. Do not present heuristic detection as a guaranteed financial fact.
