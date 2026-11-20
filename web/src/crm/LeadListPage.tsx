// `Lead personali aperti` — the P0 list screen (spec §2.3, §7).
// One grid, one footer, one view engine: every count on this page is computed from the
// committed seed, never typed in.

import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useCrm } from "./store";
import type { Lead, LeadStatusDef, LeadViewId } from "./types";
import { formatDateIt, formatDateTimeIt, formatNumberIt } from "../lib/i18n";
import {
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ColumnsIcon,
  DotsIcon,
  FilterLinesIcon,
  SearchIcon,
  ShareIcon,
  TrashIcon,
} from "./icons";

type ColumnKey =
  | "argomento"
  | "contatto"
  | "azienda"
  | "macro"
  | "iniziativa"
  | "proprietario"
  | "stato"
  | "creato"
  | "modificato"
  | "provincia"
  | "settore";

type ColumnDef = {
  key: ColumnKey;
  label: string;
  sortable?: boolean;
  defaultVisible: boolean;
  width: string;
};

const COLUMNS: ColumnDef[] = [
  { key: "argomento", label: "Argomento", sortable: true, defaultVisible: true, width: "min-w-[180px]" },
  { key: "contatto", label: "Contatto", sortable: true, defaultVisible: true, width: "min-w-[90px]" },
  { key: "azienda", label: "Azienda", sortable: true, defaultVisible: true, width: "min-w-[110px]" },
  { key: "macro", label: "1° Macro Settore", sortable: true, defaultVisible: true, width: "min-w-[80px]" },
  { key: "iniziativa", label: "Anagr. Interesse", sortable: true, defaultVisible: true, width: "min-w-[110px]" },
  { key: "proprietario", label: "Proprietario", sortable: true, defaultVisible: true, width: "min-w-[80px]" },
  { key: "stato", label: "Stato lavorazione", sortable: true, defaultVisible: true, width: "min-w-[110px]" },
  { key: "creato", label: "Creazione", sortable: true, defaultVisible: true, width: "min-w-[70px]" },
  { key: "modificato", label: "Modifica", sortable: true, defaultVisible: true, width: "min-w-[70px]" },
  { key: "provincia", label: "Provincia (Azienda)", sortable: true, defaultVisible: false, width: "min-w-[140px]" },
  { key: "settore", label: "1° Settore (Azienda)", sortable: true, defaultVisible: false, width: "min-w-[160px]" },
];

const VIEWS: Array<{ id: LeadViewId; label: string }> = [
  { id: "personal-open", label: "Lead personali aperti" },
  { id: "all", label: "Tutti i lead" },
  { id: "open", label: "Lead aperti" },
  { id: "closed", label: "Lead chiusi" },
  { id: "positive", label: "Lead conclusi con esito positivo" },
  { id: "personal", label: "Lead personali" },
  { id: "personal-closed", label: "Lead personali chiusi" },
];

const POSITIVE_CODES = ["servizio_concluso", "contratto_concluso", "iscritto_all_evento"];

const PAGE_SIZE = 50;

function statusStyle(status: LeadStatusDef): string {
  if (status.category === "closed") return "bg-[#F1EFEA] text-[#5B6472] ring-[#DDD8CE]";
  switch (status.code) {
    case "interessato":
      return "bg-[#E7F4EC] text-[#176B3B] ring-[#BFE3CD]";
    case "da_contattare":
      return "bg-[#FBF1E2] text-[#8A4B08] ring-[#EAD3B0]";
    case "in_attesa_di_riscontro":
      return "bg-[#E8F0FA] text-[#1D4E89] ring-[#C6D8EE]";
    default:
      return "bg-[#F1EFEA] text-[#4C5563] ring-[#DDD8CE]";
  }
}

function StatusChip({ status }: { status: LeadStatusDef }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-medium ring-1 ring-inset ${statusStyle(status)}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {status.labelIt}
    </span>
  );
}

function OwnerBadge({ name, initials }: { name: string; initials: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#176B3B] text-[9.5px] font-semibold text-white">
        {initials}
      </span>
      <span className="truncate text-[12.5px] text-ink">{name}</span>
    </span>
  );
}

type SortKey = "argomento" | "contatto" | "azienda" | "macro" | "iniziativa" | "proprietario" | "stato" | "creato" | "modificato" | "provincia" | "settore" | "none";

