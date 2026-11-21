# Screen check: Lead 360

Phase 2, screen 4 of 7. Checked against the never-list in `crm design/DESIGN.md` section 8.

## Stitch references

| Item | Stitch screen ID | File |
|---|---|---|
| Final screen (owner picked Variant 2, two edit rounds) | `a0a7ba7292e6465c850fd6f8070948a0` | `designs/lead-360/lead-360.png` |
| Loading state | `0419d69b755342548b41d74d512a1157` | `designs/lead-360/loading.png` |
| Error state | `7f5bee2bbe33423fa236599843f1a583` | `designs/lead-360/error.png` |
| Chosen variant before edits | `5bf9012ddb184018bba822da5c024572` | Variant 2, Hero Affiancato |

Design system: `assets/d4a66eeb6e2e4771b7ab89cb118b7ddc`.

## Never-list check

| # | Rule | Result | Note |
|---|---|---|---|
| 1 | One font family, tabular numbers on figures | PASS | DM Sans, AUC and percentages tabular |
| 2 | Buttons sentence case, uppercase only section headers | PASS | Tabs and actions in sentence case |
| 3 | Titles are nouns, no taglines | PASS | The marketing footer line was removed; the methodological note on calibration stays |
| 4 | Tables are tables, no card per row | PASS | Driver rows are a form of comparison, not decorative cards |
| 5 | Borders not shadows, no gradients, corners 0 to 4px | PASS | Flat panels with 1px borders |
| 6 | Blue only for action and selection; green only for positive closed statuses | PASS | Stability dot is neutral; only the negative driver uses red |
| 7 | Each value appears once | PASS | The duplicate `+31,3 punti` box was removed; the delta appears once in the dial legend |
| 8 | Empty, loading and error states designed | PASS | Loading and error saved; this screen has no empty state in the spec |

## Owner feedback applied

1. Removed the invented `Priorità Alta` badge.
2. Removed the duplicated `Impegna leva` and `Registra azione` buttons; the tabs remain the navigation.
3. Replaced the green stability dot with a neutral indicator.
4. Removed the invented `Iniziative precedenti` history.
5. Removed the footer tagline.
6. Title uses `Moretti Componenti S.a.s. · Missione Svezia - Wine`.
7. **Wheel UX:** the dial is about 300px, `60%` is 56px, and the `28,66%` prevalence moved out of the ring into a legend below it, with the `+31,3 punti` difference. No text sits on the arc, and the end labels `0%` and `100%` have room.
8. Removed the light blue box that repeated the `+31,3 punti` difference under the values.
9. **Threshold marker:** the `28,66%` line on the dial is now a 4px ink stroke with a 6px dot at the arc and a `28.66%` flag outside the ring, matching the legend swatch. It is no longer a hairline.

## Carried to implementation

1. The marker label uses a dot (`28.66%`) while the legend uses the Italian comma (`28,66%`). The implementation must format both with the Italian locale.
2. The model panel keeps the real artifacts: `lead-win-lgbm-v1`, AUC 0.773, calibration error 0.0104, scored 18/11/2026 16:10.
3. The driver points (`+14,2`, `+6,8`, `-3,1`) are design examples. The implementation must compute them from the SHAP values.
4. The company facts (`Giorni apertura 150`, `Stato dormienza Attivo`) come from the ML dataset and are real for this record in the demo.

## Owner approval

Variant 2 approved, with the fix list and the wheel request, on 2026-11-20. The final screen and the loading and error states are not yet approved. Phase 2 stops here until they are.
