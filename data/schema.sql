-- Data contract for crm-churn-demo. SQLite dialect, Postgres-portable.
--
-- Entity model: a COMPANY is the master record; LEADS are initiatives proposed to that
-- company; a won lead becomes an active initiative. There is no renewal event — the
-- business renews by winning the next initiative — so the model target is lead win/loss,
-- not contract churn.
--
-- Pilot scope: Italy only, five macro-regions. Currency EUR.
-- Scoring point: a lead is scored at qualification (or at its current stage if still open).
-- Features may only describe the world at or before the scoring point. Labels live apart in
-- lead_outcomes and must never be read by feature code.

PRAGMA foreign_keys = ON;

CREATE TABLE companies (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  vat_number      TEXT NOT NULL,              -- synthetic, format-plausible IT VAT
  region          TEXT NOT NULL CHECK (region IN
                    ('nord-ovest', 'nord-est', 'centro', 'sud', 'isole')),
  city            TEXT NOT NULL,
  industry        TEXT NOT NULL,
  employees       INTEGER NOT NULL,
  created_at      TEXT NOT NULL,
  owner_rep       TEXT NOT NULL
);

-- An initiative proposed to a company. Status is the lead's success state.
CREATE TABLE leads (
  id              TEXT PRIMARY KEY,
  company_id      TEXT NOT NULL REFERENCES companies(id),
  created_at      TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN
                    ('new', 'contacted', 'qualified', 'proposal', 'won', 'lost')),
  source          TEXT NOT NULL CHECK (source IN
                    ('inbound', 'outbound', 'referral', 'partner', 'event')),
  owner_rep       TEXT NOT NULL,
  first_response_hours REAL,
  first_response_at TEXT,                     -- when the first response happened; NULL if never
  qualified_at    TEXT,
  proposal_at     TEXT,
  closed_at       TEXT,
  lost_reason     TEXT CHECK (lost_reason IS NULL OR lost_reason IN
                    ('price', 'no_budget', 'competitor', 'no_fit', 'timing', 'silent')),
  amount_arr      REAL,
  discount_pct    REAL NOT NULL DEFAULT 0
);

CREATE TABLE company_usage_weekly (
  company_id      TEXT NOT NULL REFERENCES companies(id),
  week_start      TEXT NOT NULL,
  events          INTEGER NOT NULL,
  PRIMARY KEY (company_id, week_start)
);

CREATE TABLE tickets (
  id              TEXT PRIMARY KEY,
  company_id      TEXT NOT NULL REFERENCES companies(id),
  opened_at       TEXT NOT NULL,
  closed_at       TEXT,
  severity        TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  resolution_hours REAL
);

CREATE TABLE invoices (
  id              TEXT PRIMARY KEY,
  company_id      TEXT NOT NULL REFERENCES companies(id),
  issued_at       TEXT NOT NULL,
  due_at          TEXT NOT NULL,
  paid_at         TEXT,
  amount          REAL NOT NULL
);

CREATE TABLE nps_surveys (
  company_id      TEXT NOT NULL REFERENCES companies(id),
  surveyed_at     TEXT NOT NULL,
  score           INTEGER NOT NULL CHECK (score BETWEEN -100 AND 100),
  PRIMARY KEY (company_id, surveyed_at)
);

CREATE TABLE interactions (
  id              TEXT PRIMARY KEY,
  company_id      TEXT NOT NULL REFERENCES companies(id),
  lead_id         TEXT REFERENCES leads(id),
  kind            TEXT NOT NULL CHECK (kind IN ('meeting', 'email', 'call')),
  direction       TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  occurred_at     TEXT NOT NULL,
  answered        INTEGER NOT NULL DEFAULT 1
);

