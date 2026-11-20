# Screen check: Lead personali aperti

Phase 2, screen 1 of 7. Checked against the never-list in `crm design/DESIGN.md` section 8.

## Stitch references

| Item | Stitch screen ID | File |
|---|---|---|
| Final screen (owner picked Variant 3, refined twice) | `0444e72a6d5d437a9878b2ad2dfcd8c7` | `designs/lead-personali-aperti/lead-personali-aperti.png` |
| Empty state | `0ce0b786b02742c38cd5ad1f161a9546` | `designs/lead-personali-aperti/empty.png` |
| Loading state | `4084a4d95eff4b9292b9581dfde12294` | `designs/lead-personali-aperti/loading.png` |
| Error state | `cb52a8be727f4e3183621309da0571a1` | `designs/lead-personali-aperti/error.png` |
| Chosen variant before edits | `f39047d0c7754e37866b299547846336` | owner picked Variant 3 |
| First edit (table fit and Previsioni nav) | `0444e72a6d5d437a9878b2ad2dfcd8c7` | used as the final |
| Second edit (wider table) | `11ea51bc9b234071ac3c33e206adcfe6` | rejected, it widened the table |

Design system: `assets/d4a66eeb6e2e4771b7ab89cb118b7ddc` (Promos Sales Fresh, created from `DESIGN.md`).

## Never-list check

| # | Rule | Result | Note |
|---|---|---|---|
| 1 | One font family, PowerGrotesk only in the logo, tabular numbers | PASS | DM Sans throughout, dates tabular |
| 2 | Buttons sentence case, uppercase only table headers | PASS | `Nuovo`, `Modifica`, `Assegna` in sentence case |
| 3 | Titles are nouns, no taglines, Italian labels exact | PARTIAL | Title and labels correct; three column headers truncate with ellipsis (`1° MACRO ...`, `ANAGR. INTE...`, `PROPRIE...`). Implementation must show them in full |
| 4 | Tables are tables, no card per row, at least 25 rows at 1080p | PARTIAL | Pure table, no cards. The canvas is 2560x2048 and shows 14 rows; the implementation must reach 25 rows at 1080p with 32 to 36px rows |
| 5 | Borders not shadows, no gradients, no entrance animation, corners 0 to 4px | PASS | 1px borders, flat surfaces, 4px corners |
| 6 | Blue only for action, link, selection; status colors only for status; green not decorative | PASS | Blue on primary action and selection, status chips neutral or tinted, no green |
| 7 | Each value appears once per row | PASS | No duplicated numbers |
| 8 | Empty, loading and error states designed in Stitch | PASS | Three screens generated and saved. They drift slightly in the shell (the empty state repeats the logo and uses a different top bar), which the implementation should normalise |

## Known defects carried to implementation

1. The table overflows the canvas: the right columns (`Stato lavorazione`, `Creazione`, `Data modifica`) are clipped, and no horizontal scrollbar is visible in the static design. The live grid already scrolls horizontally; the implementation must also fix column widths so the nine P0 columns truncate instead of pushing the table wide.
2. Three header labels are truncated. Use the full labels from `SITE.md`.
3. The three state screens were generated independently, so the shell is not pixel-identical across them. Treat the final screen as the reference for chrome.
4. The empty state shows the logo twice (`PROMOS` and `PROMOS ITALIA`). Use the single `CRM CCIAA - PROMOS` lockup.

## Owner approval

Variant 3 approved on 2026-11-20. The two edit rounds were run on my own defect findings; the owner has not yet approved the refined screen or the states. Phase 2 stops here until that approval.
