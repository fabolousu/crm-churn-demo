// Builds the checked-in demo fixtures from one authored world.
//
//   node scripts/build-fixtures.mjs
//
// The JSON in src/fixtures/ is committed; this script exists so the queue,
// lead pages, levers, actions and portfolio cannot drift apart. It is never
// imported by the app.
//
// Numbers come from the real build:
//   * 19,752 open initiatives
//   * 28.66% win prevalence
//   * mean proposed ARR €36,246 (data/generator.py CALIBRATED_Z.amount_arr)
//   * model AUC 0.773, calibration error 0.0104, latent ceiling 0.789
//   * five Italian macro-regions
//
// Counterfactual fixtures are precomputed with the documented feature effects
// in docs/LABEL.md (one meeting +0.25 logit, +5 NPS +0.20 logit, discount
// -0.20 logit per z). With VITE_API_BASE set, the app calls the real model
// instead and these values are unused.

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, "..", "src", "fixtures");

// ---------------------------------------------------------------------------
// Snapshot and model facts
// ---------------------------------------------------------------------------

const SNAPSHOT = "2026-11-18";
const SNAPSHOT_ISO = "2026-11-18T06:00:00+01:00";
const MODEL_VERSION = "lead-win-gbm-0.3.0";
const MEAN_ARR = 36246.04918124; // generator reference mean, used for the portfolio roll-up

const OPEN_LEADS = 19_752;
const PREVALENCE = 0.2866;
const TOTAL_EXPECTED_VALUE = 205_190_000;

const MODEL = {
  auc: 0.773,
  calibration_error: 0.0104,
  latent_auc: 0.789,
};

// Portfolio is authored from the same facts: expected value per region is
// open_leads x win_rate x mean proposed ARR, rounded to €10k. Sum = 205.19M.
const REGIONS = [
  { region: "nord-ovest", open_leads: 2370, wins: 758, expected_value: 27_480_000 },
  { region: "nord-est", open_leads: 2370, wins: 802, expected_value: 29_070_000 },
  { region: "centro", open_leads: 3951, wins: 1225, expected_value: 44_400_000 },
  { region: "sud", open_leads: 5530, wins: 1499, expected_value: 54_330_000 },
  { region: "isole", open_leads: 5531, wins: 1377, expected_value: 49_910_000 },
];

// Ten decile bins. Predicted means average to prevalence; the weighted
// absolute gap is exactly 0.0104 (the calibration error the model reports).
const CALIBRATION = [
  { predicted: 0.055, actual: 0.067 },
  { predicted: 0.095, actual: 0.085 },
  { predicted: 0.14, actual: 0.149 },
  { predicted: 0.19, actual: 0.177 },
  { predicted: 0.24, actual: 0.251 },
  { predicted: 0.295, actual: 0.287 },
  { predicted: 0.355, actual: 0.369 },
  { predicted: 0.42, actual: 0.41 },
  { predicted: 0.49, actual: 0.497 },
  { predicted: 0.586, actual: 0.576 },
];

const DRIFT = { psi: 0.041, status: "stable" };

// ---------------------------------------------------------------------------
// Model arithmetic for the fixture counterfactuals
// ---------------------------------------------------------------------------

const Z_REFERENCE_SCALE = 1.25;
const Z = {
  meetings: 1.25527411,
  nps: 34.99411608,
  discount: 8.35726263,
};
const BETA = { meetings: 0.25, nps: 0.2, discount: -0.2 };

const EXEC_DELTA =
  (Z_REFERENCE_SCALE / Z.meetings) * BETA.meetings +
  (5 * Z_REFERENCE_SCALE) / Z.nps * BETA.nps;
const DISCOVERY_DELTA = (Z_REFERENCE_SCALE / Z.meetings) * BETA.meetings;

const sigmoid = (x) => 1 / (1 + Math.exp(-x));
const logit = (p) => Math.log(p / (1 - p));
const round = (x, places = 4) => Number(x.toFixed(places));

function rescore(p, logitDelta) {
  const next = sigmoid(logit(p) + logitDelta);
  return {
    current_probability: round(p),
    hypothetical_probability: round(next),
    delta: round(next - p),
  };
}

function discountLogitDelta(currentPct, nextPct) {
  return (
    BETA.discount *
    ((nextPct - currentPct) * Z_REFERENCE_SCALE) /
    Z.discount
  );
}

