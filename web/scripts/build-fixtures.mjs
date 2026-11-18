// Generate the web fixtures from the running API and its database.
//
//   python tools/run_pipeline.py
//   python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
//   pnpm --dir web fixtures
//
// Nothing in src/fixtures/ is authored here. The queue, lead details, company
// details, counterfactuals, action re-scores, portfolio, model metrics and
// demo defaults all come from the live responses. The only database reads are
// the totals the API does not expose (total open ARR, closed-lead selection,
// labelled win prevalence).
//
// Environment:
//   API_BASE             default http://127.0.0.1:8000
//   DB_PATH              default <repo>/data/demo.db
//   FIXTURE_CONCURRENCY  default 6
//
// The script is deliberately a build step, never imported by the app. The app
// only reads the committed JSON.

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");
const OUT = resolve(HERE, "..", "src", "fixtures");
const API_BASE = (process.env.API_BASE ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const DB_PATH = process.env.DB_PATH ?? resolve(ROOT, "data", "demo.db");
const CONCURRENCY = Number(process.env.FIXTURE_CONCURRENCY ?? 6);
const DISCOUNTS = [0, 5, 10, 15, 20, 25, 30];
const OPEN_STATUSES = ["new", "contacted", "qualified", "proposal"];

const errors = [];
const warnings = [];
const check = (ok, message) => {
  if (!ok) errors.push(message);
};

async function api(path, init) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (!response.ok) {
    throw new Error(
      `${init?.method ?? "GET"} ${path} -> ${response.status}: ${(await response.text()).slice(0, 300)}`,
    );
  }
  return response.json();
}

const get = (path) => api(path);
const post = (path, body) =>
  api(path, { method: "POST", body: JSON.stringify(body) });

async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let next = 0;
  const worker = async () => {
    while (true) {
      const index = next++;
      if (index >= items.length) return;
      out[index] = await fn(items[index], index);
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, () => worker()),
  );
  return out;
}

const round = (value, places = 6) => Number(value.toFixed(places));

// ---------------------------------------------------------------------------
// Live service + database facts the API does not expose
// ---------------------------------------------------------------------------

console.log(`API ${API_BASE}`);
const health = await get("/api/health");
console.log(`health: ${health.status} ${health.model_version}`);

const pipeline = await get("/api/pipeline?limit=200");
const portfolio = await get("/api/portfolio");
const metricsRaw = JSON.parse(
  readFileSync(resolve(ROOT, "ml", "artifacts", "metrics.json"), "utf8"),
);

const db = new DatabaseSync(DB_PATH, { readOnly: true });
const openArr = db
  .prepare(
    `SELECT COALESCE(SUM(amount_arr), 0) AS total
     FROM leads WHERE status IN (${OPEN_STATUSES.map(() => "?").join(",")})`,
  )
  .get(...OPEN_STATUSES).total;
const labelled = db
  .prepare("SELECT SUM(won) AS won, COUNT(*) AS n FROM lead_outcomes")
  .get();
const closed = db
  .prepare(
    `SELECT l.id
     FROM leads AS l
     WHERE l.status IN ('won', 'lost')
       AND l.amount_arr >= 50000
       AND (SELECT COUNT(*) FROM leads AS p
            WHERE p.company_id = l.company_id AND p.created_at < l.created_at) >= 2
     ORDER BY l.id
     LIMIT 1`,
  )
  .get();
db.close();

if (!closed) throw new Error("the database has no closed lead with prior initiatives");
const winPrevalence = round(Number(labelled.won) / Number(labelled.n));
console.log(
  `open ARR €${openArr.toLocaleString("en-GB")} · labelled prevalence ${(winPrevalence * 100).toFixed(3)}%`,
);

const items = pipeline.items;
const ids = items.map((item) => item.lead_id);

// ---------------------------------------------------------------------------
// Lead details (every queue row must open) + one real closed lead
// ---------------------------------------------------------------------------