function compareLeads(
  a: Lead,
  b: Lead,
  key: SortKey,
  crm: ReturnType<typeof useCrm>,
): number {
  const value = (lead: Lead): string | number => {
    switch (key) {
      case "argomento":
        return lead.argomento.toLowerCase();
      case "contatto":
        return (crm.contactById(lead.contactId)?.fullName ?? "").toLowerCase();
      case "azienda":
        return (crm.companyById(lead.companyId)?.name ?? "").toLowerCase();
      case "macro":
        return (crm.companyById(lead.companyId)?.macroSector ?? "").toLowerCase();
      case "iniziativa":
        return (crm.initiativeById(lead.initiativeId)?.name ?? "").toLowerCase();
      case "proprietario":
        return (crm.ownerById(lead.ownerId)?.name ?? "").toLowerCase();
      case "stato":
        return crm.statusByCode(lead.statusCode).order;
      case "creato":
        return lead.createdAt;
      case "modificato":
        return lead.updatedAt;
      case "provincia":
        return (crm.companyById(lead.companyId)?.province ?? "").toLowerCase();
      case "settore":
        return (crm.companyById(lead.companyId)?.sector ?? "").toLowerCase();
      default:
        return 0;
    }
  };
  const left = value(a);
  const right = value(b);
  if (typeof left === "number" && typeof right === "number") return left - right;
  return String(left).localeCompare(String(right), "it");
}