-- Materialised at the scoring point by ml/features.py. One row per scored lead.
-- A NULL in a signal column means NOT MEASURED; it never means zero. The model (LightGBM)
-- handles missing values natively, and a sentinel 0.0 would distort the z-scored distribution.
-- Every column must be knowable at `snapshot_date`; nothing may encode the outcome.
CREATE TABLE lead_features (
  lead_id         TEXT PRIMARY KEY REFERENCES leads(id),
  snapshot_date   TEXT NOT NULL,

  -- the lead itself, at scoring time
  source          TEXT NOT NULL,
  stage_at_scoring TEXT NOT NULL CHECK (stage_at_scoring IN
                    ('new', 'contacted', 'qualified', 'proposal')),
  age_days_at_scoring INTEGER NOT NULL,
  amount_arr      REAL NOT NULL,
  discount_pct    REAL NOT NULL,
  first_response_hours REAL,                  -- NULL if never answered
  first_response_at TEXT,                     -- when the first response happened; NULL if never

  -- company context
  region          TEXT NOT NULL,
  industry        TEXT NOT NULL,
  employees       INTEGER NOT NULL,
  company_age_days INTEGER NOT NULL,
  prior_won_initiatives INTEGER NOT NULL,
  prior_lost_initiatives INTEGER NOT NULL,
  days_since_last_initiative INTEGER NOT NULL,
  lifetime_won_arr REAL NOT NULL,
  open_initiatives_count INTEGER NOT NULL,

  -- relationship signals, measured before the scoring point
  usage_trend_slope REAL,                     -- NULL when usage history is too short to fit a slope
  tickets_90d     INTEGER NOT NULL,
  nps_last        INTEGER,                    -- NULL when the company was never surveyed
  payment_delay_days_avg_180d REAL,           -- NULL when no invoice fell in the window
  meetings_before_scoring INTEGER NOT NULL,
  owner_win_rate_180d REAL                    -- NULL when the rep has no prior closures
);

-- Ground truth. Written once by the generator; never read by feature or training code.
-- Reviewers: any read of this table from ml/ is a defect.
CREATE TABLE lead_outcomes (
  lead_id         TEXT PRIMARY KEY REFERENCES leads(id),
  snapshot_date   TEXT NOT NULL,
  won             INTEGER NOT NULL CHECK (won IN (0, 1)),
  closed_at       TEXT NOT NULL,
  latent_p        REAL NOT NULL               -- generating probability, for audit only
);

CREATE TABLE lead_scores (
  lead_id         TEXT NOT NULL REFERENCES leads(id),
  scored_at       TEXT NOT NULL,
  model_version   TEXT NOT NULL,
  probability     REAL NOT NULL CHECK (probability BETWEEN 0 AND 1),
  band            TEXT NOT NULL CHECK (band IN ('low', 'medium', 'high', 'critical')),
  drivers_json    TEXT NOT NULL,              -- [{feature,label,contribution,value,direction}]
  amount_arr      REAL NOT NULL,
  expected_value  REAL NOT NULL,              -- probability * amount_arr
  PRIMARY KEY (lead_id, scored_at)
);

CREATE TABLE actions (
  id              TEXT PRIMARY KEY,
  lead_id         TEXT NOT NULL REFERENCES leads(id),
  kind            TEXT NOT NULL CHECK (kind IN
                    ('call', 'exec_sponsor_meeting', 'discovery_meeting', 'discount_review')),
  note            TEXT,
  created_at      TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('open', 'done', 'cancelled'))
);

CREATE TABLE model_runs (
  model_version   TEXT PRIMARY KEY,
  trained_at      TEXT NOT NULL,
  metrics_json    TEXT NOT NULL,              -- auc, calibration_error, lift_at_10
  artifact_path   TEXT NOT NULL
);

CREATE INDEX idx_leads_company      ON leads(company_id, created_at);
CREATE INDEX idx_leads_status       ON leads(status, closed_at);
CREATE INDEX idx_tickets_company    ON tickets(company_id, opened_at);
CREATE INDEX idx_invoices_company   ON invoices(company_id, due_at);
CREATE INDEX idx_interactions_company ON interactions(company_id, occurred_at);
CREATE INDEX idx_scores_expected    ON lead_scores(expected_value DESC);
