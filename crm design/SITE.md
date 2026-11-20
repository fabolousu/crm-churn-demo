# Stitch SITE.md: CRM CCIAA - PROMOS

This document is the project constitution and screen specification for the Stitch design phase.
It covers screen definitions, navigation flows, exact Italian labels, legacy state wording, P0 rules, and backlog priorities.

---

## 1. Core Identity

* **Project Name:** CRM CCIAA - PROMOS (Sales Module & Previsioni)
* **Stitch Project ID:** `3133723532266431010`
* **Mission:** A B2B CRM for an Italian chamber of commerce agency (Promos Italia) that manages customer initiatives, leads, and master data, paired with an AI module (Previsioni) that ranks opportunities by expected value and explains win probability drivers.
* **Target Audience:** Initiative managers (Referente dell'iniziativa, record owner/Proprietario), sales representatives, and agency leadership.
* **Voice:** Professional, institutional, calm, cockpit-dense, strictly informational, and data-centric.

---

## 2. Visual Language

* **Primary Aesthetic:** Cockpit-dense (table density showing 25+ rows at 1080p, tabular numerals, 0 to 2px corners).
* **Secondary Aesthetic:** Border-driven (dividers and underlines using `#DBE2E8` and `#AFBAC4`, no shadows, no gradients).
* **Tertiary Aesthetic:** Promos Italia palette (Brand Blue `#005EB8` for primary actions and selection, Ink `#19242E` for dark text, Surface `#EEF2F5` for structural chrome, Positive Green `#88E771` reserved strictly for positive-closed statuses).

---

## 3. Architecture & File Structure

* **Root Output Directory:** `crm design/designs/`
* **Asset Flow:** Stitch generates screens into `crm design/designs/` -> Verification -> Integration into `web/`
* **Navigation Strategy:**
  * Top bar: App launcher, App name `CRM CCIAA - PROMOS`, sub-label `TRADE AGENCY`, global search `Cerca`, Quick create `+ Crea`, Assistant, Advanced find, Settings, Help `?`, User avatar.
  * Collapsible left navigation (sitemap):
    * Top group: `Home`, `Recenti`, `Aggiunti`
    * `Attività personali`: `Dashboard`, `Impegni`
    * `Clienti`: `Aziende`, `Contatti`, `Rel. Aziende-Contatti`
    * `Interazioni`: `Lead`, `Manif. Interesse`, `Servizi`
    * `Entità di configurazione`: `Anagr. Iniziative`
    * `Previsioni` (AI module): `Pipeline` (Queue), `Portfolio`, `Lead 360` (drilldown from Queue), `Lever` (drilldown), `Act` (drilldown)
    * Bottom: `Area di lavoro`

---

## 4. Live Sitemap & Screen Inventory

| Route | Screen Name / Code | Role & Scope | Status | Priority |
|---|---|---|---|---|
| `/` | `Lead personali aperti` | Main CRM home grid, personal open leads view | Live | P0 |
| `/lead/:id` | `Scheda Lead` (Visualizzazione) | Lead record detail view (3 tabs, flyouts, preview panels) | Live | P0 |
| `/lead/new` | `Scheda Lead` (Creazione) | New lead creation form with contextual rules | Live | P0 |
| `/previsioni` | `Previsioni queue` (Pipeline) | Ranked queue of initiatives by expected value | Live | P0 |
| `/previsioni/leads/:id` | `Lead 360` | Initiative detail with probability, 3 SHAP drivers, calibration | Live | P0 |
| `/previsioni/leads/:id/lever` | `Lever` (Cosa muove la probabilità) | Action simulator, point lifts, what-if discount analysis | Live | P0 |
| `/previsioni/act` | `Act` (Ciclo di azione) | Action commitment loop, probability impact, outcome logging | Live | P0 |
| `/previsioni/portfolio` | `Portfolio` (Vista portafoglio) | Macro portfolio metrics, expected value, calibration, drift | Live | P0 |
| `/aziende` | `Tutte le aziende` | Master data read-only company list | Live | P1 |
| `/contatti` | `Tutti i contatti` | Master data read-only contact list | Live | P1 |
| `/iniziative` | `Anagrafiche Iniziative` | Master data read-only initiative catalogue | Live | P1 |
| `/stati` | `Stati e schemi di stato` | Reference screen for system states (empty, loading, error) | Target | P0 |
| `/non-incluso` | `Gap screen` | Explanatory placeholder for out-of-scope modules | Live | P1 |

---

## 5. Detailed Screen Specifications

### 5.1 Lead personali aperti (Home Grid)
* **Priority:** P0
* **Route:** `/`
* **Role:** The primary daily workspace for sales owners. Displays open leads owned by the user.
* **Header & View Selector:**
  * Title: `Lead personali aperti`
  * Badge: `Predefinito`
  * System Views Selector (`Visualizzazioni di sistema`):
    1. `Lead personali aperti` (Predefinito di sistema)
    2. `Tutti i lead`
    3. `Lead aperti`
    4. `Lead chiusi`
    5. `Lead conclusi con esito positivo`
    6. `Lead personali`
    7. `Lead personali chiusi`
* **Status Chips (Filter bar):**
  * `Tutti` (42)
  * `Interessato` (18)
  * `Da contattare` (11)
  * `In attesa di riscontro` (13)
* **Command Bar Actions:**
  * `Nuovo` (creates lead), `Mostra grafico`, `Aggiorna`, `Modifica` (bulk edit when rows selected), `Assegna`, `Elimina`, `Condividi`, `Esporta in Excel` (CSV in live app), `⋮` (overflow).
  * Panel toggles: `Modifica colonne`, `Modifica filtri`, search box `Cerca in questa vista`.
* **Grid Columns (Default 9 + 2 expandable):**
  1. `Argomento` (text link, double-click opens record)
  2. `Contatto` (lookup text)
  3. `Azienda` (lookup text)
  4. `1° Macro Settore` (lookup text)
  5. `Anagr. Interesse` (lookup text)
  6. `Proprietario` (owner badge with initials)
  7. `Stato lavorazione` (status chip)
  8. `Creazione` (date: `dd/mm/yyyy`)
  9. `Modifica` (datetime: `dd/mm/yyyy HH:mm`)
  10. *(Optional column)* `Provincia (Azienda)`
  11. *(Optional column)* `1° Settore (Azienda)`
* **Grid Footer:**
  * Counter: `1 - 42 di 42 record` (or `0 di 0 record`)
  * Selection badge: `N selezionati`, with action `Deseleziona tutti`
  * Selector: `Righe per pagina: 50`
  * Pager: `Pagina 1 di 1` (First, Previous, Next, Last)
* **States & Legacy Wording:**
  * Empty State: `Nessun lead in questa vista. Modifica i filtri o crea un nuovo lead.` (Legacy grid: `Nessun dato disponibile`, footer reads `0 - 0 di 0`).
  * Loading State: `Caricamento dati in corso...`
  * Error State: `Si è verificato un errore durante il caricamento dei record. Riprovare.`
* **P0 Rules Enforced:**
  * Multi-column sort: secondary sort by `Modifica` descending.
  * Row checkboxes with select-all.
  * Bulk edit (`Modifica N record`) updates status and owner in batch.
  * Leads assigned away or closed leave `Lead personali aperti`.

---

### 5.2 Scheda Lead: Visualizzazione (Lead Record View)
* **Priority:** P0
* **Route:** `/lead/:id`
* **Role:** Detailed working view of an existing lead record.
* **Command Bar:**
  * `←` (Back to list), `Salva`, `Salva e chiudi`, `+ Nuovo`, `Aggiorna`, `Assegna`, `Condividi`, `Invia link`, `Segui`, `⋮` (overflow).
* **Record Header:**
  * Entity label: `LEAD`
  * Record Title: e.g. `Interesse partecipazione B2B agroalimentare Stoccolma, Moltren Società Agricola Semplice`
  * Save Indicator: `Salvataggio completato` (saved) or `Non salvato` (modified)
  * Header Fields (editable via chevron flyout):
    * `Stato lavorazione`: dropdown with 10 standard statuses
    * `Proprietario`: type-ahead user lookup (default owner: Marta Rossi)
* **Tabs:**
  1. `Generale`
  2. `Dati Amministrativi`
  3. `Elementi correlati`
* **Tab 1: Generale (Sections & Fields):**
  * Section `INFORMAZIONI PRINCIPALI`:
    * `Argomento` (text, required/locked)
    * `Contatto` (lookup, locked)
    * `Azienda` (lookup, locked)
    * `Anagrafica interesse` (lookup, locked)
    * `Fonte` (choice, locked, e.g. `Manifestazione di interesse`)
    * `Descrizione` (multiline text)
  * Section `INTERESSE`:
    * `Manifestazione interesse origine` (lookup, read-only/locked, e.g. `MI-2025-08420`)
    * `Tipo interesse` (choice, read-only, e.g. `Prima Assistenza`)
    * `Richieste del Contatto/Cliente` (multiline text, read-only)
  * Section `DETTAGLI`:
    * `Data creazione` (datetime, read-only)
    * `Data chiusura` (datetime, read-only, set when closed, cleared when reopened)
* **Tab 2: Dati Amministrativi:**
  * `Note migrate` (multiline text, editable)
  * `ID lead` (text, locked, e.g. `L-9020`)
  * `Proprietario attuale` (text, locked)
* **Tab 3: Elementi correlati (Timeline / Sequenza temporale):**
  * Activity items list (Email, Telefonata, Nota)
  * Item structure: icon, title (`E-mail inviata da Marta Rossi`), timestamp, body preview
* **Side Panels (Right column):**
  * `Preview Azienda`: Denominazione, Settori, Provincia, Tipologia, Partita IVA.
  * `Preview Contatto`: Nome completo, E-mail, Telefono, Maturità anagrafica, Consenso privacy.
  * `Regole attive` panel:
    * Un lead per contatto e iniziativa (unicità).
    * Una sola azienda del contatto: compilata automaticamente.
    * Stato chiuso imposta Data chiusura; la riapertura la cancella.
* **States & Legacy Wording:**
  * Empty Timeline: `Nessuna attività registrata per questo lead.`
  * Loading State: `Caricamento scheda lead in corso...` (Timeline loading: `Caricamento sequenza temporale in corso`)
  * Error State: `Impossibile caricare il lead specificato. Verificare l'identificativo o i permessi di accesso.`
* **P0 Rules Enforced:**
  * B2: Moving to a closed status stamps `Data chiusura`; reopening clears it.
  * B5: Reassignment moves the lead to the new owner's queue.

---

### 5.3 Scheda Lead: Creazione (Lead Record Create)
* **Priority:** P0
* **Route:** `/lead/new`
* **Role:** Creation form for manual lead intake.
* **Command Bar:**
  * `←` (Back), `Salva`, `Salva e chiudi`, `+ Nuovo`.
* **Record Header:**
  * Entity label: `LEAD`
  * Record Title: `Nuovo Lead`
  * Save Indicator: `Non salvato`
  * Header Fields:
    * `Stato lavorazione`: defaults to `Nuovo` (choice)
    * `Proprietario`: defaults to current user (Marta Rossi)
* **Form Sections & Fields:**
  * `Contatto *` (lookup, required)
  * `Azienda *` (lookup, required, auto-linked if single relationship exists)
  * `Anagrafica interesse *` (lookup, required)
  * `Fonte` (choice, defaults to `Contatto diretto` or `Manuale`)
  * `Descrizione` (multiline text)
  * `Richieste del Contatto/Cliente` (multiline text)
* **Conditional Visibility Rules (Manual vs Origin):**
  * If created manually without an expression of interest: hide `Manifestazione interesse origine` and `Tipo interesse`; show `Evento di origine` where relevant.
* **Validation & Uniqueness Gate:**
  * Duplicate check: If `(Contatto, Anagrafica interesse)` pair already exists, block submission with message: `Esiste già un lead per questo contatto e questa iniziativa.` and provide a deep link: `Apri lead esistente (L-XXXX)`.
* **Side Panels:**
  * `Preview Contatto` and `Preview Azienda` dynamically reflect lookups.
  * Notice on `Elementi correlati`: `Salva il record per aggiungere attività alla sequenza temporale.`
* **States & Legacy Wording:**
  * Loading Lookup: `Caricamento anagrafiche in corso...`
  * Unsaved warning: `Le modifiche non salvate andranno perse.`

---

### 5.4 Previsioni: Pipeline Queue
* **Priority:** P0
* **Route:** `/previsioni`
* **Role:** Open initiatives queue ranked by expected value (valore atteso = probability * proposed ARR).
* **Header:**
  * Eyebrow: `Pipeline · Previsioni AI`
  * Title: `Iniziative per valore atteso`
  * Subtitle: `Coda delle opportunità ordinate per valore atteso: probabilità moltiplicata per ARR proposto.`
  * Actions: Link button `Vista Portfolio` (`/previsioni/portfolio`)
* **KPI Summary Cards (Top):**
  1. `Valore atteso pipeline`: Expected value sum (EUR format)
  2. `Valore a rischio`: Pipeline ARR minus expected value
  3. `Tasso di conversione storico` (Win prevalence baseline): percentage
  4. `Iniziative aperte`: total count
* **Filters & Sorting:**
  * Region filter: `Tutte le regioni`, `Nord-Ovest`, `Nord-Est`, `Centro`, `Sud e Isole`
  * Sort selector:
    * `Valore atteso` (expected value, default)
    * `Valore a rischio` (at risk)
    * `Leva massima` (leverage)
* **Queue Row Elements:**
  * Rank number (`#1`, `#2`, ...)
  * Company name (`Azienda`) & Initiative name (`Iniziativa`)
  * Primary SHAP driver badge (top factor moving the probability)
  * Probability badge (`Probabilità`) with visual dial/percentage
  * Proposed ARR (`Valore ARR`)
  * Expected Value (`Valore atteso`)
  * Actions: `Dettagli Lead 360` (`/previsioni/leads/:id`)
* **States & Legacy Wording:**
  * Empty State: `Nessuna iniziativa trovata per i filtri selezionati.`
  * Loading State: `Calcolo previsioni e ordinamento pipeline in corso...`
  * Error State: `Impossibile caricare la coda delle previsioni. Errore di connessione al servizio AI.`
* **P0 Rules Enforced:**
  * Terms stay mathematically honest: probability (probabilità), three drivers (tre fattori determinanti / driver SHAP), expected value (valore atteso).
  * Tabular numbers on all currency and percentage figures.

---

### 5.5 Previsioni: Lead 360
* **Priority:** P0
* **Route:** `/previsioni/leads/:id`
* **Role:** Explainability cockpit for an individual initiative win probability.
* **Header & Navigation:**
  * Back link: `← Torna alla coda pipeline`
  * Title: Company Name & Initiative Name
  * Status badge & Rank: `#N nella coda pipeline`
  * Sub-navigation tabs: `Lead 360`, `Leva (Lever)`, `Azione (Act)`
* **Core Score Display:**
  * `Probabilità di conversione` (Win probability %): displayed in large dial
  * `Valore atteso` (Expected value in EUR)
  * `ARR proposto` (Proposed ARR in EUR)
  * `Contesto di calibrazione`: Comparison against regional and global baseline win rate
* **Three Drivers Section (Tre fattori determinanti):**
  * Lists the top 3 SHAP drivers:
    1. Strongest positive or negative driver
    2. Second driver
    3. Third driver
  * Each driver card displays:
    * Metric name (e.g. `Coinvolgimento sponsor esecutivo`, `Storico iniziative concluse`, `Complessità bando`)
    * SHAP point impact: e.g. `+14.2 punti` or `-8.5 punti`
    * Narrative explanation of the score contribution
* **Model Stability & Metadata:**
  * `Affidabilità della previsione`: Stabilità modello (Stabile / Attenzione)
  * `Versione modello`: LightGBM v2.4 (AUC 0.773, Errore calibrazione 0.0104)
  * `Data attribuzione punteggio`: Datetime
* **States & Legacy Wording:**
  * Loading State: `Caricamento analisi Lead 360 in corso...`
  * Error State: `Impossibile calcolare i fattori determinanti per questa iniziativa.`

---

### 5.6 Previsioni: Lever (Cosa muove la probabilità)
* **Priority:** P0
* **Route:** `/previsioni/leads/:id/lever`
* **Role:** Prescriptive leverage simulator showing which committable actions raise the win probability most.
* **Header & Tabs:** Same sub-navigation tabs as Lead 360.
* **Interactive Levers List:**
  1. `Incontro con sponsor esecutivo`:
     * Description: Un incontro strutturato con il decisore aziendale e miglioramento della salute della relazione.
     * Potential lift: e.g. `+18 punti percentuali`
     * Status: Azione raccomandata (Rank 1)
  2. `Sessione di discovery approfondita`:
     * Description: Sessione di analisi requisiti con il buyer per validare i requisiti tecnici ed economici.
     * Potential lift: e.g. `+9 punti percentuali`
  3. `Variazione sconto (What-if)`:
     * Description: Simulazione ipotetica. Il modello tratta lo sconto elevato come attrito; non costituisce una raccomandazione operativa.
     * Interactive slider: Percentuale sconto (0% - 40%)
* **Simulated Outcome Card:**
  * `Probabilità attuale` vs `Probabilità simulata`
  * `Incremento valore atteso`: Difference in EUR
  * CTA: `Pianifica questa azione` (redirects to Act screen)
* **States & Legacy Wording:**
  * Loading State: `Simulazione leve in corso...`
  * Error State: `Errore durante il calcolo delle variazioni di probabilità.`

---

### 5.7 Previsioni: Act (Ciclo di azione)
* **Priority:** P0
* **Route:** `/previsioni/act` (or `/previsioni/act?leadId=:id&lever=:key`)
* **Role:** Execution loop where the salesperson commits an action and registers the real-world probability move.
* **Action Selector:**
  * Action types: `Incontro con sponsor esecutivo`, `Sessione di discovery`, `Telefonata di allineamento`, `Follow-up e-mail`
  * Action date picker & Notes field: `Note operative sull'azione`
* **Impact Preview:**
  * Pre-action rank & probability vs Post-action projected rank & probability
  * Pipeline repositioning indicator: e.g. `Avanza di 4 posizioni nella coda pipeline`
* **Commit Bar:**
  * Action button: `Conferma e registra azione`
* **Post-Commit Outcome Logging:**
  * Confirmation banner: `Azione registrata con successo. Il modello ha aggiornato il punteggio.`
  * Summary table showing before vs after probability, expected value, and new position.
* **States & Legacy Wording:**
  * Loading State: `Registrazione azione e ricalcolo punteggio in corso...`
  * Error State: `Impossibile completare la registrazione dell'azione.`

---

### 5.8 Previsioni: Portfolio
* **Priority:** P0
* **Route:** `/previsioni/portfolio`
* **Role:** Executive overview of total pipeline value, model calibration, drift, and regional health.
* **Macro KPI Cards:**
  1. `Valore totale pipeline`: Gross pipeline ARR
  2. `Valore atteso totale`: Total probability-weighted expected ARR
  3. `Valore a rischio`: ARR at risk (Total - Expected)
  4. `Stato calibrazione`: Expected vs Observed win rate
* **Regional Breakdown (Table & Bar Chart):**
  * Columns: `Regione`, `Iniziative aperte`, `ARR totale`, `Valore atteso`, `Tasso di vincita stimato`
  * Regions: `Nord-Ovest`, `Nord-Est`, `Centro`, `Sud e Isole`
* **Model Quality & Drift Metrics:**
  * `Stato stabilità dati`: `Stabile` (Drift status)
  * `AUC ROC`: 0.773 (Tetto latente: 0.789)
  * `Errore di calibrazione (ECE)`: 0.0104
  * `Grafico di calibrazione`: Scatter chart of predicted probabilities vs observed win rate
* **States & Legacy Wording:**
  * Loading State: `Caricamento metriche di portafoglio in corso...`
  * Error State: `Impossibile recuperare i dati aggregati di portafoglio.`

---

### 5.9 Master Data Lists (Anagrafiche)
* **Priority:** P1 (Essential for real navigation and preview links)

#### 5.9.1 Tutte le aziende (`/aziende`)
* **Title:** `Tutte le aziende` (12 aziende)
* **Badge:** `Predefinito`
* **Columns:**
  1. `Denominazione` (Primary, company name)
  2. `Codice Fiscale` (Tabular text)
  3. `Partita IVA` (Tabular text)
  4. `Provincia` (Lookup code, e.g. RAVENNA)
  5. `1° Macro Settore` (e.g. Agroalimentare, Meccanica)
  6. `Tipologia` (e.g. PMI, Media impresa, Micro impresa)
* **Empty State:** `Nessun dato disponibile` (legacy) / `0 - 0 di 0`

#### 5.9.2 Tutti i contatti (`/contatti`)
* **Title:** `Tutti i contatti` (14 contatti)
* **Badge:** `Predefinito`
* **Columns:**
  1. `Nome completo` (Primary)
  2. `E-mail` (Clickable `mailto:` link)
  3. `Telefono` (Clickable `tel:` link)
  4. `Maturità anagrafica` (Prospect, Lead, Cliente)
  5. `Aziende` (Related company names)
* **Empty State:** `Nessun dato disponibile` (legacy) / `0 - 0 di 0`

#### 5.9.3 Anagrafiche Iniziative (`/iniziative`)
* **Title:** `Anagrafiche Iniziative con codici` (8 iniziative)
* **Badge:** `Predefinito`
* **Columns:**
  1. `Codice` (INI-2025-XXXXXX)
  2. `Iniziativa` (Primary name)
  3. `1° Referente` (Owner name)
* **Empty State:** `Nessun dato disponibile` (legacy) / `0 - 0 di 0`

---

### 5.10 Stati e schemi di stato (States Specification Screen)
* **Priority:** P0 (Design system compliance)
* **Route:** `/stati`
* **Role:** Dedicated visual catalog of all system states across components to ensure zero unhandled edge states.
* **Component States Catalog:**
  1. **Griglia vuota (Empty Grid):**
     * Text: `Nessun dato disponibile`
     * Sub-text: `Nessun lead in questa vista. Modifica i filtri o crea un nuovo lead.`
     * Footer: `0 - 0 di 0 record`
  2. **Caricamento griglia (Grid Loading):**
     * Text: `Caricamento dati in corso...`
     * Skeleton row placeholders with `#EEF2F5` tint
  3. **Caricamento scheda e sequenza temporale (Form & Timeline Loading):**
     * Text: `Caricamento scheda lead in corso...`
     * Timeline text: `Caricamento sequenza temporale in corso`
  4. **Stato non salvato (Unsaved Changes Warning):**
     * Title: `Modifiche non salvate`
     * Text: `Le modifiche non salvate andranno perse. Continuare?`
     * Actions: `Salva modifiche`, `Annulla`
  5. **Errore di caricamento o validazione (Error Banner & Field Error):**
     * Text: `Si è verificato un errore durante l'operazione.`
     * Field error border: `#E74C3C`, background tint `#FDECEA`
  6. **Stato duplicato bloccato (Uniqueness Warning):**
     * Text: `Esiste già un lead per questo contatto e questa iniziativa.`
     * Link: `Apri lead esistente`

---

## 6. Business Rules and P0 Enforcement Summary

* **B1 (Status Model Table):** 14 statuses implemented as a configurable table:
  * Open (6): `Nuovo`, `Interessato`, `Da contattare`, `In attesa di riscontro`, `Interessato InBuyer` (legacy), `Da richiamare` (legacy).
  * Closed (8): `Prefattibilità negativa`, `Nessuna risposta`, `Non interessato`, `Iscritto all'evento`, `Servizio concluso`, `Contratto concluso`, `Concluso` (legacy), `Perso` (legacy).
* **B2 (Closing Date Hook):** Moving to any of the 8 closed statuses automatically populates `Data chiusura = now()`. Reopening to any open status clears `Data chiusura`.
* **B3 (Lead Uniqueness):** At most one lead per `(Contatto, Anagrafica interesse)` pair. Creation blocks duplicates and renders a direct link to the existing record.
* **B4 (Company Auto-link):**
  * If the selected contact is linked to exactly one company: `Azienda` is automatically filled and locked.
  * If the contact is linked to multiple companies: `Azienda` requires a choice from the filtered list of associated companies.
* **B5 (Queue Hygiene on Reassignment):** Changing the owner removes the lead from the current owner's `Lead personali aperti` view upon refresh.
* **B6 (Timeline Activation):** The activity timeline is disabled on unsaved new leads, showing: `Salva il record per aggiungere attività alla sequenza temporale.`
* **D3 (Previsioni Terminology):** All Previsioni UI labels are in Italian while preserving model rigor:
  * Probability: `Probabilità di conversione`
  * Three drivers: `Tre fattori determinanti (SHAP)`
  * Expected value: `Valore atteso (Probabilità × ARR)`

---

## 7. Roadmap Backlog

### High Priority (P0)
- [x] CRM Shell layout with top bar, left navigation, user profile
- [x] Main grid: `Lead personali aperti` with default 9 columns and filters
- [x] Lead record: `Scheda Lead` view mode with 3 tabs and header flyout
- [x] Lead record: `Scheda Lead` create mode with uniqueness enforcement
- [x] Previsioni: Pipeline queue with expected value sorting and region filter
- [x] Previsioni: Lead 360 with win probability and 3 SHAP drivers
- [x] Previsioni: Lever simulation with point value calculation
- [x] Previsioni: Act action commitment loop and outcome logging
- [x] Previsioni: Portfolio aggregation view with calibration and drift
- [ ] Visual States catalog screen (`/stati`) in Stitch canvas

### Medium Priority (P1)
- [x] Master data list: `Tutte le aziende`
- [x] Master data list: `Tutti i contatti`
- [x] Master data list: `Anagrafiche Iniziative con codici`
- [x] Honest gap screen (`/non-incluso`)
- [ ] View manager: Personal views save, save-as, reset, and share
- [ ] Excel export (.xlsx) replacing client-side CSV export
- [ ] Timeline interactive composers for E-mail, Telefonata, Nota

### Low Priority (P2)
- [ ] Full polymorphic `Impegni` / `Attività` master view
- [ ] Many-to-many `Rel. Aziende-Contatti` relationship grid
- [ ] `Manif. Interesse` and `Servizi` standalone entity lists
- [ ] `Recenti` and `Aggiunti` left-nav expandable trees
- [ ] Mailbox bidirectional synchronization (Gmail / Exchange IMAP)
