# Site requirements and features

**Product:** a B2B CRM for an Italian chamber-of-commerce agency (CRM CCIAA - PROMOS),
with an AI module (**Previsioni**) that ranks initiatives by expected value and explains
every win probability.

**Status:** merged at `c2a981d` (2026-11-20). The CRM shell, the lead list and the lead
record are live; the five ML screens live under `/previsioni`. The detailed P0 row-by-row
mapping is in [`CRM_UI_STATUS.md`](CRM_UI_STATUS.md); the functional source of truth is
`crm design/CRM_Sales_Module_Rebuild_Spec.md`; the priority list is
[`UI_FEATURE_INVENTORY.md`](UI_FEATURE_INVENTORY.md).

**Where it runs**

| Environment | URL | Mode |
|---|---|---|
| Production | <https://crm-churn-demo.vercel.app> | CRM + `/previsioni`; `/api/health` and `/api/pipeline` served by a slim serverless API over `data/demo.slim.db` |
| Static mirror | <https://fabolousu.github.io/crm-churn-demo/> | Same screens, fixture-only (no server) |
| Local | `pnpm --dir web preview` after `pnpm --dir web build`; API via `uvicorn api.app:app --port 8000` | Full local stack |

Priority keys: **P0** = required for the designed screens; **P1** = specified and
reachable from a designed screen; **P2** = specified but not visible in the designs.

---

## 1. Site map

| Route | Screen | Status |
|---|---|---|
| `/` | `Lead personali aperti` — the CRM home grid | Live |
| `/lead/new` | `Scheda Lead` in create mode | Live |
| `/lead/:id` | `Scheda Lead` — record form | Live |
| `/aziende` | `Tutte le aziende` (read-only list) | Live (P1) |
| `/contatti` | `Tutti i contatti` (read-only list) | Live (P1) |
| `/iniziative` | `Anagrafiche Iniziative` (read-only list) | Live (P1) |
| `/non-incluso?entity=…` | Named gap screen for P1/P2 entities | Live |
| `/previsioni` | Pipeline queue, ranked by expected value | Live |
| `/previsioni/leads/:id` | Lead 360 — drivers and explanation | Live |
| `/previsioni/leads/:id/lever` | The lever — what would move the probability | Live |
| `/previsioni/act` | The act loop — commit an action, see the effect | Live |
| `/previsioni/portfolio` | Portfolio view — value, drift, calibration | Live |
| `/leads/:id`, `/act`, `/portfolio` | Legacy ML links | Redirect to `/previsioni/...` |
| any other | Not-found screen | Live |

---

## 2. Requirements

### 2.1 Application shell

| ID | Requirement | Pri | Status |
|---|---|---|---|
| S1 | Top bar with app launcher, app name `CRM CCIAA - PROMOS`, global search `Cerca` | P0 | Done |
| S2 | Top-bar icons: assistant, quick create `+ Crea`, advanced find, settings, help, avatar | P0 | Done |
| S3 | Collapsible left nav with the exact Italian groups: `Attività personali`, `Clienti`, `Interazioni`, `Entità di configurazione`, plus `Previsioni` | P0 | Done |
| S4 | `Recenti` / `Aggiunti` expandable lists and the `Area di lavoro` switcher | P2 | Labels only; listed as a gap |
| S5 | Global search across all entities | P1 | Lead-scoped, not cross-entity |

### 2.2 Lead list — `Lead personali aperti`

| ID | Requirement | Pri | Status |
|---|---|---|---|
| L1 | View title, `Predefinito` badge and a selector with the 7 system views | P0 | Done |
| L2 | Command bar: `Nuovo`, `Mostra grafico`, `Aggiorna`, `Modifica`, `Assegna`, `Elimina`, `Condividi`, `Esporta in Excel`, overflow | P0 | Done (some entries are inert placeholders) |
| L3 | `Modifica colonne` and `Modifica filtri` panels | P0 | Done |
| L4 | Nine default columns: Argomento, Contatto, Azienda, 1° Macro Settore, Anagr. interesse, Proprietario, Stato lavorazione, Creazione, Modifica | P0 | Done |
| L5 | Row checkboxes, select-all, `Modifica (N)` on selection | P0 | Done |
| L6 | Footer range and count, page size 50, pager | P0 | Done (single page at 42 rows) |
| L7 | Double-click / link on `Argomento` opens the record | P0 | Done |
| L8 | Sortable headers, quick find, status chips, bulk edit, CSV export | P1 | Done |
| L9 | Personal views (save/save-as/reset/share), Excel export, charts, import | P1/P2 | Gap — CSV only, no saved views |

### 2.3 Lead record — `Scheda Lead`

