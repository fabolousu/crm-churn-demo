# Screen check: Portfolio

Phase 2, screen 7 of 7. Checked against the never-list in `crm design/DESIGN.md` section 8.

## Stitch references

| Item | Stitch screen ID | File |
|---|---|---|
| Final screen (owner picked Variant 1, one edit round) | `fe282bbc38d04fc58321be597a930aa7` | `designs/portfolio/portfolio.png` |
| Loading state | `83ea772e89a74cfab59a743ab1c18b6b` | `designs/portfolio/loading.png` |
| Error state | `b0bd6d4f28b64408a23d34c492006a80` | `designs/portfolio/error.png` |
| Chosen variant before edits | `a0df59bbfce040d382137744da73c2af` | Variant 1, Top Cockpit |

Design system: `assets/d4a66eeb6e2e4771b7ab89cb118b7ddc`.

## Never-list check

| # | Rule | Result | Note |
|---|---|---|---|
| 1 | One font family, tabular numbers | PASS | DM Sans, all amounts and percentages tabular |
| 2 | No small spaced capitals except table headers | PASS | The drift status is `Da osservare` in sentence case |
| 3 | Titles are nouns, no taglines | PASS | `Portfolio pipeline`, `Andamento per regione`, `Qualita del modello` |
| 4 | Tables are tables, no card per row | PASS | Regional table with 1px separators |
| 5 | Borders not shadows, no gradients, corners 0 to 4px | PASS | Flat panels, 4px corners |
| 6 | Blue only for action and selection; green only for positive closed statuses | PASS | Blue bars and links, amber drift status, no green |
| 7 | Each value appears once | PARTIAL | The total expected value €282M appears in the KPI and again in the table total row. A total row on a table is conventional, but the implementation should decide one place |
| 8 | Empty, loading and error states designed | PASS | Loading and error saved; this screen has no empty state |

## Fixes applied in the edit round

1. Removed `Brier Score: 0,124` (not in `metrics.json`).
2. Removed the invented PSI band `(range 0,10 - 0,25)`.
3. Removed `DECILI 10/10` and `Ottimale`.
4. Removed the `Ponderazione: Macro-regionale omogenea` badge.
5. Removed `Aggiornamento automatico` and `100% volume`.
6. Replaced the calibration note `cluster agroalimentare ed export` with `Metriche verificate su iniziative chiuse.`
7. Changed `DA OSSERVARE` to `Da osservare`.

## Data contract gap

`SITE.md` asks for an `ARR totale` column per region. The portfolio contract (`api/openapi.yaml`) exposes only `region`, `open_leads`, `win_rate` and `expected_value`. The design therefore shows `Valore atteso` and `Quota portfolio` instead of regional ARR. Either extend the API contract or keep the table as designed.

## Carried to implementation

1. `Soglia massima target < 0,05` next to the ECE is an invented acceptance threshold. Remove it unless the threshold is defined in the model card.
2. The methodology note claims `Nessun overfitting geografico riscontrato nei controlli settimanali`. That is not evidenced; drop the claim.
3. `Quota portfolio`, `39,1% del lordo` and `60,9% non convertibile` are simple ratios of real totals. Keep them only if the owner wants the extra context.
4. The calibration chart points are the ten deciles from `portfolio.json`; the implementation must read them from the API, not hard-code them.

## Owner approval

Variant 1 approved on 2026-11-21. The edited final and the two states are not yet approved. Phase 2 is complete after this screen.
