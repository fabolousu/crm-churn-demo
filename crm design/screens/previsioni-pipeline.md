# Screen check: Previsioni queue

Phase 2, screen 3 of 7. Checked against the never-list in `crm design/DESIGN.md` section 8.

## Stitch references

| Item | Stitch screen ID | File |
|---|---|---|
| Final screen (owner picked Variant 1, one edit round) | `3dc7283ff58a417cae4c78ccac9d7802` | `designs/previsioni-pipeline/pipeline.png` |
| Empty state | `9cc51f16b1c843e5a93f9f46238b90b1` | `designs/previsioni-pipeline/empty.png` |
| Loading state | `2779bcc3424046308dc0a4d2948d3af4` | `designs/previsioni-pipeline/loading.png` |
| Error state | `ee19b0302ede48d5ab5940bba6dfd848` | `designs/previsioni-pipeline/error.png` |
| Chosen variant before edits | `c3e71d24446945f3a4962a847f152fb7` | Variant 1, Dense Cockpit |

Design system: `assets/d4a66eeb6e2e4771b7ab89cb118b7ddc`.

## Never-list check

| # | Rule | Result | Note |
|---|---|---|---|
| 1 | One font family, tabular numbers on figures | PASS | DM Sans, currency and percentages tabular |
| 2 | Buttons sentence case, uppercase only headers | PASS | `Vista Portfolio`, `Riprova` in sentence case |
| 3 | Titles are nouns, no taglines, Italian labels exact | PASS | `Iniziative per valore atteso`, `Valore atteso`, `Valore a rischio`, `Leva massima` |
| 4 | Tables are tables, no card per row | PASS | Queue is a table with 1px separators |
| 5 | Borders not shadows, no gradients, corners 0 to 4px | PASS | Flat surfaces, 4px corners |
| 6 | Blue only for action, link, selection; status colors only for status | PASS | Blue on the active nav, active sort and chevrons |
| 7 | Each value appears once per row | PASS | ARR and expected value appear once |
| 8 | Empty, loading and error states designed | PASS | Three states saved |

## Fixes applied in the edit round

1. Title corrected to `Iniziative per valore atteso`.
2. Removed the fifth KPI `Atteso in vista (top 5)`.
3. Removed the `Ricalcola AI` button.
4. Removed the invented probability bands `Alta`, `Vertice`, `Media`. The column now shows only the percentage and its bar.
5. Fixed the clipped sort control. It is now a visible segmented control with `Valore atteso` active, `Valore a rischio`, `Leva massima`.
6. Removed the fabricated page counter `Pagina 1 di 3.951` and the "in tempo reale" claim. The footer now reads `Mostrate 5 di 19.752 iniziative` and `Coda ordinata dal modello predittivo`.

## Carried to implementation

1. The KPI label reads `TASSO CONVERSIONE` with the hint `storico chiuso`. The full label from the spec is `Tasso di conversione storico`; use it in the implementation.
2. The column header reads `PROBABILITA AI`. The spec label is `Probabilita`; the AI wording is acceptable but should be decided once.
3. The left navigation brand reads `PROMOS CRM` while the top bar reads `CRM CCIAA - PROMOS`. Unify in the implementation.
4. The queue shows the top 5 of 19,752. The real screen should page or virtualise; the design documents the top of the list.

## Owner approval

Variant 1 approved on 2026-11-20. The edited final and the three states are not yet approved. Phase 2 stops here until they are.
