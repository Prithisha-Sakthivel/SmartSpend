# SmartSpend UI/UX Guidelines

## Product character

SmartSpend should feel like a considered independent fintech product: calm, editorial, practical, and reassuring without becoming cute or overly decorative. Prioritize readable numbers, direct language, deliberate whitespace, and visible explanations for financial estimates. Use the supplied purple direction consistently. Avoid generic dashboard grids, unnecessary cards, gradients, glass effects, decorative illustrations, excessive corner rounding, and motion without a user benefit.

## Design tokens

### Colour palette

| Token | Hex | Use |
|---|---|---|
| `plum-900` / Deep Plum | `#40205F` | Primary brand actions, selected navigation, important headings |
| `purple-700` / Royal Purple | `#7041A6` | Interactive emphasis, chart series, links and focus accents |
| `canvas` / Warm Canvas | `#FBFAF8` | Main page background |
| `lavender-100` / Soft Lavender | `#E9DDF5` | Subtle selected surfaces, secondary chart fills, gentle highlights |
| `charcoal-900` / Dark Purple-Charcoal | `#261C30` | Primary text and high-contrast surfaces |
| `slate-600` / Muted Slate | `#777080` | Secondary text, metadata, axes |

Define semantic tokens for `surface`, `surface-muted`, `border`, `success`, `warning`, `danger`, and focus rings. Their implementation values must be tested for readable contrast and must harmonize with the required palette; do not use colour as the only signal for status. Prefer warm neutral surfaces and thin, quiet borders. Reserve saturated purple for meaningful actions and information hierarchy.

### Typography

- **Playfair Display** for page titles and selected editorial section headings. Use a restrained scale and avoid using it for dense numeric tables or controls.
- **Plus Jakarta Sans** for body copy, navigation, labels, controls, tables, and numerical data where legibility is important.
- Load fonts responsibly with sensible system fallbacks and avoid blocking content if remote font loading fails.
- Establish a clear type scale: compact metadata, comfortable body copy, prominent page title, and one or two larger financial figures per view. Use tabular numerals for aligned currency and tables when supported.
- Keep labels descriptive and sentence case. Use short helper text near financial assumptions instead of vague tooltips as the only explanation.

### Spacing, shape, and depth

- Use a consistent 4 px base spacing scale (4, 8, 12, 16, 24, 32, 40, 48, 64 px) and group related controls more tightly than unrelated sections.
- Maintain generous page gutters and clear section separation. Align headings, content, and tables to a deliberate grid.
- Use small corner radii for inputs and compact controls; reserve moderate rounding for larger panels. Avoid pill-shaped everything.
- Prefer borders and spacing over shadows. Use a subtle shadow only when it communicates a floating layer such as a menu or dialog.
- Keep motion short and purposeful: focus, hover, disclosure, success-state feedback, and quick count-up transitions for loaded INR totals. Use count-ups only for real server-rendered values, keep the final value visible and exact, and never animate runway dates or unavailable states. Respect `prefers-reduced-motion` and avoid distracting page transitions.

## Components

- **Navigation:** Compact top bar or restrained desktop side navigation with clear active state, text labels, and logical grouping. Mobile navigation must remain reachable and not obscure the primary action.
- **Buttons:** One clear primary action per view or form section; secondary actions use quiet outlines or text. Destructive actions are visually distinct and require clear context. Every button must perform a real action.
- **Forms:** Persistent labels, useful examples, inline validation, sensible defaults, and clear required/optional status. Amount inputs accept familiar INR notation, then clearly display the normalized amount. Do not use placeholder text as the sole label. Upload controls state accepted avatar formats and size limits and show validation errors accessibly.
- **Financial summaries:** Use a small number of well-prioritized figures with period labels and explanatory comparison text. Avoid surrounding every value with an individual card.
- **Tables and transaction lists:** Align dates, descriptions, categories, and right-aligned amounts. Use readable row height, subtle separators, mobile-friendly reflow, and explicit edit/delete affordances.
- **Charts:** Use Chart.js with a restrained palette based on plum/purple/lavender plus neutral context. Label axes and time periods, format INR, provide legends only when needed, and include a text or tabular summary. Ensure chart meaning remains clear without colour alone.
- **Status and alerts:** Explain the condition and next action in plain language. Pair colour with text/icon. Use inline feedback for routine states and focused dialogs only for meaningful confirmation.
- **Empty/loading/error states:** Explain what is missing, provide a relevant next action, and distinguish no data from loading or failure. Keep sample/demo records visibly marked.
- **Dialogs and menus:** Keyboard-operable, correctly labelled, focus-managed, dismissible where safe, and sized for small screens.
- **Motion and micro-interactions:** Use one shared easing/timing vocabulary. Small hover lift is limited to interactive goal/challenge panels; transaction rows and buttons respond lightly; primary actions may shift by only a few pixels on fine pointers. Progress transitions reflect server-rendered values, success messages get a brief entrance/check treatment, and auth submit feedback must not prevent or delay submission. Do not add modal, tab, or loading-skeleton patterns to pages that have no corresponding workflow.