| ID | Requirement | Pri | Status |
|---|---|---|---|
| C1 | Command bar: back, `Salva`, `Salva e chiudi`, `+ Nuovo`, `Aggiorna`, `Assegna`, `Condividi`, `Invia link`, `Segui`, overflow | P0 | Done |
| C2 | Header: title, save state (`Salvataggio completato` / `Non salvato`), entity label, status + owner | P0 | Done |
| C3 | Tabs `Generale`, `Dati Amministrativi`, `Elementi correlati` | P0 | Done |
| C4 | All P0 fields, with `Manifestazione origine` and `Tipo interesse` read-only | P0 | Done |
| C5 | Required `*` markers and locked fields | P0 | Done |
| C6 | `Preview Azienda` / `Preview Contatto` panels and the activity list | P1 | Done (read-only) |
| C7 | Timeline with an activity composer, e-mail send and mailbox sync | P1/P2 | Display only |
| C8 | Record pager `14 di 86` | P1 | Shows index and count |

### 2.4 Business rules

| ID | Rule | Pri | Status |
|---|---|---|---|
| B1 | Status model is a configurable table (code, IT/EN label, category, order, legacy, active) | P0 | Done — 14 statuses |
| B2 | Moving to a closed status sets `Data chiusura`; reopening clears it | P0 | Done |
| B3 | One lead per `(Contatto, Iniziativa)`; the warning links to the existing lead | P0 | Done |
| B4 | A contact with one company auto-fills `Azienda`; several force a filtered choice | P0 | Done |
| B5 | Reassignment removes the lead from the old owner's open view | P0 | Done |
| B6 | Timeline unavailable before the first save | P1 | Done |
| B7 | Intake APIs (`POST /api/intake/*`), owner e-mail, audit trail | P1 | Not built (backend lane T13) |

### 2.5 Previsioni (AI module)

| ID | Requirement | Pri | Status |
|---|---|---|---|
| P1 | Ranked queue of open initiatives by expected value, with filters and sort | P0 | Done |
| P2 | Win probability plus the three SHAP drivers behind it | P0 | Done |
| P3 | The lever: the committable action that would raise the probability most | P0 | Done |
| P4 | Act loop: commit the action and show the probability move | P0 | Done |
| P5 | Portfolio view: expected value, drift/stability, calibration | P0 | Done |
| P6 | Model quality gate: AUC vs latent ceiling, calibration error, lift | P0 | Done (`tools/check_metrics.py` in CI) |

### 2.6 Non-functional

| ID | Requirement | Status |
|---|---|---|
| N1 | Italian locale by default: `dd/mm/yyyy HH:mm`, Europe/Rome, EUR | Done for the CRM; the Previsioni module is labelled in English |
| N2 | Accessibility: WCAG 2.0/2.1 A/AA, checked by axe on every route template | Pass — 0 violations |
| N3 | Responsive layout down to mobile (collapsible nav, scrollable grid) | Done |
| N4 | No secrets in the repository; public read-only demo API with validation, CORS allowlist, `nosniff`/`no-referrer` | Done (D7, documented exceptions) |
| N5 | The showcase runs without a backend (fixtures), so the pitch survives bad Wi-Fi | Done |
| N6 | Deployment: merge to `main` builds and deploys; uptime probe and deployment smoke | Done |

---

## 3. Features, screen by screen

### 3.1 The shell

A white top bar (`CRM CCIAA - PROMOS`, `TRADE AGENCY`), a global search box, the
quick-create button and the user avatar. The left navigation groups the areas in the
order the agency works: personal activity, customers, interactions, configuration, and
the **Previsioni** module. The bottom card shows the model version, when it was scored,
and whether it is live or running on fixtures.

### 3.2 `Lead personali aperti` (home)

The salesperson's work list. Each row answers *who, which company, which initiative,
whose, at what stage, since when*. Status chips carry their computed counts
(`Interessato 18`, `Da contattare 11`, `In attesa di riscontro 13` — 42 open leads in the
seeded demo).

- Seven system views: personal open, all, open, closed, positive outcomes, personal,
  personal closed.
- Filters by status, a quick find box, sortable columns, and a column picker that can add
  `Provincia (Azienda)` and `1° Settore (Azienda)`.
- Selection enables bulk edit (status + owner) and shows `N selezionati`.
- `Esporta in Excel` downloads exactly the filtered view as CSV.
- Row count, page size 50 and the pager are all computed from the data.

### 3.3 `Scheda Lead` (record)

The full record: contact, company, initiative, source, read-only references, requests,
internal notes, and the three date stamps. The header carries the working status and the
owner; the chevron opens the flyout where both are changed, then the record is saved.

