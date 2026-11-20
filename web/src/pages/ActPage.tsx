import { useEffect, useMemo, useState, type ReactNode } from "react";
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
    label: "Executive sponsor meeting",
    description: "Adds the meeting and the sponsor lift to the score.",
    icon: <UsersIcon className="h-4 w-4" />,
  },
  {
    kind: "discovery_meeting",
    label: "Discovery meeting",
    description: "Adds one structured discovery session.",
    icon: <CalendarIcon className="h-4 w-4" />,
  },
  {
    kind: "call",
    label: "Call",
    description: "A conversation. Logged, but it does not move the score.",
    icon: <ChatIcon className="h-4 w-4" />,
  },
  {
    kind: "discount_review",
    label: "Discount review",
    description: "Logs a pricing review. The review itself does not move the score.",
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
          title={invalidId ? "That initiative is not in the queue" : "Choose an initiative"}
          subtitle={
            invalidId
              ? "The queue only carries open initiatives. Pick another one and the loop still works."
              : "The queue is empty in this view. Pick an initiative to log an action."
          }
        />
        <Card className="max-w-xl p-6">
          <label
            htmlFor="lead-fallback"
            className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted"
          >
            Initiative
          </label>
          <select
            id="lead-fallback"
            defaultValue=""
            onChange={(event) => navigate(`/previsioni/act/${event.target.value}`)}
            className="mt-2 w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-[13px] text-ink focus:outline-none focus:ring-2 focus:ring-accent/30"
          >
            <option value="" disabled>
              Pick from the queue
            </option>
            {ranked.map(({ item, rank }) => (
              <option key={item.lead_id} value={item.lead_id}>
                #{rank} · {item.company_name} · {formatPercent(item.probability)}
              </option>
            ))}
          </select>
          <Link to="/previsioni" className={buttonSecondary + " mt-5"}>
            <ArrowLeftIcon className="h-4 w-4" />
            Back to the queue
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
          : "The action could not be logged.",
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
        eyebrow="Act · 18 November 2026"
        title="Close the loop"
        subtitle="Log what you did. The same model re-scores the initiative, and the queue re-ranks in front of you."
        actions={
          <Link to={`/previsioni/leads/${selected.lead_id}`} className={buttonSecondary}>
            <ArrowLeftIcon className="h-4 w-4" />
            Back to the lead
          </Link>
        }
      />

      <LeadTabs leadId={selected.lead_id} active="act" />

      <Card className="mt-7 p-5">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              On deck
            </p>
            <h2 className="mt-1.5 truncate font-display text-[26px] leading-tight text-ink">
              {selected.company_name}
            </h2>
            <p className="mt-1 text-[11.5px] text-muted">
              {regionLabel(selected.region)} · {statusLabel(selected.status)} ·{" "}
              {selected.days_open} days open
            </p>
          </div>

          <div className="grid grid-cols-3 gap-6">
            <div>
              <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                Win probability
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
                Expected value
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
                Queue rank
              </p>
              <p className="mt-1 font-display text-[26px] leading-none tabular-nums text-ink">
                #{currentRank ?? "—"}
              </p>
              <p className="mt-1.5 text-[10.5px] text-muted">by expected value</p>
            </div>
          </div>

          <div className="w-full lg:w-[270px]">
            <label
              htmlFor="lead-picker"
              className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted"
            >
              Initiative
            </label>
            <select
              id="lead-picker"
              value={selected.lead_id}
              onChange={(event) => navigate(`/previsioni/act/${event.target.value}`)}
              className="mt-1.5 w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-[12px] text-ink focus:outline-none focus:ring-2 focus:ring-accent/30"
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

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
        <div className="space-y-5">
          {outcome ? (
            <Card className="p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#E7F4EC] text-risk-low">
                    <CheckIcon className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-[13px] font-semibold text-ink">
                      Action logged
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
                      ? "bg-[#E7F4EC] text-[#05603A]"
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
                    Probability
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    {formatPercent(outcome.after.probability, 1)}
                  </p>
                  <p className="mt-1 text-[10.5px] text-muted">
                    from {formatPercent(outcome.before.probability, 1)}
                  </p>
                </div>
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                    Expected value
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    {formatEURCompact(outcome.after.expectedValue)}
                  </p>
                  <p className="mt-1 text-[10.5px] text-muted">
                    {formatSignedEUR(
                      outcome.after.expectedValue - outcome.before.expectedValue,
                    )}{" "}
                    from {formatEURCompact(outcome.before.expectedValue)}
                  </p>
                </div>
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                    Queue rank
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    #{outcome.after.rank}
                  </p>
                  <p className="mt-1 text-[10.5px] text-muted">
                    {moved ? `from #${outcome.before.rank}` : "holding position"}
                  </p>
                </div>
              </div>

              {outcome.response.delta === 0 ? (
                <p className="mt-5 border-t border-line pt-4 text-[11.5px] leading-relaxed text-muted">
                  A {actionLabel.toLowerCase()} is activity, not a lever. The
                  score and the queue stay where they were — which is the honest
                  answer from the model.
                </p>
              ) : (
                <p className="mt-5 border-t border-line pt-4 text-[11.5px] leading-relaxed text-muted">
                  The re-score is the model's answer, not a forecast someone typed.
                  {moved
                    ? " The queue has already re-ordered around it."
                    : " The score changed, but the order around it held."}
                </p>
              )}

              {outcome.response.action.note ? (
                <p className="mt-3 text-[11px] italic text-muted">
                  “{outcome.response.action.note}”
                </p>
              ) : null}

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Link to={`/previsioni/leads/${outcome.leadId}`} className={buttonPrimary}>
                  Open the updated lead
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
                  Log another action
                </button>
              </div>
            </Card>
          ) : (
            <Card className="p-6">
              <SectionHeading
                label="The action"
                title="What did you do?"
                hint="This is the only write in the demo: one action row, then a re-score by the same model."
              />

              <div className="grid gap-2 sm:grid-cols-2">
                {ACTIONS.map((option) => {
                  const selectedOption = kind === option.kind;
                  return (
                    <label
                      key={option.kind}
                      className={cn(
                        "cursor-pointer rounded-xl border p-3.5 transition",
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
                            "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
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
                    Note
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
                  placeholder="What was agreed? Who was in the room?"
                  className="mt-1.5 w-full resize-none rounded-lg border border-line bg-surface px-3.5 py-3 text-[12.5px] leading-relaxed text-ink placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent/30"
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
                  {pending ? "Logging action…" : "Log action & re-score"}
                </button>
                <p className="text-[10.5px] text-muted">
                  One write, then the same model answers.
                </p>
              </div>
            </Card>
          )}

          {outcome ? (
            <Card className="p-5">
              <SectionHeading
                label="The queue"
                title="The lead moves"
                hint={`Rank ${outcome.before.rank} → ${outcome.after.rank} by expected value. The rows on screen are the same queue, re-ranked.`}
              />
              <div className="grid gap-5 sm:grid-cols-2">
                <QueueSnapshot
                  title="Before re-score"
                  items={outcome.beforeItems}
                  highlightId={outcome.leadId}
                />
                <QueueSnapshot
                  title="After re-score"
                  items={outcome.afterItems}
                  highlightId={outcome.leadId}
                />
              </div>
            </Card>
          ) : (
            <InlineNotice>
              Logging an executive sponsor meeting adds one meeting and the
              relationship-health lift. A call is logged but does not change the
              model's inputs, so it does not move the score — the demo does not
              pretend otherwise.
            </InlineNotice>
          )}
        </div>

        <aside className="space-y-4">
          <Card className="p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              How the loop works
            </p>
            <ol className="mt-3 space-y-3 text-[11.5px] leading-relaxed text-muted">
              <li className="flex gap-2.5">
                <span className="font-display text-[12px] text-accent">01</span>
                The action is recorded against this initiative.
              </li>
              <li className="flex gap-2.5">
                <span className="font-display text-[12px] text-accent">02</span>
                The same model re-scores with the action's feature change.
              </li>
              <li className="flex gap-2.5">
                <span className="font-display text-[12px] text-accent">03</span>
                Expected value updates, and the queue re-ranks.
              </li>
            </ol>
            <p className="mt-4 border-t border-line pt-3 text-[10.5px] leading-relaxed text-muted">
              There is no separate “activity score”. The number on screen is the
              win probability, updated by the model.
            </p>
          </Card>

          <Card className="p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              This initiative
            </p>
            <dl className="mt-3 space-y-2.5 text-[11.5px]">
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Proposed ARR</dt>
                <dd className="font-medium tabular-nums text-ink">
                  {formatEUR(selected.amount_arr)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Expected value</dt>
                <dd className="font-medium tabular-nums text-ink">
                  {formatEUR(currentExpected)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Source</dt>
                <dd className="font-medium text-ink">
                  {sourceLabel(selected.source)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Days open</dt>
                <dd className="font-medium tabular-nums text-ink">
                  {selected.days_open}
                </dd>
              </div>
            </dl>
          </Card>

          <InlineNotice>
            The action response returns probability and delta; the expected value
            and the new rank are computed from the proposed ARR already in the
            queue. No extra fields are invented.
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
                "flex items-center gap-3 rounded-lg border px-3 py-2.5",
                acted
                  ? "border-accent/50 bg-accent-soft/40"
                  : "border-line bg-[#FAF8F3]",
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