## Page-wise requirements

1. **Login and registration:** Quiet, compact pages with a clear wordmark/title, short purpose statement, labelled fields, password visibility control, validation, a functional “Forgot password?” route, and a direct link between login and registration. Reset request and completion pages use the same compact visual treatment, explain next steps without revealing whether an account exists, and confirm completion without displaying sensitive token details. Keep decorative treatment minimal and match the purple palette.
2. **Dashboard:** Start with a personalized greeting and date scope. Prioritize safe-to-spend and cash-flow context, then a concise runway/commitments view, budget status, recent transactions, and savings progress. Use a few carefully composed regions rather than a wall of cards. Show first-run guidance when there are no records.
3. **Transactions:** Provide an obvious add-income/add-expense action, useful date/category/type filters, search, and a scannable ledger. Forms support create/edit with inline validation. Confirm deletions and provide a clear result state.
4. **Safe-to-Spend:** Make the estimate the focus, with the inclusive date range and a compact signed breakdown: current funds + scheduled income − scheduled bills − planned savings − safety buffer, clamped to a minimum display value of zero. Explain that current funds come from the user's balance snapshot and later posted ledger entries. Link each component to its records/settings, identify a missing snapshot as setup required, and show any deficit separately instead of hiding it.
5. **Zero-Day Runway:** Show estimated days/date with the exact trailing-30-calendar-day average daily posted expense basis, available amount, and dated scheduled income/bills in the projection. Explain the fixed-burn assumption. For an existing nonpositive balance, show “at/under zero now”; for absent history or missing balance show a useful unavailable/setup state and allow a clearly labelled manual daily burn override. Do not display an infinite or precise runway when the burn rate is zero.
6. **Before You Buy:** Use a focused input form and a result comparison showing effect on safe-to-spend, relevant category budget, and runway. Explain the comparison and offer distinct actions to save for cooling-off, cancel, or record as an expense.
7. **Cooling-Off:** Present pending purchases in review-date order with amount, date added, remaining wait, and status. Make proceed, cancel, and reschedule actions understandable and reversible where practical. Include a useful no-pending-items state.
8. **Budgets:** Show period selector, category limit, spent, remaining, and threshold state in a compact list/table. Make over-budget or near-limit status text explicit and link to contributing transactions.
9. **Insights:** Lead with a small number of evidence-backed observations, explain the time window and supporting transactions, and mark all detected patterns as suggestions. Provide a way to dismiss or revisit an insight if included.
10. **Goals and challenges:** Show target, contribution total, target date, and progress with clear units. Describe each challenge's date range, target, and cadence. Make adding a contribution a deliberate flow; when one contribution is linked to both a goal and challenge, explain that the same event counts toward both targets but appears once in the activity history.
11. **Reports/export:** Place date and category filters before summary and charts, include a detailed transaction table, and provide an export control that names the exported scope. Empty and filtered-empty states must be distinct.
12. **Settings/profile/demo data:** Group account details, financial assumptions, and demo-data controls. Provide an editable display name and email plus an optional avatar picker, preview, replace, and remove action. Keep avatar controls keyboard-accessible, show accepted formats/size before upload, provide a neutral fallback avatar, and expose clear upload/error/success feedback. Clearly identify demo content and explain the effect of adding or removing it before the action. Include a prominent way to update password where supported.

## Responsive design

- Design from the content outward with breakpoints for narrow mobile, tablet, and desktop rather than shrinking a desktop grid mechanically.
- Keep primary actions and key figures visible near the top on mobile. Convert side navigation into a compact, accessible menu or bottom navigation only if labels remain clear.
- Reflow multi-column summaries into a purposeful vertical sequence; preserve the intended hierarchy and spacing.
- Tables should switch to compact stacked rows or controlled horizontal overflow with clear affordance. Do not clip amounts or labels.
- Charts resize without losing labels; provide an accompanying summary for small screens.
- Use comfortable touch targets (around 44 px), adequate field spacing, readable body sizes, and avoid hover-only functionality.
- Test portrait and landscape mobile widths, tablet widths, and wide desktop layouts. Prevent horizontal page overflow.

## Accessibility and interaction quality

- Use semantic headings, landmarks, buttons, and form labels; maintain logical keyboard order and visible focus.
- Check text and control contrast, including muted labels and chart colors, against their actual backgrounds.
- Announce dynamic status and validation feedback to assistive technology. Do not rely on animation, colour, or icons without text context.
- Make keyboard behavior work for menus/dialogs and ensure reduced-motion preference is respected.
- Format currency consistently as INR with grouping and two decimal places where useful; distinguish zero, unavailable, and not-yet-calculable values.
- Use realistic demo content sparingly and label it as illustrative. Every visible control must work, explain why it is disabled, or be omitted.
