import type { ReactNode } from "react";
import type { Band } from "../lib/types";
import { BAND_STYLES } from "../lib/bands";
import { formatPercent } from "../lib/format";

export function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export const buttonPrimary =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-[13px] font-semibold text-white shadow-sm transition hover:bg-accent-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:cursor-not-allowed disabled:opacity-50";

export const buttonSecondary =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-line bg-surface px-4 py-2.5 text-[13px] font-semibold text-ink transition hover:border-ink/25 hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 disabled:cursor-not-allowed disabled:opacity-50";

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-9 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
      <div>
        <div className="flex items-center gap-3">
          <span className="h-px w-7 bg-accent/50" />
          <p className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-muted">
            {eyebrow}
          </p>
        </div>
        <h1 className="mt-3 max-w-3xl font-display text-[36px] leading-[1.04] tracking-[-0.01em] text-ink md:text-[52px]">
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-4 max-w-2xl text-[14.5px] leading-relaxed text-muted">
            {subtitle}
          </p>
        ) : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </header>
  );
}

export function SectionHeading({
  label,
  title,
  hint,
  action,
}: {
  label?: string;
  title: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        {label ? (
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted">
            {label}
          </p>
        ) : null}
        <h2 className="mt-1.5 font-display text-[24px] leading-tight text-ink">
          {title}
        </h2>
        {hint ? <p className="mt-1.5 text-[12.5px] text-muted">{hint}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Card({
  children,
  className,
  as = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article";
}) {
  const Tag = as;
  return (
    <Tag
      className={cn(
        "rounded-2xl border border-line bg-surface shadow-card",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

export function BandPill({
  band,
  className,
  compact = false,
}: {
  band: Band;
  className?: string;
  compact?: boolean;
}) {
  const style = BAND_STYLES[band];
  return (
    <span
      title={`Model probability band: ${style.label.toLowerCase()}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-semibold ring-1 ring-inset",
        compact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]",
        style.pill,
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
      {style.label}
    </span>
  );
}

export function ProbabilityMeter({
  probability,
  band,
  className,
  showBenchmark = false,
}: {
  probability: number;
  band: Band;
  className?: string;
  showBenchmark?: boolean;
}) {
  const style = BAND_STYLES[band];
  const width = Math.max(0, Math.min(100, probability * 100));

  return (
    <div
      className={cn("relative h-1.5 w-full rounded-full bg-[#EEE9DF]", className)}
      role="presentation"
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-700 ease-out", style.bar)}
        style={{ width: `${width}%` }}
      />
      {showBenchmark ? (
        <span
          className="absolute top-1/2 h-2.5 w-px -translate-y-1/2 bg-ink/30"
          style={{ left: "28.66%" }}
          title="Portfolio win rate 28.66%"
        />
      ) : null}
    </div>
  );
}

const DIAL_RADIUS = 92;
const DIAL_CENTER_X = 120;
const DIAL_CENTER_Y = 118;
const DIAL_CIRCUMFERENCE = Math.PI * DIAL_RADIUS;

function dialPoint(probability: number, radius: number) {
  const angle = Math.PI * (1 - probability);
  return {
    x: DIAL_CENTER_X + radius * Math.cos(angle),
    y: DIAL_CENTER_Y - radius * Math.sin(angle),
  };
}

export function ProbabilityDial({
  probability,
  band,
  className,
  benchmark = 0.2866,
  compact = false,
}: {
  probability: number;
  band: Band;
  className?: string;
  benchmark?: number;
  compact?: boolean;
}) {
  const style = BAND_STYLES[band];
  const clamped = Math.max(0, Math.min(1, probability));
  const offset = DIAL_CIRCUMFERENCE * (1 - clamped);
  const benchmarkPoint = dialPoint(benchmark, DIAL_RADIUS);
  const activePoint = dialPoint(clamped, DIAL_RADIUS);

  return (
    <div className={cn("w-full", className)}>
      <svg
        viewBox="0 0 240 150"
        className="w-full"
        role="img"
        aria-label={`${formatPercent(probability, 1)} win probability, ${BAND_STYLES[band].label}`}
      >
        <path
          d={`M ${DIAL_CENTER_X - DIAL_RADIUS} ${DIAL_CENTER_Y} A ${DIAL_RADIUS} ${DIAL_RADIUS} 0 0 1 ${DIAL_CENTER_X + DIAL_RADIUS} ${DIAL_CENTER_Y}`}
          fill="none"
          stroke="#ECE7DC"
          strokeWidth={compact ? 10 : 12}
          strokeLinecap="round"
        />
        {clamped > 0.001 ? (
          <path
            d={`M ${DIAL_CENTER_X - DIAL_RADIUS} ${DIAL_CENTER_Y} A ${DIAL_RADIUS} ${DIAL_RADIUS} 0 0 1 ${DIAL_CENTER_X + DIAL_RADIUS} ${DIAL_CENTER_Y}`}
            fill="none"
            stroke={style.hex}
            strokeWidth={compact ? 10 : 12}
            strokeLinecap="round"
            strokeDasharray={DIAL_CIRCUMFERENCE}
            strokeDashoffset={offset}
            className="transition-[stroke-dashoffset] duration-700 ease-out"
          />
        ) : null}

        <circle
          cx={benchmarkPoint.x}
          cy={benchmarkPoint.y}
          r={compact ? 2.2 : 2.6}
          fill="#F6F4EF"
          stroke="#8A8378"
          strokeWidth={1.4}
        />

        <circle
          cx={activePoint.x}
          cy={activePoint.y}
          r={compact ? 3.2 : 4}
          fill={style.hex}
          stroke="#F6F4EF"
          strokeWidth={2}
        />

        <text
          x={DIAL_CENTER_X}
          y={DIAL_CENTER_Y - 26}
          textAnchor="middle"
          className={cn(
            "fill-ink font-display tabular-nums",
            compact ? "text-[30px]" : "text-[40px]",
          )}
        >
          {formatPercent(probability, 1)}
        </text>
        <text
          x={DIAL_CENTER_X}
          y={DIAL_CENTER_Y - 7}
          textAnchor="middle"
          className="fill-muted text-[8.5px] font-medium uppercase tracking-[0.2em]"
        >
          to win
        </text>

        <text
          x={DIAL_CENTER_X - DIAL_RADIUS}
          y={DIAL_CENTER_Y + 18}
          textAnchor="middle"
          className="fill-muted text-[8.5px]"
        >
          0%
        </text>
        <text
          x={DIAL_CENTER_X + DIAL_RADIUS}
          y={DIAL_CENTER_Y + 18}
          textAnchor="middle"
          className="fill-muted text-[8.5px]"
        >
          100%
        </text>
      </svg>
      <p className="mt-1 flex items-center justify-center gap-1.5 text-[10.5px] text-muted">
        <span className="h-1.5 w-1.5 rounded-full border border-[#8A8378] bg-paper" />
        Portfolio win rate {formatPercent(benchmark, 2)}
      </p>
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
        {label}
      </p>
      <p className="mt-1.5 font-display text-[30px] leading-none tracking-tight text-ink tabular-nums md:text-[34px]">
        {value}
      </p>
      {hint ? <p className="mt-2 text-[11.5px] leading-snug text-muted">{hint}</p> : null}
    </div>
  );
}

export function InlineNotice({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex gap-2.5 rounded-lg border border-line/80 bg-[#FAF8F3] px-3.5 py-3 text-[11.5px] leading-relaxed text-muted",
        className,
      )}
    >
      <svg
        viewBox="0 0 24 24"
        className="mt-0.5 h-4 w-4 shrink-0 text-accent"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v5.5M12 7.8v.4" />
      </svg>
      <div>{children}</div>
    </div>
  );
}

export function MetaRow({
  label,
  value,
  className,
}: {
  label: string;
  value: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-baseline justify-between gap-4 py-2", className)}>
      <dt className="text-[11.5px] text-muted">{label}</dt>
      <dd className="text-right text-[12.5px] font-medium text-ink">{value}</dd>
    </div>
  );
}
