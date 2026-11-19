# UI feature inventory — CRM sales module

Derived from every file in `crm design/`:

| File | What it gave |
|---|---|
| `CRM_Sales_Module_Rebuild_Spec.md` (509 lines) | The full functional spec: 16 sections, domain glossary, data model, status model, workflows, views/filters, import/export, security, NFRs, 12 acceptance tests |
| `.stitch/metadata.json` | Stitch project `3133723532266431010`, design system **Promos Sales Fresh** (Inter, light, accent `#1F8A4C`, 8px radius), 3 screens |
| `designs/lead-personali-aperti.html` (+ `.png`) | Lead list, v1: shell, command bar, view title + `Predefinito`, 9 grid columns |
| `designs/lead-personali-aperti-v2.html` (+ `.png`) | Same list, v2 (revised column labels, `Sincronizzato adesso`, no `Ctrl+K`) |
| `designs/scheda-lead.html` (+ `.png`) | Lead record form: save/save-and-close, record pager `14 di 86`, save state, timeline |
| `www.pipedrive.com_it_edited.png` (5 MB) | Visual reference only — the target look-and-feel language |

**The designed screens are the P0 scope**: the application shell, the `Lead personali aperti`
list, and the `Scheda Lead` form. Everything else in the spec is P1/P2 and is listed as a gap
with a target — the gate for this workstream allows gaps, but not unlisted ones.

Priority keys: **P0** = on a designed screen, must exist for the demo to be the specified
product. **P1** = named in the spec and reachable from a designed screen. **P2** = specified
but not visible in the three designs.

## A. Application shell (§2)

| ID | Feature | Spec | Pri | Target |
|---|---|---|---|---|
| A1 | Top bar: app launcher, org logo, app name `CRM CCIAA - PROMOS` | §2.1 | P0 | `AppShell` |
| A2 | Global search `Cerca` (type-ahead across entities) | §2.1, §7.5 | P1 | `TopBar` + `/api/search` |
| A3 | Icons: assistant, quick create `+`, advanced find, settings, help, avatar | §2.1 | P0 | `TopBar` |
| A4 | Collapsible left nav with the six groups and exact Italian labels | §2.2 | P0 | `SideNav` |
| A5 | `Recenti` / `Aggiunti` expandable recent + pinned lists | §2.2 | P2 | `SideNav` |
| A6 | `Area di lavoro` workspace switcher | §2.2 | P2 | `SideNav` |
| A7 | Locale: Italian default, `dd/mm/yyyy HH:mm`, Europe/Rome, i18n resources | §14 | P0 | `i18n/` |

## B. Lead list — `Lead personali aperti` (§2.3, §7)

| ID | Feature | Spec | Pri | Target |
|---|---|---|---|---|
| B1 | View title + `Predefinito` badge + view selector dropdown | §7.1, §7.2 | P0 | `/leads?view=` , `ViewSelector` |
| B2 | Command bar: `Nuovo`, `Mostra grafico`, `Aggiorna`, `Modifica`, `Assegna`, `Elimina`, `Condividi`, `Esporta in Excel`, `⋮` | §2.3 | P0 | `CommandBar` |
| B3 | `Modifica colonne` and `Modifica filtri` entry points | §7.3, §7.4 | P0 | list toolbar |
| B4 | Grid columns: Argomento, Contatto, Azienda, 1° Macro Settore, Anagr. interesse, Proprietario, Stato lavorazione, Creazione, Modifica | §7.1 | P0 | `LeadGrid` |
| B5 | Row checkboxes + select-all; `Modifica` appears on selection | §2.3 | P0 | `LeadGrid` |
| B6 | Sortable headers with per-column menu (`Ordina A-Z`, `Z-A`, `Filtra per`) | §7.4 | P1 | `ColumnMenu` |
| B7 | Footer: `1 - 50 di N` (≥5000 → `5000+`), first/prev/next pager, page size 50 | §2.3 | P0 | `GridFooter` |
| B8 | Double-click primary cell opens the record; lookup cells open related records | §2.3 | P0 | `LeadGrid` |
| B9 | Quick find in this view, leading `*` = contains-search | §7.5 | P1 | list toolbar |
| B10 | System views: personali aperti, tutti, aperti, chiusi, conclusi positivi, personali, personali chiusi | §7.1 | P1 | view registry |
| B11 | Personal views: save, save-as, reset, set-default, manage/share; `*` unsaved marker | §7.2 | P1 | view engine |
| B12 | Edit-columns panel with related-entity fields (`Provincia (Azienda)`), search, type filter, drag reorder | §7.3 | P2 | column panel |
| B13 | Filter builder: operators per type, multi-select lookups, AND/OR groups | §7.4 | P2 | filter builder |
| B14 | Bulk edit dialog `Modifica N record`, only changed fields written, result summary | §7.6 | P1 | bulk dialog |
| B15 | `Esporta in Excel` — whole filtered view, not the page | §8.1 | P1 | `/api/export` |
| B16 | Charts pane (`Mostra grafico`), dashboards, `Esegui report` | §7.7 | P2 | dashboards |
| B17 | Import from Excel, Excel templates | §8.1 | P2 | import |

## C. Lead form — `Scheda Lead` (§2.4, §3.6, §4, §6)