function band(p) {
  if (p < 0.15) return "critical";
  if (p < 0.3) return "high";
  if (p < 0.5) return "medium";
  return "low";
}

function daysBetween(from, to) {
  const a = Date.parse(`${from}T00:00:00Z`);
  const b = Date.parse(`${to}T00:00:00Z`);
  return Math.round((b - a) / 86_400_000);
}

// ---------------------------------------------------------------------------
// The authored world: 12 initiatives, enough for every region and every state
// ---------------------------------------------------------------------------

const leads = [
  {
    lead_id: "L-10482",
    company_id: "C-00318",
    company_name: "Fonderia Valsesia S.p.A.",
    region: "nord-ovest",
    industry: "Manifattura",
    employees: 420,
    source: "referral",
    status: "proposal",
    created_at: "2026-11-01",
    amount_arr: 360_000,
    discount_pct: 8.5,
    probability: 0.34,
    drivers: [
      {
        feature: "prior_lost_initiatives",
        label: "Lost initiatives",
        contribution: -0.34,
        value: "2 of the last 4 initiatives lost",
        direction: "decreases",
      },
      {
        feature: "first_response_hours",
        label: "First response",
        contribution: -0.27,
        value: "11 hours to first response",
        direction: "decreases",
      },
      {
        feature: "owner_win_rate_180d",
        label: "Rep track record",
        contribution: 0.22,
        value: "Rep wins 41% of initiatives",
        direction: "increases",
      },
    ],
    open_actions: [
      {
        id: "ACT-0412",
        kind: "call",
        status: "open",
        created_at: "2026-11-17T09:15:00+01:00",
        created_by: "Marco Rossi",
        note: "Confirm the technical sponsor for the proposal review.",
      },
    ],
    history: [
      { id: "L-09881", status: "won", source: "referral", created_at: "2026-08-16", closed_at: "2026-09-30", amount_arr: 610_000, discount_pct: 5, lost_reason: null },
      { id: "L-08914", status: "lost", source: "outbound", created_at: "2026-04-02", closed_at: "2026-05-20", amount_arr: 240_000, discount_pct: 12, lost_reason: "price" },
      { id: "L-07742", status: "won", source: "partner", created_at: "2025-11-14", closed_at: "2025-12-19", amount_arr: 355_000, discount_pct: 4, lost_reason: null },
      { id: "L-06603", status: "lost", source: "outbound", created_at: "2025-06-27", closed_at: "2025-08-01", amount_arr: 310_000, discount_pct: 9, lost_reason: "competitor" },
    ],
  },
  {
    lead_id: "L-10517",
    company_id: "C-00542",
    company_name: "Cantieri Marini S.p.A.",
    region: "nord-est",
    industry: "Costruzioni",
    employees: 280,
    source: "partner",
    status: "proposal",
    created_at: "2026-10-20",
    amount_arr: 284_000,
    discount_pct: 6,
    probability: 0.43,
    drivers: [
      {
        feature: "meetings_before_scoring",
        label: "Meetings held",
        contribution: 0.33,
        value: "Six meetings already held",
        direction: "increases",
      },
      {
        feature: "prior_won_initiatives",
        label: "Won initiatives",
        contribution: 0.24,
        value: "Two initiatives won together",
        direction: "increases",
      },
      {
        feature: "amount_arr",
        label: "Deal size",
        contribution: -0.18,
        value: "€284,000 proposed — larger initiatives close less often",
        direction: "decreases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09602", status: "won", source: "partner", created_at: "2026-07-21", closed_at: "2026-09-02", amount_arr: 420_000, discount_pct: 4, lost_reason: null },
      { id: "L-08277", status: "won", source: "referral", created_at: "2026-02-10", closed_at: "2026-03-30", amount_arr: 320_000, discount_pct: 5, lost_reason: null },
      { id: "L-07119", status: "lost", source: "outbound", created_at: "2025-05-12", closed_at: "2025-06-25", amount_arr: 180_000, discount_pct: 8, lost_reason: "competitor" },
    ],
  },
  {
    lead_id: "L-10396",
    company_id: "C-00271",
    company_name: "Tecnoimpianti Sabina S.r.l.",
    region: "centro",
    industry: "Elettronica",
    employees: 150,
    source: "referral",
    status: "qualified",
    created_at: "2026-09-28",
    amount_arr: 215_000,
    discount_pct: 12,
    probability: 0.56,
    drivers: [
      {
        feature: "prior_won_initiatives",
        label: "Won initiatives",
        contribution: 0.3,
        value: "Three initiatives won together",
        direction: "increases",
      },
      {
        feature: "source",
        label: "Lead source",
        contribution: 0.27,
        value: "Referral from an existing customer",
        direction: "increases",
      },
      {
        feature: "discount_pct",
        label: "Discount",
        contribution: -0.14,
        value: "12% discount requested",
        direction: "decreases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09003", status: "won", source: "referral", created_at: "2026-06-03", closed_at: "2026-07-15", amount_arr: 210_000, discount_pct: 6, lost_reason: null },
      { id: "L-07841", status: "won", source: "inbound", created_at: "2025-10-20", closed_at: "2025-12-01", amount_arr: 200_000, discount_pct: 3, lost_reason: null },
      { id: "L-06214", status: "lost", source: "outbound", created_at: "2025-03-05", closed_at: "2025-04-10", amount_arr: 90_000, discount_pct: 10, lost_reason: "no_budget" },
    ],
  },
  {
    lead_id: "L-10533",
    company_id: "C-00786",
    company_name: "Officine Bertolini S.p.A.",
    region: "nord-ovest",
    industry: "Meccanica",
    employees: 510,
    source: "outbound",
    status: "proposal",
    created_at: "2026-08-24",
    amount_arr: 380_000,
    discount_pct: 10,
    probability: 0.31,
    drivers: [
      {
        feature: "amount_arr",
        label: "Deal size",
        contribution: -0.38,
        value: "€380,000 proposed — larger initiatives close less often",
        direction: "decreases",
      },
      {
        feature: "days_since_last_initiative",
        label: "Relationship gap",
        contribution: -0.26,
        value: "172 days without a new initiative",
        direction: "decreases",
      },
      {
        feature: "tickets_90d",
        label: "Support friction",
        contribution: -0.19,
        value: "4 support tickets in 90 days",
        direction: "decreases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09418", status: "won", source: "outbound", created_at: "2026-05-30", closed_at: "2026-07-10", amount_arr: 720_000, discount_pct: 7, lost_reason: null },
      { id: "L-07455", status: "won", source: "partner", created_at: "2025-09-01", closed_at: "2025-10-20", amount_arr: 600_000, discount_pct: 4, lost_reason: null },
      { id: "L-05602", status: "lost", source: "outbound", created_at: "2024-12-10", closed_at: "2025-01-30", amount_arr: 250_000, discount_pct: 11, lost_reason: "timing" },
    ],
  },
  {
    lead_id: "L-10455",
    company_id: "C-00409",
    company_name: "Logistica Mediterranea S.r.l.",
    region: "sud",
    industry: "Logistica",
    employees: 190,
    source: "inbound",
    status: "qualified",
    created_at: "2026-10-15",
    amount_arr: 175_000,
    discount_pct: 5,
    probability: 0.62,
    drivers: [
      {
        feature: "source",
        label: "Lead source",
        contribution: 0.24,
        value: "Inbound interest from the website",
        direction: "increases",
      },
      {
        feature: "meetings_before_scoring",
        label: "Meetings held",
        contribution: 0.23,
        value: "Four meetings already held",
        direction: "increases",
      },
      {
        feature: "first_response_hours",
        label: "First response",
        contribution: 0.19,
        value: "2 hours to first response",
        direction: "increases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09740", status: "won", source: "inbound", created_at: "2026-08-01", closed_at: "2026-09-15", amount_arr: 180_000, discount_pct: 2, lost_reason: null },
      { id: "L-08105", status: "lost", source: "outbound", created_at: "2026-01-20", closed_at: "2026-03-01", amount_arr: 120_000, discount_pct: 9, lost_reason: "price" },
      { id: "L-07022", status: "won", source: "partner", created_at: "2025-04-15", closed_at: "2025-05-30", amount_arr: 150_000, discount_pct: 3, lost_reason: null },
    ],
  },
  {
    lead_id: "L-10561",
    company_id: "C-00812",
    company_name: "Agrumi di Sicilia S.r.l.",
    region: "isole",
    industry: "Alimentare",
    employees: 120,
    source: "outbound",
    status: "contacted",
    created_at: "2026-09-02",
    amount_arr: 395_000,
    discount_pct: 9,
    probability: 0.27,
    drivers: [
      {
        feature: "days_since_last_initiative",
        label: "Relationship gap",
        contribution: -0.33,
        value: "212 days without a new initiative",
        direction: "decreases",
      },
      {
        feature: "amount_arr",
        label: "Deal size",
        contribution: -0.29,
        value: "€395,000 proposed — larger initiatives close less often",
        direction: "decreases",
      },
      {
        feature: "prior_lost_initiatives",
        label: "Lost initiatives",
        contribution: -0.12,
        value: "1 of the last 3 initiatives lost",
        direction: "decreases",
      },
    ],
    open_actions: [
      {
        id: "ACT-0388",
        kind: "call",
        status: "open",
        created_at: "2026-11-12T11:40:00+01:00",
        created_by: "Giulia Bianchi",
        note: "Re-open the conversation after the harvest season.",
      },
    ],
    history: [
      { id: "L-08612", status: "lost", source: "outbound", created_at: "2026-04-20", closed_at: "2026-06-01", amount_arr: 140_000, discount_pct: 13, lost_reason: "no_budget" },
      { id: "L-07230", status: "won", source: "outbound", created_at: "2025-08-10", closed_at: "2025-09-20", amount_arr: 180_000, discount_pct: 6, lost_reason: null },
    ],
  },
  {
    lead_id: "L-10408",
    company_id: "C-00596",
    company_name: "Serigrafia Veneta S.r.l.",
    region: "nord-est",
    industry: "Grafica",
    employees: 85,
    source: "event",
    status: "proposal",
    created_at: "2026-10-05",
    amount_arr: 210_000,
    discount_pct: 22,
    probability: 0.48,
    drivers: [
      {
        feature: "discount_pct",
        label: "Discount",
        contribution: -0.31,
        value: "22% discount requested",
        direction: "decreases",
      },
      {
        feature: "meetings_before_scoring",
        label: "Meetings held",
        contribution: 0.21,
        value: "Five meetings already held",
        direction: "increases",
      },
      {
        feature: "owner_win_rate_180d",
        label: "Rep track record",
        contribution: 0.18,
        value: "Rep wins 39% of initiatives",
        direction: "increases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09755", status: "won", source: "event", created_at: "2026-08-25", closed_at: "2026-10-01", amount_arr: 90_000, discount_pct: 5, lost_reason: null },
      { id: "L-08008", status: "won", source: "inbound", created_at: "2026-01-12", closed_at: "2026-02-20", amount_arr: 120_000, discount_pct: 4, lost_reason: null },
      { id: "L-06518", status: "lost", source: "outbound", created_at: "2025-03-18", closed_at: "2025-04-22", amount_arr: 60_000, discount_pct: 7, lost_reason: "no_fit" },
    ],
  },
  {
    lead_id: "L-10502",
    company_id: "C-00633",
    company_name: "Studio Medico Appia S.r.l.",
    region: "centro",
    industry: "Sanità",
    employees: 60,
    source: "outbound",
    status: "qualified",
    created_at: "2026-09-19",
    amount_arr: 260_000,
    discount_pct: 7,
    probability: 0.38,
    drivers: [
      {
        feature: "tickets_90d",
        label: "Support friction",
        contribution: -0.3,
        value: "5 support tickets in 90 days",
        direction: "decreases",
      },
      {
        feature: "first_response_hours",
        label: "First response",
        contribution: -0.22,
        value: "24 hours to first response",
        direction: "decreases",
      },
      {
        feature: "owner_win_rate_180d",
        label: "Rep track record",
        contribution: 0.17,
        value: "Rep wins 39% of initiatives",
        direction: "increases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09510", status: "won", source: "outbound", created_at: "2026-07-02", closed_at: "2026-08-10", amount_arr: 80_000, discount_pct: 5, lost_reason: null },
      { id: "L-07644", status: "lost", source: "outbound", created_at: "2025-11-05", closed_at: "2025-12-15", amount_arr: 60_000, discount_pct: 10, lost_reason: "competitor" },
    ],
  },
  {
    lead_id: "L-10574",
    company_id: "C-00847",
    company_name: "Salumi Irpini S.p.A.",
    region: "sud",
    industry: "Alimentare",
    employees: 210,
    source: "outbound",
    status: "contacted",
    created_at: "2026-10-08",
    amount_arr: 390_000,
    discount_pct: 11,
    probability: 0.24,
    drivers: [
      {
        feature: "first_response_hours",
        label: "First response",
        contribution: -0.36,
        value: "38 hours to first response",
        direction: "decreases",
      },
      {
        feature: "amount_arr",
        label: "Deal size",
        contribution: -0.28,
        value: "€390,000 proposed — larger initiatives close less often",
        direction: "decreases",
      },
      {
        feature: "days_since_last_initiative",
        label: "Relationship gap",
        contribution: -0.18,
        value: "141 days without a new initiative",
        direction: "decreases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09320", status: "won", source: "outbound", created_at: "2026-06-30", closed_at: "2026-08-08", amount_arr: 160_000, discount_pct: 6, lost_reason: null },
      { id: "L-07798", status: "lost", source: "outbound", created_at: "2025-12-02", closed_at: "2026-01-15", amount_arr: 100_000, discount_pct: 9, lost_reason: "timing" },
      { id: "L-05884", status: "won", source: "partner", created_at: "2025-02-14", closed_at: "2025-03-28", amount_arr: 100_000, discount_pct: 4, lost_reason: null },
    ],
  },
  {
    lead_id: "L-10441",
    company_id: "C-00471",
    company_name: "Hotel Riviera del Sud S.r.l.",
    region: "isole",
    industry: "Turismo",
    employees: 140,
    source: "referral",
    status: "qualified",
    created_at: "2026-10-26",
    amount_arr: 178_000,
    discount_pct: 4,
    probability: 0.52,
    drivers: [
      {
        feature: "nps_last",
        label: "Relationship health",
        contribution: 0.27,
        value: "NPS 62 — a strong relationship",
        direction: "increases",
      },
      {
        feature: "source",
        label: "Lead source",
        contribution: 0.25,
        value: "Referral from an existing customer",
        direction: "increases",
      },
      {
        feature: "prior_won_initiatives",
        label: "Won initiatives",
        contribution: 0.14,
        value: "One initiative won together",
        direction: "increases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09964", status: "won", source: "referral", created_at: "2026-09-10", closed_at: "2026-10-22", amount_arr: 105_000, discount_pct: 3, lost_reason: null },
      { id: "L-08331", status: "won", source: "inbound", created_at: "2026-02-18", closed_at: "2026-03-30", amount_arr: 90_000, discount_pct: 2, lost_reason: null },
    ],
  },
  {
    lead_id: "L-10588",
    company_id: "C-00903",
    company_name: "Cooperativa Edilizia Tevere S.r.l.",
    region: "centro",
    industry: "Costruzioni",
    employees: 95,
    source: "outbound",
    status: "contacted",
    created_at: "2026-11-07",
    amount_arr: 400_000,
    discount_pct: 25,
    probability: 0.19,
    drivers: [
      {
        feature: "first_response_hours",
        label: "First response",
        contribution: -0.34,
        value: "No first response yet",
        direction: "decreases",
      },
      {
        feature: "discount_pct",
        label: "Discount",
        contribution: -0.22,
        value: "25% discount already offered",
        direction: "decreases",
      },
      {
        feature: "amount_arr",
        label: "Deal size",
        contribution: -0.2,
        value: "€400,000 proposed — larger initiatives close less often",
        direction: "decreases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09845", status: "lost", source: "outbound", created_at: "2026-08-20", closed_at: "2026-09-28", amount_arr: 55_000, discount_pct: 8, lost_reason: "price" },
      { id: "L-08011", status: "won", source: "outbound", created_at: "2026-01-12", closed_at: "2026-02-20", amount_arr: 88_000, discount_pct: 5, lost_reason: null },
    ],
  },
  {
    lead_id: "L-10529",
    company_id: "C-00724",
    company_name: "Mobilificio Salentino S.r.l.",
    region: "sud",
    industry: "Manifattura",
    employees: 130,
    source: "outbound",
    status: "proposal",
    created_at: "2026-09-12",
    amount_arr: 205_000,
    discount_pct: 7,
    probability: 0.35,
    drivers: [
      {
        feature: "owner_win_rate_180d",
        label: "Rep track record",
        contribution: 0.26,
        value: "Rep wins 44% of initiatives",
        direction: "increases",
      },
      {
        feature: "days_since_last_initiative",
        label: "Relationship gap",
        contribution: -0.21,
        value: "133 days without a new initiative",
        direction: "decreases",
      },
      {
        feature: "tickets_90d",
        label: "Support friction",
        contribution: -0.09,
        value: "2 support tickets in 90 days",
        direction: "decreases",
      },
    ],
    open_actions: [],
    history: [
      { id: "L-09528", status: "won", source: "outbound", created_at: "2026-07-08", closed_at: "2026-08-20", amount_arr: 125_000, discount_pct: 5, lost_reason: null },
      { id: "L-07512", status: "lost", source: "outbound", created_at: "2025-10-01", closed_at: "2025-11-10", amount_arr: 80_000, discount_pct: 9, lost_reason: "no_fit" },
      { id: "L-06109", status: "won", source: "inbound", created_at: "2025-01-20", closed_at: "2025-03-01", amount_arr: 80_000, discount_pct: 2, lost_reason: null },
    ],
  },
];

