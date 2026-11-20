// The CRM shell (spec §2): top bar + collapsible left navigation.
//
// Q1: the CRM is the shell and the five ML screens live under `/previsioni` as a
// module. The shell therefore renders both, with the ML module as its own nav group.

import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useCrm } from "../crm/store";
import { usePipeline } from "../state/PipelineProvider";
import { formatDateTimeIt } from "../lib/i18n";
import {
  BulbIcon,
  BuildingIcon,
  ChevronDownIcon,
  ClockIcon,
  ConfigIcon,
  DashboardIcon,
  FunnelIcon,
  GearIcon,
  HelpIcon,
  HomeIcon,
  LeadIcon,
  LinkIcon,
  MegaphoneIcon,
  PinIcon,
  PlusIcon,
  SearchIcon,
  ServiceIcon,
  TaskIcon,
  UserIcon,
  WaffleIcon,
} from "../crm/icons";

type NavEntry = {
  to: string;
  label: string;
  icon: ReactNode;
  match?: (pathname: string) => boolean;
  hint?: string;
};

type NavGroup = { label: string; entries: NavEntry[] };

const topEntries: NavEntry[] = [
  { to: "/", label: "Home", icon: <HomeIcon />, match: (p) => p === "/" },
  { to: "/non-incluso?entity=Recenti", label: "Recenti", icon: <ClockIcon />, hint: "P2" },
  { to: "/non-incluso?entity=Aggiunti", label: "Aggiunti", icon: <PinIcon />, hint: "P2" },
];

const groups: NavGroup[] = [
  {
    label: "Attività personali",
    entries: [
      { to: "/non-incluso?entity=Dashboard", label: "Dashboard", icon: <DashboardIcon /> },
      { to: "/non-incluso?entity=Impegni", label: "Impegni", icon: <TaskIcon /> },
    ],
  },
  {
    label: "Clienti",
    entries: [
      { to: "/aziende", label: "Aziende", icon: <BuildingIcon /> },
      { to: "/contatti", label: "Contatti", icon: <UserIcon /> },
      {
        to: "/non-incluso?entity=Relazioni",
        label: "Rel. Aziende-Contatti",
        icon: <LinkIcon />,
      },
    ],
  },
  {
    label: "Interazioni",
    entries: [
      { to: "/", label: "Lead", icon: <LeadIcon />, match: (p) => p === "/" || p.startsWith("/lead") },
      {
        to: "/non-incluso?entity=Manifestazioni",
        label: "Manif. Interesse",
        icon: <MegaphoneIcon />,
      },
      { to: "/non-incluso?entity=Servizi", label: "Servizi", icon: <ServiceIcon /> },
    ],
  },
  {
    label: "Entità di configurazione",
    entries: [
      { to: "/iniziative", label: "Anagr. Iniziative", icon: <ConfigIcon /> },
    ],
  },
  {
    label: "Previsioni",
    entries: [
      {
        to: "/previsioni",
        label: "Pipeline",
        icon: <LeadIcon />,
        match: (p) => p === "/previsioni" || p.startsWith("/previsioni/leads"),
      },
      {
        to: "/previsioni/act",
        label: "Act",
        icon: <TaskIcon />,
        match: (p) => p.startsWith("/previsioni/act"),
      },
      {
        to: "/previsioni/portfolio",
        label: "Portfolio",
        icon: <DashboardIcon />,
        match: (p) => p.startsWith("/previsioni/portfolio"),
      },
    ],
  },
];

