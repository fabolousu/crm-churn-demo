// Honest gap screen: the P0 gate allows gaps, but they must be listed and owned.
// (docs/UI_FEATURE_INVENTORY.md, "Gaps and open items".)

import { Link, useSearchParams } from "react-router-dom";

const GAPS: Record<string, { title: string; priority: string; next: string }> = {
  Dashboard: {
    title: "Dashboard",
    priority: "P1 · §7.7",
    next: "Charts and dashboards are specified but not on a designed screen; the data is ready in the CRM seed.",
  },
  Impegni: {
    title: "Impegni",
    priority: "P2 · §3.8",
    next: "The polymorphic Attività entity backs this list; only the lead timeline slice is implemented.",
  },
  Relazioni: {
    title: "Rel. Aziende-Contatti",
    priority: "P1 · §3.3",
    next: "The relationship is modelled in the seed (a contact can belong to several companies) but has no list screen yet.",
  },
  Manifestazioni: {
    title: "Manif. Interesse",
    priority: "P2 · §3.5",
    next: "The lead carries a read-only Manifestazione origine reference; the entity itself is a P2 gap.",
  },
  Servizi: {
    title: "Servizi",
    priority: "P2 · §3.7",
    next: "Servizio is under-specified in the source manual (§16.1); no fields are invented.",
  },
  Recenti: {
    title: "Recenti",
    priority: "P2 · §2.2",
    next: "Recent and pinned records are a shell affordance, not part of the P0 demo path.",
  },
  Aggiunti: {
    title: "Aggiunti",
    priority: "P2 · §2.2",
    next: "Recent and pinned records are a shell affordance, not part of the P0 demo path.",
  },
};

export default function GapPage() {
  const [params] = useSearchParams();
  const key = params.get("entity") ?? "";
  const gap = GAPS[key] ?? {
    title: key || "Modulo",
    priority: "P2",
    next: "This screen is outside the P0 demo scope.",
  };

  return (
    <div className="mx-auto max-w-2xl py-10">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
        Fuori dal percorso demo · {gap.priority}
      </p>
      <h1 className="mt-2 text-[26px] font-semibold tracking-tight text-ink">{gap.title}</h1>
      <p className="mt-3 text-[13.5px] leading-relaxed text-muted">{gap.next}</p>
      <p className="mt-4 text-[12px] leading-relaxed text-muted">
        La demo P0 copre la shell, <strong>Lead personali aperti</strong>, <strong>Scheda Lead</strong> e il
        modulo <strong>Previsioni</strong>. Le lacune sono elencate e assegnate in{" "}
        <code className="rounded bg-ink/[0.06] px-1 py-0.5 text-[11px]">docs/UI_FEATURE_INVENTORY.md</code>.
      </p>
      <div className="mt-6 flex gap-2">
        <Link
          to="/"
          className="inline-flex h-9 items-center rounded-md bg-[#176B3B] px-4 text-[13px] font-semibold text-white hover:bg-[#14562F]"
        >
          Torna ai lead
        </Link>
        <Link
          to="/previsioni"
          className="inline-flex h-9 items-center rounded-md border border-line px-4 text-[13px] font-medium text-ink hover:bg-ink/[0.03]"
        >
          Apri Previsioni
        </Link>
      </div>
    </div>
  );
}