// ---------------------------------------------------------------------------
// Derive every view from the authored world
// ---------------------------------------------------------------------------

const details = {};
const pipelineItems = [];

for (const lead of leads) {
  const daysOpen = daysBetween(lead.created_at, SNAPSHOT);
  const lastInitiative = lead.history[0].created_at;
  const daysSinceLast = daysBetween(lastInitiative, SNAPSHOT);
  const lifetimeWon = lead.history
    .filter((h) => h.status === "won")
    .reduce((sum, h) => sum + h.amount_arr, 0);

  const drivers = [...lead.drivers].sort(
    (a, b) => Math.abs(b.contribution) - Math.abs(a.contribution),
  );

  const score = {
    probability: lead.probability,
    band: band(lead.probability),
    model_version: MODEL_VERSION,
    scored_at: SNAPSHOT_ISO,
    expected_value: Math.round(lead.probability * lead.amount_arr),
  };

  details[lead.lead_id] = {
    lead: {
      id: lead.lead_id,
      status: lead.status,
      source: lead.source,
      created_at: lead.created_at,
      closed_at: null,
      amount_arr: lead.amount_arr,
      discount_pct: lead.discount_pct,
      lost_reason: null,
    },
    company: {
      id: lead.company_id,
      name: lead.company_name,
      region: lead.region,
      industry: lead.industry,
      employees: lead.employees,
      lifetime_won_arr: lifetimeWon,
      dormant: daysSinceLast >= 180,
    },
    score,
    drivers,
    prior_initiatives: lead.history,
    open_actions: lead.open_actions,
  };

  pipelineItems.push({
    lead_id: lead.lead_id,
    company_name: lead.company_name,
    region: lead.region,
    source: lead.source,
    status: lead.status,
    amount_arr: lead.amount_arr,
    probability: lead.probability,
    band: band(lead.probability),
    expected_value: score.expected_value,
    days_open: daysOpen,
    top_driver: drivers[0],
  });
}

