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
  counterfactualExplanation,
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
    title: "Incontro con sponsor esecutivo",
    description:
      "Un incontro strutturato con il decisore aziendale e miglioramento della salute della relazione.",
    icon: <UsersIcon className="h-4 w-4" />,
  },
  {
    key: "discovery",
    title: "Sessione di discovery approfondita",
    description:
      "Sessione di analisi requisiti con il buyer per validare i requisiti tecnici ed economici.",
    icon: <CalendarIcon className="h-4 w-4" />,
  },
  {
    key: "discount",
    title: "Variazione sconto",
    description:
      "Solo simulazione. Il modello tratta lo sconto elevato come attrito; non costituisce una raccomandazione operativa e non può essere impegnata come azione.",
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
              : "Impossibile aprire questa iniziativa.",
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
              : "Errore durante il calcolo delle variazioni di probabilità.",
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
    if (lever === "exec") return "un incontro con sponsor esecutivo";
    if (lever === "discovery") return "una sessione di discovery";
    return `uno sconto del ${discount}%`;
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
          Torna alla coda
        </Link>
        <PageHeader eyebrow="Cosa muove la probabilità" title="Impossibile ricalcolare questa iniziativa" subtitle={error} />
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
          Torna alla coda
        </Link>
        <PageHeader eyebrow="Cosa muove la probabilità" title="Apertura iniziativa in corso" />
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
        Torna a {detail.company.name}
      </Link>

      <PageHeader
        eyebrow={`Cosa muove la probabilità · ${detail.company.name}`}
        title="Qual è l'azione che vale di più?"
        subtitle="Ricalcolo effettuato dallo stesso modello, senza introdurre nuovi dati. Questo è il confronto da fare prima di investire il tempo della riunione."
      />

      <LeadTabs leadId={lead.id} active="lever" />

      <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.8fr)]">
        <div className="space-y-5">
          <Card className="p-6">
            <div className="grid items-center gap-5 sm:grid-cols-[1fr_auto_1fr]">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                  Probabilità attuale
                </p>
                <p className="mt-1 font-display text-[54px] leading-none tabular-nums text-ink">
                  {formatPercent(current, 1)}
                </p>
                <div className="mt-3">
                  <BandPill band={currentBand} />
                </div>
                <p className="mt-3 text-[11.5px] text-muted">
                  {formatEUR(expectedNow)} valore atteso
                </p>
              </div>

              <div className="flex flex-row items-center justify-center gap-2 sm:flex-col">
                <span
                  className={cn(
                    "inline-flex items-center rounded-full px-3 py-1.5 text-[12px] font-semibold tabular-nums",
                    deltaPositive
                      ? "bg-[#CBE4FB] text-[#00499D]"
                      : deltaNegative
                        ? "bg-[#FDECEA] text-[#912018]"
                        : "bg-ink/[0.05] text-muted",
                  )}
                >
                  {formatPoints(delta)}
                </span>
                <span className="text-[10px] text-muted">
                  {pending
                    ? "Simulazione in corso..."
                    : deltaPositive
                      ? "probabilità migliore"
                      : deltaNegative
                        ? "probabilità peggiore"
                        : "nessuna variazione"}
                </span>
              </div>

              <div className="sm:text-right">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                  Probabilità simulata
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
                  {formatEUR(expectedAfter)} valore atteso
                </p>
              </div>
            </div>

            <div className="mt-7 space-y-3 border-t border-line pt-5">
              <div>
                <div className="mb-1.5 flex items-center justify-between text-[10px] text-muted">
                  <span>Ora</span>
                  <span className="tabular-nums">
                    {formatPercent(current, 1)}
                  </span>
                </div>
                <ProbabilityMeter probability={current} band={currentBand} />
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between text-[10px] text-muted">
                  <span>Con {leverLabel}</span>
                  <span className="tabular-nums">
                    {formatPercent(hypothetical, 1)}
                  </span>
                </div>
                <ProbabilityMeter probability={hypothetical} band={nextBand} />
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-baseline justify-between gap-3 rounded-[4px] bg-[#F7FAFD] px-4 py-3">
              <p className="text-[11.5px] leading-relaxed text-muted">
                {result?.explanation ? counterfactualExplanation(result.explanation) :
                  "Simulazione leve in corso..."}
              </p>
              <p className="text-[11.5px] font-semibold tabular-nums text-ink">
                {formatSignedEUR(expectedAfter - expectedNow)} incremento valore atteso
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
                Pianifica questa azione
              </Link>
            ) : (
              <span className="inline-flex items-center rounded-[4px] border border-line bg-surface px-4 py-2.5 text-[12px] font-medium text-muted">
                Solo simulazione
              </span>
            )}
            <p className="max-w-md text-[10.5px] leading-relaxed text-muted">
              {commitKind
                ? "La leva è una simulazione. Pianificare l'azione conferma il ricalcolo del punteggio."
                : "Attenzione: questo è solo un what-if. Lo sconto non è un'azione consigliata e non può essere impegnata."}
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-[4px] border border-accent/30 bg-accent-soft/45 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-accent-deep">
              Dove conviene investire
            </p>
            <p className="mt-1 font-display text-[32px] leading-none tabular-nums text-ink">
              {maxLeverage !== null ? formatPoints(maxLeverage) : "—"}
            </p>
            <p className="mt-2 text-[10.5px] leading-relaxed text-muted">
              Incremento <span className="font-semibold text-ink">impegnabile</span>{" "}
              massimo per questa iniziativa. La mediana del libro e{" "}
              {formatPoints(LEVERAGE_BOOK.median, 2)}; il 90° percentile e{" "}
              {formatPoints(LEVERAGE_BOOK.p90, 2)}. {LEVERAGE_BOOK.noPositive.toLocaleString("it-IT")}{" "}
              su {LEVERAGE_BOOK.leads.toLocaleString("it-IT")} iniziative non hanno
              nessuna mossa impegnabile positiva: questa è un caso estremo, non tipico.
            </p>
            {topByEv ? (
              <p className="mt-2 border-t border-accent/20 pt-2 text-[10px] leading-relaxed text-muted">
                Opportunità più grande in coda:{" "}
                <span className="font-medium text-ink">{topByEv.company_name}</span>{" "}
                {formatPoints(topByEv.max_leverage ?? 0)} impegnabile,{" "}
                {formatPoints(topByEv.discount_upside ?? 0)} simulazione sconto.
              </p>
            ) : null}
            <Link
              to="/previsioni?sort=leverage"
              className="mt-2.5 inline-flex items-center gap-1.5 text-[10.5px] font-semibold text-accent transition hover:text-accent-deep"
            >
              Vedi dove conviene investire
              <ArrowUpRightIcon className="h-3 w-3" />
            </Link>
          </div>

          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
            Scegli una leva
          </p>

          {LEVERS.map((option) => {
            const selected = lever === option.key;
            return (
              <div
                key={option.key}
                className={cn(
                  "rounded-[4px] border p-4 transition",
                  selected
                    ? "border-accent/60 bg-accent-soft/35"
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
                      "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[4px]",
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
                        Sconto proposto
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
                      className="mt-3 w-full accent-[#005EB8]"
                    />
                    <div className="mt-1 flex justify-between text-[9px] text-muted">
                      <span>0%</span>
                      <span>attuale {(lead.discount_pct ?? 0).toFixed(1)}%</span>
                      <span>30%</span>
                    </div>
                    <p className="mt-2 text-[10px] leading-relaxed text-muted">
                      Una variazione dello sconto modifica il punteggio attraverso lo stesso modello. Non è una leva persuasiva: uno sconto più alto lo abbassa. Questa leva non viene mai classificata come leverage e non può essere impegnata.
                    </p>
                    {discountUpside !== null ? (
                      <p className="mt-2 rounded-[4px] bg-ink/[0.04] px-2 py-1.5 text-[10px] leading-relaxed text-muted">
                        Simulazione sconto:{" "}
                        <span className="font-semibold text-ink">
                          {formatPoints(discountUpside)}
                        </span>{" "}
                        solo what-if, non un'azione.
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}

          <p className="px-1 text-[10px] leading-relaxed text-muted">
            Lo sconto è solo una simulazione. Non è mai incluso in{" "}
            <code>max_leverage</code>, non concorre all'ordinamento per leva
            nella coda e non può essere impegnato come azione. La coda classifica
            solo le leve che un referente può effettivamente prenotare.
          </p>

          <InlineNotice className="mt-1">
            <strong className="font-semibold text-ink">
              Nessuna leva di avanzamento di fase.
            </strong>{" "}
            Il modello è addestrato su iniziative etichettate alla qualificazione,
            quindi un salto alla fase di proposta non è apprendibile. Mostrarlo
            significherebbe esporre un numero inventato.
          </InlineNotice>
        </div>
      </div>

      <div className="mt-8 grid gap-4 border-t border-line pt-5 text-[10.5px] leading-relaxed text-muted md:grid-cols-3">
        <p>
          <span className="font-semibold text-ink">Solo prospettico.</span>{" "}
          Le leve cambiano cio che può ancora accadere; nulla riscrive una risposta
          già avvenuta.
        </p>
        <p>
          <span className="font-semibold text-ink">Stesso modello.</span> Il punteggio
          attuale e quello ipotetico provengono dallo stesso modello: il delta e
          un confronto omogeneo.
        </p>
        <p>
          <span className="font-semibold text-ink">Non una promessa.</span> Un
          punteggio di{" "}
          {formatPercent(current, 1)} significa che circa {Math.round(current * 10)}{" "}
          iniziative su 10 comparabili vengono vinte, non questa in particolare.
        </p>
      </div>
    </div>
  );
}
