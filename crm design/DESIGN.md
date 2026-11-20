# Design System: CRM CCIAA - PROMOS

---

## 1. Visual Theme and Atmosphere

A cockpit-dense, border-driven work tool for sales agents at Promos Italia. The
interface is unambiguous, information-first, and calm: white content areas with
cool-blue structural surfaces, one brand accent, and no decoration that does not
carry meaning.

**Density:** 9 out of 10. At 1080p the main table must show at least 25 rows without
scrolling. No hero sections, no asymmetric layouts, no motion beyond system-level
focus transitions.

**Variance:** 2 out of 10. Predictable, symmetric: left nav, top bar, right main area.
Consistent vertical rhythm. No asymmetric whitespace, no offset columns.

**Motion:** 1 out of 10. Static and restrained. No page-entrance animations, no
perpetual micro-loops, no staggered reveals. Focus rings and hover background changes
are instant or at most a 100ms linear transition. This is a form-heavy work tool, not
an interactive experience.

The visual register is Promos Italia blue: the brand color `#005EB8` does the structural
work, ink `#19242E` reads every piece of data, and `#EEF2F5` holds the chrome. Green
`#88E771` appears only where something went right.

---

## 2. Color Palette and Roles

| Token | Hex | Role |
|---|---|---|
| Brand Blue | `#005EB8` | Primary actions (buttons, links), active nav item, selection highlight, focus rings |
| Blue Dark | `#00499D` | Hover and pressed state of brand-blue interactive elements |
| Light Blue | `#CBE4FB` | Selected row background, active chip fill, soft highlight on form fields |
| Ink | `#19242E` | All primary text: headings, cell values, form labels, button text on light surfaces |
| Muted | `#5B6472` (derived) | Secondary text: table sub-labels, timestamps, helper text, placeholder text |
| White | `#FFFFFF` | Content surface: table body rows, form panels, modal dialogs |
| Surface | `#EEF2F5` | Structural chrome: top bar, left nav, table header row, side panels, login card |
| Border | `#DBE2E8` | All structural dividers: row separators, section rules, input underlines |
| Border Strong | `#AFBAC4` | Column resize handles, active input underline, focused cell outline |
| Green Positive | `#88E771` | Positive-closed status chip fill (Servizio concluso, Contratto concluso, Iscritto all'evento) with `#19242E` text |
| Green Positive Hover | `#9CF088` | Hover state of green-positive chips; not used anywhere else |
| Red Error | `#E74C3C` | Validation errors, error state banners |
| Red Error Light | `#FDECEA` (derived) | Error chip fill, error field background tint |
| White Page | `#FFFFFF` | The page canvas; the app shell is always white |

**Rules:**
- Brand Blue is the only interactive accent. No second accent color.
- Green `#88E771` is not a decoration and not a CTA color. It appears only on the three
  positive-closed statuses listed above. All other statuses use neutral or blue tints.
- Status colors serve status only. They must never be used for borders, icons, or
  backgrounds outside their status chip context.
- Never use `#000000`. Ink `#19242E` is the darkest value.
- No gradients anywhere in the application.
- No decorative shadows. The only shadow allowed is a 1px bottom border on the top bar
  to separate it from the content.

---

## 3. Typography Rules

### Font family

The UI uses one typeface: **DM Sans** (the closest geometric-grotesque available in
Stitch to `forma-djr-text`). Both are low-contrast, single-story, geometric-grotesque
sans-serifs with a neutral, professional character. Use DM Sans in Regular (400) and
SemiBold (600) only. Bold (700) is permitted for emphasis in table headers.

When the real `forma-djr-text` font kit is loaded from Promos Italia's CDN, replace DM
Sans with `forma-djr-text, DM Sans, sans-serif` in the CSS cascade. Until then DM Sans
is the production font.

PowerGrotesk is never used in the UI. It belongs to the logo lockup only.

### Type scale (base 13px for dense work tool)

| Level | Size | Weight | Line height | Letter spacing | Use |
|---|---|---|---|---|---|
| `page-title` | 15px | 600 | 20px | 0 | Page titles, modal headings |
| `section-heading` | 13px | 600 | 18px | 0.02em | Form section labels (all-caps), panel headings |
| `body` | 13px | 400 | 18px | 0 | Cell text, form field values, body copy |
| `label` | 12px | 400 | 16px | 0 | Form labels above inputs, helper text |
| `small` | 11px | 400 | 15px | 0 | Timestamps, secondary metadata, row counts |
| `table-header` | 11px | 700 | 15px | 0.06em | Column headers (uppercase, spaced) |
| `button` | 13px | 600 | 18px | 0 | All button labels (sentence case) |
| `chip` | 11.5px | 500 | 15px | 0 | Status chips, tag labels |
| `mono` | 12px | 400 | 18px | 0 | Tabular numbers in every column showing numeric values |

### Number formatting

Every column that contains numbers uses tabular (monospaced) numerals. This applies to:
probability percentages in the Previsioni views, ARR values, record counts, dates
displayed as timestamps. In practice, set `font-variant-numeric: tabular-nums` on all
`<td>` and all numeric `<span>` elements.

### Typography rules

- One font family in the entire UI. No mixed-family headings.
- Small-caps spaced-out lettering is permitted only on table column headers. Buttons are
  sentence case (`Salva`, `Nuovo`, `Esporta in Excel`), never uppercase.
- Titles are nouns, not slogans. `Lead personali aperti` not `Gestisci i tuoi lead`.
- No explanatory taglines anywhere.
- Maximum line length in running text (help panels, empty-state descriptions):
  65 characters.
- Serif fonts are banned. No `Times New Roman`, `Georgia`, `Garamond` or any serif
  variant.
- Inter is not used. DM Sans replaces it throughout.

---

## 4. Component Stylings

### Buttons

- **Primary (filled):** Background `#005EB8`, text `#FFFFFF`, 13px 600. Hover:
  `#00499D`. Active: 1px translate down. Corner radius: 2px. No outer glow, no shadow.
  Padding: 7px 14px.
- **Secondary (outline):** 1px border `#DBE2E8`, background `#FFFFFF`, text `#19242E`,
  13px 400. Hover: background `#EEF2F5`. Corner radius: 2px.
- **Ghost (text):** No border, no background. Text `#005EB8`, 13px 400. Hover:
  background `#EEF2F5`. Corner radius: 2px.
- **Destructive:** background `#E74C3C`, text `#FFFFFF`. Same shape as primary.
- All button labels are in sentence case. The only uppercase text in buttons is an error
  that must be corrected.
- Minimum tap target height: 32px for desktop. Touch targets on mobile: 44px.

### Status chips (Stato lavorazione)

Chips are inline-block pills with 2px corner radius, 11.5px 500 text, 4px 10px padding.
No colored dot. Each chip has a background tint and a text color drawn from the status
palette below.

| Status | Background | Text color | Category |
|---|---|---|---|
| Nuovo | `#EEF2F5` | `#19242E` | Open |
| Da contattare | `#EEF2F5` | `#19242E` | Open |
| In attesa di riscontro | `#CBE4FB` | `#005EB8` | Open |
| Interessato | `#CBE4FB` | `#005EB8` | Open |
| Prefattibilita negativa | `#FDECEA` | `#E74C3C` | Open |
| Nessuna risposta | `#EEF2F5` | `#5B6472` | Open |
| Non interessato | `#EEF2F5` | `#5B6472` | Open |
| Contratto concluso | `#88E771` | `#19242E` | Closed positive |
| Servizio concluso | `#88E771` | `#19242E` | Closed positive |
| Iscritto all'evento | `#88E771` | `#19242E` | Closed positive |
| Concluso (legacy) | `#EEF2F5` | `#5B6472` | Closed legacy |
| Interessato InBuyer (legacy) | `#CBE4FB` | `#005EB8` | Open legacy |
| Da richiamare (legacy) | `#EEF2F5` | `#19242E` | Open legacy |
| Perso (legacy) | `#FDECEA` | `#E74C3C` | Closed legacy |

Green `#88E771` appears only for the three positive-closed statuses above. No other
status, badge, icon or surface uses it.

### Tables

The core component of the application. Tables are tables: a dense striped grid,
not cards.

- **Row height:** 32px. At 1080p viewport height with a 56px top bar and 36px table
  header, this yields at least 25 visible rows without scrolling.
- **Column header:** background `#EEF2F5`, 11px 700 uppercase 0.06em tracking, text
  `#19242E`, 32px height, 1px bottom border `#AFBAC4`. Sortable columns show a caret
  icon on hover; active sort key shows a filled caret.
- **Row:** background `#FFFFFF`. Even rows: `#FAFBFC` (very light tint; optional, use
  only if the product decision is to stripe). Hover row: background `#EEF2F5`.
  Selected row: background `#CBE4FB`.
- **Cell:** 13px 400, text `#19242E`. Padding: 0 8px. Vertical align: middle.
- **Column dividers:** 1px `#DBE2E8` between columns. No dividers between rows unless
  explicitly specified; bottom border `#DBE2E8` on each row is acceptable.
- **A-to-Z jump bar:** shown above the table when the view is sorted alphabetically.
  Small, single-character buttons in `#EEF2F5`.
- **Empty state (Nessun dato disponibile):** center the message in the table body area.
  One line `Nessun dato disponibile` in 13px 400 `#5B6472`. Below it: `0 - 0 di 0` in
  11px 400 `#5B6472`. No illustration.
- **Loading state:** show the table header and two to three skeleton rows with a 60px
  wide shimmer bar in `#EEF2F5` per cell. Text: `Caricamento ... in corso` above the
  skeleton, 13px 400 `#5B6472`.
- **Page counter:** `1 - 50 di 342` in 11px 400 `#5B6472`, right-aligned, below the
  table. Page size default 50.
- **No card-per-row layouts.** No replacing table rows with summary cards.

### Forms

- **Layout:** two-column form grid for entity forms with many fields; single-column for
  compact dialogs (column picker, filter dialog, bulk edit).
- **Sections:** bold uppercase heading `INFORMAZIONI PRINCIPALI`, `INTERESSE`,
  `DETTAGLI` in `section-heading` scale. 1px top border `#DBE2E8` above each section.
- **Field:** label above input. Label: 12px 400 `#5B6472`. Input: 13px 400 `#19242E`,
  background `#FFFFFF`, 1px bottom border `#DBE2E8`. Height: 32px. No floating labels.
  Corner radius: 0px (sharp). Required field: asterisk `*` in `#E74C3C` after the label.
- **Locked fields:** background `#EEF2F5`, text `#19242E`. The lock icon (padlock,
  16px) appears at the right of the field. Locked fields cannot receive focus.
- **Focus state:** border color changes to `#005EB8`, 2px; focus ring `#CBE4FB` 2px
  offset outset ring. No background change on focus.
- **Error state:** border color `#E74C3C`, error message below the field in 11px 400
  `#E74C3C`. No inline icon inside the input.
- **Helper text:** below the field, 11px 400 `#5B6472`.
- **Dropdowns:** same size and style as text inputs. The open dropdown panel: white
  background, 1px border `#AFBAC4`, max-height 240px, overflow scroll. Options: 32px
  row height, 13px 400, hover background `#EEF2F5`, selected background `#CBE4FB`.
- **Checkboxes:** 14px square, 1px border `#AFBAC4`, checked background `#005EB8`,
  checkmark white. No fully-rounded checkbox.

### Record header / flyout

The record header shows the entity icon, record title (15px 600 `#19242E`), save state,
entity type, and 2 to 4 header fields. The chevron next to the owner opens an inline
flyout panel to change `Stato lavorazione` and `Proprietario`. The flyout is a white
card with 1px border `#DBE2E8`, 4px corner radius, and a `Salva` button at the bottom.

### Navigation

- **Top bar:** height 56px, background `#EEF2F5`, 1px bottom border `#DBE2E8`. Left:
  logotype (CRM CCIAA - PROMOS, TRADE AGENCY in 13px 600 `#005EB8`). Center: global
  search input (white, 1px border `#DBE2E8`, magnifier icon, 32px height). Right:
  quick-create button (primary), gear icon, user avatar.
- **Left nav:** width 240px, background `#EEF2F5`, right border 1px `#DBE2E8`. Nav
  groups: `Attivita personali`, `Clienti`, `Interazioni`, `Entita di configurazione`,
  `Previsioni`. Group labels: 11px 700 uppercase `#5B6472`. Nav items: 13px 400
  `#19242E`, 32px height, 4px corner radius on hover/active. Active item: background
  `#CBE4FB`, text `#005EB8`, left 2px border `#005EB8`. Bottom card: model version
  and score date in 11px 400 `#5B6472`.
- **Command bar (above table or form):** height 36px, background `#FFFFFF`, 1px bottom
  border `#DBE2E8`. Left: view name or entity title. Right: `Nuovo`, `Mostra come`,
  `Condividi`, overflow `...` button.

### Modals and panels

- Overlay: rgba(25, 36, 46, 0.4) full-screen. No blur.
- Dialog card: white, 4px corner radius, 1px border `#DBE2E8`, max-width 560px.
  Header: 15px 600 `#19242E`, 1px bottom border `#DBE2E8`. Footer: `Salva` (primary)
  and `Annulla` (secondary/ghost).
- Right panel (column picker, filter builder): slides in from the right, width 320px,
  white background, 1px left border `#DBE2E8`. Same header and footer pattern.

### Quick-view panels (right column on record forms)

Width 280px, background `#EEF2F5`, 1px left border `#DBE2E8`. Shows a preview card for
the linked Company and Contact: entity name in 13px 600, two to three key fields in
12px 400 `#5B6472`. Read-only.

### Empty, loading and error states

Each state applies to the full content area (table body, form panel, modal body).

**Empty (table):** `Nessun dato disponibile` in 13px 400 `#5B6472`, centered. Below:
`0 - 0 di 0` counter. No illustration, no decorative icon.

**Empty (form sub-grid before first save):** One line in 13px 400 `#5B6472`:
`Il record deve essere salvato prima di aggiungere elementi correlati.`

**Loading (table):** Text `Caricamento ... in corso` in 13px 400 `#5B6472` above two
skeleton rows. Each skeleton cell is a 60px wide bar in `#EEF2F5` with a shimmer
animation (opacity 0.4 to 1 and back, 1.2s linear loop). Only the shimmer moves;
no spinner.

**Loading (timeline):** `Caricamento sequenza temporale in corso` in 13px 400
`#5B6472`, centered in the timeline area. Same shimmer skeleton rows below.

**Error (page-level):** A 1px border `#E74C3C` banner below the command bar, 36px
height, background `#FDECEA`. Left red bar 3px wide. Text: 13px 400 `#19242E`
describing the error. Right: `Riprova` ghost button.

---

## 5. Layout Principles

The application shell is a fixed three-zone layout:
- Left nav: 240px fixed, sticky.
- Top bar: 56px fixed, sticky.
- Main content area: remaining width, scrollable vertically.

No horizontal scroll at any viewport width the application supports (1024px and above).
The main content area uses a max-width of 1500px centered within itself.

**Form layout:** forms use CSS Grid, not Flexbox percentage math. Two columns for the
main Generale tab; single column for narrow panels. Sections stack vertically with
consistent 24px gap between sections and 16px gap between fields within a section.

**Table layout:** full width within the content area. Column widths are user-adjustable.
Sticky column header. No card wrappers around the table: the table sits directly on
the white content surface.

**No hero sections.** No asymmetric whitespace columns. No decorative full-width
background panels. `#EEF2F5` is structural chrome only: nav, header row, side panels.
White `#FFFFFF` is content. Everything else is a border.

**Spacing scale:**

| Token | Value | Use |
|---|---|---|
| `space-1` | 4px | Icon gap, tight inline spacing |
| `space-2` | 8px | Cell padding, chip padding, icon-to-text gap |
| `space-3` | 12px | Label-to-input gap, button padding |
| `space-4` | 16px | Field-to-field gap within a section |
| `space-5` | 24px | Section-to-section gap, card padding |
| `space-6` | 32px | Panel padding, page header to first section |
| `space-8` | 48px | Modal vertical padding |

---

## 6. Previsioni (AI module) - Italian presentation

Decision D3: all labels in this module are in Italian to match the locale requirement
N1 and to be consistent with the rest of the CRM.

The five screens under `/previsioni` use the same shell, same table density, same
typography and same color roles as the rest of the application. No special dark themes,
no large probability dials that compete with the data.

### 6.1 Pipeline (Coda di lavoro prioritizzata)

A ranked list of open initiatives ordered by valore atteso (probabilita x ARR proposto).

**List columns (order):** Priorita, Iniziativa, Driver principale, Probabilita di
successo, Valore atteso.

**Column labels (Italian):**

| Data field | Italian label |
|---|---|
| Rank | Priorita |
| Initiative name | Iniziativa |
| Strongest SHAP driver | Driver principale |
| Win probability | Probabilita di successo |
| Expected value (prob x ARR) | Valore atteso |
| Leverage (max probability lift) | Leva disponibile |

**Probability presentation:** a tabular-numbers percentage (`73%`) in 13px 600
`#19242E`. Beside it, a band chip (see probability bands below) in the same chip style
as status chips but with the band palette.

**Probability band chips:**

| Band | Italian label | Background | Text |
|---|---|---|---|
| Below 20% | Bassa | `#FDECEA` | `#E74C3C` |
| 20% to 39% | Media | `#FFF8E6` | `#9A6600` |
| 40% to 59% | Alta | `#CBE4FB` | `#005EB8` |
| 60% and above | Vertice | `#CBE4FB` | `#005EB8` with 600 weight |

**Driver principale:** the label of the strongest positive or negative SHAP driver,
truncated to 40 characters if needed. No bar chart in the queue row; the full driver
breakdown is on the Lead 360 screen.

**Valore atteso:** EUR value with two decimal places, tabular numbers, right-aligned.

### 6.2 Lead 360 (Perche questa probabilita?)

Shows the three SHAP drivers and the calibration context for one lead.

**Italian labels:**

| Field | Italian label |
|---|---|
| Screen title | Perche questa probabilita? |
| Section: three drivers | I tre driver principali |
| Driver bar chart heading | Contributo al punteggio |
| Probability | Probabilita di successo |
| Prevalence / base rate | Tasso base del modello |
| Calibration note | Nota di calibrazione |
| Stability note | Nota di stabilita |
| Closed initiative note | Iniziativa chiusa: nessuna leva disponibile |

**Driver bar:** a horizontal bar whose width represents the absolute SHAP contribution.
Bars that push the probability up use `#CBE4FB` fill with `#005EB8` text. Bars that push
it down use `#FDECEA` fill with `#E74C3C` text. Each bar shows the driver label and the
contribution in tabular-numbers points (for example `+8.3 pt`).

The three drivers are numbered 1, 2, 3 in order of absolute contribution. No unranked
list. No decorative icons next to driver names.

### 6.3 Leva (Qual e l'azione che vale di piu?)

Presents the committable actions and their estimated probability lifts.

**Italian labels:**

| Field | Italian label |
|---|---|
| Screen title | Qual e l'azione che vale di piu? |
| Action: executive sponsor meeting | Riunione con sponsor dirigenziale |
| Action: discovery meeting | Riunione di discovery |
| Action: discount (what-if only) | Sconto proposto (solo simulazione) |
| Estimated lift label | Incremento stimato |
| What-if warning | Attenzione: questo e solo un what-if. Lo sconto non e un'azione consigliata e non puo essere impegnata. |
| Current probability | Probabilita attuale |
| Hypothetical probability | Probabilita ipotetica |
| Commit action button | Impegna questa azione |

The discount counterfactual is always labeled as simulation only and cannot be
committed. Its row carries a warning badge with `#9A6600` text on `#FFF8E6` background.

### 6.4 Azione (Impegna e registra)

The act loop: commit one action and record the outcome.

**Italian labels:**

| Field | Italian label |
|---|---|
| Screen title | Impegna e registra |
| Action committed | Azione impegnata |
| Projected probability | Probabilita proiettata |
| Recorded outcome | Esito registrato |
| Confirm button | Conferma |
| Cancel | Annulla |

### 6.5 Portfolio (Vista d'insieme)

**Italian labels:**

| Field | Italian label |
|---|---|
| Screen title | Vista d'insieme del portafoglio |
| Pipeline value | Valore di pipeline |
| At-risk value | Valore a rischio |
| Win rate | Tasso di successo |
| Calibration status | Stato calibrazione |
| Drift status | Stato drift |
| Model version | Versione modello |
| Score date | Data punteggio |

**Metric display:** each KPI is a compact two-line block: label in 11px 700 uppercase
`#5B6472`, value in 20px 600 `#19242E` with tabular numbers. No decorative cards with
shadows. The blocks sit in a single-row grid separated by 1px vertical borders
`#DBE2E8`.

---

## 7. Focus and Selection

**Keyboard focus ring:** 2px solid `#005EB8` with a 2px white offset, applied to every
focusable element. The ring must be visible on both white and `#EEF2F5` backgrounds.
Never hide the focus ring (no `outline: none` without a custom replacement).

**Row selection (table):** background `#CBE4FB`. The checkbox column is the first
column, 32px wide. Checked state: `#005EB8` fill. When one or more rows are selected,
the command bar shows `N selezionati` and enables `Modifica`, `Assegna` and `Elimina`.

**Active nav item:** background `#CBE4FB`, left 2px solid border `#005EB8`, text
`#005EB8`.

**Active view tab:** 2px bottom border `#005EB8`, text `#005EB8` 600. Inactive tabs:
text `#19242E` 400, no border.

---

## 8. Never-list (verbatim from DESIGN_INPUTS.md)

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

### Additional banned patterns (from taste-design anti-pattern review)

- No emojis anywhere in the UI.
- No Inter font. DM Sans only until forma-djr-text is available.
- No pure black (`#000000`). Ink `#19242E` is the darkest permitted value.
- No neon or outer-glow shadows on any element.
- No oversaturated accent colors. The palette is defined above; no additions.
- No gradient text on headings or labels.
- No custom mouse cursors.
- No 3-column equal-card feature rows. Use tables and grids.
- No generic filler names (`John Doe`, `Acme Corp`, `Nexus`). Use Italian placeholder
  labels when real data is not available.
- No invented metrics, uptime percentages, or response-time numbers that do not come
  from the actual model artifacts (`ml/artifacts/metrics.json`). The only model metrics
  that may appear in the UI are those explicitly provided: AUC 0.773, calibration error
  0.0104, lift at 10 2.26.
- No AI copywriting cliches (`Seamless`, `Elevate`, `Unleash`, `Next-Gen`).
- No `LABEL // YEAR` formatting patterns.
- No page-entrance animations, no staggered cascade reveals, no perpetual micro-loops.
- No broken image links. Use SVG initials avatars for contacts and companies.
- No hero sections in a work tool.
- No asymmetric or uneven layouts. The shell is always left nav, top bar, main content.
- No decorative gradients on any surface.

---

## 9. Stitch Generation Notes

When generating or editing screens in Stitch, describe the UI using these terms:

**Atmosphere:** "A cockpit-dense CRM work tool for Italian trade-agency sales agents.
White content area, cool-blue structural surfaces (`#EEF2F5`), brand-blue
(`#005EB8`) for all interactive elements. Borders define structure, not shadows."

**Tables:** "A dense data table with 32px row height, 11px uppercase column headers on
`#EEF2F5` background, white rows, hover to `#EEF2F5`, selected row `#CBE4FB`.
At least 25 rows visible at 1080p without scrolling."

**Status chips:** "Inline pill chips, 2px radius, 11.5px medium text. Green `#88E771`
only for Servizio concluso, Contratto concluso, Iscritto all'evento. All other statuses
use neutral or blue tints. No colored dot."

**Buttons:** "Small flat buttons, 2px radius, no shadow, no glow. Primary: `#005EB8`
fill, white text. Secondary: 1px border `#DBE2E8`, white fill. Sentence case labels."

**Font:** "DM Sans, one weight Regular for body and cells, SemiBold for headings and
buttons. Tabular numbers on all numeric columns."

**Previsioni:** "Italian labels throughout. Probability as a tabular percentage (`73%`).
Driver contribution as a horizontal bar with `+N.N pt` label. No dial charts, no
animated ring charts. SHAP drivers labeled in plain Italian."
