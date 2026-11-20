import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import LeadTabs from "../components/LeadTabs";
import {
  ArrowLeftIcon,
  ArrowUpRightIcon,
  BoltIcon,
  CalendarIcon,
  CheckIcon,
  UsersIcon,
} from "../components/icons";
import {
  BandPill,
  buttonPrimary,
  Card,
  cn,
  InlineNotice,
  PageHeader,
  ProbabilityMeter,
} from "../components/ui";
import {
  fixtureBestLever,
  initialLeadDetail,
  isLiveApi,
} from "../lib/api";
import { bandForProbability } from "../lib/bands";
import {
  formatEUR,
  formatPercent,
  formatPoints,
  formatSignedEUR,
} from "../lib/format";
import { LEVERAGE_BOOK } from "../lib/model";
import { usePipeline } from "../state/PipelineProvider";
import type {
  CounterfactualResponse,
  LeadDetail,
} from "../lib/types";

type Lever = "exec" | "discovery" | "discount";

const LEVERS: Array<{
  key: Lever;
  title: string;
  description: string;
  icon: ReactNode;
}> = [
  {
    key: "exec",
    title: "Executive sponsor meeting",
    description:
      "One meeting with an executive sponsor, plus the relationship-health lift the model associates with it.",
    icon: <UsersIcon className="h-4 w-4" />,
  },
  {
    key: "discovery",
    title: "Discovery meeting",
    description:
      "One structured discovery session with the buyer. A meeting, re-scored by the same model.",
    icon: <CalendarIcon className="h-4 w-4" />,
  },
  {
    key: "discount",
    title: "Change the discount",
    description:
      "What-if only. The model treats a larger discount as friction, and the action contract cannot record a proposed discount, so this is never ranked as leverage.",
    icon: <BoltIcon className="h-4 w-4" />,
  },
];

