# Screenshot audit: legacy CRM vs rebuild spec

Compares the 40 screenshots in `crm must have features/` (legacy Dynamics 365, CRM CCIAA - PROMOS)
against `CRM_Sales_Module_Rebuild_Spec.md`. Written 2026-11-20. The spec has **not** been edited yet:
section 3 below is the change list to apply.

Legend: **C** = the screenshot contradicts the spec. **M** = visible, missing from the spec.
**IC** = the spec marks it [inferred] and the screenshot confirms it.

## 1. Reference roles (read before designing)

| Source | Use it for | Do not use it for |
|---|---|---|
| `crm must have features/*.png` | **What** the CRM must do: fields, statuses, views, commands, workflows | The look. This is the Dynamics UI the rebuild moves away from |
| `promositalia.com_*.png`, `font-family ... .txt`, `figma-colors.json`, `*.aco`, `*.sketchpalette` | **Brand**: colors, type, corner radius, tone. The CRM must feel like a Promos Italia product | Layout. A marketing site is not a work tool |
| `www.pipedrive.com_it_edited.png` | **UX patterns** only: pipeline thinking, next-step and follow-up reminders, inline assistant, low-friction actions | Colors, fonts, the marketing layout |

## 2. Screenshot index by screen type

| Screen type | Files | Phase 2 screen it feeds |
|---|---|---|
| Lead grid, views, overflow menu | p05_006, p10_020, p21_065, p22_067 | Lead personali aperti |
| Lead bulk edit dialog | p11_023 | Lead personali aperti |
| Lead form, status/owner flyout | p03_001, p09_017, p20_062 | Scheda Lead |
| Lead form, timeline | p06_009, p06_010 | Scheda Lead |
| New lead form (from Contact / Initiative) | p15_037, p19_054 | Scheda Lead (create mode) |
| E-mail composer | p07_013 | Scheda Lead (timeline) |
| Contact grid + quick find `*` | p12_027, p13_029, p13_030 | Master data lists |
| Contact form (Generale, Sales) | p08_015, p14_033, p14_034 | Master data forms |
| Company grid + quick find, column menu | p16_041, p28_088 | Master data lists |
| Company form (Generale, Sales) | p17_044, p17_045 | Master data forms |
| Initiative grid | p18_049 | Master data lists |
| Initiative form, Lead sub-grid | p19_053, p23_070 | Master data forms |
| Relationships grid, filtered view | p24_074, p29_092 | Views / filters |
| Edit columns panel, add columns picker | p25_077, p26_079, p26_080, p27_085 | Views / filters |
| Column filter dialog | p28_089 | Views / filters |
| View selector (personal + system) | p30_093 | Views / filters |
| Dashboard, gear menu | p31_095, p32_097 | Dashboard (P2) |
| Personal options | p33_099 | Settings (P2) |
| E-mail signatures (list, form, editor) | p34_101, p35_103, p36_106 | Settings (P2) |

## 3. Differences to apply to the spec

### Contradictions (fix the spec text)

| # | Spec § | Screenshot | Finding |
|---|---|---|---|
| C1 | 4.1 | p03_001, p11_023 | Dropdown order of `Stato lavorazione` is: Nuovo, Da contattare, In attesa di riscontro, Interessato, Prefattibilità negativa, Nessuna risposta, Non interessato, Contratto concluso, Servizio concluso, Iscritto all'evento. Legacy statuses (Interessato InBuyer, Concluso, Da richiamare, Perso) come last and appear **only in bulk edit**, not on the single-record form |
| C2 | 2.4 | p08_015, p17_044, p15_037 | The record command bar varies by entity. Contact and Company: Salva, Salva e chiudi, Nuovo, Disattiva, Invia link, Aggiorna, Verifica l'accesso (no Assegna, Condividi, Processo). New unsaved record: Salva, Salva e chiudi, Nuovo, Flusso only |
| C3 | 3.4 | p18_049 | `Linea di attività` renders as a link, so it is a **lookup**, not a choice |
| C4 | 7.1, 3.4 | p05_006, p10_020, p16_041, p18_049, p24_074 | Default views use two sort keys. Lead views: Stato lavorazione ↓ then Data modifica ↓. Aziende: Denominazione ↑ then Provincia ↑. Iniziative: Iniziativa ↑ then Data inizio ↓. Relazioni: Azienda ↓. Multi-column sort must be supported |
| C5 | 11.1 | p35_103 | Signature form labels: `Nome *` (the grid column is `Titolo`), `Imposta come predefinito` (default No), plus a required `Lingua *` (default Italiano (Italia)) |
| C6 | 3.1 | p28_088, p31_095 | Company `Tipologia` header reads `Tipologia s...`, so the label is probably longer (e.g. "Tipologia soggetto"). Values seen: Impresa, Privato. Confirm with stakeholders |

