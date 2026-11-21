# Screen check: Scheda Lead (view)

Phase 2, screen 2 of 7. Checked against the never-list in `crm design/DESIGN.md` section 8.

## Stitch references

| Item | Stitch screen ID | File |
|---|---|---|
| Final screen (Variant 1, edited twice) | `b9a8187339204f0fa4d2c244348698cd` | `designs/scheda-lead/scheda-lead.png` |
| Timeline empty | `509e3c130acc4fa1a34ad5a94905a7c1` | `designs/scheda-lead/empty.png` |
| Timeline populated | `a372d58780c8431faea2989d8491e450` | `designs/scheda-lead/timeline.png` |
| Loading state | `f3b55c0769f940a0a2916b05b3b46cf1` | `designs/scheda-lead/loading.png` |
| Error state | `204357fd7ef54895bcd6f5f6630d4e9a` | `designs/scheda-lead/error.png` |
| Chosen variant before edits | `c53a3bf7ea9d4fd6951d37b647ed7416` | Variant 1, Form Ampio 70/30 |

Design system: `assets/d4a66eeb6e2e4771b7ab89cb118b7ddc`.

## Never-list check

| # | Rule | Result | Note |
|---|---|---|---|
| 1 | One font family, tabular numbers | PASS | DM Sans throughout |
| 2 | Buttons sentence case, uppercase only table and section headers | PASS | `Salva`, `Aggiorna`, `Assegna` in sentence case |
| 3 | Titles are nouns, no taglines, Italian labels exact | PASS | Field labels match `SITE.md` |
| 4 | Tables are tables, no card per row, density | PASS | Form screen; dense 13px fields |
| 5 | Borders not shadows, no gradients, corners 0 to 4px | PASS | Panels use 1px borders, 4px corners |
| 6 | Blue only for action, link, selection; status colors only for status | PASS | Blue on `Salva` and links |
| 7 | Each value appears once | PASS | No duplicated values |
| 8 | Empty, loading and error states designed | PASS | Timeline empty, timeline populated, loading, error |

## Owner feedback applied

1. **Lighter header.** The repeated `Iniziativa: Foodex Japan Edition` line is removed from the final, the empty timeline and the populated timeline. The header keeps the LEAD label, the title, the save state and the creation date.
2. **`Quick-View` removed.** The label crowded the `Contatto` tab. The tab strip now has only `AZIENDA` and `CONTATTO`, cleanly spaced.
3. **Timeline button rule.** Empty timeline uses `Registra prima attività`. Once activities exist, the action becomes `+ Nuova attività`. Both screens are saved so the pair is documented.

## Earlier fixes

1. The fourth tab `Sequenza temporale` was removed; the timeline lives inside `Elementi correlati`.
2. The invented `ID Scheda: AZ-2024-9102` was removed from `Preview Azienda`.

## Carried to implementation

1. The loading and error screens were generated before the header and `Quick-View` changes, so they still show the old header. Align them in a later pass or when the screen is built.
2. The empty timeline adds a `Registra prima attività` button; the populated one uses `+ Nuova attività`. The implementation should switch the label on the activity count, not on a different button.
3. Preview panels use bordered containers. They are structural side panels, not cards per row.

## Owner approval

Variant 1 approved on 2026-11-20. The header, `Quick-View` and timeline button changes were requested in the same round. The final screen, the empty timeline and the populated timeline are ready for approval. Loading and error remain from the previous pass.