export default function LeverPage() {
  const { leadId = "" } = useParams();
  const { loadLead, counterfactual, pipeline } = usePipeline();
  const [detail, setDetail] = useState<LeadDetail | null>(() =>
    initialLeadDetail(leadId),
  );
  const initialBest = fixtureBestLever(leadId);
  const [lever, setLever] = useState<Lever>(initialBest?.lever ?? "exec");
  const [discount, setDiscount] = useState(initialBest?.discount_pct ?? 20);
  const [result, setResult] = useState<CounterfactualResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setDetail(initialLeadDetail(leadId));
    loadLead(leadId)
      .then((next) => {
        if (!cancelled) setDetail(next);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof Error
              ? cause.message
              : "That initiative could not be opened.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [leadId, loadLead]);

  const lead = detail?.lead;
  const pipelineItem = pipeline.items.find((item) => item.lead_id === lead?.id);
  const maxLeverage = pipelineItem?.max_leverage ?? null;
  const discountUpside = pipelineItem?.discount_upside ?? null;
  const topByEv = useMemo(
    () =>
      [...pipeline.items].sort(
        (a, b) => b.expected_value - a.expected_value,
      )[0] ?? null,
    [pipeline.items],
  );

  useEffect(() => {
    const best = fixtureBestLever(leadId);
    if (best) {
      setLever(best.lever);
      setDiscount(best.discount_pct ?? 20);
    }
  }, [leadId]);

  // Live mode has no precomputed best-lever map. Compare the two committable
  // levers and open on the stronger one; discount is deliberately excluded.
  useEffect(() => {
    if (!isLiveApi || !lead) return;
    let cancelled = false;
    Promise.all([
      counterfactual(lead.id, { exec_sponsor_meeting: true }),
      counterfactual(lead.id, { discovery_meeting: true }),
    ])
      .then(([exec, discovery]) => {
        if (!cancelled) {
          setLever(discovery.delta > exec.delta ? "discovery" : "exec");
        }
      })
      .catch(() => {
        // Keep the current lever; the manual controls still work.
      });
    return () => {
      cancelled = true;
    };
  }, [lead, counterfactual]);

  useEffect(() => {
    if (!lead) return;
    let cancelled = false;
    setPending(true);
    setError(null);

    const request =
      lever === "exec"
        ? { exec_sponsor_meeting: true }
        : lever === "discovery"
          ? { discovery_meeting: true }
          : { discount_pct: discount };

    counterfactual(lead.id, request)
      .then((next) => {
        if (!cancelled) setResult(next);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof Error
              ? cause.message
              : "The model could not re-score that lever.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setPending(false);
      });

    return () => {
      cancelled = true;
    };
  }, [lead, lever, discount, counterfactual]);

  const current = result?.current_probability ?? detail?.score.probability ?? 0;
  const hypothetical =
    result?.hypothetical_probability ?? detail?.score.probability ?? 0;
  const delta = result?.delta ?? 0;
  const nextBand = bandForProbability(hypothetical);
  const currentBand = bandForProbability(current);

  const amount = lead?.amount_arr ?? 0;
  const expectedNow = Math.round(current * amount);
  const expectedAfter = Math.round(hypothetical * amount);

  const leverLabel = useMemo(() => {
    if (lever === "exec") return "an executive sponsor meeting";
    if (lever === "discovery") return "a discovery meeting";
    return `a ${discount}% discount`;
  }, [lever, discount]);

  // The action contract can record a meeting, but it has no field for a
  // proposed discount value. Meetings can be committed; the discount stays a
  // preview rather than claiming a re-score the write path cannot express.
  const commitKind =
    lever === "exec"
      ? ("exec_sponsor_meeting" as const)
      : lever === "discovery"
        ? ("discovery_meeting" as const)
        : null;

  if (error && !detail) {
    return (
      <div>
        <Link
          to="/previsioni"
          className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
        >
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Back to the queue
        </Link>
        <PageHeader eyebrow="The lever" title="This initiative cannot re-score" subtitle={error} />
      </div>
    );
  }

  if (!detail || !lead) {
    return (
      <div>
        <Link
          to="/previsioni"
          className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
        >
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Back to the queue
        </Link>
        <PageHeader eyebrow="The lever" title="Opening the initiative" />
      </div>
    );
  }

  const deltaPositive = delta > 0.0005;
  const deltaNegative = delta < -0.0005;

  return (
    <div>
      <Link
        to={`/previsioni/leads/${lead.id}`}
        className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
      >
        <ArrowLeftIcon className="h-3.5 w-3.5" />
        Back to {detail.company.name}
      </Link>

      <PageHeader
        eyebrow={`The lever · ${detail.company.name}`}
        title="What would move this initiative?"
        subtitle="Re-scored by the same model, with no new data invented. This is the call you can have before spending the meeting."
      />

      <LeadTabs leadId={lead.id} active="lever" />

      <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.8fr)]">
        <div className="space-y-5">
          <Card className="p-6">
            <div className="grid items-center gap-5 sm:grid-cols-[1fr_auto_1fr]">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                  Now
                </p>
                <p className="mt-1 font-display text-[54px] leading-none tabular-nums text-ink">
                  {formatPercent(current, 1)}
                </p>
                <div className="mt-3">
                  <BandPill band={currentBand} />
                </div>
                <p className="mt-3 text-[11.5px] text-muted">
                  {formatEUR(expectedNow)} expected value
                </p>
              </div>

              <div className="flex flex-row items-center justify-center gap-2 sm:flex-col">
                <span
                  className={cn(
                    "inline-flex items-center rounded-full px-3 py-1.5 text-[12px] font-semibold tabular-nums",
                    deltaPositive
                      ? "bg-[#E7F4EC] text-[#05603A]"
                      : deltaNegative
                        ? "bg-[#FDECEA] text-[#912018]"
                        : "bg-ink/[0.05] text-muted",
                  )}
                >
                  {formatPoints(delta)}
                </span>
                <span className="text-[10px] text-muted">
                  {pending
                    ? "Re-scoring…"
                    : deltaPositive
                      ? "better odds"
                      : deltaNegative
                        ? "worse odds"
                        : "no change"}
                </span>
              </div>

              <div className="sm:text-right">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                  With {leverLabel}
                </p>
                <p
                  className={cn(
                    "mt-1 font-display text-[54px] leading-none tabular-nums",
                    deltaNegative ? "text-risk-high" : "text-ink",
                  )}
                >
                  {formatPercent(hypothetical, 1)}
                </p>
                <div className="mt-3 sm:flex sm:justify-end">
                  <BandPill band={nextBand} />
                </div>
                <p className="mt-3 text-[11.5px] text-muted">
                  {formatEUR(expectedAfter)} expected value
                </p>
              </div>
            </div>

            <div className="mt-7 space-y-3 border-t border-line pt-5">
              <div>
                <div className="mb-1.5 flex items-center justify-between text-[10px] text-muted">
                  <span>Now</span>
                  <span className="tabular-nums">
                    {formatPercent(current, 1)}
                  </span>
                </div>
                <ProbabilityMeter probability={current} band={currentBand} />
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between text-[10px] text-muted">
                  <span>With {leverLabel}</span>
                  <span className="tabular-nums">
                    {formatPercent(hypothetical, 1)}
                  </span>
                </div>
                <ProbabilityMeter probability={hypothetical} band={nextBand} />
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-baseline justify-between gap-3 rounded-lg bg-[#FAF8F3] px-4 py-3">
              <p className="text-[11.5px] leading-relaxed text-muted">
                {result?.explanation ??
                  "Asking the model for the re-score under this lever."}
              </p>
              <p className="text-[11.5px] font-semibold tabular-nums text-ink">
                {formatSignedEUR(expectedAfter - expectedNow)} expected value
              </p>
            </div>

            {error ? (
              <p className="mt-4 border-l-2 border-risk-high pl-3 text-[11.5px] text-risk-high">
                {error}
              </p>
            ) : null}
          </Card>

          <div className="flex flex-wrap items-center justify-between gap-3">
            {commitKind ? (
              <Link
                to={`/previsioni/act/${lead.id}`}
                state={{ kind: commitKind }}
                className={buttonPrimary}
              >
                Log this action
              </Link>
            ) : (
              <span className="inline-flex items-center rounded-lg border border-line bg-surface px-4 py-2.5 text-[12px] font-medium text-muted">
                Preview only
              </span>
            )}
            <p className="max-w-md text-[10.5px] leading-relaxed text-muted">
              {commitKind
                ? "The lever is a preview. Logging the action commits the re-score."
                : "The action contract records a discount review, but not the proposed discount value, so this preview cannot be committed exactly."}
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-xl border border-accent/30 bg-accent-soft/45 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-accent-deep">
              Where effort pays off
            </p>
            <p className="mt-1 font-display text-[32px] leading-none tabular-nums text-ink">
              {maxLeverage !== null ? formatPoints(maxLeverage) : "—"}
            </p>
            <p className="mt-2 text-[10.5px] leading-relaxed text-muted">
              Largest <span className="font-semibold text-ink">committable</span>{" "}
              lift for this initiative. The book median is{" "}
              {formatPoints(LEVERAGE_BOOK.median, 2)}; the 90th percentile is{" "}
              {formatPoints(LEVERAGE_BOOK.p90, 2)}. {LEVERAGE_BOOK.noPositive.toLocaleString("en-GB")}{" "}
              of {LEVERAGE_BOOK.leads.toLocaleString("en-GB")} leads have no
              positive committable move — this one is a tail case, not a
              typical one.
            </p>
            {topByEv ? (
              <p className="mt-2 border-t border-accent/20 pt-2 text-[10px] leading-relaxed text-muted">
                Biggest deal on the page:{" "}
                <span className="font-medium text-ink">{topByEv.company_name}</span>{" "}
                — {formatPoints(topByEv.max_leverage ?? 0)} committable,{" "}
                {formatPoints(topByEv.discount_upside ?? 0)} discount what-if.
              </p>
            ) : null}
            <Link
              to="/previsioni?sort=leverage"
              className="mt-2.5 inline-flex items-center gap-1.5 text-[10.5px] font-semibold text-accent transition hover:text-accent-deep"
            >
              See where effort pays off
              <ArrowUpRightIcon className="h-3 w-3" />
            </Link>
          </div>

          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
            Choose a lever
          </p>

          {LEVERS.map((option) => {
            const selected = lever === option.key;
            return (
              <div
                key={option.key}
                className={cn(
                  "rounded-xl border p-4 transition",
                  selected
                    ? "border-accent/60 bg-accent-soft/35 shadow-card"
                    : "border-line bg-surface hover:border-ink/20",
                )}
              >
                <label className="flex cursor-pointer items-start gap-3">
                  <input
                    type="radio"
                    name="lever"
                    value={option.key}
                    checked={selected}
                    onChange={() => setLever(option.key)}
                    className="sr-only"
                  />
                  <span
                    className={cn(
                      "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                      selected
                        ? "bg-accent text-white"
                        : "bg-ink/[0.05] text-muted",
                    )}
                  >
                    {option.icon}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[12.5px] font-semibold text-ink">
                      {option.title}
                      {option.key === "discount" ? (
                        <span className="ml-2 rounded-full bg-ink/[0.07] px-1.5 py-0.5 text-[8.5px] font-semibold uppercase tracking-[0.1em] text-muted">
                          What-if
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-1 block text-[10.5px] leading-relaxed text-muted">
                      {option.description}
                    </span>
                  </span>
                  <span
                    className={cn(
                      "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                      selected
                        ? "border-accent bg-accent text-white"
                        : "border-line bg-surface",
                    )}
                  >
                    {selected ? <CheckIcon className="h-2.5 w-2.5" /> : null}
                  </span>
                </label>

                {selected && option.key === "discount" ? (
                  <div className="mt-4 border-t border-line pt-4">
                    <div className="flex items-baseline justify-between">
                      <label
                        htmlFor="discount"
                        className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted"
                      >
                        Proposed discount
                      </label>
                      <span className="font-display text-[20px] tabular-nums text-ink">
                        {discount}%
                      </span>
                    </div>
                    <input
                      id="discount"
                      type="range"
                      min={0}
                      max={30}
                      step={5}
                      value={discount}
                      onChange={(event) =>
                        setDiscount(Number(event.target.value))
                      }
                      className="mt-3 w-full accent-[#0F6B5C]"
                    />
                    <div className="mt-1 flex justify-between text-[9px] text-muted">
                      <span>0%</span>
                      <span>current {(lead.discount_pct ?? 0).toFixed(1)}%</span>
                      <span>30%</span>
                    </div>
                    <p className="mt-2 text-[10px] leading-relaxed text-muted">
                      A discount changes the score through the same model. It is
                      not a persuasion dial: a larger discount lowers it. This
                      lever is never ranked as leverage and cannot be committed.
                    </p>
                    {discountUpside !== null ? (
                      <p className="mt-2 rounded-md bg-ink/[0.04] px-2 py-1.5 text-[10px] leading-relaxed text-muted">
                        Modeled discount upside:{" "}
                        <span className="font-semibold text-ink">
                          {formatPoints(discountUpside)}
                        </span>{" "}
                        — a what-if, not an action.
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}

          <p className="px-1 text-[10px] leading-relaxed text-muted">
            Discount is a what-if. It is never part of{" "}
            <code>max_leverage</code>, never the queue's leverage sort, and
            cannot be committed as an action. The queue ranks only levers a rep
            can actually book.
          </p>

          <InlineNotice className="mt-1">
            <strong className="font-semibold text-ink">
              No stage-advance lever.
            </strong>{" "}
            The model is trained on leads labelled at qualification, so a
            proposal-stage jump is unlearnable. Showing one would put a fabricated
            number on screen.
          </InlineNotice>
        </div>
      </div>

      <div className="mt-8 grid gap-4 border-t border-line pt-5 text-[10.5px] leading-relaxed text-muted md:grid-cols-3">
        <p>
          <span className="font-semibold text-ink">Forward-looking only.</span>{" "}
          Levers change what can still happen; nothing rewrites a response that
          already happened.
        </p>
        <p>
          <span className="font-semibold text-ink">Same model.</span> Current and
          hypothetical scores come from one model, so the delta is a
          like-for-like comparison.
        </p>
        <p>
          <span className="font-semibold text-ink">Not a promise.</span> A{" "}
          {formatPercent(current, 1)} score means about {Math.round(current * 10)}{" "}
          in 10 comparable initiatives win — not this one for certain.
        </p>
      </div>
    </div>
  );
}
