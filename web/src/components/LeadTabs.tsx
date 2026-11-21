import { Link } from "react-router-dom";
import { cn } from "./ui";

type Tab = "overview" | "lever" | "act";

const TABS: Array<{ key: Tab; label: string; href: (id: string) => string }> = [
  { key: "overview", label: "Panoramica", href: (id) => `/previsioni/leads/${id}` },
  { key: "lever", label: "Leva", href: (id) => `/previsioni/leads/${id}/lever` },
  { key: "act", label: "Azione", href: (id) => `/previsioni/act/${id}` },
];

export default function LeadTabs({
  leadId,
  active,
}: {
  leadId: string;
  active: Tab;
}) {
  return (
    <nav
      className="mt-6 flex gap-1 border-b border-line"
      aria-label="Sezioni dell'iniziativa"
    >
      {TABS.map((tab) => {
        const selected = tab.key === active;
        return (
          <Link
            key={tab.key}
            to={tab.href(leadId)}
            aria-current={selected ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 px-3.5 py-2.5 text-[12.5px] font-medium transition",
              selected
                ? "border-accent text-ink"
                : "border-transparent text-muted hover:border-line hover:text-ink",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
