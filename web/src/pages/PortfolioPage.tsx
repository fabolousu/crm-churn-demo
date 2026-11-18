import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import {
  Card,
  cn,
  PageHeader,
  SectionHeading,
  Stat,
} from "../components/ui";
import { formatEURCompact, formatPercent, regionLabel } from "../lib/format";
import { MODEL_METRICS, OPEN_LEADS, winPrevalence } from "../lib/model";
import { usePipeline } from "../state/PipelineProvider";

const CALIBRATION_DOMAIN: [number, number] = [0, 0.7];

export default function PortfolioPage() {
  const { portfolio, health } = usePipeline();
  const prevalence = winPrevalence(portfolio.by_region);
  const maxExpected = Math.max(
    ...portfolio.by_region.map((region) => region.expected_value),
  );

  const regionData = portfolio.by_region.map((region) => ({
    ...region,
    label: regionLabel(region.region),
    millions: region.expected_value / 1_000_000,
  }));

  const drift = portfolio.drift;
  const latentGap = MODEL_METRICS.latentAuc - MODEL_METRICS.auc;

  return (
    <div>
      <PageHeader
        eyebrow="Portfolio · 18 November 2026"
        title="One model, five regions"
        subtitle="A pooled model with region as a feature and per-region calibration. 34% means 34% — that is the difference between a dashboard and a decision tool."
      />

      <Card className="grid grid-cols-2 gap-y-6 p-6 sm:grid-cols-4 sm:gap-0 sm:divide-x sm:divide-line sm:p-0">
        <div className="sm:px-6 sm:py-6">
          <Stat
            label="Expected pipeline value"
            value={formatEURCompact(portfolio.total_expected_value)}
            hint={`${OPEN_LEADS.toLocaleString("en-GB")} open initiatives`}
          />
        </div>
        <div className="border-l border-line pl-5 sm:border-0 sm:px-6 sm:py-6">
          <Stat
            label="Win rate"
            value={formatPercent(prevalence, 2)}
            hint="calibrated prevalence"
          />
        </div>
        <div className="sm:px-6 sm:py-6">
          <Stat
            label="Ranking quality"
            value={MODEL_METRICS.auc.toFixed(3)}
            hint={`AUC · ${latentGap.toFixed(3)} below the latent ceiling`}
          />
        </div>
        <div className="border-l border-line pl-5 sm:border-0 sm:px-6 sm:py-6">
          <Stat
            label="Calibration error"
            value={MODEL_METRICS.calibrationError.toFixed(4)}
            hint="mean absolute gap, decile bins"
          />
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
        <Card className="p-5 md:p-6">
          <SectionHeading
            label="By region"
            title="Pipeline value and win rate"
            hint="Italy pilot, five macro-regions. One pooled model, not five separate ones."
          />

          <div className="h-[250px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={regionData}
                layout="vertical"
                margin={{ top: 4, right: 58, bottom: 4, left: 4 }}
              >
                <CartesianGrid
                  horizontal={false}
                  stroke="#EDE8DE"
                  strokeDasharray="2 4"
                />
                <XAxis
                  type="number"
                  domain={[0, maxExpected * 1.08]}
                  hide
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={78}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#5B6472", fontSize: 11.5 }}
                />
                <Tooltip
                  cursor={{ fill: "rgba(15,107,92,0.05)" }}
                  content={<RegionTooltip />}
                />
                <Bar
                  dataKey="expected_value"
                  fill="#0F6B5C"
                  radius={6}
                  barSize={20}
                  isAnimationActive={false}
                >
                  <LabelList
                    dataKey="expected_value"
                    position="right"
                    formatter={(value: number) => formatEURCompact(value)}
                    style={{
                      fill: "#14181F",
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-5 border-t border-line pt-4">
            <div className="flex items-center justify-between text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
              <span>Win rate by region</span>
              <span>Portfolio {formatPercent(prevalence, 2)}</span>
            </div>
            <div className="mt-3 space-y-2.5">
              {regionData.map((region) => (
                <div
                  key={region.region}
                  className="grid grid-cols-[76px_1fr_52px] items-center gap-3"
                >
                  <span className="text-[11px] text-ink/80">{region.label}</span>
                  <div className="relative h-1.5 rounded-full bg-[#EEE9DF]">
                    <div
                      className="h-full rounded-full bg-accent/75"
                      style={{ width: `${(region.win_rate / 0.4) * 100}%` }}
                    />
                    <span
                      className="absolute top-1/2 h-2.5 w-px -translate-y-1/2 bg-ink/30"
                      style={{ left: `${(prevalence / 0.4) * 100}%` }}
                      title={`Portfolio win rate ${formatPercent(prevalence, 2)}`}
                    />
                  </div>
                  <span className="text-right text-[11px] font-medium tabular-nums text-ink">
                    {formatPercent(region.win_rate, 1)}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[10px] leading-relaxed text-muted">
              Nord-Ovest and Nord-Est carry the highest base rates; Isole the
              lowest. The difference is a region effect, not a separate model.
            </p>
          </div>
        </Card>

        <Card className="flex flex-col p-5 md:p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                Model health
              </p>
              <h2 className="mt-1.5 font-display text-[24px] leading-tight text-ink">
                {drift.status === "stable"
                  ? "Stable"
                  : drift.status === "watch"
                    ? "On watch"
                    : "Alert"}
              </h2>
            </div>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] ring-1 ring-inset",
                drift.status === "stable"
                  ? "bg-[#E7F4EC] text-[#05603A] ring-[#B7E1C6]"
                  : drift.status === "watch"
                    ? "bg-[#FDF1E3] text-[#8A3A06] ring-[#F5D0A9]"
                    : "bg-[#FDECEA] text-[#912018] ring-[#F5C2BC]",
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  drift.status === "stable"
                    ? "bg-risk-low"
                    : drift.status === "watch"
                      ? "bg-risk-medium"
                      : "bg-risk-high",
                )}
              />
              {drift.status}
            </span>
          </div>

          <div className="mt-6">
            <div className="flex items-baseline justify-between">
              <span className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                Population stability
              </span>
              <span className="font-display text-[24px] tabular-nums text-ink">
                {drift.psi.toFixed(3)}
              </span>
            </div>
            <div className="relative mt-2 h-2 overflow-hidden rounded-full bg-[#EEE9DF]">
              <div className="absolute inset-y-0 left-0 w-[28.6%] bg-[#CFE7D9]" />
              <div className="absolute inset-y-0 left-[28.6%] w-[42.9%] bg-[#F5E3C4]" />
              <div className="absolute inset-y-0 left-[71.5%] right-0 bg-[#F3D0CB]" />
            </div>
            <div className="relative mt-1 h-2">
              <span
                className="absolute -top-2.5 h-3 w-0.5 -translate-x-1/2 bg-ink"
                style={{ left: `${Math.min(98, (drift.psi / 0.35) * 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[9px] text-muted">
              <span>stable &lt; 0.10</span>
              <span>watch 0.25</span>
              <span>alert</span>
            </div>
            <p className="mt-2 text-[10.5px] leading-relaxed text-muted">
              PSI {drift.psi.toFixed(3)} is below the 0.10 watch threshold. One
              panel, one status — no drift infrastructure in this build.
            </p>
          </div>

          <dl className="mt-6 space-y-3 border-t border-line pt-4 text-[11.5px]">
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">AUC</dt>
              <dd className="font-medium tabular-nums text-ink">
                {MODEL_METRICS.auc.toFixed(3)}
                <span className="ml-2 text-[10px] font-normal text-muted">
                  ceiling {MODEL_METRICS.latentAuc.toFixed(3)}
                </span>
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">Calibration error</dt>
              <dd className="font-medium tabular-nums text-ink">
                {MODEL_METRICS.calibrationError.toFixed(4)}
                <span className="ml-2 text-[10px] font-normal text-muted">
                  target &lt; 0.05
                </span>
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">Model</dt>
              <dd className="text-right font-medium text-ink">
                {health.model_version}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">Last scored</dt>
              <dd className="text-right font-medium text-ink">
                {new Intl.DateTimeFormat("en-GB", {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                  timeZone: "Europe/Rome",
                }).format(new Date(health.scored_at))}
              </dd>
            </div>
          </dl>

          <p className="mt-auto border-t border-line pt-4 text-[10px] leading-relaxed text-muted">
            Measured build facts: AUC {MODEL_METRICS.auc}, calibration error{" "}
            {MODEL_METRICS.calibrationError}, latent ceiling{" "}
            {MODEL_METRICS.latentAuc}. The API contract exposes the calibration
            bins and the drift PSI, not these; they are held here until the
            contract carries them.
          </p>
        </Card>
      </div>

      <Card className="mt-6 p-5 md:p-6">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
          <div>
            <SectionHeading
              label="Calibration"
              title="Does 34% mean 34%?"
              hint="Predicted win rate against what actually happened, in ten decile bins."
            />
            <div className="h-[290px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart
                  margin={{ top: 8, right: 18, bottom: 8, left: 0 }}
                >
                  <CartesianGrid stroke="#EDE8DE" strokeDasharray="2 4" />
                  <XAxis
                    type="number"
                    dataKey="predicted"
                    name="Predicted"
                    domain={CALIBRATION_DOMAIN}
                    tickFormatter={(value: number) => formatPercent(value)}
                    tick={{ fill: "#5B6472", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="number"
                    dataKey="actual"
                    name="Actual"
                    domain={CALIBRATION_DOMAIN}
                    tickFormatter={(value: number) => formatPercent(value)}
                    tick={{ fill: "#5B6472", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={44}
                  />
                  <ZAxis range={[85, 85]} />
                  <ReferenceLine
                    segment={[
                      { x: 0, y: 0 },
                      { x: 0.7, y: 0.7 },
                    ]}
                    stroke="#B9B2A6"
                    strokeDasharray="4 4"
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    content={<CalibrationTooltip />}
                  />
                  <Scatter
                    data={portfolio.calibration}
                    dataKey="actual"
                    fill="#0F6B5C"
                    fillOpacity={0.85}
                    stroke="#FFFFFF"
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2 text-[10px] text-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-accent" />
                Decile bin
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-px w-5 border-t border-dashed border-[#B9B2A6]" />
                Perfect calibration
              </span>
              <span>Predicted (x) vs actual (y) win rate</span>
            </div>
          </div>

          <div className="flex flex-col justify-center rounded-xl bg-[#FAF8F3] p-5">
            <p className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted">
              Mean calibration error
            </p>
            <p className="mt-1 font-display text-[44px] leading-none tabular-nums text-ink">
              {MODEL_METRICS.calibrationError.toFixed(4)}
            </p>
            <p className="mt-3 text-[12px] leading-relaxed text-muted">
              Ten bins, one number. The points sit on the diagonal, so a 34%
              score wins about 34% of the time. That is what makes the queue a
              decision tool rather than a ranking.
            </p>
            <div className="mt-5 space-y-2 border-t border-line pt-4 text-[10.5px]">
              <div className="flex justify-between gap-3">
                <span className="text-muted">Coverage</span>
                <span className="font-medium tabular-nums text-ink">
                  {OPEN_LEADS.toLocaleString("en-GB")} leads
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted">Win prevalence</span>
                <span className="font-medium tabular-nums text-ink">
                  {formatPercent(prevalence, 2)}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted">Regions</span>
                <span className="font-medium text-ink">
                  {portfolio.by_region.length} · one pooled model
                </span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <div className="mt-6 grid gap-4 border-t border-line pt-5 text-[10.5px] leading-relaxed text-muted md:grid-cols-3">
        <p>
          <span className="font-semibold text-ink">Expected value</span> is
          probability × proposed ARR. It is the sort key because the CFO thinks
          in ARR, and EUR is the only currency in the demo.
        </p>
        <p>
          <span className="font-semibold text-ink">Trained on closed
          initiatives.</span> Leads still open at the snapshot have no label, so
          they are excluded — including them would teach the model that open
          means lost.
        </p>
        <p>
          <span className="font-semibold text-ink">No churn model.</span> A
          relationship decays when initiatives stop; dormancy is shown on the
          company, not predicted as an event.
        </p>
      </div>
    </div>
  );
}

type RegionTooltipProps = {
  active?: boolean;
  payload?: Array<{
    payload: {
      label: string;
      expected_value: number;
      win_rate: number;
      open_leads: number;
    };
  }>;
};

function RegionTooltip({ active, payload }: RegionTooltipProps) {
  if (!active || !payload?.length) return null;
  const region = payload[0].payload;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 shadow-card">
      <p className="text-[11px] font-semibold text-ink">{region.label}</p>
      <p className="mt-0.5 text-[10.5px] text-muted">
        {formatEURCompact(region.expected_value)} expected ·{" "}
        {region.open_leads.toLocaleString("en-GB")} open
      </p>
      <p className="text-[10.5px] text-muted">
        {formatPercent(region.win_rate, 2)} win rate
      </p>
    </div>
  );
}

type CalibrationTooltipProps = {
  active?: boolean;
  payload?: Array<{
    payload: { predicted: number; actual: number };
  }>;
};

function CalibrationTooltip({ active, payload }: CalibrationTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  const gap = point.actual - point.predicted;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 shadow-card">
      <p className="text-[11px] font-semibold text-ink">
        {formatPercent(point.predicted, 1)} predicted
      </p>
      <p className="mt-0.5 text-[10.5px] text-muted">
        {formatPercent(point.actual, 1)} actually won
      </p>
      <p className="text-[10.5px] text-muted">
        Gap {gap > 0 ? "+" : ""}
        {(gap * 100).toFixed(1)} pts
      </p>
    </div>
  );
}
