# SmartSpend Project Plan

## Project objective

Build SmartSpend, a responsive personal-finance web application for an individual or household to understand available spending capacity, record income and expenses, control discretionary purchases, manage category budgets, and make progress toward savings goals. The project demonstrates a Python-first application architecture, SQLite persistence, and working C implementations of the required data structures and algorithms exposed to Python through `ctypes` and a compiled DLL/shared library.

The college mini-project should be understandable, demonstrable locally, testable, and honest about what its estimates mean. Calculations are decision support based on user-entered data; they are not banking, investment, credit, or tax advice.

## Problem statement

People often make day-to-day spending decisions without a clear view of committed bills, upcoming income, category limits, or the effect of a purchase on their short-term cash runway. A simple ledger alone does not answer “Can I afford this now?” SmartSpend brings a private transaction ledger together with transparent short-term calculations, purchase reflection, budgets, insights, and goals. It should make the underlying assumptions and source transactions inspectable instead of presenting unexplained scores.

## Users and scope

- A registered user maintains their own profile, transactions, budgets, goals, and purchase decisions.
- A user may add income and expenses, optionally assign a category and date, and correct or remove entries.
- The initial product is a single-currency local web app using INR. Monetary values are stored as integer paise; formatting and input conversion are handled at the Python boundary.
- There is no bank aggregation, payment execution, credit decision, investment advice, or multi-currency conversion in the initial scope.
- Demo data is opt-in, clearly labelled, user-scoped, and removable without affecting other accounts.

## Feature plan

1. **Registration, login, profile:** Register with validated credentials, securely hash passwords, authenticate with Flask sessions, log out, and edit profile details including an optional avatar upload. Include a complete forgot-password/reset flow using single-use, expiring reset tokens. Enforce unique normalized email addresses and user ownership for every private record.
2. **Financial dashboard:** Show current-period income, expenses, net cash flow, safe-to-spend estimate, runway, budget usage, recent transactions, and goal progress. Provide clear date ranges, empty states, and links to the relevant records.
3. **Income, expense, and scheduled commitment management:** Create, list, edit, and delete dated ledger transactions with description, type, paise amount, and optional category/notes. Separately create and manage upcoming bill, expected income, and planned savings commitment entries with due dates/status (and optional recurrence). Completing a bill/income must link it to one ledger transaction so it is never counted twice. Validate positive amounts, supported type, date, and ownership. Keep derived summaries synchronized with persisted records.
4. **Safe-to-Spend calculator:** For a selected horizon, calculate `max(0, current funds + scheduled income - scheduled bills - planned savings contributions - safety buffer)`. Current funds come from a user-entered balance snapshot plus posted ledger transactions after that snapshot. Include scheduled items due from today through the horizon end. Show the assumptions and source totals; never imply bank connectivity. If no snapshot exists, label the result incomplete and prompt setup rather than treating ledger net as a verified balance.
5. **Zero-Day Runway estimator:** Estimate the first day funds reach zero by applying a fixed daily burn rate from the trailing 30 calendar days of posted expenses, plus dated scheduled bills and income. Define zero/negative balances, sparse history, and date inclusion rules; show the rate and projection caveat.
6. **Before You Buy simulator:** Let the user enter a proposed purchase amount, category, and optional description. Compare it with safe-to-spend, remaining category budget, and runway impact, with transparent results and a “record purchase” route to create an expense.
7. **Cooling-Off purchases:** Put an undecided purchase into a dated cooling-off queue, display its review date/status, and allow the user to proceed, cancel, or reschedule. Persist queue entries in SQLite; the C queue is an in-memory working representation synchronized from the user-scoped database records.
8. **Category budgets:** Create and edit period budgets by category, view spend and remaining allowance, and flag configurable thresholds. Define a consistent rule for transaction date, budget period, and uncategorized expenses.
9. **Insights and money-leak detection:** Present understandable observations such as recurring or repeated discretionary spend, category changes, and subscriptions/manual recurring charges inferred from transaction history. Label heuristic findings as suggestions, show their supporting records, and do not claim certainty.
10. **Savings goals and challenges:** Create goals with target amount/date and accumulated contributions, and time-bounded challenges with defined target/rule, cadence, and dates. Record contribution events with optional links to a goal and/or challenge, show progress without counting one event twice within a target, and validate contribution dates and amounts.
11. **Reports and CSV export:** Filter summaries and transaction reports by date/category/type, show category breakdown, income/expense comparison, budget performance, savings progress, and trends, and export only the signed-in user's filtered records. Use safe CSV encoding and correct paise/INR display conventions.
12. **Settings and demo data:** Manage profile preferences, default buffer/planning assumptions, and demo data. Include explicit add/reset controls with confirmation at the UI level and ensure data operations are scoped to the current user.