### Missing (add to the spec)

| # | Spec § | Screenshot | Finding |
|---|---|---|---|
| M1 | 3.6 | p03_001, p09_017, p20_062, p06_010 | On a saved lead, `Azienda`, `Contatto`, `Anagrafica interesse`, `Manifestazione interesse origine` and `Fonte` are **locked** |
| M2 | 3.6 | p03_001, p19_054 | Lead form sections: `INFORMAZIONI PRINCIPALI`, `INTERESSE`, `DETTAGLI` (Note migrate, on Generale). `Stato lavorazione` also appears in the body on a new lead |
| M3 | 3.6 | p19_054 | Conditional fields: a manual lead shows `Evento di origine` and hides Manifestazione origine, Tipo interesse, Richieste del Contatto |
| M4 | 5.1 | p20_062 | Auto-created leads copy `Richieste del Contatto/Cliente` into `Descrizione` too |
| M5 | 3.2 | p08_015 | Contact header fields: Maturità anagrafica, E-mail, Completezza anagrafica, Proprietario. Default owner Team Anagrafiche Promos. `E-mail validata` is locked. `RELAZIONI AZIENDE` sub-grid is on Generale |
| M6 | 3.2 | p14_034 | Contact Sales tab Lead sub-grid columns: Argomento ↑, Anagrafica interesse, Azienda, Stato lavorazione, Data creazione ↓, Data chiusura, Proprietario |
| M7 | 3.1 | p17_044, p26_080 | Company header adds `Codice Fiscale` (IC: it is locked). Sections INFORMAZIONI SULL'AZIENDA, SETTORI DI ATTIVITÀ. Types: Provincia and Provincia (RI) are lookups, Provincia (indirizzo) is text |
| M8 | 3.4 | p19_053, p23_070 | Initiative header shows only `Proprietario`. Sub-grid `⋮` items Flusso, Esegui report, Modelli di Excel, Esporta Lead open submenus |
| M9 | 6 | p06_009, p06_010, p19_054 | Timeline `+` menu starts with `Impegno`. Loading state "Caricamento sequenza temporale in corso". New look titles it `Timeline` |
| M10 | 2.3 | p31_095, p16_041, p12_027, p17_045 | Grid: A to Z jump bar, hierarchy column, clickable mailto/tel cells, empty state "Nessun dato disponibile" with `0 - 0 di 0` |
| M11 | 2.3 | p18_049, p22_067 | New-look command bar: `Mostra come ⌄` (grid / other layouts), `Condividi ⌄` pinned right, `Esporta in Excel` and `Importa da Excel` have submenus |
| M12 | 7.7 | p31_095, p32_097 | System dashboard `Dashboard globale`; commands Salva con nome, Nuovo, Imposta come predefinito, Aggiorna tutto |
| M13 | 2.1 | p32_097 | Gear menu: Impostazioni di personalizzazione, Impostazioni avanzate, Informazioni, Privacy e cookie, Condizioni di licenza |
| M14 | 11.3 | p33_099 | IC: Record per pagina = 50, default landing page. Add: landing default is role-based; `Visualizzazione ricerca avanzata` Semplice / Dettagliata |
| M15 | 14, 3.2 | p30_093 | Personal view names imply consent data on **companies** with an expiry date, and a `Fonte` field on Contact |
| M16 | 14 | p29_092 | Migrated data contains placeholder contacts ("da inserire"); the import and data-quality plan must handle them |
| M17 | 7.3 | p25_077, p26_079, p27_085 | Type icon on each current column, reset disabled while unmodified, new column appended last, relations include Autore (delegato) and Autore modifica (delegato) |

Minor items (split buttons, editor toolbar extras, form switcher) are in the agent transcripts and do not change the design.