pipelineItems.sort((a, b) => b.expected_value - a.expected_value);

// Counterfactuals: one lever at a time, exactly what the UI offers.
const counterfactuals = {};
const actions = {};

for (const lead of leads) {
  const p = lead.probability;
  const cf = {
    "exec_sponsor_meeting=true": {
      ...rescore(p, EXEC_DELTA),
      explanation:
        "An executive sponsor meeting adds a meeting and lifts relationship health. The same model re-scores this initiative.",
    },
    "discovery_meeting=true": {
      ...rescore(p, DISCOVERY_DELTA),
      explanation:
        "A discovery meeting adds one structured session with the buyer. The same model re-scores this initiative.",
    },
  };

  for (let pct = 0; pct <= 30; pct += 5) {
    const delta = discountLogitDelta(lead.discount_pct, pct);
    const result = rescore(p, delta);
    const points = Math.abs(result.delta * 100).toFixed(1);
    cf[`discount_pct=${pct}`] = {
      ...result,
      explanation:
        pct === lead.discount_pct
          ? "The proposed discount is unchanged."
          : pct > lead.discount_pct
            ? `Raising the proposed discount to ${pct}% lowers the score by ${points} points — a discount does not buy the win.`
            : `Lowering the proposed discount to ${pct}% raises the score by ${points} points.`,
    };
  }

  counterfactuals[lead.lead_id] = cf;

  actions[lead.lead_id] = {
    call: { probability_after: round(p), delta: 0 },
    exec_sponsor_meeting: {
      probability_after: round(sigmoid(logit(p) + EXEC_DELTA)),
      delta: round(sigmoid(logit(p) + EXEC_DELTA) - p),
    },
    discovery_meeting: {
      probability_after: round(sigmoid(logit(p) + DISCOVERY_DELTA)),
      delta: round(sigmoid(logit(p) + DISCOVERY_DELTA) - p),
    },
    discount_review: { probability_after: round(p), delta: 0 },
  };
}

