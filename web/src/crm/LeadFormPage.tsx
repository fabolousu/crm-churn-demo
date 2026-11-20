// `Scheda Lead` — the P0 record form (spec §2.4, §3.6, §4, §5.3, §6).
// The header flyout owns `Stato lavorazione` + `Proprietario`; the closing-date hook and
// the (Contatto, Anagrafica interesse) uniqueness check live here so the demo behaves
// like the specified product rather than a mock-up.

import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useCrm } from "./store";
import type { Lead } from "./types";
import { formatDateTimeIt } from "../lib/i18n";
import {
  ArrowLeftIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  DotsIcon,
  MailIcon,
  PlusIcon,
  SaveIcon,
  ShareIcon,
  StarIcon,
} from "./icons";

type TabId = "generale" | "amministrativi" | "correlati";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "generale", label: "Generale" },
  { id: "amministrativi", label: "Dati Amministrativi" },
  { id: "correlati", label: "Elementi correlati" },
];

const SOURCES = [
  "Manifestazione di interesse",
  "Evento",
  "Contatto diretto",
  "Referral",
  "Bando regionale",
];

function nowIso(): string {
  return new Date().toISOString();
}

function nextLeadId(existing: Lead[]): string {
  const numbers = existing
    .map((lead) => Number.parseInt(lead.id.replace(/\D/g, ""), 10))
    .filter((value) => Number.isFinite(value));
  const max = numbers.length > 0 ? Math.max(...numbers) : 9000;
  return `L-${max + 1}`;
}

function Field({
  label,
  required,
  locked,
  children,
  hint,
}: {
  label: string;
  required?: boolean;
  locked?: boolean;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="flex items-center gap-1.5 text-[11.5px] font-medium text-ink">
        {label}
        {required ? (
          <span className="text-[#B42318]" aria-label="campo obbligatorio">
            *
          </span>
        ) : null}
        {locked ? (
          <span className="text-[10px] font-normal uppercase tracking-[0.08em] text-muted">
            bloccato
          </span>
        ) : null}
      </span>
      <div className="mt-1">{children}</div>
      {hint ? <p className="mt-1 text-[10.5px] text-muted">{hint}</p> : null}
    </label>
  );
}

const inputClass =
  "h-9 w-full rounded-md border border-line bg-surface px-2.5 text-[13px] text-ink focus:border-[#176B3B]/40 focus:outline-none focus:ring-2 focus:ring-[#1F8A4C]/20 disabled:bg-[#F4F2ED] disabled:text-muted";

