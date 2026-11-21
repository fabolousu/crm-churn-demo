import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Link,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import LeadTabs from "../components/LeadTabs";
import {
  ArrowLeftIcon,
  ArrowUpRightIcon,
  BoltIcon,
  CalendarIcon,
  ChatIcon,
  CheckIcon,
  UsersIcon,
} from "../components/icons";
import {
  BandPill,
  buttonPrimary,
  buttonSecondary,
  Card,
  cn,
  InlineNotice,
  PageHeader,
  ProbabilityTransition,
  SectionHeading,
} from "../components/ui";
import { bandForProbability } from "../lib/bands";
import {
  actionKindLabel,
  formatDateTime,
  formatEUR,
  formatEURCompact,
  formatPercent,
  formatPoints,
  formatSignedEUR,
  regionLabel,
  sourceLabel,
  statusLabel,
} from "../lib/format";
import { usePipeline } from "../state/PipelineProvider";
import type {
  ActionKind,
  ActionResponse,
  PipelineItem,
} from "../lib/types";

type RankedItem = { item: PipelineItem; rank: number };

type Outcome = {
  leadId: string;
  kind: ActionKind;
  response: ActionResponse;
  before: { probability: number; expectedValue: number; rank: number };
  after: { probability: number; expectedValue: number; rank: number };
  beforeItems: RankedItem[];
  afterItems: RankedItem[];
};

const ACTIONS: Array<{
  kind: ActionKind;
  label: string;
  description: string;
  icon: ReactNode;
}> = [
  {
    kind: "exec_sponsor_meeting",
    label: "Incontro con sponsor esecutivo",
    description: "Registra l'incontro e il miglioramento della relazione con lo sponsor.",
    icon: <UsersIcon className="h-4 w-4" />,
  },
  {
    kind: "discovery_meeting",
    label: "Sessione di discovery",
    description: "Registra una sessione di discovery strutturata.",
    icon: <CalendarIcon className="h-4 w-4" />,
  },
  {
    kind: "call",
    label: "Telefonata di allineamento",
    description: "Una conversazione registrata, ma non sposta il punteggio.",
    icon: <ChatIcon className="h-4 w-4" />,
  },
  {
    kind: "discount_review",
    label: "Follow-up e-mail",
    description: "Registra una revisione della proposta. La revisione stessa non sposta il punteggio.",
    icon: <BoltIcon className="h-4 w-4" />,
  },
];

function rankAll(items: PipelineItem[]): RankedItem[] {
  return [...items]
    .sort((a, b) => b.expected_value - a.expected_value)
    .map((item, index) => ({ item, rank: index + 1 }));
}

function windowAround(
  ranked: RankedItem[],
  leadId: string,
  size = 5,
): RankedItem[] {
  const index = ranked.findIndex((entry) => entry.item.lead_id === leadId);
  if (index === -1) return ranked.slice(0, size);
  const start = Math.max(0, Math.min(ranked.length - size, index - 2));
  return ranked.slice(start, start + size);
}