const portfolio = {
  total_expected_value: TOTAL_EXPECTED_VALUE,
  by_region: REGIONS.map((r) => ({
    region: r.region,
    open_leads: r.open_leads,
    win_rate: round(r.wins / r.open_leads),
    expected_value: r.expected_value,
  })),
  calibration: CALIBRATION,
  drift: DRIFT,
};

const health = {
  status: "ok",
  model_version: MODEL_VERSION,
  scored_at: SNAPSHOT_ISO,
};

const pipeline = {
  total: OPEN_LEADS,
  total_expected_value: TOTAL_EXPECTED_VALUE,
  items: pipelineItems,
};

// ---------------------------------------------------------------------------
// Validate before writing: the fixtures are the demo, so they must add up
// ---------------------------------------------------------------------------

const errors = [];
const sum = (xs) => xs.reduce((a, b) => a + b, 0);

if (pipelineItems.length !== leads.length) errors.push("pipeline item count");
const evs = pipelineItems.map((i) => i.expected_value);
for (let i = 1; i < evs.length; i += 1) {
  if (evs[i] > evs[i - 1]) errors.push(`queue not ranked at ${i}`);
}
for (const item of pipelineItems) {
  const detail = details[item.lead_id];
  if (!detail) errors.push(`missing detail ${item.lead_id}`);
  if (detail.score.expected_value !== item.expected_value) errors.push(`EV drift ${item.lead_id}`);
  if (detail.drivers[0].feature !== item.top_driver.feature) errors.push(`top driver drift ${item.lead_id}`);
  if (detail.score.band !== item.band) errors.push(`band drift ${item.lead_id}`);
}
if (sum(REGIONS.map((r) => r.open_leads)) !== OPEN_LEADS) errors.push("region leads do not sum to 19,752");
if (Math.abs(sum(REGIONS.map((r) => r.wins)) / OPEN_LEADS - PREVALENCE) > 1e-4) {
  errors.push(`prevalence ${sum(REGIONS.map((r) => r.wins)) / OPEN_LEADS}`);
}
if (sum(REGIONS.map((r) => r.expected_value)) !== TOTAL_EXPECTED_VALUE) {
  errors.push("region EV does not sum to total");
}
for (const r of REGIONS) {
  const implied = (r.open_leads * (r.wins / r.open_leads) * MEAN_ARR) / 1_000_000;
  const shown = r.expected_value / 1_000_000;
  if (Math.abs(implied - shown) > 0.08) errors.push(`region EV off: ${r.region}`);
}
const ece =
  CALIBRATION.reduce((acc, b) => acc + Math.abs(b.actual - b.predicted), 0) /
  CALIBRATION.length;
if (Math.abs(ece - MODEL.calibration_error) > 1e-9) errors.push(`ECE ${ece}`);
const meanPredicted = sum(CALIBRATION.map((b) => b.predicted)) / CALIBRATION.length;
if (Math.abs(meanPredicted - PREVALENCE) > 0.0001) errors.push(`calibration mean ${meanPredicted}`);

if (errors.length) {
  console.error("fixture validation failed:");
  for (const e of errors) console.error(" -", e);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Write
// ---------------------------------------------------------------------------

mkdirSync(OUT, { recursive: true });

function write(name, value) {
  writeFileSync(resolve(OUT, name), `${JSON.stringify(value, null, 2)}\n`, "utf8");
  console.log(`wrote src/fixtures/${name}`);
}

write("pipeline.json", pipeline);
write("leads.json", details);
write("counterfactuals.json", counterfactuals);
write("actions.json", actions);
write("portfolio.json", portfolio);
write("health.json", health);

console.log(
  `\n${pipelineItems.length} queue items | €${(TOTAL_EXPECTED_VALUE / 1e6).toFixed(2)}M expected | ` +
    `${(PREVALENCE * 100).toFixed(2)}% prevalence | ECE ${MODEL.calibration_error} | AUC ${MODEL.auc}`,
);
