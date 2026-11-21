# Screen check: Act

Phase 2, screen 6 of 7. Checked against the never-list in `crm design/DESIGN.md` section 8.

## Stitch references

| Item | Stitch screen ID | File |
|---|---|---|
| Final screen (owner picked Variant 1, one edit round) | `561cae0231ae4588a3f63f24574a58ab` | `designs/act/act.png` |
| Preview in progress (mid slide) | `24dd05b5d7b8461aa84b9f7b8796195b` | `designs/act/midslide.png` |
| Loading state | `2fb5fe70e80d45b594b53f5ade8f21ae` | `designs/act/loading.png` |
| Error state | `cb8f4231e7324d68ab77b790233a84ac` | `designs/act/error.png` |
| Chosen variant before edits | `2b0e4ae5310740c0afaea20be432a347` | Variant 1, Top Cockpit |

Design system: `assets/d4a66eeb6e2e4771b7ab89cb118b7ddc`.

## The probability slide component (option A plus D)

The impact strip now has a horizontal 0 to 100 track with two fixed markers:

- a grey ghost marker at 60%, labelled `Prima 60%`;
- a solid blue marker at 78%, labelled `Dopo 78%`;
- no position labels under the track: the rank change lives only in the `Avanza di 4 posizioni` badge;
- the band between them filled light blue `#CBE4FB`;
- a play button `Anteprima` that runs the slide once;
- the caption `Anteprima visiva, non una previsione`.

The mid-slide screen shows the moving marker between the two points with no intermediate number. That is deliberate: only the two endpoints are model values, and the transition must not imply a live recalculation. The implementation should animate the marker and count the number from 60 to 78 once, with `prefers-reduced-motion` falling back to a static swap.

## Never-list check

| # | Rule | Result | Note |
|---|---|---|---|
| 1 | One font family, tabular numbers | PASS | DM Sans, all percentages and amounts tabular |
| 2 | No small spaced capitals except table headers | PASS | Section labels are normal case; no decorative uppercase badges |
| 3 | Titles are nouns, no taglines | PASS | `Registra un'azione`, `Tipo di azione`, `Impatto previsto` |
| 4 | Tables are tables, no card per row | PASS | The action list is a choice list, not a data table |
| 5 | Borders not shadows, no gradients, corners 0 to 4px | PASS | Flat panels, 4px corners |
| 6 | Blue only for action and selection; green only for positive closed statuses | PASS | Blue marker, CTA and selected action; no green |
| 7 | Each value appears once | PARTIAL | The commit bar summarises `+18 pt (+€42,7K)`, repeating the strip. It is a confirmation summary; the implementation may drop it |
| 8 | Empty, loading and error states designed | PASS | Mid-slide, loading and error saved; this screen has no empty state |

## Fixes applied in the edit round

1. `Raccomandata dal modello` became `Azione raccomandata · Rank 1`.
2. Removed the `LIVE PREVIEW` badge.
3. Removed the invented `efficacia storica del touchpoint` note.
4. Replaced the boxed before and after percentages with the slide component.
5. Inset the commit bar from the viewport edge.
6. Removed the `Posizione #7` and `Posizione #3` lines under the track. The two labels `Prima 60%` and `Dopo 78%` sit on one baseline without overlapping, and the rank change is only in the badge.

## Carried to implementation

1. The breadcrumb still shows `MISSIONE SVEZIA – WINE` with an en dash. Use a hyphen.
2. The post-commit success banner (`Azione registrata con successo...`) from the spec is not designed yet. It is a separate success state for a later pass.
3. The slide must not expose a draggable midpoint and must not show numbers between 60 and 78.
4. The `+18` comes from the selected lever; if the rep picks another action, the markers and the delta must follow that lever.

## Owner approval

Variant 1 approved, and the slide component chosen as option A plus D, on 2026-11-21. The final screen and the states are not yet approved. Phase 2 stops here until they are.
