# Screen check: Scheda Lead (view)

Phase 2, screen 2 of 7. Checked against the never-list in `crm design/DESIGN.md` section 8.

## Stitch references

| Item | Stitch screen ID | File |
|---|---|---|
| Final screen (owner picked Variant 1, one edit round) | `54b86fff89254adaa925c1e23752157e` | `designs/scheda-lead/scheda-lead.png` |
| Empty timeline (Elementi correlati) | `cc33244b338e4a9e86d6af423db433a0` | `designs/scheda-lead/empty.png` |
| Loading state | `f3b55c0769f940a0a2916b05b3b46cf1` | `designs/scheda-lead/loading.png` |
| Error state | `204357fd7ef54895bcd6f5f6630d4e9a` | `designs/scheda-lead/error.png` |
| Chosen variant before edits | `c53a3bf7ea9d4fd6951d37b647ed7416` | Variant 1, Form Ampio 70/30 |

Design system: `assets/d4a66eeb6e2e4771b7ab89cb118b7ddc`.

## Never-list check

| # | Rule | Result | Note |
|---|---|---|---|
| 1 | One font family, tabular numbers | PASS | DM Sans throughout |
| 2 | Buttons sentence case, uppercase only table and section headers | PASS | `Salva`, `Aggiorna`, `Assegna` in sentence case; section labels uppercase |
| 3 | Titles are nouns, no taglines, Italian labels exact | PASS | Record title is the seed argomento; field labels match `SITE.md` |
| 4 | Tables are tables, no card per row, density | PASS | Form screen; dense 13px fields, no decorative cards |
| 5 | Borders not shadows, no gradients, corners 0 to 4px | PASS | Panels use 1px borders, no shadows, 4px corners |
| 6 | Blue only for action, link, selection; status colors only for status | PASS | Blue on `Salva` and links; `Interessato` chip neutral |
| 7 | Each value appears once | PASS | No duplicated values |
| 8 | Empty, loading and error states designed | PASS | Timeline empty, loading and error saved |

## Defects fixed in the edit round

1. A fourth tab `Sequenza temporale` was removed. The timeline now lives inside `Elementi correlati`, which is what the spec asks for.
2. The header line `Iniziativa: B2B Agro Stoccolma 2026` contradicted the selected `Anagrafica interesse`. It now reads `Iniziativa: Foodex Japan Edition`.
3. The invented `ID Scheda: AZ-2024-9102` was removed from `Preview Azienda`.

## Carried to implementation

1. The header repeats the initiative (`Iniziativa: Foodex Japan Edition`) even though the field is already in the form. Acceptable, but it can be dropped if the owner wants a quieter header.
2. The preview panels use bordered containers. They are structural side panels, not cards per row, so the never-list is satisfied.
3. The empty timeline adds a `Registra prima attività` button. The spec has a `+ Nuova attività` action; either wording is fine, the implementation should pick one.

## Owner approval

Variant 1 approved on 2026-11-20. The edited final screen and the three states are not yet approved. Phase 2 stops here until they are.
