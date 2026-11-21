# Screen check: Lever

Phase 2, screen 5 of 7. Checked against the never-list in `crm design/DESIGN.md` section 8.

## Stitch references

| Item | Stitch screen ID | File |
|---|---|---|
| Final screen (owner picked Variant 2, one edit round) | `4872ea6c331f4922bf53a8bd6c593e57` | `designs/lever/lever.png` |
| Loading state | `f3203bf0a4ef4c15824a4a8c75ae517b` | `designs/lever/loading.png` |
| Error state | `a3a1087fa0bd4fb3b7f20c0d6a696e59` | `designs/lever/error.png` |
| Chosen variant before edits | `d5e57762658c45388bca952908814505` | Variant 2, Split Bilanciato |

Design system: `assets/d4a66eeb6e2e4771b7ab89cb118b7ddc`.

## Never-list check

| # | Rule | Result | Note |
|---|---|---|---|
| 1 | One font family, tabular numbers | PASS | DM Sans, percentages tabular |
| 2 | No small spaced capitals except table headers | PASS | The decorative `INSPECTOR DI IMPATTO` badge was removed; the model badge is sentence case |
| 3 | Titles are nouns, no taglines | PASS | `Cosa muove la probabilita` and lever names |
| 4 | Tables are tables, no card per row | PASS | Levers are selectable choices, not rows of a data table |
| 5 | Borders not shadows, no gradients, corners 0 to 4px | PASS | Flat panels, 4px corners |
| 6 | Blue only for action and selection; green only for positive closed statuses | PASS | Blue on the selected lever, CTA and links; no green |
| 7 | Each value appears once | PARTIAL | `+18` appears on the lever, on the simulated chip and in the `Calcolato su ... (+18 pt su base 60%)` note. The implementation should keep the lever lift and the chip, and drop the note |
| 8 | Empty, loading and error states designed | PASS | Loading and error saved; this screen has no empty state |

## Fixes applied in the edit round

1. `MODELLO: PROMOS-WIN-V4` replaced with `Modello lead-win-lgbm-v1`, in sentence case.
2. Removed the decorative `INSPECTOR DI IMPATTO` badge.
3. Removed the `Avanzamento probabilità di conversione` bar that repeated `60% -> 78%`.
4. Removed every `4.200 contratti esteri conclusi` claim. The calibration note now reads `Metriche verificate su iniziative chiuse.`
5. Title set to `Moretti Componenti S.a.s. · Missione Svezia - Wine`.

## Carried to implementation

1. The `+18` lift is still repeated three times. Show it on the lever and on the simulated probability chip, and drop the `Calcolato su ...` note.
2. The what-if card keeps the warning and the 0 to 40% slider. It must never appear as a committable action.
3. The simulated probability is `attuale + lift` (60 + 18 = 78). The implementation computes it from the model, not from a fixed delta.
4. The title punctuation should be a plain hyphen and a middle dot, as in the other screens.

## Owner approval

Variant 2 approved on 2026-11-21. The edited final and the two states are not yet approved. Phase 2 stops here until they are.