export default function LeadFormPage() {
  const crm = useCrm();
  const navigate = useNavigate();
  const { leadId } = useParams<{ leadId: string }>();
  const [params] = useSearchParams();

  // `/lead/new` is a static route, so it matches without a `leadId` param.
  const isNew = !leadId || leadId === "new";
  const savedLead = useMemo(
    () => crm.leads.find((lead) => lead.id === leadId),
    [crm.leads, leadId],
  );

  const initial = useMemo<Lead>(() => {
    if (savedLead) return { ...savedLead };
    const contactId = params.get("contactId") ?? "";
    const initiativeId = params.get("initiativeId") ?? "";
    const companyId = params.get("companyId") ?? "";
    const contact = contactId ? crm.contactById(contactId) : undefined;
    const autoCompany =
      companyId ||
      (contact && contact.companyIds.length === 1 ? contact.companyIds[0] : "");
    const initiative = initiativeId ? crm.initiativeById(initiativeId) : undefined;
    const company = autoCompany ? crm.companyById(autoCompany) : undefined;
    return {
      id: "new",
      argomento:
        initiative && company ? `${initiative.name} — ${company.name}` : "",
      descrizione: "",
      requests: "",
      noteMigrate: "",
      contactId: contactId,
      companyId: autoCompany,
      initiativeId,
      statusCode: "nuovo",
      ownerId: crm.currentUserId,
      source: "Manifestazione di interesse",
      tipoInteresse: "",
      manifestazioneOrigine: "",
      createdAt: "",
      updatedAt: "",
      closedAt: null,
    };
    // Initial values are captured once, on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [draft, setDraft] = useState<Lead>(initial);
  const [tab, setTab] = useState<TabId>("generale");
  const [flyoutOpen, setFlyoutOpen] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [headerStatus, setHeaderStatus] = useState(initial.statusCode);
  const [headerOwner, setHeaderOwner] = useState(initial.ownerId);

  const status = crm.statusByCode(draft.statusCode);
  const owner = crm.ownerById(draft.ownerId);
  const contact = draft.contactId ? crm.contactById(draft.contactId) : undefined;
  const company = draft.companyId ? crm.companyById(draft.companyId) : undefined;
  const initiative = draft.initiativeId
    ? crm.initiativeById(draft.initiativeId)
    : undefined;

  const dirty = savedLead
    ? JSON.stringify({ ...draft, updatedAt: "" }) !==
      JSON.stringify({ ...savedLead, updatedAt: "" })
    : true;

  const activities = crm.activities.filter((activity) => activity.leadId === draft.id);
  const duplicate =
    draft.contactId && draft.initiativeId
      ? crm.findDuplicate(
          draft.contactId,
          draft.initiativeId,
          isNew ? undefined : draft.id,
        )
      : undefined;

  const companyOptions = draft.contactId
    ? crm.companiesForContact(draft.contactId)
    : crm.companies;
  const contactOptions = draft.companyId
    ? crm.contacts.filter((candidate) =>
        candidate.companyIds.includes(draft.companyId),
      )
    : crm.contacts;

  const recordIndex = savedLead
    ? crm.leads.findIndex((lead) => lead.id === savedLead.id) + 1
    : crm.leads.length + 1;

  function update<K extends keyof Lead>(key: K, value: Lead[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function setContact(contactId: string) {
    const next = crm.contactById(contactId);
    const options = next ? next.companyIds : [];
    setDraft((current) => ({
      ...current,
      contactId,
      // P0 C15: one relationship auto-fills, several force a choice from the filtered list.
      companyId:
        options.length === 1
          ? options[0]
          : options.includes(current.companyId)
            ? current.companyId
            : "",
    }));
  }

  function applyHeader() {
    setDraft((current) => {
      const nextStatus = crm.statusByCode(headerStatus);
      const closedAt =
        nextStatus.category === "closed"
          ? (current.closedAt ?? nowIso())
          : null;
      return {
        ...current,
        statusCode: headerStatus,
        ownerId: headerOwner,
        closedAt,
      };
    });
    setFlyoutOpen(false);
    setNotice("Campi intestazione aggiornati. Salva per confermare.");
  }

  function save(closeAfter: boolean) {
    setError("");
    if (!draft.contactId || !draft.companyId || !draft.initiativeId) {
      setError(
        "Contatto, Azienda e Anagrafica interesse sono obbligatori.",
      );
      return;
    }
    if (duplicate) {
      setError(
        `Esiste già un lead per questo contatto e questa iniziativa (${duplicate.id}).`,
      );
      return;
    }
    const argomento =
      draft.argomento.trim() ||
      `${initiative?.name ?? "Iniziativa"} — ${company?.name ?? "Azienda"}`;
    const payload: Lead = { ...draft, argomento };

    if (isNew) {
      const id = nextLeadId(crm.leads);
      const created = crm.createLead({
        ...payload,
        id,
        createdAt: nowIso(),
        updatedAt: nowIso(),
        closedAt: null,
      } as Lead);
      crm.saveLead(created);
      setNotice("Lead creato e salvato.");
      if (closeAfter) {
        navigate("/");
      } else {
        navigate(`/lead/${id}`, { replace: true });
      }
      return;
    }

    crm.saveLead(payload);
    setNotice("Salvataggio completato.");
    if (closeAfter) navigate("/");
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-1">
        <Link
          to="/"
          aria-label="Torna alla lista"
          className="mr-1 inline-flex h-8 w-8 items-center justify-center rounded-md text-[#4C5563] hover:bg-ink/[0.05] hover:text-ink"
        >
          <ArrowLeftIcon className="h-4 w-4" />
        </Link>
        <CommandButton label="Salva" icon={<SaveIcon className="h-4 w-4" />} onClick={() => save(false)} primary testId="record-save" />
        <CommandButton label="Salva e chiudi" onClick={() => save(true)} />
        <span className="mx-1 h-5 w-px bg-line" aria-hidden="true" />
        <Link to="/lead/new" className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium text-ink/75 hover:bg-ink/[0.05] hover:text-ink">
          <PlusIcon className="h-4 w-4" /> Nuovo
        </Link>
        <CommandButton label="Aggiorna" onClick={() => setNotice("Dati aggiornati.")} />
        <CommandButton label="Assegna" onClick={() => setFlyoutOpen(true)} />
        <CommandButton label="Condividi" icon={<ShareIcon className="h-4 w-4" />} />
        <CommandButton label="Invia link tramite messaggio" icon={<MailIcon className="h-4 w-4" />} />
        <CommandButton label="Segui" icon={<StarIcon className="h-4 w-4" />} />
        <CommandButton label="Altre azioni" icon={<DotsIcon className="h-4 w-4" />} showIconOnly />
        <span className="ml-auto inline-flex items-center gap-1 text-[11.5px] text-muted">
          <button type="button" disabled aria-label="Record precedente" className="rounded p-1 text-ink/25">
            <ChevronLeftIcon className="h-4 w-4" />
          </button>
          <span>
            Lead <span className="tabular-nums">{recordIndex}</span> di{" "}
            <span className="tabular-nums">{crm.leads.length}</span>
          </span>
          <button type="button" disabled aria-label="Record successivo" className="rounded p-1 text-ink/25">
            <ChevronRightIcon className="h-4 w-4" />
          </button>
        </span>
      </div>

      <div className="rounded-xl border border-line bg-surface shadow-card">
        <div className="relative flex flex-wrap items-start gap-4 border-b border-line px-5 py-4">
          <span className="mt-0.5 inline-flex h-11 w-11 items-center justify-center rounded-lg bg-[#E7F4EC] text-[#176B3B]">
            <span className="text-[15px] font-semibold">L</span>
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="max-w-3xl text-[19px] font-semibold leading-snug tracking-tight text-ink">
              {draft.argomento ||
                (isNew ? "Nuovo lead" : "Senza argomento")}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11.5px] text-muted">
              <span className="rounded bg-[#F1EFEA] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[#4C5563]">
                Lead
              </span>
              <span data-testid="save-state" className="inline-flex items-center gap-1.5">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${dirty ? "bg-[#D9A06B]" : "bg-[#176B3B]"}`}
                />
                {dirty ? "Non salvato" : "Salvataggio completato"}
              </span>
              {!isNew && savedLead ? (
                <span>· Creato il {formatDateTimeIt(savedLead.createdAt)}</span>
              ) : null}
            </div>
          </div>

          <div className="flex items-start gap-6">
            <div className="text-[10px] uppercase tracking-[0.1em] text-muted">
              Stato lavorazione
              <div className="mt-1">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#E7F4EC] px-2.5 py-1 text-[12px] font-medium normal-case tracking-normal text-[#176B3B] ring-1 ring-inset ring-[#BFE3CD]">
                  <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
                  {status.labelIt}
                </span>
              </div>
            </div>
            <div className="text-[10px] uppercase tracking-[0.1em] text-muted">
              Proprietario
              <div className="mt-1 flex items-center gap-2">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#176B3B] text-[9.5px] font-semibold text-white">
                  {owner?.initials}
                </span>
                <span className="text-[12.5px] font-medium normal-case tracking-normal text-ink">
                  {owner?.name}
                </span>
                <button
                  type="button"
                  onClick={() => setFlyoutOpen((open) => !open)}
                  aria-expanded={flyoutOpen}
                  aria-label="Modifica campi intestazione"
                  className="rounded p-0.5 text-ink/50 hover:bg-ink/[0.05] hover:text-ink"
                >
                  <ChevronDownIcon className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          {flyoutOpen ? (
            <div data-testid="header-flyout" className="absolute right-4 top-[calc(100%-8px)] z-20 w-[320px] rounded-lg border border-line bg-surface p-4 shadow-card">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                  Modifica campi intestazione
                </p>
                <button
                  type="button"
                  onClick={() => setFlyoutOpen(false)}
                  aria-label="Chiudi"
                  className="text-ink/40 hover:text-ink"
                >
                  ✕
                </button>
              </div>
              <label className="mt-3 block text-[11.5px] font-medium text-ink">
                Stato lavorazione
                <select
                  data-testid="header-status"
                  value={headerStatus}
                  onChange={(event) => setHeaderStatus(event.target.value)}
                  className={`${inputClass} mt-1`}
                >
                  {crm.statuses.map((entry) => (
                    <option key={entry.code} value={entry.code}>
                      {entry.labelIt}
                      {entry.category === "closed" ? " (chiuso)" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="mt-3 block text-[11.5px] font-medium text-ink">
                Proprietario
                <select
                  data-testid="header-owner"
                  value={headerOwner}
                  onChange={(event) => setHeaderOwner(event.target.value)}
                  className={`${inputClass} mt-1`}
                >
                  {crm.owners.map((entry) => (
                    <option key={entry.id} value={entry.id}>
                      {entry.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setFlyoutOpen(false)}
                  className="h-8 rounded-md border border-line px-3 text-[12px] font-medium text-ink"
                >
                  Annulla
                </button>
                <button
                  type="button"
                  data-testid="header-apply"
                  onClick={applyHeader}
                  className="h-8 rounded-md bg-[#176B3B] px-3 text-[12px] font-semibold text-white hover:bg-[#14562F]"
                >
                  Salva
                </button>
              </div>
            </div>
          ) : null}
        </div>

        <div className="flex gap-1 border-b border-line px-5">
          {TABS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              onClick={() => setTab(entry.id)}
              aria-current={tab === entry.id ? "page" : undefined}
              className={`relative -mb-px px-3 py-2.5 text-[12.5px] font-medium transition ${
                tab === entry.id
                  ? "border-b-2 border-[#176B3B] text-[#176B3B]"
                  : "border-b-2 border-transparent text-muted hover:text-ink"
              }`}
            >
              {entry.label}
              {entry.id === "correlati" && activities.length > 0 ? (
                <span className="ml-1.5 rounded-full bg-[#F1EFEA] px-1.5 text-[10px] text-[#4C5563]">
                  {activities.length}
                </span>
              ) : null}
            </button>
          ))}
        </div>

        {error ? (
          <div data-testid="form-error" role="alert" className="mx-5 mt-4 rounded-md border border-[#F3C6C0] bg-[#FDF2F0] px-3 py-2 text-[12px] text-[#8A1C10]">
            {error}
          </div>
        ) : null}
        {duplicate ? (
          <div data-testid="duplicate-warning" className="mx-5 mt-4 rounded-md border border-[#EAD3B0] bg-[#FDF7EC] px-3 py-2 text-[12px] text-[#8A4B08]">
            Attenzione: esiste già un lead per questo contatto e questa iniziativa.{" "}
            <Link to={`/lead/${duplicate.id}`} className="font-semibold underline">
              Apri il lead esistente
            </Link>
            .
          </div>
        ) : null}
        <p className="px-5 pt-2 text-[11px] text-muted" aria-live="polite">
          {notice}
        </p>

        <div className="grid gap-6 px-5 py-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div>
            {tab === "generale" ? (
              <div className="space-y-4">
                <div className="rounded-lg border border-line">
                  <p className="border-b border-line px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                    Generale
                  </p>
                  <div className="space-y-3 p-3">
                    <Field label="Argomento" hint="Generato automaticamente dal sistema se lasciato vuoto.">
                      <input
                        value={draft.argomento}
                        onChange={(event) => update("argomento", event.target.value)}
                        className={inputClass}
                        placeholder="Argomento del lead"
                      />
                    </Field>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field label="Contatto" required>
                        <select
                          data-testid="lead-contact"
                          value={draft.contactId}
                          onChange={(event) => setContact(event.target.value)}
                          className={inputClass}
                        >
                          <option value="">Seleziona un contatto…</option>
                          {contactOptions.map((entry) => (
                            <option key={entry.id} value={entry.id}>
                              {entry.fullName}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field
                        label="Azienda"
                        required
                        hint={
                          contact && contact.companyIds.length > 1
                            ? "Il contatto ha più aziende: scegli quella corretta."
                            : undefined
                        }
                      >
                        <select
                          data-testid="lead-company"
                          value={draft.companyId}
                          onChange={(event) => update("companyId", event.target.value)}
                          className={inputClass}
                          disabled={Boolean(contact && contact.companyIds.length === 1)}
                        >
                          <option value="">Seleziona un'azienda…</option>
                          {companyOptions.map((entry) => (
                            <option key={entry.id} value={entry.id}>
                              {entry.name}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>

                    <Field label="Anagrafica interesse" required>
                      <select
                        data-testid="lead-initiative"
                        value={draft.initiativeId}
                        onChange={(event) => update("initiativeId", event.target.value)}
                        className={inputClass}
                      >
                        <option value="">Seleziona un'iniziativa…</option>
                        {crm.initiatives.map((entry) => (
                          <option key={entry.id} value={entry.id}>
                            {entry.code} · {entry.name}
                          </option>
                        ))}
                      </select>
                    </Field>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field label="Fonte">
                        <select
                          value={draft.source}
                          onChange={(event) => update("source", event.target.value)}
                          className={inputClass}
                        >
                          {SOURCES.map((source) => (
                            <option key={source} value={source}>
                              {source}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Tipo interesse" locked>
                        <input
                          value={draft.tipoInteresse}
                          readOnly
                          placeholder="Compilato dall'integrazione"
                          className={inputClass}
                        />
                      </Field>
                    </div>

                    <Field label="Manifestazione origine" locked hint="Riferimento di sola lettura alla manifestazione che ha generato il lead.">
                      <input
                        value={draft.manifestazioneOrigine}
                        readOnly
                        placeholder="MI-2025-…"
                        className={inputClass}
                      />
                    </Field>

                    <Field label="Richieste del contatto">
                      <textarea
                        value={draft.requests}
                        onChange={(event) => update("requests", event.target.value)}
                        rows={3}
                        className="w-full rounded-md border border-line bg-surface px-2.5 py-2 text-[13px] focus:border-[#176B3B]/40 focus:outline-none focus:ring-2 focus:ring-[#1F8A4C]/20"
                      />
                    </Field>

                    <Field label="Descrizione & Note interne">
                      <textarea
                        value={draft.descrizione}
                        onChange={(event) => update("descrizione", event.target.value)}
                        rows={4}
                        placeholder="Aggiungi una descrizione o nota interna…"
                        className="w-full rounded-md border border-line bg-surface px-2.5 py-2 text-[13px] focus:border-[#176B3B]/40 focus:outline-none focus:ring-2 focus:ring-[#1F8A4C]/20"
                      />
                    </Field>

                    <div className="grid gap-3 text-[11.5px] text-muted sm:grid-cols-3">
                      <div>
                        <span className="block text-[10px] uppercase tracking-[0.1em]">Creazione</span>
                        {savedLead ? formatDateTimeIt(savedLead.createdAt) : "—"}
                      </div>
                      <div>
                        <span className="block text-[10px] uppercase tracking-[0.1em]">Modifica</span>
                        {savedLead ? formatDateTimeIt(savedLead.updatedAt) : "—"}
                      </div>
                      <div>
                        <span className="block text-[10px] uppercase tracking-[0.1em]">Data chiusura</span>
                        <span data-testid="closed-at">
                          {draft.closedAt ? formatDateTimeIt(draft.closedAt) : "—"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            {tab === "amministrativi" ? (
              <div className="rounded-lg border border-line">
                <p className="border-b border-line px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                  Dati Amministrativi
                </p>
                <div className="space-y-3 p-3">
                  <Field label="Note migrate">
                    <textarea
                      value={draft.noteMigrate}
                      onChange={(event) => update("noteMigrate", event.target.value)}
                      rows={4}
                      className="w-full rounded-md border border-line bg-surface px-2.5 py-2 text-[13px] focus:border-[#176B3B]/40 focus:outline-none focus:ring-2 focus:ring-[#1F8A4C]/20"
                    />
                  </Field>
                  <Field label="ID lead" locked>
                    <input value={isNew ? "Assegnato al salvataggio" : draft.id} readOnly className={inputClass} />
                  </Field>
                  <Field label="Proprietario attuale" locked>
                    <input value={owner?.name ?? ""} readOnly className={inputClass} />
                  </Field>
                </div>
              </div>
            ) : null}

            {tab === "correlati" ? (
              <div className="rounded-lg border border-line">
                <p className="border-b border-line px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                  Elementi correlati
                </p>
                {isNew ? (
                  <p className="p-4 text-[12.5px] text-muted">
                    Salva il record per aggiungere attività alla sequenza temporale.
                  </p>
                ) : activities.length === 0 ? (
                  <p className="p-4 text-[12.5px] text-muted">
                    Nessuna attività registrata per questo lead.
                  </p>
                ) : (
                  <ul className="divide-y divide-line">
                    {activities.map((activity) => (
                      <li key={activity.id} className="flex gap-3 p-3">
                        <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#F1EFEA] text-[10px] font-semibold text-[#4C5563]">
                          {activity.kind === "email"
                            ? "✉"
                            : activity.kind === "call"
                              ? "☎"
                              : activity.kind === "note"
                                ? "✎"
                                : "•"}
                        </span>
                        <div className="min-w-0">
                          <p className="text-[12px] font-medium text-ink">
                            {activity.title} · {formatDateTimeIt(activity.at)}
                          </p>
                          <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted">
                            {activity.body}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : null}
          </div>

          <aside className="space-y-4">
            <div className="rounded-lg border border-line">
              <p className="border-b border-line px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                Preview Azienda
              </p>
              <div className="space-y-1.5 p-3 text-[12px]">
                <p className="font-medium text-ink">{company?.name ?? "Nessuna azienda"}</p>
                <p className="text-muted">{company?.macroSector} · {company?.sector}</p>
                <p className="text-muted">Provincia: {company?.province ?? "—"}</p>
                <p className="text-muted">Tipologia: {company?.tipologia ?? "—"}</p>
                <p className="text-muted">P. IVA: {company?.vat ?? "—"}</p>
              </div>
            </div>

            <div className="rounded-lg border border-line">
              <p className="border-b border-line px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
                Preview Contatto
              </p>
              <div className="space-y-1.5 p-3 text-[12px]">
                <p className="font-medium text-ink">{contact?.fullName ?? "Nessun contatto"}</p>
                <p className="break-all text-muted">{contact?.email ?? "—"}</p>
                <p className="text-muted">{contact?.phone ?? "—"}</p>
                <p className="text-muted">Maturità: {contact?.maturity ?? "—"}</p>
                <p className="text-muted">
                  Consenso privacy: {contact?.privacyConsent ? "Sì" : "No"}
                </p>
              </div>
            </div>

            <div className="rounded-lg border border-[#BFE3CD] bg-[#F2FAF5] p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#176B3B]">
                Regole attive
              </p>
              <ul className="mt-1.5 space-y-1 text-[11.5px] leading-relaxed text-[#21583A]">
                <li>· Un lead per contatto e iniziativa (unicità).</li>
                <li>· Una sola azienda del contatto → compilata automaticamente.</li>
                <li>· Stato chiuso imposta Data chiusura; la riapertura la cancella.</li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function CommandButton({
  label,
  onClick,
  icon,
  primary,
  showIconOnly,
  testId,
}: {
  label: string;
  onClick?: () => void;
  icon?: ReactNode;
  primary?: boolean;
  showIconOnly?: boolean;
  testId?: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      aria-label={showIconOnly ? label : undefined}
      className={
        primary
          ? "inline-flex h-8 items-center gap-1.5 rounded-md bg-[#176B3B] px-3 text-[12px] font-semibold text-white hover:bg-[#14562F]"
          : "inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium text-ink/75 transition hover:bg-ink/[0.05] hover:text-ink"
      }
    >
      {icon}
      {showIconOnly ? null : label}
    </button>
  );
}