The form enforces the process:

- `Contatto`, `Azienda` and `Anagrafica interesse` are required.
- A contact with one company locks `Azienda` to it; a contact with several companies
  offers only those companies.
- A second lead for the same contact and initiative is blocked, with a link to the
  existing one.
- A closed status stamps `Data chiusura`; reopening clears it.
- `Elementi correlati` lists the activity history; before the first save it says the
  record must be saved first.
- The right column previews the company and the contact and restates the active rules.

### 3.4 Previsioni

Five screens, reached from the left nav:

1. **Pipeline** — open initiatives ordered by expected value (probability × proposed
   ARR), with region filters and a sort switch. Each card shows the strongest driver,
   the probability and the value.
2. **Lead 360** — why this probability: the three drivers in SHAP points, the
   calibration context, the stability note.
3. **Lever** — what would move it: the committable actions, their point value, and a
   clearly-marked what-if (the discount counterfactual is never presented as advice).
4. **Act** — commit the action, see the projected probability and the recorded outcome.
5. **Portfolio** — pipeline value, at-risk value, win rate, calibration and drift status.

The model behind it: LightGBM, **AUC 0.773** against a latent ceiling of **0.789**,
calibration error **0.0104**, lift@10 **2.26** over 19,752 scored leads.

### 3.5 Master data

Read-only lists for **Aziende** (12), **Contatti** (14) and **Anagr. Iniziative** (8),
showing the columns the spec asks for (fiscal code, VAT, province, macro sector,
maturity, initiative code and owner). They exist so the navigation is real, not a set of
dead links.

### 3.6 Gaps, named

Entities outside the P0 demo (`Dashboard`, `Impegni`, `Rel. Aziende-Contatti`,
`Manif. Interesse`, `Servizi`, `Recenti`, `Aggiunti`) open a screen that says the module
is out of the P0 scope and points to the inventory. Nothing is faked as done.

---

## 4. Data

- **CRM seed** (`web/src/crm/seed.ts`): deterministic, Italian, 12 companies, 14 contacts,
  8 initiatives, 48 leads (42 open + 6 closed), 14 statuses. The builder enforces
  `(Contatto, Iniziativa)` uniqueness, so the data obeys the rule the UI checks.
- **ML dataset**: synthetic world of 20,000 companies and 60,000 leads, prevalence
  28.66%, generated with a known latent process (`data/generator.py`, seed 42).
- **Serving DB**: `data/demo.slim.db` (2.4 MB) with the top 2,000 open leads by expected
  value and precomputed leverage; the 240 MB training DB stays local.
- **No fabricated numbers**: every figure on screen is computed from the seed, the API,
  or `ml/artifacts/metrics.json`.

## 5. API surface

| Endpoint | Serverless | Local |
|---|---|---|
| `GET /api/health` | Yes | Yes |
| `GET /api/pipeline` | Yes | Yes |
| `GET /api/leads/{id}` | No | Yes |
| `GET /api/leads/{id}/counterfactual` | No | Yes |
| `GET /api/leads/{id}/actions` | No | Yes |
| `GET /api/companies/{id}` | No | Yes |
| `GET /api/portfolio` | No | Yes |

The deployed UI runs on fixtures; `VITE_API_BASE` switches it to the API. Full endpoint
parity on the serverless function is a later lane.

## 6. How the site is verified

| Gate | What it proves |
|---|---|
| `pytest` (191 tests) | Generator, features, model, API contract, CRM schema, serverless, deployment scripts |
| `tools/check_metrics.py` | Model quality: AUC vs ceiling, calibration, lift |
| `tsc --noEmit` + `vite build` | Type safety and a production build |
| `pnpm --dir web check:crm` | 13 P0 behaviours driven in a real browser (validation, auto-link, uniqueness, closing date, reassignment, views, columns) |
| `pnpm --dir web check:ui` | axe WCAG 2.0/2.1 A/AA and a rendered link crawl: 23 routes, 13 templates, 0 violations, 0 broken links |
| CI + CodeRabbit + Vercel + deployment smoke | Every merge is reviewed, built, deployed and probed |

## 7. Glossary

| Term | Meaning |
|---|---|
| **Iniziativa** | A trade mission, event, course or service the agency promotes to companies |
| **Lead** | One company's interest in one initiative — the unit of work |
| **Contatto** | The person at the company |
| **Azienda** | The company |
| **Anagrafica interesse** | The initiative attached to a lead |
| **Stato lavorazione** | The working status (open or closed) |
| **Data chiusura** | Closing date, set automatically by a closed status |
| **Previsioni** | The AI module: ranked pipeline, drivers, lever, act loop, portfolio |
