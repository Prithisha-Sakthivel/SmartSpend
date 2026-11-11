# SmartSpend Feature Guide

## Daily money management

- **Dashboard:** Balance snapshot, month-to-date income and expenses, Safe-to-Spend, runway, recent ledger, category budgets, savings goals, and upcoming bills/income.
- **Transactions:** Add income/expense records in INR; the server converts to paise using decimal arithmetic. Search by description or ID and filter by type, category, and inclusive date range. Create/edit/delete operations save undo images. Undo is last-in-first-out and protected against overwriting a changed row.
- **Commitments:** Schedule bills, expected income, and planned savings with amounts, dates, and status. Weekly/monthly recurrences create dated instances for the next year. Completing a bill or income creates a linked ledger transaction atomically; savings commitments do not silently alter goal progress.
- **Budgets:** Monthly category limits compare only expenses in the budget date range. The view shows spent, remaining/over amount, progress, and near-limit/overspend states.

## Spending decisions

- **Safe-to-Spend:** Applies the selected planning horizon to the user's balance snapshot, scheduled income, bills, planned savings, and buffer. Missing balance snapshot is shown as setup required; the system does not infer a bank balance from ledger history.
- **Zero-Day Runway:** Uses trailing 30-day average posted expenses as a constant daily burn and applies future scheduled bills/income by date. The runway page explains its inputs and accepts an optional user-entered daily estimate if recent history is insufficient.
- **Before You Buy:** A product name, amount, and category produce a preview of post-purchase balance, safe amount, remaining budget, and approximate days of burn. Preview does not write a transaction. The user can record the expense or place it in a two-day cooling-off queue.
- **Cooling-off manager:** Pending purchases can be proceeded (creating an expense), cancelled, or assigned a different review date. Queue rows persist in SQLite and are ordered through C when the DLL is available.

## Saving and reflection

- **Goals:** Store a target amount/date and an append-only contribution history; progress derives from non-reversed events.
- **Challenges:** Fixed-cadence and target-by-date challenges use contribution events. One event can support both a goal and a challenge without being duplicated in the activity history. No-spend challenges require explicit met/missed daily check-ins and a selected category; SmartSpend does not infer a streak from absent entries.
- **Savings streak:** Reports consecutive dates with recorded savings contributions. An unrecorded date breaks the sequence.
- **Insights:** Rules flag repeated small expenses (five or more under ₹1,000 in the last 30 days), repeated descriptions (three or more), largest spending category, expenses at least twice the period average when there are at least three records, and over-budget categories. The suggested saving amount is 20% of positive month-to-date net cash flow after the next 30 days’ scheduled bill/savings commitments, capped by Safe-to-Spend when available.
- **Weekly summary and reports:** Week-to-date income, spending, contributions and highest-spending category; selected-period category chart, net cash flow, budget performance, goal progress, and top expenses.
- **CSV export:** Exports only current-user transactions within requested dates; text that could start a spreadsheet formula is neutralized.

## Account and privacy

Registration, login/logout, reset-password links, account email/name editing, avatar upload/removal, password change, planning settings, and demo-data reset are available. Password recovery uses SMTP when configured. Local debug mode provides a development-only reset link if SMTP is not configured. Use the dedicated seed script to create or refresh demo records for a local demo account.