| ID | Feature | Spec | Pri | Target |
|---|---|---|---|---|
| C1 | Command bar: back, `Salva`, `Salva e chiudi`, `+ Nuovo`, `Aggiorna`, `Assegna`, `Condividi`, `Invia link tramite messaggio`, `Segui`, `⋮` | §2.4, §9 | P0 | `/leads/:id`, `FormCommandBar` |
| C2 | Header: title, save state (`Salvataggio completato` / `Non salvato`), entity label, header fields `Stato lavorazione` + `Proprietario` with chevron flyout | §2.4 | P0 | `RecordHeader` |
| C3 | Record pager `14 di 86` | §2.4 | P1 | `RecordHeader` |
| C4 | Tabs: `Generale`, `Dati Amministrativi`, `Elementi correlati` | §3.6 | P0 | `LeadForm` |
| C5 | Fields: Argomento (auto), Descrizione, Azienda*, Contatto*, Anagrafica interesse*, Manifestazione origine (RO), Tipo interesse (RO), Richieste (RO), Fonte, Note migrate, Data creazione/chiusura/modifica | §3.6 | P0 | `LeadForm` |
| C6 | Required markers `*`, locked fields, read-only fields | §2.4 | P0 | field renderer |
| C7 | Quick views `Preview Azienda` and `Preview Contatto` | §3.6 | P1 | `PreviewPanel` |
| C8 | Sub-grids on the record (`Elementi correlati`) | §2.4 | P1 | `SubGrid` |
| C9 | Timeline: `+` create (Appuntamento, Attività, E-mail, Telefonata, Nota), filter, search, inline note, status chip | §6 | P1 | `Timeline` |
| C10 | Timeline unavailable before first save: "Save the record to add activities" | §5.3 | P1 | `Timeline` |
| C11 | Lead status model as a **configurable table** (code, IT/EN label, category, defaults, legacy, active) | §4.1 | P0 | `lead_statuses` + seed |
| C12 | Closed status sets `Data chiusura`; reopening clears it | §4.2 | P0 | status transition hook |
| C13 | Status change via header flyout then `Salva`; bulk via §7.6 | §4.3 | P0 | header flyout |
| C14 | Uniqueness: one lead per (Contatto, Anagrafica interesse), with a warning linking to the existing lead | §3.6 | P0 | API constraint |
| C15 | Company auto-link: one relationship → autofill; several → filtered lookup | §5.3 | P0 | lead create flow |
| C16 | Three manual creation entry points (Contact, Company, Initiative tabs) with prefills | §5.3 | P1 | create routes |
| C17 | Reassignment via owner flyout or `Assegna`; disappears from old owner's open view | §5.4 | P0 | owner flyout |
| C18 | E-mail composer: From/To/Cc/Bcc, rich text, templates, signature, attach, send | §6.1 | P2 | composer |
| C19 | Mailbox sync (Sent folder) + `CRM:NNNNNNN` tracking token | §6.1 | P2 | mail integration |

## D. Intake, security, notifications (§5.1, §10, §12)

| ID | Feature | Spec | Pri | Target |
|---|---|---|---|---|
| D1 | `POST /api/intake/interest` → lead `Interessato`, owner = initiative 1° Referente, idempotent | §5.1 | P1 | intake API |
| D2 | `POST /api/intake/event-registration` → lead `Iscritto all'evento` (closed) | §5.1 | P1 | intake API |
| D3 | `POST /api/intake/inbuyer-signup` → open lead | §5.1 | P2 | intake API |
| D4 | New-lead e-mail to owner with working deep link | §5.1, §12 | P1 | notifier |
| D5 | RBAC, teams, business units, sharing, `Verifica l'accesso` | §10 | P2 | authz |
| D6 | Audit trail on status and owner changes | §10, §14 | P1 | audit log |
| D7 | GDPR: consent fields, export and erasure per contact | §14 | P2 | privacy |

## E. Master data behind the screens (§3.1–3.5, §3.7, §3.8)

| ID | Feature | Pri | Note |
|---|---|---|---|
| E1 | `Azienda` entity + fields + tabs + sub-grids | P1 | Needed by lead Azienda lookup and previews |
| E2 | `Contatto` entity + fields + sub-grids | P1 | Needed by lead Contatto lookup and previews |
| E3 | `Relazione Azienda Contatto` join entity | P1 | Drives the company auto-link rule |
| E4 | `Anagrafica Iniziativa` + code pattern `INI-NNNNNN` + referenti | P1 | Drives owner default and `Anagr. interesse` lookup |
| E5 | `Manifestazione di Interesse` + back-reference to the generated lead | P2 | Source of the intake flow |
| E6 | `Servizio` entity | P2 | Spec says "no details given" — open question §16.1 |
| E7 | Polymorphic `Attività` (E-mail, Nota, Appuntamento, Telefonata, Attività) | P2 | Backs the timeline |

## Gaps and open items (this workstream, before implementation)

| # | Gap | Owner | Next step |
|---|---|---|---|
| G1 | **No entity exists in the current backend for Azienda, Contatto, Iniziativa, Attività.** Today's schema is `companies/leads/lead_features/...` for the ML demo | Backend lane | Add the CRM entities as a new schema unit; keep the ML tables untouched |
| G2 | **The spec describes a CRM; the repo contains an ML win-probability demo.** They are different products sharing a shell | Product (you) | Decide: replace the demo UI with the CRM, or add the CRM as the primary app and keep the ML screens as an "AI" module |
| G3 | P0 has no data source yet: 9 grid columns + form fields need seeded Azienda/Contatto/Iniziativa/Lead rows | Data lane | Seed a deterministic Italian dataset (reuse `data/generator.py` style) |
| G4 | Real e-mail send + mailbox sync needs provider credentials | Integrations | Out of scope for the demo; document as P2 gap |
| G5 | Excel export/import needs a library and server-side query engine | Backend | P1; schedule after P0 |
| G6 | `Servizio` is unspecified in the source manual | Stakeholder | Ask (§16.1); do not invent fields |
| G7 | Three HTML designs disagree slightly (v1 vs v2 column labels, `Ctrl+K`) | Design | Implement **v2** as the current truth, keep v1 as history |
