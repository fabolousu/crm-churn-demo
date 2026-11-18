import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { usePipeline } from "../state/PipelineProvider";
import { formatDateTime } from "../lib/format";
import { BoltIcon, GridIcon, QueueIcon } from "./icons";

type NavItem = {
  to: string;
  label: string;
  icon: ReactNode;
  match: (pathname: string) => boolean;
};

const NAV: NavItem[] = [
  {
    to: "/",
    label: "Pipeline",
    icon: <QueueIcon />,
    match: (pathname) => pathname === "/" || pathname.startsWith("/leads"),
  },
  {
    to: "/act",
    label: "Act",
    icon: <BoltIcon />,
    match: (pathname) => pathname.startsWith("/act"),
  },
  {
    to: "/portfolio",
    label: "Portfolio",
    icon: <GridIcon />,
    match: (pathname) => pathname.startsWith("/portfolio"),
  },
];

function Wordmark() {
  return (
    <Link to="/" className="group flex items-center gap-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-paper shadow-sm transition group-hover:bg-accent-deep">
        <svg
          viewBox="0 0 32 32"
          className="h-5 w-5"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M9 22V15M16 22V10M23 22V18"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
          />
          <circle cx="23" cy="12.5" r="2.1" fill="#D9A06B" />
        </svg>
      </span>
      <span className="leading-tight">
        <span className="block text-[15px] font-semibold tracking-[0.14em] text-paper">
          INIZIATIVA
        </span>
        <span className="block text-[10px] uppercase tracking-[0.16em] text-paper/45">
          Pipeline intelligence
        </span>
      </span>
    </Link>
  );
}

function ModelCard() {
  const { health, portfolio, live } = usePipeline();
  const stable = portfolio.drift.status === "stable";

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.16em] text-paper/45">
          Model
        </span>
        <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.12em] text-paper/60">
          <span
            className={
              stable
                ? "h-1.5 w-1.5 rounded-full bg-[#5FD3A5]"
                : "h-1.5 w-1.5 rounded-full bg-[#F0B45A]"
            }
          />
          {stable ? "Stable" : portfolio.drift.status}
        </span>
      </div>
      <p className="mt-2 text-[13px] font-medium text-paper">
        {health.model_version}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed text-paper/45">
        Scored {formatDateTime(health.scored_at)}
      </p>
      <p className="mt-3 border-t border-white/10 pt-2 text-[10px] uppercase tracking-[0.14em] text-paper/35">
        {live ? "Live service" : "Fixture build · offline"}
      </p>
    </div>
  );
}

function NavLinks({
  compact = false,
  onPaper = false,
}: {
  compact?: boolean;
  onPaper?: boolean;
}) {
  const { pathname } = useLocation();

  return (
    <nav className={compact ? "flex gap-1" : "space-y-1"}>
      {NAV.map((item) => {
        const active = item.match(pathname);
        const activeClass = onPaper
          ? "bg-ink/[0.06] text-ink"
          : "bg-white/[0.09] text-paper";
        const idleClass = onPaper
          ? "text-ink/55 hover:bg-ink/[0.04] hover:text-ink"
          : "text-paper/55 hover:bg-white/[0.05] hover:text-paper/85";
        const iconClass = active
          ? onPaper
            ? "text-accent"
            : "text-[#8FCFBE]"
          : onPaper
            ? "text-ink/35 group-hover:text-ink/60"
            : "text-paper/35 group-hover:text-paper/60";

        return (
          <Link
            key={item.to}
            to={item.to}
            className={[
              "group flex items-center gap-3 rounded-lg text-[13.5px] font-medium transition",
              compact ? "px-3 py-2" : "px-3 py-2.5",
              active ? activeClass : idleClass,
            ].join(" ")}
          >
            <span className={iconClass}>{item.icon}</span>
            {item.label}
            {active && !compact ? (
              <span className="ml-auto h-1 w-1 rounded-full bg-[#8FCFBE]" />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const { health } = usePipeline();

  return (
    <div className="min-h-screen bg-paper lg:flex">
      <aside className="sticky top-0 hidden h-screen w-[252px] shrink-0 flex-col justify-between border-r border-black/10 bg-ink px-5 py-6 lg:flex">
        <div>
          <Wordmark />
          <div className="mt-10">
            <p className="px-3 text-[10px] font-medium uppercase tracking-[0.18em] text-paper/35">
              Workspace
            </p>
            <div className="mt-3">
              <NavLinks />
            </div>
          </div>
          <div className="mt-10 rounded-xl border border-white/10 p-4">
            <p className="text-[10px] uppercase tracking-[0.18em] text-paper/35">
              The argument
            </p>
            <p className="mt-2 font-display text-[15px] leading-snug text-paper/85">
              Contracts renew when someone proposes the next initiative. This is
              the queue that knows which one is at risk.
            </p>
          </div>
        </div>
        <ModelCard />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-paper/95 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between px-5 py-4">
            <Link to="/" className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-paper">
                <svg viewBox="0 0 32 32" className="h-4 w-4" fill="none">
                  <path
                    d="M9 22V15M16 22V10M23 22V18"
                    stroke="currentColor"
                    strokeWidth="2.6"
                    strokeLinecap="round"
                  />
                  <circle cx="23" cy="12.5" r="2.1" fill="#D9A06B" />
                </svg>
              </span>
              <span className="text-[13px] font-semibold tracking-[0.14em] text-ink">
                INIZIATIVA
              </span>
            </Link>
            <span className="text-[10px] uppercase tracking-[0.14em] text-muted">
              {formatDateTime(health.scored_at)}
            </span>
          </div>
          <div className="border-t border-line px-3 pb-3 pt-2">
            <NavLinks compact onPaper />
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1240px] flex-1 px-5 py-8 md:px-8 md:py-12 lg:px-12">
          {children}
        </main>

        <footer className="mx-auto w-full max-w-[1240px] px-5 pb-8 md:px-8 lg:px-12">
          <div className="flex flex-col gap-2 border-t border-line pt-5 text-[11px] text-muted md:flex-row md:items-center md:justify-between">
            <p>Iniziativa demo · Italy pilot · five macro-regions · EUR</p>
            <p>
              Probabilities are calibrated on closed initiatives. Every number is
              computed, never asserted.
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