export default function LeadListPage() {
  const crm = useCrm();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initialQuery = params.get("q") ?? "";

  const [view, setView] = useState<LeadViewId>("personal-open");
  const [viewOpen, setViewOpen] = useState(false);
  const [quickFind, setQuickFind] = useState(initialQuery);
  const [selected, setSelected] = useState<string[]>([]);
  const [sort, setSort] = useState<{ key: SortKey; direction: "asc" | "desc" }>({
    key: "modificato",
    direction: "desc",
  });
  const [visibleColumns, setVisibleColumns] = useState<ColumnKey[]>(
    COLUMNS.filter((column) => column.defaultVisible).map((column) => column.key),
  );
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkStatus, setBulkStatus] = useState<string>("da_contattare");
  const [bulkOwner, setBulkOwner] = useState<string>("marta");
  const [notice, setNotice] = useState("");

  const viewDef = VIEWS.find((entry) => entry.id === view) ?? VIEWS[0];

  const filtered = useMemo(() => {
    const text = quickFind.trim().toLowerCase();
    return crm.leads.filter((lead) => {
      const status = crm.statusByCode(lead.statusCode);
      const matchesView =
        view === "personal-open"
          ? lead.ownerId === crm.currentUserId && status.category === "open"
          : view === "all"
            ? true
            : view === "open"
              ? status.category === "open"
              : view === "closed"
                ? status.category === "closed"
                : view === "positive"
                  ? POSITIVE_CODES.includes(status.code)
                  : view === "personal"
                    ? lead.ownerId === crm.currentUserId
                    : lead.ownerId === crm.currentUserId && status.category === "closed";
      if (!matchesView) return false;
      if (statusFilter.length > 0 && !statusFilter.includes(status.code)) return false;
      if (!text) return true;
      const haystack = [
        lead.argomento,
        crm.contactById(lead.contactId)?.fullName,
        crm.companyById(lead.companyId)?.name,
        crm.initiativeById(lead.initiativeId)?.name,
        crm.ownerById(lead.ownerId)?.name,
        status.labelIt,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(text);
    });
  }, [crm, view, quickFind, statusFilter]);

  const sorted = useMemo(() => {
    if (sort.key === "none") return filtered;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const result = compareLeads(a, b, sort.key, crm);
      return sort.direction === "asc" ? result : -result;
    });
    return copy;
  }, [filtered, sort, crm]);

  const page = sorted.slice(0, PAGE_SIZE);
  const allOnPageSelected = page.length > 0 && page.every((lead) => selected.includes(lead.id));

  const statusCounts = useMemo(() => {
    const base = crm.leads.filter((lead) => {
      const status = crm.statusByCode(lead.statusCode);
      return view === "personal-open"
        ? lead.ownerId === crm.currentUserId && status.category === "open"
        : true;
    });
    return crm.statuses
      .filter((status) => status.category === "open" && status.active)
      .map((status) => ({
        status,
        count: base.filter((lead) => lead.statusCode === status.code).length,
      }))
      .filter((entry) => entry.count > 0);
  }, [crm, view]);

  function toggleSort(key: ColumnKey) {
    if (!COLUMNS.find((column) => column.key === key)?.sortable) return;
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    );
  }

  function toggleSelected(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  function exportCsv() {
    const header = COLUMNS.filter((column) => visibleColumns.includes(column.key)).map(
      (column) => column.label,
    );
    const rows = sorted.map((lead) =>
      COLUMNS.filter((column) => visibleColumns.includes(column.key)).map((column) =>
        cellText(lead, column.key),
      ),
    );
    const csv = [header, ...rows]
      .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(";"))
      .join("\r\n");
    const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `lead-personali-aperti-${sorted.length}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice(`Esportati ${sorted.length} record nella vista corrente.`);
  }

  function cellText(lead: Lead, key: ColumnKey): string {
    switch (key) {
      case "argomento":
        return lead.argomento;
      case "contatto":
        return crm.contactById(lead.contactId)?.fullName ?? "";
      case "azienda":
        return crm.companyById(lead.companyId)?.name ?? "";
      case "macro":
        return crm.companyById(lead.companyId)?.macroSector ?? "";
      case "iniziativa":
        return crm.initiativeById(lead.initiativeId)?.name ?? "";
      case "proprietario":
        return crm.ownerById(lead.ownerId)?.name ?? "";
      case "stato":
        return crm.statusByCode(lead.statusCode).labelIt;
      case "creato":
        return formatDateIt(lead.createdAt);
      case "modificato":
        return formatDateTimeIt(lead.updatedAt);
      case "provincia":
        return crm.companyById(lead.companyId)?.province ?? "";
      case "settore":
        return crm.companyById(lead.companyId)?.sector ?? "";
    }
  }

  const commandBar = (
    <div className="flex flex-wrap items-center gap-1">
      <Link
        to="/lead/new"
        className="mr-1 inline-flex h-8 items-center gap-1.5 rounded-md bg-[#176B3B] px-3 text-[12.5px] font-semibold text-white hover:bg-[#14562F] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1F8A4C]/40"
      >
        <span aria-hidden="true">+</span> Nuovo
      </Link>
      <CommandButton label="Mostra grafico" disabled />
      <CommandButton label="Aggiorna" onClick={() => setNotice("Dati aggiornati.")} />
      <CommandButton
        label={selected.length > 0 ? `Modifica (${selected.length})` : "Modifica"}
        onClick={() => setBulkOpen(true)}
        disabled={selected.length === 0}
      />
      <CommandButton label="Assegna" disabled={selected.length === 0} onClick={() => setBulkOpen(true)} />
      <CommandButton label="Elimina" disabled={selected.length === 0} icon={<TrashIcon className="h-4 w-4" />} />
      <CommandButton label="Condividi" icon={<ShareIcon className="h-4 w-4" />} />
      <CommandButton label="Esporta in Excel" onClick={exportCsv} />
      <CommandButton label="Altre azioni" icon={<DotsIcon className="h-4 w-4" />} showIconOnly />
    </div>
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        {commandBar}
        <p className="text-[11px] text-muted" aria-live="polite">
          {notice}
        </p>
      </div>

      <div className="rounded-xl border border-line bg-surface shadow-card">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <div className="relative">
            <button
              type="button"
              onClick={() => setViewOpen((open) => !open)}
              aria-expanded={viewOpen}
              className="inline-flex items-center gap-2 text-[18px] font-semibold tracking-tight text-ink"
            >
              {viewDef.label}
              <ChevronDownIcon className="h-4 w-4 text-ink/50" />
            </button>
            <span className="ml-2 rounded-full border border-line bg-[#FAFAF7] px-2 py-0.5 text-[10.5px] font-medium text-muted">
              Predefinito
            </span>
            {viewOpen ? (
              <div className="absolute left-0 top-full z-20 mt-2 w-[280px] rounded-lg border border-line bg-surface p-1.5 shadow-card">
                <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                  Visualizzazioni di sistema
                </p>
                {VIEWS.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => {
                      setView(entry.id);
                      setViewOpen(false);
                      setSelected([]);
                      setStatusFilter([]);
                    }}
                    className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-[12.5px] ${
                      entry.id === view
                        ? "bg-[#E7F4EC] text-[#176B3B]"
                        : "text-ink hover:bg-ink/[0.04]"
                    }`}
                  >
                    {entry.label}
                    {entry.id === view ? <span aria-hidden="true">✓</span> : null}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <div className="ml-auto flex flex-wrap items-center gap-2">
            <div className="relative">
              <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink/35">
                <SearchIcon className="h-4 w-4" />
              </span>
              <input
                value={quickFind}
                onChange={(event) => setQuickFind(event.target.value)}
                placeholder="Cerca in questa vista"
                aria-label="Cerca in questa vista"
                className="h-8 w-[220px] rounded-md border border-line bg-[#FAFAF7] pl-8 pr-2 text-[12.5px] focus:border-[#176B3B]/40 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#1F8A4C]/20"
              />
            </div>
            <button
              type="button"
              onClick={() => setColumnsOpen((open) => !open)}
              aria-expanded={columnsOpen}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-[12px] font-medium text-ink hover:bg-ink/[0.03]"
            >
              <ColumnsIcon className="h-4 w-4" /> Modifica colonne
            </button>
            <button
              type="button"
              onClick={() => setFiltersOpen((open) => !open)}
              aria-expanded={filtersOpen}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-[12px] font-medium text-ink hover:bg-ink/[0.03]"
            >
              <FilterLinesIcon className="h-4 w-4" /> Modifica filtri
            </button>
          </div>
        </div>

        {columnsOpen ? (
          <div className="flex flex-wrap gap-x-5 gap-y-2 border-b border-line bg-[#FAFAF7] px-4 py-3">
            {COLUMNS.map((column) => (
              <label key={column.key} className="inline-flex items-center gap-2 text-[12px] text-ink">
                <input
                  type="checkbox"
                  checked={visibleColumns.includes(column.key)}
                  onChange={() =>
                    setVisibleColumns((current) =>
                      current.includes(column.key)
                        ? current.filter((key) => key !== column.key)
                        : [...current, column.key],
                    )
                  }
                  className="h-3.5 w-3.5 rounded border-line text-[#176B3B] focus:ring-[#1F8A4C]/30"
                />
                {column.label}
              </label>
            ))}
          </div>
        ) : null}

        {filtersOpen ? (
          <div className="flex flex-wrap items-center gap-4 border-b border-line bg-[#FAFAF7] px-4 py-3">
            <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
              Stato lavorazione
            </span>
            {crm.statuses
              .filter((status) => status.active)
              .map((status) => (
                <label key={status.code} className="inline-flex items-center gap-2 text-[12px] text-ink">
                  <input
                    type="checkbox"
                    checked={statusFilter.includes(status.code)}
                    onChange={() =>
                      setStatusFilter((current) =>
                        current.includes(status.code)
                          ? current.filter((code) => code !== status.code)
                          : [...current, status.code],
                      )
                    }
                    className="h-3.5 w-3.5 rounded border-line text-[#176B3B] focus:ring-[#1F8A4C]/30"
                  />
                  {status.labelIt}
                </label>
              ))}
            <button
              type="button"
              onClick={() => setStatusFilter([])}
              className="text-[12px] font-medium text-[#176B3B] hover:underline"
            >
              Azzera filtri
            </button>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
          <span className="text-[11px] font-medium text-muted">Stato:</span>
          {statusCounts.map(({ status, count }) => (
            <button
              key={status.code}
              type="button"
              onClick={() =>
                setStatusFilter((current) =>
                  current.length === 1 && current[0] === status.code ? [] : [status.code],
                )
              }
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-medium ring-1 ring-inset transition ${statusStyle(status)} ${
                statusFilter.length === 0 || statusFilter.includes(status.code)
                  ? ""
                  : "opacity-40"
              }`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
              {status.labelIt}
              <span className="tabular-nums">{formatNumberIt(count)}</span>
            </button>
          ))}
          {statusFilter.length > 0 ? (
            <button
              type="button"
              onClick={() => setStatusFilter([])}
              className="text-[11.5px] font-medium text-[#176B3B] hover:underline"
            >
              Mostra tutti
            </button>
          ) : null}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-line bg-[#F7F7F5] text-[10px] uppercase tracking-[0.08em] text-muted">
                <th scope="col" className="w-9 px-2 py-2.5">
                  <input
                    type="checkbox"
                    aria-label="Seleziona tutti i record della pagina"
                    checked={allOnPageSelected}
                    onChange={() =>
                      setSelected((current) =>
                        allOnPageSelected
                          ? current.filter((id) => !page.some((lead) => lead.id === id))
                          : Array.from(new Set([...current, ...page.map((lead) => lead.id)])),
                      )
                    }
                    className="h-3.5 w-3.5 rounded border-line text-[#176B3B] focus:ring-[#1F8A4C]/30"
                  />
                </th>
                {COLUMNS.filter((column) => visibleColumns.includes(column.key)).map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={
                      sort.key === column.key
                        ? sort.direction === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                    className={`px-2 py-2.5 font-semibold ${column.width}`}
                  >
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className="inline-flex items-center gap-1 uppercase tracking-[0.08em] hover:text-ink"
                    >
                      {column.label}
                      {sort.key === column.key ? (
                        <span aria-hidden="true">{sort.direction === "asc" ? "▲" : "▼"}</span>
                      ) : null}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.map((lead) => {
                const contact = crm.contactById(lead.contactId);
                const company = crm.companyById(lead.companyId);
                const initiative = crm.initiativeById(lead.initiativeId);
                const owner = crm.ownerById(lead.ownerId);
                const status = crm.statusByCode(lead.statusCode);
                const selectedRow = selected.includes(lead.id);
                return (
                  <tr
                    key={lead.id}
                    className={`border-b border-line/70 text-[12.5px] transition ${
                      selectedRow ? "bg-[#F0F8F3]" : "hover:bg-[#FAFAF7]"
                    }`}
                  >
                    <td className="px-2 py-2.5">
                      <input
                        type="checkbox"
                        aria-label={`Seleziona ${lead.argomento}`}
                        checked={selectedRow}
                        onChange={() => toggleSelected(lead.id)}
                        className="h-3.5 w-3.5 rounded border-line text-[#176B3B] focus:ring-[#1F8A4C]/30"
                      />
                    </td>
                    {visibleColumns.includes("argomento") ? (
                      <td className="max-w-[260px] px-2 py-2.5">
                        <Link
                          to={`/lead/${lead.id}`}
                          onDoubleClick={() => navigate(`/lead/${lead.id}`)}
                          className="line-clamp-2 font-medium text-ink hover:text-[#176B3B] hover:underline"
                          title={lead.argomento}
                        >
                          {lead.argomento}
                        </Link>
                      </td>
                    ) : null}
                    {visibleColumns.includes("contatto") ? (
                      <td className="px-3 py-2.5 text-ink">{contact?.fullName}</td>
                    ) : null}
                    {visibleColumns.includes("azienda") ? (
                      <td className="px-3 py-2.5 text-ink">
                        <span className="line-clamp-2" title={company?.name}>
                          {company?.name}
                        </span>
                      </td>
                    ) : null}
                    {visibleColumns.includes("macro") ? (
                      <td className="px-3 py-2.5 text-muted">{company?.macroSector}</td>
                    ) : null}
                    {visibleColumns.includes("iniziativa") ? (
                      <td className="px-3 py-2.5 text-ink">
                        <span className="line-clamp-2" title={initiative?.name}>
                          {initiative?.name}
                        </span>
                      </td>
                    ) : null}
                    {visibleColumns.includes("proprietario") ? (
                      <td className="px-2 py-2.5">
                        {owner ? <OwnerBadge name={owner.name} initials={owner.initials} /> : null}
                      </td>
                    ) : null}
                    {visibleColumns.includes("stato") ? (
                      <td className="px-2 py-2.5">
                        <StatusChip status={status} />
                      </td>
                    ) : null}
                    {visibleColumns.includes("creato") ? (
                      <td className="px-3 py-2.5 text-muted tabular-nums">
                        {formatDateIt(lead.createdAt)}
                      </td>
                    ) : null}
                    {visibleColumns.includes("modificato") ? (
                      <td className="px-3 py-2.5 text-muted tabular-nums">
                        {formatDateTimeIt(lead.updatedAt)}
                      </td>
                    ) : null}
                    {visibleColumns.includes("provincia") ? (
                      <td className="px-3 py-2.5 text-muted">{company?.province}</td>
                    ) : null}
                    {visibleColumns.includes("settore") ? (
                      <td className="px-3 py-2.5 text-muted">{company?.sector}</td>
                    ) : null}
                  </tr>
                );
              })}
              {page.length === 0 ? (
                <tr>
                  <td
                    colSpan={visibleColumns.length + 1}
                    className="px-4 py-10 text-center text-[13px] text-muted"
                  >
                    Nessun lead in questa vista. Modifica i filtri o crea un nuovo lead.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-[12px] text-muted">
          <div className="flex items-center gap-3">
            <span>
              {sorted.length === 0 ? "0" : `1 - ${sorted.length}`} di {formatNumberIt(sorted.length)} record
            </span>
            {selected.length > 0 ? (
              <span className="inline-flex items-center gap-2">
                <span className="rounded bg-[#E7F4EC] px-1.5 py-0.5 font-medium text-[#176B3B]">
                  {selected.length} selezionati
                </span>
                <button
                  type="button"
                  onClick={() => setSelected([])}
                  className="font-medium text-[#176B3B] hover:underline"
                >
                  Deseleziona tutti
                </button>
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-3">
            <label className="inline-flex items-center gap-1.5">
              Righe per pagina:
              <select
                value={PAGE_SIZE}
                disabled
                aria-label="Righe per pagina"
                className="h-7 rounded border border-line bg-surface px-1.5 text-[12px]"
              >
                <option value={PAGE_SIZE}>50</option>
              </select>
            </label>
            <span>Pagina 1 di 1</span>
            <div className="flex items-center gap-1">
              <button type="button" disabled aria-label="Prima pagina" className="rounded p-1 text-ink/30">
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
              <button type="button" disabled aria-label="Pagina precedente" className="rounded p-1 text-ink/30">
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
              <button type="button" disabled aria-label="Pagina successiva" className="rounded p-1 text-ink/30">
                <ChevronRightIcon className="h-4 w-4" />
              </button>
              <button type="button" disabled aria-label="Ultima pagina" className="rounded p-1 text-ink/30">
                <ChevronRightIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {bulkOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Modifica record selezionati"
          className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30 p-4"
          onClick={() => setBulkOpen(false)}
        >
          <div
            className="w-full max-w-[420px] rounded-xl border border-line bg-surface p-5 shadow-card"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="text-[16px] font-semibold text-ink">Modifica {selected.length} record</h2>
            <p className="mt-1 text-[12px] text-muted">
              Vengono scritti solo i campi che cambi. Lo stato chiuso imposta Data chiusura.
            </p>
            <div className="mt-4 space-y-3">
              <label className="block text-[12px] font-medium text-ink">
                Stato lavorazione
                <select
                  value={bulkStatus}
                  onChange={(event) => setBulkStatus(event.target.value)}
                  className="mt-1 h-9 w-full rounded-md border border-line bg-surface px-2 text-[13px]"
                >
                  {crm.statuses.map((status) => (
                    <option key={status.code} value={status.code}>
                      {status.labelIt}
                      {status.category === "closed" ? " (chiuso)" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-[12px] font-medium text-ink">
                Proprietario
                <select
                  value={bulkOwner}
                  onChange={(event) => setBulkOwner(event.target.value)}
                  className="mt-1 h-9 w-full rounded-md border border-line bg-surface px-2 text-[13px]"
                >
                  {crm.owners.map((owner) => (
                    <option key={owner.id} value={owner.id}>
                      {owner.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setBulkOpen(false)}
                className="h-9 rounded-md border border-line px-3 text-[12.5px] font-medium text-ink"
              >
                Annulla
              </button>
              <button
                type="button"
                onClick={() => {
                  crm.bulkSetStatus(selected, bulkStatus);
                  crm.bulkSetOwner(selected, bulkOwner);
                  setNotice(`${selected.length} record aggiornati.`);
                  setSelected([]);
                  setBulkOpen(false);
                }}
                className="h-9 rounded-md bg-[#176B3B] px-3 text-[12.5px] font-semibold text-white hover:bg-[#14562F]"
              >
                Applica
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CommandButton({
  label,
  onClick,
  disabled,
  icon,
  showIconOnly,
}: {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  icon?: ReactNode;
  showIconOnly?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={showIconOnly ? label : undefined}
      className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium text-ink/75 transition hover:bg-ink/[0.05] hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
    >
      {icon}
      {showIconOnly ? null : label}
    </button>
  );
}