export default function ActPage() {
  const { pipeline, defaultActLeadId, logAction } = usePipeline();
  const { leadId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const incomingKind = (location.state as { kind?: ActionKind } | null)?.kind;
  const initialKind =
    incomingKind && ACTIONS.some((action) => action.kind === incomingKind)
      ? incomingKind
      : "exec_sponsor_meeting";

  const selected = useMemo(
    () =>
      pipeline.items.find(
        (item) => item.lead_id === (leadId || defaultActLeadId),
      ) ?? null,
    [pipeline.items, leadId, defaultActLeadId],
  );

  const ranked = useMemo(() => rankAll(pipeline.items), [pipeline.items]);

  const [kind, setKind] = useState<ActionKind>(initialKind);
  const [note, setNote] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const bannerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!outcome) return;
    setBannerDismissed(false);
    const frame = requestAnimationFrame(() => bannerRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [outcome]);

  useEffect(() => {
    if (!leadId && defaultActLeadId) {
      navigate(`/previsioni/act/${defaultActLeadId}`, { replace: true });
    }
  }, [leadId, defaultActLeadId, navigate]);

  useEffect(() => {
    setOutcome(null);
    setError(null);
    setNote("");
    setPending(false);
  }, [leadId]);

  if (!selected) {
    const invalidId = leadId && !pipeline.items.some((i) => i.lead_id === leadId);

    return (
      <div>
        <PageHeader
          eyebrow="Act"
          title={invalidId ? "Questa iniziativa non è nella coda" : "Scegli un'iniziativa"}
          subtitle={
            invalidId
              ? "La coda contiene solo le iniziative aperte. Selezionane un'altra per continuare il ciclo."
              : "La coda è vuota in questa vista. Seleziona un'iniziativa per registrare un'azione."
          }
        />
        <Card className="max-w-xl p-6">
          <label
            htmlFor="lead-fallback"
            className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted"
          >
            Iniziativa
          </label>
          <select
            id="lead-fallback"
            defaultValue=""
            onChange={(event) => navigate(`/previsioni/act/${event.target.value}`)}
            className="mt-2 w-full rounded-[4px] border border-line bg-surface px-3 py-2.5 text-[13px] text-ink focus:outline-none focus:ring-2 focus:ring-accent/30"
          >
            <option value="" disabled>
              Seleziona dalla coda
            </option>
            {ranked.map(({ item, rank }) => (
              <option key={item.lead_id} value={item.lead_id}>
                #{rank} · {item.company_name} · {formatPercent(item.probability)}
              </option>
            ))}
          </select>
          <Link to="/previsioni" className={buttonSecondary + " mt-5"}>
            <ArrowLeftIcon className="h-4 w-4" />
            Torna alla coda
          </Link>
        </Card>
      </div>
    );
  }

  const currentRank =
    ranked.find((entry) => entry.item.lead_id === selected.lead_id)?.rank ?? null;
  const currentExpected = Math.round(
    selected.probability * selected.amount_arr,
  );

  async function submit() {
    if (!selected || pending) return;
    setPending(true);
    setError(null);

    const beforeRanked = rankAll(pipeline.items);
    const beforeEntry = beforeRanked.find(
      (entry) => entry.item.lead_id === selected.lead_id,
    );

    try {
      const response = await logAction(selected.lead_id, {
        kind,
        ...(note.trim() ? { note: note.trim() } : {}),
      });

      const nextItems = pipeline.items.map((item) =>
        item.lead_id === selected.lead_id
          ? {
              ...item,
              probability: response.probability_after,
              band: bandForProbability(response.probability_after),
              expected_value: Math.round(
                response.probability_after * item.amount_arr,
              ),
            }
          : item,
      );
      const afterRanked = rankAll(nextItems);
      const afterEntry = afterRanked.find(
        (entry) => entry.item.lead_id === selected.lead_id,
      );

      setOutcome({
        leadId: selected.lead_id,
        kind,
        response,
        before: {
          probability: selected.probability,
          expectedValue: beforeEntry?.item.expected_value ?? currentExpected,
          rank: beforeEntry?.rank ?? 0,
        },
        after: {
          probability: response.probability_after,
          expectedValue: afterEntry?.item.expected_value ?? 0,
          rank: afterEntry?.rank ?? 0,
        },
        beforeItems: windowAround(beforeRanked, selected.lead_id),
        afterItems: windowAround(afterRanked, selected.lead_id),
      });
    } catch (cause: unknown) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Impossibile completare la registrazione dell'azione.",
      );
    } finally {
      setPending(false);
    }
  }

  const actionLabel = actionKindLabel(kind);
  const moved = outcome
    ? outcome.after.rank !== outcome.before.rank
    : false;

  return (
    <div>
      <PageHeader
        eyebrow="Act · 18 novembre 2026"
        title="Chiudi il ciclo"
        subtitle="Registra un'azione. Lo stesso modello ricalcola il punteggio dell'iniziativa e la coda si riordina."
        actions={
          <Link to={`/previsioni/leads/${selected.lead_id}`} className={buttonSecondary}>
            <ArrowLeftIcon className="h-4 w-4" />
            Torna al lead
          </Link>
        }
      />

      <LeadTabs leadId={selected.lead_id} active="act" />

      <Card className="mt-7 p-5">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              In lavorazione
            </p>
            <h2 className="mt-1.5 truncate font-display text-[26px] leading-tight text-ink">
              {selected.company_name}
            </h2>
            <p className="mt-1 text-[11.5px] text-muted">
              {regionLabel(selected.region)} · {statusLabel(selected.status)} ·{" "}
              {selected.days_open} giorni aperti
            </p>
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div>
              <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                Probabilità di conversione
              </p>
              <p className="mt-1 font-display text-[26px] leading-none tabular-nums text-ink">
                {formatPercent(selected.probability, 1)}
              </p>
              <div className="mt-1.5">
                <BandPill band={selected.band} compact />
              </div>
            </div>
            <div>
              <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                Valore atteso
              </p>
              <p className="mt-1 font-display text-[26px] leading-none tabular-nums text-ink">
                {formatEURCompact(currentExpected)}
              </p>
              <p className="mt-1.5 text-[10.5px] text-muted">
                {formatEUR(selected.amount_arr)} ARR
              </p>
            </div>
            <div>
              <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                Posizione in coda
              </p>
              <p className="mt-1 font-display text-[26px] leading-none tabular-nums text-ink">
                #{currentRank ?? "—"}
              </p>
              <p className="mt-1.5 text-[10.5px] text-muted">per valore atteso</p>
            </div>
          </div>

          <div className="w-full lg:w-[270px]">
            <label
              htmlFor="lead-picker"
              className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted"
            >
              Iniziativa
            </label>
            <select
              id="lead-picker"
              value={selected.lead_id}
              onChange={(event) => navigate(`/previsioni/act/${event.target.value}`)}
              className="mt-1.5 w-full rounded-[4px] border border-line bg-surface px-3 py-2.5 text-[12px] text-ink focus:outline-none focus:ring-2 focus:ring-accent/30"
            >
              {ranked.map(({ item, rank }) => (
                <option key={item.lead_id} value={item.lead_id}>
                  #{rank} · {item.company_name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {outcome && !bannerDismissed ? (
        <div
          ref={bannerRef}
          role="status"
          aria-live="polite"
          tabIndex={-1}
          data-testid="action-success-banner"
          className="mt-6 flex flex-wrap items-center gap-3 rounded-[4px] border border-[#A9C7FF] bg-[#F2F7FC] px-4 py-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#CBE4FB] text-[#00499D]">
            <CheckIcon className="h-4 w-4" />
          </span>
          <p className="min-w-0 flex-1 text-[12.5px] font-medium text-ink">
            Azione registrata con successo. Il modello ha aggiornato il punteggio.
          </p>
          <span className="text-[12px] font-semibold tabular-nums text-[#00499D]">
            {formatPoints(outcome.response.delta)}
          </span>
          <button
            type="button"
            onClick={() => setBannerDismissed(true)}
            className="rounded-[4px] px-2 py-1 text-[11.5px] font-medium text-muted hover:bg-[#EEF2F5] hover:text-ink"
          >
            Chiudi
          </button>
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
        <div className="space-y-5">
          {outcome ? (
            <Card className="p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#CBE4FB] text-risk-low">
                    <CheckIcon className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-[13px] font-semibold text-ink">
                      Azione registrata con successo
                    </p>
                    <p className="text-[10.5px] text-muted">
                      {actionKindLabel(outcome.kind)} ·{" "}
                      {formatDateTime(outcome.response.action.created_at)}
                    </p>
                  </div>
                </div>
                <span
                  className={cn(
                    "inline-flex items-center rounded-full px-3 py-1.5 text-[12px] font-semibold tabular-nums",
                    outcome.response.delta > 0.0005
                      ? "bg-[#CBE4FB] text-[#00499D]"
                      : outcome.response.delta < -0.0005
                        ? "bg-[#FDECEA] text-[#912018]"
                        : "bg-ink/[0.05] text-muted",
                  )}
                >
                  {formatPoints(outcome.response.delta)}
                </span>
              </div>

              <div className="mt-6 grid gap-5 sm:grid-cols-3">
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                    Probabilità
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    {formatPercent(outcome.after.probability, 1)}
                  </p>
                  <p className="mt-1 text-[10.5px] text-muted">
                    da {formatPercent(outcome.before.probability, 1)}
                  </p>
                </div>
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                    Valore atteso
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    {formatEURCompact(outcome.after.expectedValue)}
                  </p>
                  <p className="mt-1 text-[10.5px] text-muted">
                    {formatSignedEUR(
                      outcome.after.expectedValue - outcome.before.expectedValue,
                    )}{" "}
                    da {formatEURCompact(outcome.before.expectedValue)}
                  </p>
                </div>
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                    Posizione in coda
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    #{outcome.after.rank}
                  </p>
                  <p className="mt-1 text-[10.5px] text-muted">
                    {moved ? `da #${outcome.before.rank}` : "posizione invariata"}
                  </p>
                </div>
              </div>

              <div className="mt-6">
                <ProbabilityTransition
                  from={outcome.before.probability}
                  to={outcome.after.probability}
                  fromLabel="Prima"
                  toLabel="Dopo"
                />
              </div>

              {outcome.response.delta === 0 ? (
                <p className="mt-5 border-t border-line pt-4 text-[11.5px] leading-relaxed text-muted">
                  {actionLabel} è un'attività, non una leva. Il punteggio e la coda rimangono invariati: questa è la risposta onesta del modello.
                </p>
              ) : (
                <p className="mt-5 border-t border-line pt-4 text-[11.5px] leading-relaxed text-muted">
                  Il ricalcolo è la risposta del modello, non una previsione digitata a mano.
                  {moved
                    ? " La coda si è già riordinata di conseguenza."
                    : " Il punteggio è cambiato, ma la posizione nella coda è rimasta invariata."}
                </p>
              )}

              {outcome.response.action.note ? (
                <p className="mt-3 text-[11px] italic text-muted">
                  "{outcome.response.action.note}"
                </p>
              ) : null}

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Link to={`/previsioni/leads/${outcome.leadId}`} className={buttonPrimary}>
                  Apri il lead aggiornato
                  <ArrowUpRightIcon className="h-4 w-4" />
                </Link>
                <button
                  type="button"
                  className={buttonSecondary}
                  onClick={() => {
                    setOutcome(null);
                    setNote("");
                  }}
                >
                  Registra un'altra azione
                </button>
              </div>
            </Card>
          ) : (
            <Card className="p-6">
              <SectionHeading
                label="Tipo di azione"
                title="Cosa hai fatto?"
                hint="Questa è l'unica scrittura nel demo: una riga di azione, poi un ricalcolo dello stesso modello."
              />

              <div className="grid gap-2 sm:grid-cols-2">
                {ACTIONS.map((option) => {
                  const selectedOption = kind === option.kind;
                  return (
                    <label
                      key={option.kind}
                      className={cn(
                        "cursor-pointer rounded-[4px] border p-3.5 transition",
                        selectedOption
                          ? "border-accent/60 bg-accent-soft/30"
                          : "border-line bg-surface hover:border-ink/20",
                      )}
                    >
                      <input
                        type="radio"
                        name="action-kind"
                        value={option.kind}
                        checked={selectedOption}
                        onChange={() => setKind(option.kind)}
                        className="sr-only"
                      />
                      <span className="flex items-start gap-2.5">
                        <span
                          className={cn(
                            "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[4px]",
                            selectedOption
                              ? "bg-accent text-white"
                              : "bg-ink/[0.05] text-muted",
                          )}
                        >
                          {option.icon}
                        </span>
                        <span className="min-w-0">
                          <span className="block text-[12px] font-semibold text-ink">
                            {option.label}
                          </span>
                          <span className="mt-0.5 block text-[10.5px] leading-relaxed text-muted">
                            {option.description}
                          </span>
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>

              <div className="mt-5">
                <div className="flex items-baseline justify-between">
                  <label
                    htmlFor="action-note"
                    className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted"
                  >
                    Note operative sull'azione
                  </label>
                  <span className="text-[10px] tabular-nums text-muted">
                    {note.length}/500
                  </span>
                </div>
                <textarea
                  id="action-note"
                  value={note}
                  maxLength={500}
                  rows={3}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Cosa è stato concordato? Chi era presente?"
                  className="mt-1.5 w-full resize-none rounded-[4px] border border-line bg-surface px-3.5 py-3 text-[12.5px] leading-relaxed text-ink placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent/30"
                />
              </div>

              {error ? (
                <p className="mt-4 border-l-2 border-risk-high pl-3 text-[11.5px] leading-relaxed text-risk-high">
                  {error}
                </p>
              ) : null}

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={submit}
                  disabled={pending}
                  className={buttonPrimary}
                >
                  {pending ? "Registrazione azione in corso..." : "Conferma e registra azione"}
                </button>
                <p className="text-[10.5px] text-muted">
                  Una scrittura, poi lo stesso modello risponde.
                </p>
              </div>
            </Card>
          )}

          {outcome ? (
            <Card className="p-5">
              <SectionHeading
                label="La coda"
                title="Impatto previsto"
                hint={`Posizione ${outcome.before.rank} → ${outcome.after.rank} per valore atteso. Le righe visualizzate sono la stessa coda, riordinata.`}
              />
              <div className="grid gap-5 sm:grid-cols-2">
                <QueueSnapshot
                  title="Prima del ricalcolo"
                  items={outcome.beforeItems}
                  highlightId={outcome.leadId}
                />
                <QueueSnapshot
                  title="Dopo il ricalcolo"
                  items={outcome.afterItems}
                  highlightId={outcome.leadId}
                />
              </div>
            </Card>
          ) : (
            <InlineNotice>
              Registrare un incontro con lo sponsor esecutivo aggiunge un incontro e il miglioramento della relazione. Una telefonata viene registrata ma non modifica gli input del modello, quindi non sposta il punteggio: il demo non afferma il contrario.
            </InlineNotice>
          )}
        </div>

        <aside className="space-y-4">
          <Card className="p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              Come funziona il ciclo
            </p>
            <ol className="mt-3 space-y-3 text-[11.5px] leading-relaxed text-muted">
              <li className="flex gap-2.5">
                <span className="font-display text-[12px] text-accent">01</span>
                L'azione viene registrata su questa iniziativa.
              </li>
              <li className="flex gap-2.5">
                <span className="font-display text-[12px] text-accent">02</span>
                Lo stesso modello ricalcola il punteggio con la variazione delle feature dell'azione.
              </li>
              <li className="flex gap-2.5">
                <span className="font-display text-[12px] text-accent">03</span>
                Il valore atteso si aggiorna e la coda si riordina.
              </li>
            </ol>
            <p className="mt-4 border-t border-line pt-3 text-[10.5px] leading-relaxed text-muted">
              Non esiste un "punteggio attività" separato. Il numero visualizzato è la probabilità di conversione, aggiornata dal modello.
            </p>
          </Card>

          <Card className="p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              Questa iniziativa
            </p>
            <dl className="mt-3 space-y-2.5 text-[11.5px]">
              <div className="flex justify-between gap-3">
                <dt className="text-muted">ARR proposto</dt>
                <dd className="font-medium tabular-nums text-ink">
                  {formatEUR(selected.amount_arr)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Valore atteso</dt>
                <dd className="font-medium tabular-nums text-ink">
                  {formatEUR(currentExpected)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Fonte</dt>
                <dd className="font-medium text-ink">
                  {sourceLabel(selected.source)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Giorni aperti</dt>
                <dd className="font-medium tabular-nums text-ink">
                  {selected.days_open}
                </dd>
              </div>
            </dl>
          </Card>

          <InlineNotice>
            La risposta dell'azione restituisce probabilità e delta; il valore atteso e la nuova posizione sono calcolati dall'ARR proposto già presente nella coda. Nessun campo aggiuntivo viene inventato.
          </InlineNotice>
        </aside>
      </div>
    </div>
  );
}

function QueueSnapshot({
  title,
  items,
  highlightId,
}: {
  title: string;
  items: RankedItem[];
  highlightId: string;
}) {
  return (
    <div>
      <p className="mb-2 text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
        {title}
      </p>
      <ol className="space-y-1.5">
        {items.map(({ item, rank }) => {
          const acted = item.lead_id === highlightId;
          return (
            <li
              key={item.lead_id}
              className={cn(
                "flex items-center gap-3 rounded-[4px] border px-3 py-2.5",
                acted
                  ? "border-accent/50 bg-accent-soft/40"
                  : "border-line bg-[#F7FAFD]",
              )}
            >
              <span
                className={cn(
                  "w-6 font-display text-[13px] tabular-nums",
                  acted ? "text-accent" : "text-muted",
                )}
              >
                #{rank}
              </span>
              <span
                className={cn(
                  "min-w-0 flex-1 truncate text-[11.5px]",
                  acted ? "font-semibold text-ink" : "text-ink/80",
                )}
              >
                {item.company_name}
              </span>
              <span className="text-[10.5px] tabular-nums text-muted">
                {formatPercent(item.probability)}
              </span>
              <span className="w-14 text-right text-[10.5px] tabular-nums text-muted">
                {formatEURCompact(item.expected_value)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
