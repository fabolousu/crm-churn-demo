-- Data contract for crm-churn-demo. SQLite dialect, Postgres-portable.
-- Snapshot date t0 is fixed at 2026-01-01 for the generated world.
-- Features may only be derived from rows with *_at <= t0. Labels live apart in
-- account_outcomes and must never be read by feature code.

PRAGMA foreign_keys = ON;

CREATE TABLE accounts (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  bu              TEXT NOT NULL CHECK (bu IN ('north', 'south', 'emea')),
  region          TEXT NOT NULL,
  industry        TEXT NOT NULL,
  created_at      TEXT NOT NULL,              -- ISO date
  arr             REAL NOT NULL,
  seats           INTEGER NOT NULL,
  seats_active    INTEGER NOT NULL,
  discount_pct    REAL NOT NULL DEFAULT 0,
  renewal_date    TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'cancelled')),
  owner_rep       TEXT NOT NULL
);

CREATE TABLE usage_weekly (
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  week_start      TEXT NOT NULL,
  events          INTEGER NOT NULL,
  PRIMARY KEY (account_id, week_start)
);

CREATE TABLE tickets (
  id              TEXT PRIMARY KEY,
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  opened_at       TEXT NOT NULL,
  closed_at       TEXT,
  severity        TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  resolution_hours REAL
);

CREATE TABLE invoices (
  id              TEXT PRIMARY KEY,
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  issued_at       TEXT NOT NULL,
  due_at          TEXT NOT NULL,
  paid_at         TEXT,
  amount          REAL NOT NULL
);

CREATE TABLE nps_surveys (
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  surveyed_at     TEXT NOT NULL,
  score           INTEGER NOT NULL CHECK (score BETWEEN -100 AND 100),
  PRIMARY KEY (account_id, surveyed_at)
);

CREATE TABLE interactions (
  id              TEXT PRIMARY KEY,
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  kind            TEXT NOT NULL CHECK (kind IN ('meeting', 'email', 'call')),
  direction       TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  occurred_at     TEXT NOT NULL,
  answered        INTEGER NOT NULL DEFAULT 1
);

-- Materialised at t0 by ml/features.py. One row per account.
CREATE TABLE features (
  account_id      TEXT PRIMARY KEY REFERENCES accounts(id),
  snapshot_date   TEXT NOT NULL,
  tenure_days     INTEGER NOT NULL,
  arr             REAL NOT NULL,
  seats           INTEGER NOT NULL,
  seats_active_ratio REAL NOT NULL,
  usage_events_90d INTEGER NOT NULL,
  usage_trend_slope REAL NOT NULL,
  tickets_90d     INTEGER NOT NULL,
  tickets_sev_high_90d INTEGER NOT NULL,
  last_login_days_ago INTEGER NOT NULL,
  renewal_days_left INTEGER NOT NULL,
  is_renewal_within_60d INTEGER NOT NULL,
  discount_pct    REAL NOT NULL,
  payment_delay_days_avg_180d REAL NOT NULL,
  nps_last        INTEGER NOT NULL,
  meetings_90d    INTEGER NOT NULL,
  emails_90d      INTEGER NOT NULL
);

-- Ground truth. Written once by the generator, never read by feature or training
-- code. Reviewers: the presence of a read here is a defect.
CREATE TABLE account_outcomes (
  account_id      TEXT PRIMARY KEY REFERENCES accounts(id),
  snapshot_date   TEXT NOT NULL,
  churned_180d    INTEGER NOT NULL CHECK (churned_180d IN (0, 1)),
  churned_on      TEXT,
  latent_p        REAL NOT NULL               -- the generating probability, for audit only
);

CREATE TABLE risk_scores (
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  scored_at       TEXT NOT NULL,
  model_version   TEXT NOT NULL,
  probability     REAL NOT NULL CHECK (probability BETWEEN 0 AND 1),
  band            TEXT NOT NULL CHECK (band IN ('low', 'medium', 'high', 'critical')),
  drivers_json    TEXT NOT NULL,              -- [{feature,label,contribution,value,direction}]
  arr_at_risk     REAL NOT NULL,
  PRIMARY KEY (account_id, scored_at)
);

CREATE TABLE actions (
  id              TEXT PRIMARY KEY,
  account_id      TEXT NOT NULL REFERENCES accounts(id),
  kind            TEXT NOT NULL CHECK (kind IN ('call','exec_meeting','discount_review','support_escalation')),
  note            TEXT,
  created_at      TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('open','done','cancelled'))
);

CREATE TABLE model_runs (
  model_version   TEXT PRIMARY KEY,
  trained_at      TEXT NOT NULL,
  metrics_json    TEXT NOT NULL,              -- auc, calibration_error, lift_at_10
  artifact_path   TEXT NOT NULL
);

CREATE INDEX idx_tickets_account_opened ON tickets(account_id, opened_at);
CREATE INDEX idx_invoices_account_due   ON invoices(account_id, due_at);
CREATE INDEX idx_interactions_account   ON interactions(account_id, occurred_at);
CREATE INDEX idx_scores_probability     ON risk_scores(probability DESC);
