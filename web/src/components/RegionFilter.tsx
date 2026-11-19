import type { Region, RegionPortfolio } from "../lib/types";
import { REGIONS, regionLabel } from "../lib/format";
import { cn } from "./ui";

export type RegionFilterValue = "all" | Region;

export default function RegionFilter({
  selected,
  onSelect,
  byRegion,
  total,
}: {
  selected: RegionFilterValue;
  onSelect: (value: RegionFilterValue) => void;
  byRegion: RegionPortfolio[];
  total: number;
}) {
  const options: Array<{
    value: RegionFilterValue;
    label: string;
    count: number;
  }> = [
    { value: "all", label: "All regions", count: total },
    ...REGIONS.map((region) => ({
      value: region as RegionFilterValue,
      label: regionLabel(region),
      count:
        byRegion.find((entry) => entry.region === region)?.open_leads ?? 0,
    })),
  ];

  return (
    <div
      className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible"
      role="group"
      aria-label="Filter by region"
    >
      {options.map((option) => {
        const active = selected === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(option.value)}
            className={cn(
              "shrink-0 rounded-full border px-3 py-1.5 text-[11.5px] font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/30",
              active
                ? "border-ink bg-ink text-paper"
                : "border-line bg-surface text-ink/65 hover:border-ink/25 hover:text-ink",
            )}
          >
            {option.label}
            <span
              className={cn(
                "ml-2 text-[10px] tabular-nums",
                active ? "text-paper/55" : "text-muted",
              )}
            >
              {option.count.toLocaleString("en-GB")}
            </span>
          </button>
        );
      })}
    </div>
  );
}
