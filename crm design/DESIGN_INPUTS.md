# Design inputs (Phase 0)

Input for the Phase 1 `taste-design` step. The final `DESIGN.md` is written from this file,
`design refs/`, and `design refs/SCREENSHOT_AUDIT.md`. Written 2026-11-20.

## 1. Brand tokens (from promositalia.com)

Source: `design refs/promositalia.com_*.png`, `design refs/font-family forma-djr-text, sans-se.txt`,
`design refs/figma-colors.json`.

| Token | Value | Seen on the site as |
|---|---|---|
| Brand blue | `#005EB8` | Header, footer, nav, links, body text color |
| Blue dark | `#00499D` | Hover / pressed |
| Ink | `#19242E` | Dark text on light surfaces |
| Green | `#88E771` (hover `#9CF088`) | Call-to-action buttons (`INVIA`, `VAI`, `ISCRIVITI`), with blue text |
| Light blue | `#CBE4FB` | Soft highlight |
| Surface | `#EEF2F5` | Login card, AREA SELLER panel |
| Border | `#DBE2E8`, strong `#AFBAC4` | Rules, input underlines |
| Red | `#E74C3C` | Errors |
| Body font | `forma-djr-text`, 400 / 700 (18/27, 14/18) | All text |
| Display font | `PowerGrotesk` 500 | Hero headlines only (60/66) |
| Corners | Square or near-square (0 to 2px) | Cards, buttons, inputs |

**Conflict with the current Stitch design system:** "Promos Sales Fresh" in project
`3133723532266431010` uses Inter, accent `#1F8A4C` and 8px corners. It does not match the brand
and must be updated in Phase 1 step 3.

**Font licensing:** `forma-djr-text` and `PowerGrotesk` are commercial fonts (Adobe Fonts / DJR,
foundry license). Stitch cannot load them. Use the closest available sans in Stitch, and in `web/`
load the real font only through Promos Italia's own font kit. Until then, fall back to the
Stitch choice.

## 2. Never-list (goes into DESIGN.md)

1. **Fonts:** one family in the app (forma-djr-text, or its fallback). PowerGrotesk only in the
   logo lockup, never in the UI. Tabular numbers in every number column.
2. **Labels:** no small spaced-out capitals except table headers. Buttons in sentence case
   (`Salva`, `Nuovo`), even though the marketing site uses uppercase buttons.
3. **Copy:** no explanatory taglines. Titles are nouns (`Lead personali aperti`), not slogans.
   Italian labels from the spec, exactly.
4. **Rows:** tables are tables. No card per row; at least 25 rows visible at 1080p.
5. **Surfaces:** borders, not shadows. No gradients, no page entrance animation. White page;
   `#EEF2F5` only for structural areas (nav, table header, side panels). Corners 0 to 4px.
6. **Color:** brand blue only for primary actions, links and selection. Status colors only for
   status. Green `#88E771` is not a decoration.
7. **Numbers:** each value appears once per row.
8. **States:** every screen has an empty, loading and error state designed in Stitch, using the
   legacy wording where it exists (`Nessun dato disponibile`, `Caricamento ... in corso`).

## 3. Open decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| D1 | Where green `#88E771` goes in a work tool | Positive closed statuses only (Servizio concluso, Contratto concluso, Iscritto all'evento). Blue stays the action color |
| D2 | Fallback font in Stitch and before the font kit arrives | The closest geometric-grotesque sans Stitch offers; pick by comparing against the site screenshot |
| D3 | Previsioni module language | Italian, to match N1 of `docs/SITE_REQUIREMENTS_AND_FEATURES.md` (it is English today) |
