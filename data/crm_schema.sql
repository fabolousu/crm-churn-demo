-- CRM Sales Module — data model (T12 / WS-B B1).
-- Dialect: SQLite 3 (PRAGMA foreign_keys=ON assumed by caller).
--
-- RATIONALE (why crm_leads is here even though B1's name list stops at five entities):
--   WS-B B2's rules — configurable status table, UNIQUE(Contatto, Iniziativa), closing
--   date, owner default from initiative's 1° Referente — have no target table unless a
--   CRM-side `crm_leads` exists. The ML layer already has a `leads` table with a closed
--   enum (new|contacted|qualified|proposal|won|lost) and a different purpose (win-probability
--   features). The architect decision is NOT to modify that table and NOT to overload it.
--   `crm_leads` is therefore added here so B2 has something to operate on.
--
-- NAMESPACE RULE: every table in this file is prefixed `crm_`. Nothing in this file edits,
-- drops or renames any pre-existing (ML) table. The migration runner also never touches
-- `data/schema.sql` content. Column names are snake_case even though the UI labels are
-- Italian (spec §14 i18n: labels live in resource files, not in DDL).
--
-- SYSTEM FIELDS. Every entity carries the full system-field set from spec §3:
--   id, created_on, created_by, created_on_behalf_by, modified_on, modified_by,
--   modified_on_behalf_by, owner, owning_team, owning_user, state, status_reason.
-- Timestamps are TEXT ISO-8601 UTC ("YYYY-MM-DDTHH:MM:SSZ"), SQLite's recommended form.
-- `state` is constrained to ('active','inactive'); `status_reason` is open text.
-- There is no users/teams table yet (documented gap G1 in UI inventory): owner/owning_team/
-- owning_user columns stay TEXT with no FK. Spec §10 (RBAC/teams) is deferred to a later lane.
--
-- LOOKUP VALUES. Spec §16.2 lists provincia, macro settore, settore, tipologia, fonte,
-- tipo interesse, posizione aziendale as open questions. Those columns are therefore plain
-- TEXT with no invented CHECK whitelist; the UI/seed lane (T14) will supply the catalogue.
--
-- POLYMORPHIC ACTIVITY. `crm_activities.regarding_type` + `regarding_id` point at a lead,
-- company, contact or initiative. SQLite cannot express a conditional / polymorphic FK, so
-- no FK is declared on that pair; application code must validate the target exists.
-- A partial-index strategy per target type is an option for T13 but is not required at B1.

CREATE TABLE IF NOT EXISTS crm_schema_migrations (
  version     TEXT PRIMARY KEY,
  applied_at  TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- crm_companies — "Azienda" (spec §3.1)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crm_companies (
  id                       TEXT PRIMARY KEY,
  denominazione            TEXT NOT NULL,                           -- primary field
  codice_fiscale           TEXT NOT NULL,                           -- read-only after create (UI rule, not DB)
  partita_iva              TEXT,
  provincia                TEXT,                                    -- open catalogue (spec §16.2)
  macro_settore_1          TEXT,
  settore_1                TEXT,
  macro_settore_2          TEXT,
  settore_2                TEXT,
  tipologia                TEXT,
  maturita_anagrafica      TEXT,                                    -- prospect | cliente | ex-cliente (UI)
  aree_export              TEXT,                                    -- multi-choice, stored comma-joined
  aree_import              TEXT,
  aree_interesse           TEXT,
  prodotti_servizi         TEXT,
  fatturazione_pregressa   INTEGER CHECK (fatturazione_pregressa IN (0,1)),

  -- address (spec "Address fields [inferred]")
  indirizzo                TEXT,
  cap                      TEXT,
  citta                    TEXT,
  nazione                  TEXT,

  -- system fields.
  -- Owner default: the spec names "Team Anagrafiche Promos" (a team).  No users/teams
  -- table exists yet; the app layer will materialise that default on insert.
  created_on                 TEXT NOT NULL,
  created_by                 TEXT,
  created_on_behalf_by       TEXT,
  modified_on                TEXT NOT NULL,
  modified_by                TEXT,
  modified_on_behalf_by      TEXT,
  owner                      TEXT,
  owning_team                TEXT,
  owning_user                TEXT,
  state                      TEXT NOT NULL DEFAULT 'active'
                                 CHECK (state IN ('active','inactive')),
  status_reason              TEXT
);
CREATE INDEX IF NOT EXISTS idx_crm_companies_denom ON crm_companies(denominazione);
CREATE INDEX IF NOT EXISTS idx_crm_companies_cf    ON crm_companies(codice_fiscale);

-- ---------------------------------------------------------------------------
-- crm_contacts — "Contatto" (spec §3.2)
-- ---------------------------------------------------------------------------
-- `nome_completo` is stored as a plain (non-generated) column, NOT GENERATED. Rationale:
--   (a) the spec calls it the primary display field, so it must be indexable;
--   (b) SQLite's STORED generated columns are 3.31+ which the project supports, but
--       using a plain column keeps the DDL compatible with the Postgres target named in
--       the spec and matches the pattern already used in `data/schema.sql`
--       (see `leads.first_response_hours` filled by the generator);
--   (c) application code already sets created_on/modified_on explicitly, so filling
--       nome_completo on insert/update is one more line of trivially-testable logic.
CREATE TABLE IF NOT EXISTS crm_contacts (
  id                       TEXT PRIMARY KEY,
  nome                     TEXT NOT NULL,
  cognome                  TEXT NOT NULL,
  nome_completo            TEXT NOT NULL,                           -- plain column, see above
  email                    TEXT NOT NULL,
  email_validata           INTEGER CHECK (email_validata IN (0,1)),
  codice_fiscale           TEXT,
  telefono                 TEXT NOT NULL,
  cellulare                TEXT,
  fax                      TEXT,
  nazionalita              TEXT,
  maturita_anagrafica      TEXT,
  completezza_anagrafica   TEXT,                                    -- completa | parziale (UI derives)

  -- GDPR (spec §14 — "add consent fields to the Contact")
  privacy_notice_type      TEXT,
  consent_marketing        INTEGER CHECK (consent_marketing IN (0,1)),
  consent_profiling        INTEGER CHECK (consent_profiling IN (0,1)),
  consent_date             TEXT,

  created_on                 TEXT NOT NULL,
  created_by                 TEXT,
  created_on_behalf_by       TEXT,
  modified_on                TEXT NOT NULL,
  modified_by                TEXT,
  modified_on_behalf_by      TEXT,
  owner                      TEXT,
  owning_team                TEXT,
  owning_user                TEXT,
  state                      TEXT NOT NULL DEFAULT 'active'
                                 CHECK (state IN ('active','inactive')),
  status_reason              TEXT
);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_nome_completo ON crm_contacts(nome_completo);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_email         ON crm_contacts(email);

-- ---------------------------------------------------------------------------
-- crm_company_contacts — "Relazione Azienda-Contatto" (spec §3.3)
-- ---------------------------------------------------------------------------
-- Drives the company auto-link rule (spec §5.3): count relationships for a contact to
-- decide whether Azienda is autofilled (exactly one) or the user must pick (several).
CREATE TABLE IF NOT EXISTS crm_company_contacts (
  id                       TEXT PRIMARY KEY,
  azienda_id               TEXT NOT NULL REFERENCES crm_companies(id),
  contatto_id              TEXT NOT NULL REFERENCES crm_contacts(id),
  posizione_aziendale      TEXT,                                    -- open catalogue

  created_on                 TEXT NOT NULL,
  created_by                 TEXT,
  created_on_behalf_by       TEXT,
  modified_on                TEXT NOT NULL,
  modified_by                TEXT,
  modified_on_behalf_by      TEXT,
  owner                      TEXT,
  owning_team                TEXT,
  owning_user                TEXT,
  state                      TEXT NOT NULL DEFAULT 'active'
                                 CHECK (state IN ('active','inactive')),
  status_reason              TEXT,

  UNIQUE (azienda_id, contatto_id)
);
CREATE INDEX IF NOT EXISTS idx_crm_cc_azienda  ON crm_company_contacts(azienda_id);
CREATE INDEX IF NOT EXISTS idx_crm_cc_contatto ON crm_company_contacts(contatto_id);

-- ---------------------------------------------------------------------------
-- crm_initiatives — "Anagrafica Iniziativa" (spec §3.4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crm_initiatives (
  id                       TEXT PRIMARY KEY,
  codice                   TEXT NOT NULL UNIQUE
                               CHECK (codice GLOB 'INI-[0-9][0-9][0-9][0-9][0-9][0-9]'),
  iniziativa               TEXT NOT NULL,                           -- name
  voucher                  INTEGER CHECK (voucher IN (0,1)),
  tipologia                TEXT,                                    -- open catalogue
  linea_attivita           TEXT,                                    -- outgoing | incoming | prima assistenza (UI)
  data_inizio              TEXT,
  data_fine                TEXT,
  stato_iniziativa         TEXT,                                    -- aperta | chiusa | ... (UI)
  referente_1              TEXT,                                    -- primary owner; will FK to users later
  referente_2              TEXT,

  created_on                 TEXT NOT NULL,
  created_by                 TEXT,
  created_on_behalf_by       TEXT,
  modified_on                TEXT NOT NULL,
  modified_by                TEXT,
  modified_on_behalf_by      TEXT,
  owner                      TEXT,
  owning_team                TEXT,
  owning_user                TEXT,
  state                      TEXT NOT NULL DEFAULT 'active'
                                 CHECK (state IN ('active','inactive')),
  status_reason              TEXT
);
CREATE INDEX IF NOT EXISTS idx_crm_initiatives_data_inizio ON crm_initiatives(data_inizio);

-- ---------------------------------------------------------------------------
-- crm_lead_statuses — configurable status catalogue (spec §4.1)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crm_lead_statuses (
  code                 TEXT PRIMARY KEY,
  label_it             TEXT NOT NULL,
  label_en             TEXT NOT NULL,
  category             TEXT NOT NULL CHECK (category IN ('open','closed')),
  sort_order           INTEGER NOT NULL,
  is_default_manual    INTEGER NOT NULL DEFAULT 0 CHECK (is_default_manual IN (0,1)),
  is_default_auto      INTEGER NOT NULL DEFAULT 0 CHECK (is_default_auto   IN (0,1)),
  is_legacy            INTEGER NOT NULL DEFAULT 0 CHECK (is_legacy         IN (0,1)),
  active               INTEGER NOT NULL DEFAULT 1 CHECK (active            IN (0,1))
);

-- Seed the 14 statuses from spec §4.1 exactly. INSERT OR IGNORE keeps re-apply idempotent.
-- Open / closed split and defaults match the table in the spec:
--   Nuovo             — open,   manual default
--   Interessato       — open,   auto default (interest / service / manual)
--   Da contattare     — open
--   In attesa di riscontro — open
--   Prefattibilità negativa — closed
--   Nessuna risposta  — closed
--   Non interessato   — closed
--   Iscritto all'evento — closed (system-set by event registration)
--   Servizio concluso — closed
--   Contratto concluso — closed
-- Legacy (is_legacy=1):
--   Interessato InBuyer — open
--   Concluso            — closed
--   Da richiamare       — open
--   Perso               — closed
INSERT OR IGNORE INTO crm_lead_statuses
  (code, label_it, label_en, category, sort_order, is_default_manual, is_default_auto, is_legacy, active)
VALUES
  ('nuovo',                   'Nuovo',                   'New',                       'open',    10,  1, 0, 0, 1),
  ('interessato',             'Interessato',             'Interested',                'open',    20,  0, 1, 0, 1),
  ('da_contattare',           'Da contattare',           'To contact',                'open',    30,  0, 0, 0, 1),
  ('in_attesa_di_riscontro',  'In attesa di riscontro',  'Awaiting reply',            'open',    40,  0, 0, 0, 1),
  ('prefattibilita_negativa', 'Prefattibilità negativa', 'Pre-feasibility negative',  'closed',  50,  0, 0, 0, 1),
  ('nessuna_risposta',        'Nessuna risposta',        'No reply',                  'closed',  60,  0, 0, 0, 1),
  ('non_interessato',         'Non interessato',         'Not interested',            'closed',  70,  0, 0, 0, 1),
  ('iscritto_all_evento',     'Iscritto all''evento',    'Registered for the event',  'closed',  80,  0, 0, 0, 1),
  ('servizio_concluso',       'Servizio concluso',       'Service completed',         'closed',  90,  0, 0, 0, 1),
  ('contratto_concluso',      'Contratto concluso',      'Contract signed',           'closed', 100,  0, 0, 0, 1),
  -- legacy
  ('interessato_inbuyer',     'Interessato InBuyer',     'Interested (InBuyer)',      'open',   200,  0, 0, 1, 1),
  ('concluso',                'Concluso',                'Concluded',                 'closed', 210,  0, 0, 1, 1),
  ('da_richiamare',           'Da richiamare',           'Call back',                 'open',   220,  0, 0, 1, 1),
  ('perso',                   'Perso',                   'Lost',                      'closed', 230,  0, 0, 1, 1);

-- ---------------------------------------------------------------------------
-- crm_leads — the CRM-side lead (spec §3.6)
-- ---------------------------------------------------------------------------
-- NOTE: this is separate from the ML `leads` table. See the file header rationale.
-- `closing_date` is nullable; B2 (T13) will own the trigger/hook that sets it when
-- status moves to a closed category and clears it on reopening (spec §4.2).
-- No lead_status_transitions table: spec §4.2 declares transitions are free.
CREATE TABLE IF NOT EXISTS crm_leads (
  id                     TEXT PRIMARY KEY,
  argomento              TEXT,                                      -- auto-generated title
  descrizione            TEXT,
  company_id             TEXT NOT NULL REFERENCES crm_companies(id),
  contact_id             TEXT NOT NULL REFERENCES crm_contacts(id),
  initiative_id          TEXT NOT NULL REFERENCES crm_initiatives(id),
  status_code            TEXT NOT NULL REFERENCES crm_lead_statuses(code),
  fonte                  TEXT,                                      -- open catalogue
  tipo_interesse         TEXT,                                      -- open catalogue; copied from MdI
  richieste              TEXT,
  note_migrate           TEXT,
  closing_date           TEXT,                                      -- "Data chiusura", set by T13 hook

  created_on                 TEXT NOT NULL,
  created_by                 TEXT,
  created_on_behalf_by       TEXT,
  modified_on                TEXT NOT NULL,
  modified_by                TEXT,
  modified_on_behalf_by      TEXT,
  owner                      TEXT,
  owning_team                TEXT,
  owning_user                TEXT,
  state                      TEXT NOT NULL DEFAULT 'active'
                                 CHECK (state IN ('active','inactive')),
  status_reason              TEXT,

  UNIQUE (contact_id, initiative_id)                                -- spec §3.6 explicit rule
);
CREATE INDEX IF NOT EXISTS idx_crm_leads_company      ON crm_leads(company_id);
CREATE INDEX IF NOT EXISTS idx_crm_leads_contact      ON crm_leads(contact_id);
CREATE INDEX IF NOT EXISTS idx_crm_leads_initiative   ON crm_leads(initiative_id);
CREATE INDEX IF NOT EXISTS idx_crm_leads_status       ON crm_leads(status_code);
CREATE INDEX IF NOT EXISTS idx_crm_leads_owner_open   ON crm_leads(owner, status_code);

-- ---------------------------------------------------------------------------
-- crm_activities — polymorphic "Attività" (spec §3.8, §6)
-- ---------------------------------------------------------------------------
-- Polymorphic: (regarding_type, regarding_id) points at a lead, company, contact or
-- initiative row. SQLite cannot express a conditional FK, so no FK is declared on that
-- pair; application code and T13's activity service must validate existence.
-- Type-specific columns are all nullable; which ones are populated depends on
-- `activity_type`. Enforcement is left to the service layer.
CREATE TABLE IF NOT EXISTS crm_activities (
  id                     TEXT PRIMARY KEY,
  activity_type          TEXT NOT NULL CHECK (activity_type IN
                           ('email','note','appointment','call','task')),
  oggetto                TEXT,
  regarding_type         TEXT NOT NULL CHECK (regarding_type IN
                           ('lead','company','contact','initiative')),
  regarding_id           TEXT NOT NULL,                             -- no FK: polymorphic (see above)
  priorita               TEXT,                                      -- e.g. 'normale'
  due_date               TEXT,
  stato                  TEXT,                                      -- activity status: bozza | completato | chiuso (spec §3.8)
  motivo_stato           TEXT,                                      -- status reason, e.g. why it was closed (spec §3.8)

  -- email-specific
  email_from             TEXT,
  email_to               TEXT,
  email_cc               TEXT,
  email_bcc              TEXT,
  body                   TEXT,                                      -- also used by note.text
  attachments            TEXT,                                      -- JSON array of {name, url, size}
  direction              TEXT,                                      -- 'inbound' | 'outbound'

  -- appointment-specific
  start_at               TEXT,
  end_at                 TEXT,
  location               TEXT,
  attendees              TEXT,                                      -- JSON array

  -- call-specific
  phone_number           TEXT,
  duration_seconds       INTEGER,

  -- task / generic
  description            TEXT,

  created_on                 TEXT NOT NULL,
  created_by                 TEXT,
  created_on_behalf_by       TEXT,
  modified_on                TEXT NOT NULL,
  modified_by                TEXT,
  modified_on_behalf_by      TEXT,
  owner                      TEXT,
  owning_team                TEXT,
  owning_user                TEXT,
  state                      TEXT NOT NULL DEFAULT 'active'
                                 CHECK (state IN ('active','inactive')),
  status_reason              TEXT
);
CREATE INDEX IF NOT EXISTS idx_crm_activities_regarding
  ON crm_activities(regarding_type, regarding_id);
CREATE INDEX IF NOT EXISTS idx_crm_activities_type_due
  ON crm_activities(activity_type, due_date);
