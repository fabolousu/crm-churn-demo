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
import { MODEL_METRICS } from "../lib/metrics";
import { winPrevalence } from "../lib/model";
import { stabilityBreakdown } from "../lib/stability";
import { usePipeline } from "../state/PipelineProvider";

const CALIBRATION_DOMAIN: [number, number] = [0, 0.7];

/** Decorative calibration point: a plain circle, not an unlabelled role="img" SVG. */
function CalibrationDot({
  cx,
  cy,
  fill,
}: {
  cx?: number;
  cy?: number;
  fill?: string;
}) {
  if (cx === undefined || cy === undefined) return <g />;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={4.5}
      fill={fill ?? "#005EB8"}
      stroke="#FFFFFF"
      strokeWidth={1.5}
    />
  );
}

export default function PortfolioPage() {
  const { portfolio, health, pipeline } = usePipeline();
  const prevalence =
    portfolio.win_prevalence ?? winPrevalence(portfolio.by_region);
  const maxExpected = Math.max(
    ...portfolio.by_region.map((region) => region.expected_value),
  );

  const regionData = portfolio.by_region.map((region) => ({
    ...region,
    label: regionLabel(region.region),
    millions: region.expected_value / 1_000_000,
  }));

  const drift = portfolio.drift;
  const stability = stabilityBreakdown(drift);
  const latentGap = MODEL_METRICS.latentAuc - MODEL_METRICS.auc;
  const stabilityStatus =
    drift.status === "stable"
      ? "Stabile"
      : drift.status === "watch"
        ? "Attenzione"
        : "Allerta";

  return (
    <div>
      <PageHeader
        eyebrow="Portfolio · 18 novembre 2026"
        title="Un modello, cinque regioni"
        subtitle="Modello unificato con la regione come variabile e calibrazione per regione. 34% significa 34%: questa è la differenza tra un cruscotto e uno strumento decisionale."
      />

      <Card className="grid grid-cols-2 gap-y-6 p-6 sm:grid-cols-4 sm:gap-0 sm:divide-x sm:divide-line sm:p-0">
        <div className="sm:px-6 sm:py-6">
          <Stat
            label="Valore atteso totale"
            value={formatEURCompact(portfolio.total_expected_value)}
            hint={`${pipeline.total.toLocaleString("it-IT")} iniziative aperte`}
          />
        </div>
        <div className="border-l border-line pl-5 sm:border-0 sm:px-6 sm:py-6">
          <Stat
            label="Tasso di vincita stimato"
            value={formatPercent(prevalence, 2)}
            hint="prevalenza calibrata"
          />
        </div>
        <div className="sm:px-6 sm:py-6">
          <Stat
            label="Qualità del modello"
            value={MODEL_METRICS.auc.toFixed(3)}
            hint={`AUC · ${latentGap.toFixed(3)} sotto il tetto latente`}
          />
        </div>
        <div className="border-l border-line pl-5 sm:border-0 sm:px-6 sm:py-6">
          <Stat
            label="Errore di calibrazione"
            value={MODEL_METRICS.calibrationError.toFixed(4)}
            hint="scarto medio assoluto, decili"
          />
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
        <Card className="p-5 md:p-6">
          <SectionHeading
            label="Andamento per regione"
            title="Valore di pipeline e tasso di vincita"
            hint="Pilot Italia, cinque macro-regioni. Un modello unificato, non cinque separati."
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
                  stroke="#DBE2E8"
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
                  fill="#005EB8"
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
              <span>Tasso di vincita per regione</span>
              <span>Portfolio {formatPercent(prevalence, 2)}</span>
            </div>
            <div className="mt-3 space-y-2.5">
              {regionData.map((region) => (
                <div
                  key={region.region}
                  className="grid grid-cols-[76px_1fr_52px] items-center gap-3"
                >
                  <span className="text-[11px] text-ink/80">{region.label}</span>
                  <div className="relative h-2 rounded-[4px] bg-[#DBE2E8]">
                    <div
                      className="h-full rounded-[4px] bg-accent/75"
                      style={{ width: `${(region.win_rate / 0.4) * 100}%` }}
                    />
                    <span
                      className="absolute top-1/2 h-2.5 w-px -translate-y-1/2 bg-ink/30"
                      style={{ left: `${(prevalence / 0.4) * 100}%` }}
                      title={`Tasso di vincita portfolio ${formatPercent(prevalence, 2)}`}
                    />
                  </div>
                  <span className="text-right text-[11px] font-medium tabular-nums text-ink">
                    {formatPercent(region.win_rate, 1)}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[10px] leading-relaxed text-muted">
              Nord-Ovest e Nord-Est presentano i tassi base più elevati; Isole il
              più basso. La differenza è un effetto regionale, non un modello separato.
            </p>
          </div>
        </Card>

        <Card className="flex flex-col p-5 md:p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                Stato stabilità dati
              </p>
              <h2 className="mt-1.5 font-display text-[24px] leading-tight text-ink">
                {stabilityStatus}
              </h2>
              <p className="mt-0.5 text-[10px] text-muted">
                {stability ? "Holdout vs train" : "Holdout vs train non disponibile"}
              </p>
            </div>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-[4px] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] ring-1 ring-inset",
                drift.status === "stable"
                  ? "bg-[#CBE4FB] text-[#00499D] ring-[#B7E1C6]"
                  : drift.status === "watch"
                    ? "bg-[#FDF1E3] text-[#8A3A06] ring-[#F5D0A9]"
                    : "bg-[#FDECEA] text-[#912018] ring-[#F5C2BC]",
              )}
            >
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-[4px]",
                  drift.status === "stable"
                    ? "bg-risk-low"
                    : drift.status === "watch"
                      ? "bg-risk-medium"
                      : "bg-risk-high",
                )}
              />
              {stabilityStatus}
            </span>
          </div>

          <div className="mt-6">
            <div className="flex items-baseline justify-between">
              <span className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                Stabilità della popolazione (PSI)
              </span>
              <span className="font-display text-[24px] tabular-nums text-ink">
                {drift.psi.toFixed(3)}
              </span>
            </div>
            <div className="relative mt-2 h-2 overflow-hidden rounded-[4px] bg-[#DBE2E8]">
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
              <span>stabile &lt; 0.10</span>
              <span>attenzione 0.25</span>
              <span>allerta</span>
            </div>
            {stability ? (
              <p className="mt-2 text-[10.5px] leading-relaxed text-muted">
                PSI {drift.psi.toFixed(3)} si trova nella fascia di attenzione. L&apos;holdout
                ottiene punteggi genuinamente più elevati rispetto al train: probabilità media{" "}
                {formatPercent(stability.holdoutMean, 1)} vs{" "}
                {formatPercent(stability.trainMean, 1)}, tasso di vincita{" "}
                {formatPercent(stability.holdoutWinRate, 1)} vs{" "}
                {formatPercent(stability.trainWinRate, 1)}. E uno spostamento reale
                del tasso base nel mondo sintetico, non un difetto del modello.
              </p>
            ) : (
              <p className="mt-2 text-[10.5px] leading-relaxed text-muted">
                PSI {drift.psi.toFixed(3)} disponibile, ma la popolazione etichettata
                non ha potuto essere suddivisa in train e holdout. Lo spostamento di
                stabilità e <strong className="font-semibold text-ink">non misurabile</strong>; nessun valore alternativo viene mostrato.
              </p>
            )}
          </div>

          <dl className="mt-6 space-y-3 border-t border-line pt-4 text-[11.5px]">
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">AUC</dt>
              <dd className="font-medium tabular-nums text-ink">
                {MODEL_METRICS.auc.toFixed(3)}
                <span className="ml-2 text-[10px] font-normal text-muted">
                  tetto {MODEL_METRICS.latentAuc.toFixed(3)}
                </span>
              </dd>
            </div>
            {stability ? (
              <>
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="text-muted">Media p holdout</dt>
                  <dd className="font-medium tabular-nums text-ink">
                    {formatPercent(stability.holdoutMean, 1)}
                    <span className="ml-2 text-[10px] font-normal text-muted">
                      train {formatPercent(stability.trainMean, 1)}
                    </span>
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="text-muted">Tasso vincita holdout</dt>
                  <dd className="font-medium tabular-nums text-ink">
                    {formatPercent(stability.holdoutWinRate, 1)}
                    <span className="ml-2 text-[10px] font-normal text-muted">
                      train {formatPercent(stability.trainWinRate, 1)}
                    </span>
                  </dd>
                </div>
              </>
            ) : (
              <div className="rounded-[4px] border border-dashed border-line bg-[#F7FAFD] px-3 py-2.5">
                <p className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-muted">
                  Non misurabile
                </p>
                <p className="mt-1 text-[10px] leading-relaxed text-muted">
                  L&apos;API non ha fornito la suddivisione train/holdout per questa popolazione.
                  Il pannello mostra il PSI ma nessuno spostamento stimato.
                </p>
              </div>
            )}
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">Errore di calibrazione</dt>
              <dd className="font-medium tabular-nums text-ink">
                {MODEL_METRICS.calibrationError.toFixed(4)}
                <span className="ml-2 text-[10px] font-normal text-muted">
                  obiettivo &lt; 0.05
                </span>
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">Modello</dt>
              <dd className="text-right font-medium text-ink">
                {health.model_version}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-muted">Ultimo punteggio</dt>
              <dd className="text-right font-medium text-ink">
                {new Intl.DateTimeFormat("it-IT", {
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
            Metriche di build misurate: AUC {MODEL_METRICS.auc}, errore di calibrazione{" "}
            {MODEL_METRICS.calibrationError}, tetto latente{" "}
            {MODEL_METRICS.latentAuc}. La stabilità proviene da `/api/portfolio`
            quando la popolazione etichettata può essere suddivisa; in assenza dei campi opzionali,
            questo pannello indica &quot;non misurabile&quot; senza valori alternativi.
          </p>
        </Card>
      </div>

      <Card className="mt-6 p-5 md:p-6">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
          <div>
            <SectionHeading
              label="Stato calibrazione"
              title="34% significa davvero 34%?"
              hint="Tasso di vincita previsto rispetto a quello effettivo, in dieci decili."
            />
            <div
              className="h-[290px] w-full"
              role="img"
              aria-label="Grafico di calibrazione: tasso di vincita previsto rispetto a quello effettivamente osservato, in dieci decili. I punti vicini alla diagonale indicano che il modello è calibrato."
            >
              <div aria-hidden="true" className="h-full w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart
                  margin={{ top: 8, right: 18, bottom: 8, left: 0 }}
                >
                  <XAxis
                    type="number"
                    dataKey="predicted"
                    name="Previsto"
                    domain={CALIBRATION_DOMAIN}
                    tickFormatter={(value: number) => formatPercent(value)}
                    tick={{ fill: "#5B6472", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="number"
                    dataKey="actual"
                    name="Osservato"
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
                    stroke="#AFBAC4"
                    strokeDasharray="4 4"
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    content={<CalibrationTooltip />}
                  />
                  <Scatter
                    data={portfolio.calibration}
                    dataKey="actual"
                    fill="#005EB8"
                    fillOpacity={0.85}
                    stroke="#FFFFFF"
                    strokeWidth={1.5}
                    shape={<CalibrationDot />}
                    isAnimationActive={false}
                  />
                </ScatterChart>
              </ResponsiveContainer>
              </div>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2 text-[10px] text-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-[4px] bg-accent" />
                Decile bin
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-px w-5 border-t border-dashed border-[#AFBAC4]" />
                Calibrazione perfetta
              </span>
              <span>Previsto (x) vs osservato (y) tasso di vincita</span>
            </div>
          </div>

          <div className="flex flex-col justify-center rounded-[4px] bg-[#F7FAFD] p-5">
            <p className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted">
              Errore di calibrazione medio
            </p>
            <p className="mt-1 font-display text-[44px] leading-none tabular-nums text-ink">
              {MODEL_METRICS.calibrationError.toFixed(4)}
            </p>
            <p className="mt-3 text-[12px] leading-relaxed text-muted">
              Dieci decili, un numero. I punti si trovano sulla diagonale, quindi un
              punteggio del 34% vince circa il 34% delle volte. Questo è ciò che
              rende la coda uno strumento decisionale e non solo una classifica.
            </p>
            <div className="mt-5 space-y-2 border-t border-line pt-4 text-[10.5px]">
              <div className="flex justify-between gap-3">
                <span className="text-muted">Copertura</span>
                <span className="font-medium tabular-nums text-ink">
                  {pipeline.total.toLocaleString("it-IT")} iniziative
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted">Prevalenza vincita</span>
                <span className="font-medium tabular-nums text-ink">
                  {formatPercent(prevalence, 2)}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted">Lift@10%</span>
                <span className="font-medium tabular-nums text-ink">
                  {MODEL_METRICS.liftAt10.toFixed(2)}x vs casuale
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted">Regioni</span>
                <span className="font-medium text-ink">
                  {portfolio.by_region.length} · un modello unificato
                </span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <div className="mt-6 grid gap-4 border-t border-line pt-5 text-[10.5px] leading-relaxed text-muted md:grid-cols-3">
        <p>
          <span className="font-semibold text-ink">Valore atteso</span> e
          probabilità x ARR proposto. E la chiave di ordinamento perché il CFO
          ragiona in ARR, e EUR e l&apos;unica valuta nel demo.
        </p>
        <p>
          <span className="font-semibold text-ink">Addestrato su iniziative chiuse.</span>{" "}
          Le iniziative ancora aperte allo snapshot non hanno etichetta, quindi
          vengono escluse: includerle insegnerebbe al modello che aperto significa perso.
        </p>
        <p>
          <span className="font-semibold text-ink">Nessun modello di abbandono.</span>{" "}
          Un rapporto decade quando le iniziative si fermano; la dormienza è mostrata
          sull&apos;azienda, non prevista come evento.
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
    <div className="rounded-[4px] border border-line bg-surface px-3 py-2">
      <p className="text-[11px] font-semibold text-ink">{region.label}</p>
      <p className="mt-0.5 text-[10.5px] text-muted">
        {formatEURCompact(region.expected_value)} atteso ·{" "}
        {region.open_leads.toLocaleString("it-IT")} aperte
      </p>
      <p className="text-[10.5px] text-muted">
        {formatPercent(region.win_rate, 2)} tasso di vincita
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
    <div className="rounded-[4px] border border-line bg-surface px-3 py-2">
      <p className="text-[11px] font-semibold text-ink">
        {formatPercent(point.predicted, 1)} previsto
      </p>
      <p className="mt-0.5 text-[10.5px] text-muted">
        {formatPercent(point.actual, 1)} effettivamente vinto
      </p>
      <p className="text-[10.5px] text-muted">
        Scarto {gap > 0 ? "+" : ""}
        {(gap * 100).toFixed(1)} pt
      </p>
    </div>
  );
}