## Technology stack

- **Python 3** is the primary language for application processing, validation, authentication, financial calculations, database access, and orchestration.
- **Flask** serves pages and JSON endpoints. Use server-rendered HTML templates and small vanilla JavaScript enhancements; no React or Node.js application framework.
- **SQLite** is the durable source of truth, accessed through Python's standard `sqlite3` module, parameterized statements, foreign keys, and migrations/schema versioning.
- **C** provides actual implementations of the transaction singly linked list, undo stack, cooling-off queue, category expense arrays/calculations, quick sort for expense ranking, and binary search over sorted transaction records.
- **Python `ctypes`** calls an explicitly defined, stable C ABI from a locally compiled DLL (Windows) or shared library (other development platforms). Python coordinates persistence and synchronizes C state from database records.
- **HTML5, CSS3, vanilla JavaScript** implement the responsive frontend. **Chart.js** renders accessible, labelled financial visualizations.
- **Automated tests** use Python's standard testing facilities or a small test dependency selected during implementation; C and Python boundary behavior are tested as well.

## Development milestones

1. **Planning approval:** Review this plan, architecture, and UI/UX guidance before implementation.
2. **Project foundation:** Establish package/folder structure, configuration, schema versioning, app factory, error handling, local build instructions, and Windows DLL compiler/build documentation.
3. **C library and binding:** Implement and compile all six required C capabilities, define ABI and ownership/error rules, add Python `ctypes` wrappers, and verify database-to-C synchronization behavior. On Windows, document a 64-bit MSVC Build Tools C toolchain and build the DLL from its Developer PowerShell/Command Prompt; match DLL architecture (x64 or x86) to Python. Keep exported functions C ABI-compatible (`__cdecl`, `extern "C"` when headers are included from C++), use fixed-width types, and load via `ctypes.CDLL` with declared signatures. GCC/MinGW is an alternative only if the resulting ABI and architecture are deliberately matched and documented.
4. **Persistence and identity:** Implement schema/repositories, registration/login/forgot-password reset/avatar profile flows, session handling, authorization checks, and user isolation.
5. **Ledger and core calculations:** Implement transaction workflows, dashboard aggregates, safe-to-spend, runway, and before-you-buy with shared calculation rules.
6. **Budgets and reflection:** Add category budgets, cooling-off queue, insights, savings goals/challenges, and settings/demo data.
7. **Frontend and reporting:** Implement all page states and responsive layouts, charts, accessible interactions, filtered reports, and CSV export.
8. **Verification and handoff:** Run automated unit, integration, C ABI, security/isolation, calculation, export, and responsive/manual checks; document setup, build, demo, limitations, and known issues.

Milestones should be implemented in small reviewable increments. The C library is not a second database: durable records remain in SQLite and can rebuild C working state.

## Testing strategy

- **C unit tests:** Verify linked-list insertion/search/removal/traversal, stack push/pop and empty behavior, queue enqueue/dequeue and empty behavior, category aggregation, quick-sort ordering and edge cases, and binary-search hits/misses/duplicates.
- **ABI and binding tests:** Verify structure sizes/field widths, string and buffer handling, return/error codes, pointer lifetime/freeing, DLL loading failures, and representative calls through Python `ctypes`.
- **Financial calculation tests:** Cover paise precision, rounding/display, date boundaries, absent balance snapshots, posted transactions after snapshots, scheduled commitments at horizon boundaries, planned savings, buffer clamping, zero/negative balances, trailing-30-day burn, sparse history, and scheduled income/bill runway effects.
- **Database/service integration tests:** Exercise schema creation/upgrades, CRUD, transaction boundaries, persisted undo and stale-state rejection, scheduled commitments, CSV filters, goal/challenge contributions, queue persistence, avatar metadata, reset-token expiry/reuse, and synchronization/rebuild of C structures.
- **Security tests:** Check password hashing/reset token behavior, session protections, upload validation and storage isolation, parameterized queries, authorization on every user-owned resource, cross-user access attempts, and CSV formula injection handling.
- **Web tests:** Exercise key routes and form validation, empty/error/success states, and confirmation or accessible status messages for consequential actions.
- **Manual UI checks:** Inspect desktop, tablet, and narrow mobile sizes; keyboard/focus navigation; readable contrast; chart labels; reduced motion; and consistency across authenticated and public pages.

## Completion criteria

The project is ready for demonstration when all twelve feature areas have working user flows, calculations explain their inputs, undo survives requests/restarts, all persisted records and uploaded avatars are user-scoped, all six C requirements execute through Python's `ctypes` binding, the Windows DLL can be built from documented instructions, the app can be set up from documented instructions, and the automated and manual checks above have been completed.
