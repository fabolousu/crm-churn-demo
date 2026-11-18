import { Link } from "react-router-dom";
import type { PipelineItem } from "../lib/types";
import {
  formatEUR,
  formatEURCompact,
  formatOrdinal,
  formatPercent,
  regionLabel,
  sourceLabel,
} from "../lib/format";
import { ChevronRightIcon, TrendDownIcon, TrendUpIcon } from "./icons";
import { BandPill, cn, ProbabilityMeter } from "./ui";

export default function QueueRow({
  item,
  rank,
  badge,
}: {
  item: PipelineItem;
  rank: number;
  badge?: string;
}) {
  const driverIncreases = item.top_driver.direction === "increases";

  return (
    <Link
      to={`/leads/${item.lead_id}`}
      className="group grid grid-cols-[2rem_minmax(0,1fr)] items-start gap-x-4 gap-y-4 rounded-2xl border border-line bg-surface px-4 py-4 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-accent/35 hover:shadow-[0_18px_40px_-26px_rgba(20,24,31,0.4)] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 md:grid-cols-[2.25rem_minmax(0,1.45fr)_minmax(0,1.02fr)_152px_116px_1rem] md:items-center md:gap-5 md:px-5 md:py-5"
    >
      <div
        className={cn(
          "pt-0.5 font-display text-[20px] leading-none tabular-nums",
          rank === 1 ? "text-accent" : "text-muted/70",
        )}
      >
        {formatOrdinal(rank)}
      </div>

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <h3 className="truncate text-[15.5px] font-semibold tracking-[-0.01em] text-ink">
            {item.company_name}
          </h3>
          {rank === 1 && badge ? (
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-accent-deep">
              {badge}
            </span>
          ) : null}
        </div>
        <p className="mt-1.5 truncate text-[11.5px] text-muted">
          {regionLabel(item.region)} · {sourceLabel(item.source)} ·{" "}
          {item.days_open} days open · {item.status}
        </p>
      </div>

      <div className="col-span-2 flex min-w-0 items-start gap-2.5 md:col-span-1">
        <span
          className={cn(
            "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
            driverIncreases
              ? "bg-[#E7F4EC] text-risk-low"
              : "bg-[#FDECEA] text-risk-high",
          )}
        >
          {driverIncreases ? (
            <TrendUpIcon className="h-3.5 w-3.5" />
          ) : (
            <TrendDownIcon className="h-3.5 w-3.5" />
          )}
        </span>
        <div className="min-w-0">
          <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
            {item.top_driver.label}
          </p>
          <p className="mt-0.5 text-[12.5px] leading-snug text-ink/80">
            {item.top_driver.value}
          </p>
        </div>
      </div>

      <div className="min-w-0">
        <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted md:hidden">
          Win probability
        </p>
        <div className="mt-0.5 flex items-baseline gap-2 md:mt-0">
          <span className="font-display text-[26px] leading-none tabular-nums text-ink">
            {formatPercent(item.probability)}
          </span>
        </div>
        <ProbabilityMeter
          probability={item.probability}
          band={item.band}
          className="mt-2 max-w-[104px]"
        />
        <div className="mt-1.5">
          <BandPill band={item.band} compact />
        </div>
      </div>

      <div className="min-w-0 md:text-right">
        <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
          <span className="md:hidden">Value · </span>
          <span className="hidden md:inline">Proposed ARR</span>
        </p>
        <p className="mt-1 text-[14px] font-semibold tabular-nums text-ink">
          {formatEUR(item.amount_arr)}
        </p>
        <p className="mt-0.5 text-[11px] tabular-nums text-muted">
          {formatEURCompact(item.expected_value)} expected
        </p>
      </div>

      <div className="hidden justify-end text-muted/50 transition group-hover:translate-x-0.5 group-hover:text-accent md:flex">
        <ChevronRightIcon className="h-4 w-4" />
      </div>
    </Link>
  );
}