const details = {};
let leadsDone = 0;
await mapLimit(ids, CONCURRENCY, async (id) => {
  details[id] = await get(`/api/leads/${id}`);
  leadsDone += 1;
  if (leadsDone % 25 === 0) console.log(`lead details ${leadsDone}/${ids.length}`);
});
const closedDetail = await get(`/api/leads/${closed.id}`);
details[closed.id] = closedDetail;
console.log(`lead details: ${Object.keys(details).length} (incl. closed ${closed.id})`);

// ---------------------------------------------------------------------------
// Counterfactuals: all three levers for every queue row, so any row's lever
// screen is live rather than a dead fixture.
// ---------------------------------------------------------------------------

const counterfactuals = {};
let cfDone = 0;
await mapLimit(ids, CONCURRENCY, async (id) => {
  const entry = {
    "exec_sponsor_meeting=true": await post(
      `/api/leads/${id}/counterfactual`,
      { exec_sponsor_meeting: true },
    ),
    "discovery_meeting=true": await post(
      `/api/leads/${id}/counterfactual`,
      { discovery_meeting: true },
    ),
  };
  for (const pct of DISCOUNTS) {
    entry[`discount_pct=${pct}`] = await post(
      `/api/leads/${id}/counterfactual`,
      { discount_pct: pct },
    );
  }
  counterfactuals[id] = entry;
  cfDone += 1;
  if (cfDone % 10 === 0) {
    console.log(`counterfactuals ${cfDone}/${ids.length}`);
  }
});
console.log(`counterfactuals: ${Object.keys(counterfactuals).length} leads x 9 states`);

// Lane C is redefining max_leverage to the best *committable* lever and adding
// discount_upside for the what-if. When the running API has those fields, use
// them. Until it does, derive exactly the same quantities from the API's own
// counterfactual responses — the two committable levers and the discount
// states. No number is authored here.
const apiHasRedefinition = items.some(
  (item) => typeof item.discount_upside === "number",
);
if (!apiHasRedefinition) {
  console.warn(
    "API predates the max_leverage redefinition; deriving committable leverage and discount_upside from the API counterfactual responses.",
  );
}

for (const item of items) {
  const states = counterfactuals[item.lead_id];
  const exec = states["exec_sponsor_meeting=true"];
  const discovery = states["discovery_meeting=true"];
  const committableMax = Math.max(exec.delta, discovery.delta, 0);
  const discountUpside = Math.max(
    ...DISCOUNTS.map((pct) => states[`discount_pct=${pct}`].delta),
    0,
  );

  if (apiHasRedefinition) {
    if (typeof item.max_leverage !== "number") {
      errors.push(`${item.lead_id}: API is missing max_leverage`);
    } else if (Math.abs(item.max_leverage - committableMax) > 1e-6) {
      warnings.push(
        `${item.lead_id}: API max_leverage ${item.max_leverage} vs committable ${committableMax}`,
      );
    }
    if (
      typeof item.discount_upside !== "number" ||
      Math.abs(item.discount_upside - discountUpside) > 1e-6
    ) {
      warnings.push(
        `${item.lead_id}: API discount_upside ${item.discount_upside} vs ${discountUpside}`,
      );
    }
  } else {
    item.max_leverage = round(committableMax);
    item.discount_upside = round(discountUpside);
  }

  const detail = details[item.lead_id];
  detail.max_leverage = item.max_leverage;
  detail.discount_upside = item.discount_upside;
  if (typeof item.max_leverage !== "number") {
    errors.push(`${item.lead_id}: no committable max_leverage`);
  }
  if (typeof item.discount_upside !== "number") {
    errors.push(`${item.lead_id}: no discount_upside`);
  }
}

// ---------------------------------------------------------------------------
// Best lever, actions, demo defaults
// ---------------------------------------------------------------------------

function bestLeverFor(states) {
  // Committable levers only. Discount is a what-if and must never be the
  // default lever or the queue's leverage ranking.
  let best = {
    lever: "exec",
    discount_pct: null,
    delta: states["exec_sponsor_meeting=true"].delta,
  };
  const discovery = states["discovery_meeting=true"];
  if (discovery.delta > best.delta) {
    best = { lever: "discovery", discount_pct: null, delta: discovery.delta };
  }
  return { lever: best.lever, discount_pct: best.discount_pct };
}

