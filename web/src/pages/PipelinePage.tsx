import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import QueueRow from "../components/QueueRow";
import RegionFilter, {
  type RegionFilterValue,
} from "../components/RegionFilter";
import { ArrowUpRightIcon, GridIcon } from "../components/icons";
import {
  buttonSecondary,
  Card,
  cn,
  PageHeader,
  Stat,
} from "../components/ui";
import {
  formatEUR,
  formatEURCompact,
  formatPercent,
  formatPoints,
  regionLabel,
} from "../lib/format";
import { LEVERAGE_BOOK, winPrevalence } from "../lib/model";
import { usePipeline } from "../state/PipelineProvider";

type SortKey = "expected_value" | "at_risk" | "leverage";

export default function PipelinePage() {
  const { pipeline, portfolio } = usePipeline();
  const [region, setRegion] = useState<RegionFilterValue>("all");
  const [searchParams, setSearchParams] = useSearchParams();

  const sortParam = searchParams.get("sort");
  const sort: SortKey =
    sortParam === "at_risk" || sortParam === "leverage"
      ? sortParam
      : "expected_value";

  const changeSort = (next: SortKey) => {
    if (next === "expected_value") setSearchParams({});
    else setSearchParams({ sort: next });
  };

  const prevalence = portfolio.win_prevalence ?? winPrevalence(portfolio.by_region);
  const openArr = pipeline.total_open_arr ?? null;
  const atRisk =
    openArr !== null
      ? Math.max(0, openArr - pipeline.total_expected_value)
      : null;

  const items = useMemo(() => {
    const filtered =
      region === "all"
        ? pipeline.items
        : pipeline.items.filter((item) => item.region === region);

    return [...filtered].sort((a, b) => {
      if (sort === "at_risk") {
        return (
          (1 - b.probability) * b.amount_arr -
          (1 - a.probability) * a.amount_arr
        );
      }
      if (sort === "leverage") {
        return (b.max_leverage ?? 0) - (a.max_leverage ?? 0);
      }
      return b.expected_value - a.expected_value;
    });
  }, [pipeline.items, region, sort]);

  const viewValue = items.reduce((sum, item) => sum + item.expected_value, 0);
  const regionOpenLeads =
    region === "all"
      ? pipeline.total
      : (portfolio.by_region.find((entry) => entry.region === region)
          ?.open_leads ?? 0);

  return (
    <div>
      <PageHeader
        eyebrow="Pipeline · Previsioni AI"
        title="Iniziative per valore atteso"
        subtitle="Coda delle opportunità ordinate per valore atteso: probabilità moltiplicata per ARR proposto."
        actions={
          <Link to="/previsioni/portfolio" className={buttonSecondary}>
            <GridIcon className="h-4 w-4" />
            Vista Portfolio
          </Link>
        }
      />

      <Card className="grid grid-cols-2 gap-6 p-6 lg:grid-cols-4 lg:gap-0 lg:divide-x lg:divide-line lg:p-0">
        <div className="lg:px-6 lg:py-6">
          <Stat
            label="Valore atteso pipeline"
            value={formatEURCompact(pipeline.total_expected_value)}
            hint={`su ${pipeline.total.toLocaleString("it-IT")} iniziative aperte`}
          />
        </div>
        <div className="lg:px-6 lg:py-6">
          <Stat
            label="Valore a rischio"
            value={atRisk !== null ? formatEURCompact(atRisk) : "—"}
            hint="ARR non atteso"
          />
        </div>
        <div className="lg:px-6 lg:py-6">
          <Stat
            label="Tasso di conversione storico"
            value={formatPercent(prevalence, 2)}
            hint="prevalenza sulle iniziative chiuse"
          />
        </div>
        <div className="lg:px-6 lg:py-6">
          <Stat
            label="Iniziative aperte"
            value={pipeline.total.toLocaleString("it-IT")}
            hint="cinque macro-regioni"
          />
        </div>
      </Card>

      <div className="mt-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <RegionFilter
          selected={region}
          onSelect={setRegion}
          byRegion={portfolio.by_region}
          total={pipeline.total}
        />

        <div className="flex items-center gap-2.5">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
            Ordina per
          </span>
          <div className="inline-flex rounded-lg border border-line bg-surface p-0.5">
            {(
              [
                ["expected_value", "Valore atteso"],
                ["at_risk", "Valore a rischio"],
                ["leverage", "Leva massima"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-pressed={sort === key}
                onClick={() => changeSort(key)}
                className={cn(
                  "rounded-[6px] px-3 py-1.5 text-[11.5px] font-medium transition",
                  sort === key
                    ? "bg-ink text-paper shadow-sm"
                    : "text-muted hover:text-ink",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[11.5px] text-muted">
          {region === "all"
            ? `Mostrate ${items.length} di ${pipeline.total.toLocaleString("it-IT")} iniziative`
            : `${items.length} mostrate · ${regionOpenLeads.toLocaleString("it-IT")} aperte in ${regionLabel(region)}`}
          <span className="mx-2 text-line">/</span>
          <span className="font-medium text-ink">
            {formatEUR(viewValue)} attesi nella vista
          </span>
        </p>
        <p className="text-[11.5px] text-muted">
          {sort === "at_risk"
            ? "Ordinate per valore a rischio: (1 − probabilità) × ARR proposto"
            : sort === "leverage"
              ? "Ordinate per leva massima: il maggiore incremento tra le tre leve"
              : "Ordinate per valore atteso: probabilità × ARR proposto"}
        </p>
      </div>

      <div className="mt-3 hidden grid-cols-[2.25rem_minmax(0,1.45fr)_minmax(0,1.02fr)_152px_116px_1rem] gap-5 px-5 pb-2 text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted md:grid">
        <span />
        <span>Iniziativa</span>
        <span>Fattore principale</span>
        <span>Probabilità</span>
        <span className="text-right">Valore</span>
        <span />
      </div>

      <div className="space-y-2.5">
        {items.map((item, index) => (
          <QueueRow
            key={item.lead_id}
            item={item}
            rank={index + 1}
            badge={
              sort === "at_risk"
                ? "Più a rischio"
                : sort === "leverage"
                  ? "Più leva"
                  : "In cima alla coda"
            }
          />
        ))}
      </div>

      <div className="mt-8 grid gap-4 border-t border-line pt-5 text-[10.5px] leading-relaxed text-muted md:grid-cols-[1fr_1fr_auto]">
        <p>
          Le fasce di probabilità seguono il modello: bassa sotto il 20%, media
          sotto il 40%, alta sotto il 60%, critica (mostrata come{" "}
          <span className="font-medium text-ink">Top</span>) dal 60% in su.
          Sono fasce di probabilità di conversione, non giudizi di rischio.
        </p>
        <p>
          La leva è il <code>max_leverage</code> del contratto: il maggiore
          incremento di probabilità tra le tre leve. La mediana del libro è{" "}
          <span className="font-medium text-ink">
            {formatPoints(LEVERAGE_BOOK.median, 2)}
          </span>
          ; il 90° percentile è{" "}
          <span className="font-medium text-ink">
            {formatPoints(LEVERAGE_BOOK.p90, 2)}
          </span>
          . Ordina per leva per vedere dove lo sforzo paga: la mediana è solo
          +0,43 punti, quindi la coda è il punto.
        </p>
        <Link
          to="/previsioni/act"
          className="inline-flex items-center gap-1.5 font-medium text-accent hover:text-accent-deep"
        >
          Registra la prossima azione
          <ArrowUpRightIcon className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