function ModelCard() {
  const { health, portfolio, live } = usePipeline();
  const stable = portfolio.drift.status === "stable";

  return (
    <div className="rounded-lg border border-line bg-[#FAFAF7] p-3.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
          Modello
        </span>
        <span
          className={`inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-[0.1em] ${
            stable ? "text-[#176B3B]" : "text-[#B54708]"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${stable ? "bg-[#176B3B]" : "bg-[#E8A33D]"}`}
          />
          {stable ? "stabile" : "da osservare"}
        </span>
      </div>
      <p className="mt-1.5 text-[12.5px] font-semibold text-ink">
        {health.model_version}
      </p>
      <p className="mt-0.5 text-[11px] text-muted">
        Punteggiato {formatDateTimeIt(health.scored_at)}
      </p>
      <p className="mt-2 border-t border-line pt-1.5 text-[10px] uppercase tracking-[0.12em] text-muted">
        {live ? "Servizio live" : "Build offline · fixture"}
      </p>
    </div>
  );
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation();
  const isActive = (entry: NavEntry) =>
    entry.match
      ? entry.match(pathname)
      : pathname === entry.to.split("?")[0];

  const linkClass = (active: boolean) =>
    [
      "group flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] font-medium transition",
      active
        ? "bg-[#E7F4EC] text-[#176B3B]"
        : "text-ink/70 hover:bg-ink/[0.04] hover:text-ink",
    ].join(" ");

  const iconClass = (active: boolean) =>
    active ? "text-[#176B3B]" : "text-ink/40 group-hover:text-ink/60";

  return (
    <nav aria-label="Navigazione principale" className="space-y-1">
      {topEntries.map((entry) => {
        const active = entry.match ? entry.match(pathname) : false;
        return (
          <Link
            key={entry.label}
            to={entry.to}
            onClick={onNavigate}
            className={linkClass(active)}
            title={entry.hint ? `${entry.label} (${entry.hint})` : undefined}
          >
            <span className={iconClass(active)}>{entry.icon}</span>
            {entry.label}
            {entry.label === "Recenti" || entry.label === "Aggiunti" ? (
              <ChevronDownIcon className="ml-auto h-3.5 w-3.5 text-ink/30" />
            ) : null}
          </Link>
        );
      })}

      {groups.map((group) => (
        <div key={group.label} className="pt-4">
          <p className="px-2.5 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.13em] text-muted">
            {group.label}
          </p>
          <div className="space-y-0.5">
            {group.entries.map((entry) => {
              const active = isActive(entry);
              return (
                <Link
                  key={entry.label}
                  to={entry.to}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={linkClass(active)}
                >
                  <span className={iconClass(active)}>{entry.icon}</span>
                  {entry.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

export default function CrmShell({ children }: { children: ReactNode }) {
  const { currentUser } = useCrm();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  return (
    <div className="min-h-screen bg-[#F7F7F5]">
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="flex h-14 items-center gap-3 px-4 lg:px-6">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="rounded-md p-1.5 text-ink/60 hover:bg-ink/[0.05] hover:text-ink lg:hidden"
            aria-label="Apri o chiudi la navigazione"
            aria-expanded={menuOpen}
          >
            <WaffleIcon />
          </button>
          <span className="hidden rounded-md p-1.5 text-ink/50 lg:inline-flex" aria-hidden="true">
            <WaffleIcon />
          </span>

          <Link to="/" className="flex items-baseline gap-2.5">
            <span className="text-[15px] font-semibold tracking-tight text-ink">
              CRM CCIAA - PROMOS
            </span>
            <span className="hidden rounded bg-[#E7F4EC] px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-[#176B3B] sm:inline">
              Trade Agency
            </span>
          </Link>

          <form
            className="ml-2 hidden flex-1 md:block"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              const trimmed = query.trim();
              navigate(trimmed ? `/?q=${encodeURIComponent(trimmed)}` : "/");
            }}
          >
            <label htmlFor="global-search" className="sr-only">
              Cerca
            </label>
            <div className="relative max-w-[420px]">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink/40">
                <SearchIcon className="h-4 w-4" />
              </span>
              <input
                id="global-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Cerca"
                className="h-9 w-full rounded-lg border border-line bg-[#F7F7F5] pl-9 pr-3 text-[13px] text-ink placeholder:text-muted/70 focus:border-[#176B3B]/40 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#1F8A4C]/20"
              />
            </div>
          </form>

          <div className="ml-auto flex items-center gap-1">
            <span className="hidden rounded-md p-2 text-ink/50 sm:inline-flex" aria-hidden="true">
              <BulbIcon />
            </span>
            <Link
              to="/lead/new"
              className="inline-flex h-8 items-center gap-1.5 rounded-md bg-[#176B3B] px-3 text-[12.5px] font-semibold text-white transition hover:bg-[#14562F] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1F8A4C]/40"
            >
              <PlusIcon className="h-4 w-4" />
              Crea
            </Link>
            <span className="hidden rounded-md p-2 text-ink/50 sm:inline-flex" aria-hidden="true">
              <FunnelIcon />
            </span>
            <span className="hidden rounded-md p-2 text-ink/50 sm:inline-flex" aria-hidden="true">
              <GearIcon />
            </span>
            <span className="hidden rounded-md p-2 text-ink/50 sm:inline-flex" aria-hidden="true">
              <HelpIcon />
            </span>
            <span
              className="ml-1 inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#176B3B] text-[11px] font-semibold text-white"
              title={currentUser.name}
            >
              {currentUser.initials}
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1500px]">
        <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-[248px] shrink-0 flex-col justify-between overflow-y-auto border-r border-line bg-surface px-3 py-4 lg:flex">
          <SidebarNav />
          <div className="space-y-3 pt-6">
            <ModelCard />
            <div className="rounded-lg border border-line px-3 py-2">
              <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                Area di lavoro
              </p>
              <p className="text-[12.5px] font-medium text-ink">Sales</p>
            </div>
          </div>
        </aside>

        {menuOpen ? (
          <div className="fixed inset-0 z-20 bg-ink/20 lg:hidden" onClick={() => setMenuOpen(false)}>
            <div
              className="h-full w-[272px] overflow-y-auto border-r border-line bg-surface px-3 py-4"
              onClick={(event) => event.stopPropagation()}
            >
              <SidebarNav onNavigate={() => setMenuOpen(false)} />
            </div>
          </div>
        ) : null}

        <main className="min-w-0 flex-1 px-4 py-5 md:px-6 md:py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