const bestLevers = {};
for (const item of items) {
  bestLevers[item.lead_id] = bestLeverFor(counterfactuals[item.lead_id]);
}

const actions = {};
for (const item of items) {
  const states = counterfactuals[item.lead_id];
  actions[item.lead_id] = {
    call: { probability_after: round(item.probability), delta: 0 },
    exec_sponsor_meeting: {
      probability_after: round(
        states["exec_sponsor_meeting=true"].hypothetical_probability,
      ),
      delta: round(states["exec_sponsor_meeting=true"].delta),
    },
    discovery_meeting: {
      probability_after: round(
        states["discovery_meeting=true"].hypothetical_probability,
      ),
      delta: round(states["discovery_meeting=true"].delta),
    },
    discount_review: { probability_after: round(item.probability), delta: 0 },
  };
}

const byEv = [...items].sort(
  (a, b) => b.expected_value - a.expected_value || a.lead_id.localeCompare(b.lead_id),
);
const topItem = byEv[0];
const leverItem = [...items].sort(
  (a, b) =>
    (b.max_leverage ?? -Infinity) - (a.max_leverage ?? -Infinity) ||
    a.lead_id.localeCompare(b.lead_id),
)[0];
const actItem = [...items].sort(
  (a, b) =>
    actions[b.lead_id].exec_sponsor_meeting.delta -
      actions[a.lead_id].exec_sponsor_meeting.delta ||
    a.lead_id.localeCompare(b.lead_id),
)[0];

const rankOf = (leadId) => byEv.findIndex((item) => item.lead_id === leadId) + 1;
const actAction = actions[actItem.lead_id].exec_sponsor_meeting;
const actEvAfter = actAction.probability_after * actItem.amount_arr;
const actRankAfter =
  [...byEv]
    .map((item) =>
      item.lead_id === actItem.lead_id
        ? { ...item, expected_value: actEvAfter }
        : item,
    )
    .sort((a, b) => b.expected_value - a.expected_value)
    .findIndex((item) => item.lead_id === actItem.lead_id) + 1;

console.log(
  `top: ${topItem.lead_id} ${topItem.company_name} EV €${topItem.expected_value.toFixed(0)} | ` +
    `leverage: ${leverItem.lead_id} ${(leverItem.max_leverage * 100).toFixed(2)} pts | ` +
    `act: ${actItem.lead_id} +${(actAction.delta * 100).toFixed(2)} pts rank ${rankOf(actItem.lead_id)} -> ${actRankAfter}`,
);

// ---------------------------------------------------------------------------
// Company details for the demo leads (the 360 uses signals + full history)
// ---------------------------------------------------------------------------

const demoLeads = [topItem, leverItem, actItem];
const demoCompanyIds = new Set(
  [...demoLeads.map((item) => details[item.lead_id]), closedDetail]
    .map((entry) => entry?.company?.id)
    .filter(Boolean),
);
const companies = {};
await mapLimit([...demoCompanyIds], Math.min(4, CONCURRENCY), async (id) => {
  companies[id] = await get(`/api/companies/${id}`);
});
console.log(`company details: ${Object.keys(companies).length}`);

// ---------------------------------------------------------------------------
// Files
// ---------------------------------------------------------------------------

const metrics = {
  auc: metricsRaw.auc,
  calibration_error: metricsRaw.calibration_error,
  lift_at_10: metricsRaw.lift_at_10,
  latent_auc: metricsRaw.latent_auc,
  model_version: metricsRaw.model_version,
};

const pipelineOut = {
  ...pipeline,
  total_open_arr: openArr,
};

const portfolioOut = {
  ...portfolio,
  win_prevalence: winPrevalence,
  total_open_arr: openArr,
};

const demo = {
  top_lead_id: topItem.lead_id,
  lever_lead_id: leverItem.lead_id,
  act_lead_id: actItem.lead_id,
  closed_lead_id: closedDetail.lead.id,
  model_version: health.model_version,
  scored_at: health.scored_at,
};

// ---------------------------------------------------------------------------
// Validate before writing: the fixture is the demo, so it must match the API
// ---------------------------------------------------------------------------

