import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import QueueRow from "../components/QueueRow";
import RegionFilter, {
  type RegionFilterValue,
} from "../components/RegionFilter";
import {
  ArrowUpRightIcon,
  GridIcon,
} from "../components/icons";
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
  regionLabel,
} from "../lib/format";
import {
  pipelineAtRisk,
  winPrevalence,
} from "../lib/model";
import { usePipeline } from "../state/PipelineProvider";

type SortKey = "expected_value" | "at_risk";

export default function PipelinePage() {
  const { pipeline, portfolio } = usePipeline();
  const [region, setRegion] = useState<RegionFilterValue>("all");
  const [sort, setSort] = useState<SortKey>("expected_value");

  const prevalence = winPrevalence(portfolio.by_region);

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
        eyebrow="Pipeline · 18 November 2026"
        title="What's worth a meeting today"
        subtitle="Open initiatives ranked by expected value — probability × proposed ARR. Not a list of records: a queue ordered by the work that pays."
        actions={
          <Link to="/portfolio" className={buttonSecondary}>
            <GridIcon className="h-4 w-4" />
            Portfolio view
          </Link>
        }
      />

      <Card className="grid gap-6 p-6 sm:grid-cols-3 sm:divide-x sm:divide-line sm:gap-0 sm:p-0">
        <div className="sm:px-6 sm:py-6">
          <Stat
            label="Expected pipeline value"
            value={formatEURCompact(portfolio.total_expected_value)}
            hint={`across ${pipeline.total.toLocaleString("en-GB")} open initiatives`}
          />
        </div>
        <div className="border-t border-line pt-6 sm:border-0 sm:px-6 sm:py-6 sm:pt-6">
          <Stat
            label="Proposed ARR at risk"
            value={formatEURCompact(pipelineAtRisk(portfolio.total_expected_value))}
            hint="open ARR not expected to convert"
          />
        </div>
        <div className="border-t border-line pt-6 sm:border-0 sm:px-6 sm:py-6 sm:pt-6">
          <Stat
            label="Win rate"
            value={formatPercent(prevalence, 2)}
            hint="model-calibrated prevalence, five regions"
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
            Sort
          </span>
          <div className="inline-flex rounded-lg border border-line bg-surface p-0.5">
            {(
              [
                ["expected_value", "Expected value"],
                ["at_risk", "Value at risk"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-pressed={sort === key}
                onClick={() => setSort(key)}
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
            ? `Showing ${items.length} of ${pipeline.total.toLocaleString("en-GB")} open initiatives`
            : `${items.length} shown · ${regionOpenLeads.toLocaleString("en-GB")} open in ${regionLabel(region)}`}
          <span className="mx-2 text-line">/</span>
          <span className="font-medium text-ink">
            {formatEUR(viewValue)} expected in view
          </span>
        </p>
        <p className="text-[11.5px] text-muted">
          {sort === "at_risk"
            ? "Sorted by value at risk — (1 − probability) × proposed ARR"
            : "Sorted by expected value — probability × proposed ARR"}
        </p>
      </div>

      <div className="mt-3 hidden grid-cols-[2.25rem_minmax(0,1.45fr)_minmax(0,1.02fr)_152px_116px_1rem] gap-5 px-5 pb-2 text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted md:grid">
        <span />
        <span>Initiative</span>
        <span>Strongest driver</span>
        <span>Win probability</span>
        <span className="text-right">Value</span>
        <span />
      </div>

      <div className="space-y-2.5">
        {items.map((item, index) => (
          <QueueRow
            key={item.lead_id}
            item={item}
            rank={index + 1}
            badge={sort === "at_risk" ? "Most at risk" : "Top of queue"}
          />
        ))}
      </div>

      <div className="mt-8 grid gap-3 border-t border-line pt-5 text-[10.5px] leading-relaxed text-muted md:grid-cols-[1fr_auto]">
        <p>
          Risk bands: critical below 15% probability, high below 30%, medium below
          50%, low at 50% or above. The contract defines the band names, not the
          cut points; the UI applies them consistently and re-bands every
          re-score.
        </p>
        <Link
          to="/act"
          className="inline-flex items-center gap-1.5 font-medium text-accent hover:text-accent-deep"
        >
          Act on the next call
          <ArrowUpRightIcon className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