check(pipeline.items.length === 200, `expected 200 queue rows, got ${pipeline.items.length}`);
check(pipeline.total === 19752, `pipeline total ${pipeline.total}`);
check(
  Math.abs(pipeline.total_expected_value - 282045124.593317) < 1,
  `total_expected_value ${pipeline.total_expected_value}`,
);
check(Math.abs(openArr - 720720300) < 1, `open ARR ${openArr}`);
check(
  Math.abs(portfolio.total_expected_value - pipeline.total_expected_value) < 1,
  "portfolio and pipeline totals disagree",
);
check(
  topItem.lead_id === "L021037" &&
    topItem.company_name === "Moretti Componenti S.a.s.",
  `top lead is ${topItem.lead_id} ${topItem.company_name}`,
);
check(
  Math.abs(topItem.expected_value - 142296.58065847863) < 0.01,
  `top EV ${topItem.expected_value}`,
);
check(
  Math.abs((topItem.max_leverage ?? 0) - 0.0046725362530714) < 1e-6,
  `Moretti committable max_leverage ${topItem.max_leverage}`,
);
check(
  Math.abs((topItem.discount_upside ?? 0) - 0.00888692922447532) < 1e-9,
  `Moretti discount_upside ${topItem.discount_upside}`,
);
check(
  leverItem.lead_id === "L021729" &&
    leverItem.company_name === "Russo Industrie S.p.A.",
  `lever lead is ${leverItem.lead_id} ${leverItem.company_name}`,
);
check(
  Math.abs((leverItem.max_leverage ?? 0) - 0.101566) < 0.001,
  `Russo committable max_leverage ${leverItem.max_leverage}`,
);
check(
  bestLevers[leverItem.lead_id]?.lever !== "discount",
  "the demo lever default must be a committable lever",
);
check(
  actItem.lead_id === leverItem.lead_id,
  `the Act lead ${actItem.lead_id} is not the lever lead ${leverItem.lead_id}`,
);
check(
  actAction.delta > 0.05 && actRankAfter < rankOf(actItem.lead_id),
  `act lead ${actItem.lead_id} does not move on an exec meeting`,
);
check(
  closedDetail.lead.status === "won" || closedDetail.lead.status === "lost",
  "closed lead is not closed",
);
check(
  closedDetail.max_leverage === null,
  `closed lead max_leverage ${closedDetail.max_leverage}`,
);
check(
  ["psi", "status", "train_mean", "holdout_mean", "train_win_rate", "holdout_win_rate"].every(
    (key) => portfolio.drift[key] !== undefined,
  ),
  "portfolio drift is missing stability fields",
);
check(Object.keys(details).length === 201, `detail count ${Object.keys(details).length}`);
check(
  Object.keys(counterfactuals).length === 200,
  `counterfactual count ${Object.keys(counterfactuals).length}`,
);
check(
  Object.keys(actions).length === 200,
  `action count ${Object.keys(actions).length}`,
);

if (warnings.length) {
  console.warn("\nwarnings:");
  for (const warning of warnings.slice(0, 20)) console.warn(` - ${warning}`);
  if (warnings.length > 20) console.warn(` - … ${warnings.length - 20} more`);
}
if (errors.length) {
  console.error("\nfixture validation failed:");
  for (const error of errors) console.error(` - ${error}`);
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

write("pipeline.json", pipelineOut);
write("leads.json", details);
write("companies.json", companies);
write("counterfactuals.json", counterfactuals);
write("actions.json", actions);
write("best-levers.json", bestLevers);
write("portfolio.json", portfolioOut);
write("health.json", health);
write("metrics.json", metrics);
write("demo.json", demo);

console.log(
  `\n${pipeline.items.length} queue rows | total ${pipeline.total.toLocaleString("en-GB")} | ` +
    `expected €${(pipeline.total_expected_value / 1e6).toFixed(2)}M | open €${(openArr / 1e6).toFixed(2)}M | ` +
    `top ${topItem.company_name} | leverage ${leverItem.company_name} ${(leverItem.max_leverage * 100).toFixed(2)} pts | ` +
    `act ${actItem.company_name}`,
);
