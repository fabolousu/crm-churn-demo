import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import LeadTabs from "../components/LeadTabs";
import {
  ArrowLeftIcon,
  ArrowUpRightIcon,
  BoltIcon,
  CalendarIcon,
  TrendDownIcon,
  TrendUpIcon,
  UsersIcon,
} from "../components/icons";
import {
  BandPill,
  buttonPrimary,
  buttonSecondary,
  Card,
  cn,
  InlineNotice,
  MetaRow,
  PageHeader,
  ProbabilityDial,
  SectionHeading,
} from "../components/ui";
import { fetchCompany, initialLeadDetail } from "../lib/api";
import {
  actionKindLabel,
  formatDate,
  formatDateTime,
  formatEUR,
  formatEURCompact,
  formatPercent,
  formatPoints,
  lostReasonLabel,
  regionLabel,
  sourceLabel,
  statusLabel,
} from "../lib/format";
import { driverNarrative } from "../lib/narratives";
import { driverLabel, driverValue } from "../lib/format";
import { winPrevalence } from "../lib/model";
import { usePipeline } from "../state/PipelineProvider";
import type { CompanyDetail, LeadDetail } from "../lib/types";

export default function LeadPage() {
  const { leadId = "" } = useParams();
  const { loadLead, rankOf, portfolio, pipeline } = usePipeline();
  const prevalence = portfolio.win_prevalence ?? winPrevalence(portfolio.by_region);
  const [detail, setDetail] = useState<LeadDetail | null>(() =>
    initialLeadDetail(leadId),
  );
  const [companyDetail, setCompanyDetail] = useState<CompanyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
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

  const company = detail?.company;
  const lead = detail?.lead;
  const score = detail?.score;
  const drivers = detail?.drivers ?? [];
  const history = detail?.prior_initiatives ?? [];

  useEffect(() => {
    const companyId = company?.id;
    if (!companyId) {
      setCompanyDetail(null);
      return;
    }
    let cancelled = false;
    fetchCompany(companyId)
      .then((next) => {
        if (!cancelled) setCompanyDetail(next);
      })
      .catch(() => {
        if (!cancelled) setCompanyDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [company?.id]);

  const priorCounts = useMemo(() => {
    const won = history.filter((item) => item.status === "won").length;
    const lost = history.filter((item) => item.status === "lost").length;
    return { won, lost };
  }, [history]);

  const signals = companyDetail?.signals;
  const counts = signals
    ? { won: signals.won, lost: signals.lost }
    : priorCounts;
  const daysSinceLast = signals?.days_since_last_initiative ?? null;
  const lastInitiative =
    companyDetail?.initiatives[0] ?? history[0] ?? null;
  const lifetimeWon = signals?.lifetime_won_arr ?? company?.lifetime_won_arr ?? 0;
  const dormant = signals?.dormant ?? company?.dormant ?? false;

  const maxContribution = useMemo(
    () =>
      Math.max(
        ...drivers.map((driver) => Math.abs(driver.contribution)),
        0.01,
      ),
    [drivers],
  );

  const rank = detail ? rankOf(detail.lead.id) : null;
  // Contract v0.3 puts max_leverage on LeadDetail too, nullable for closed
  // leads. Treat a missing value the same as null: no lever is offered.
  const maxLeverage = detail?.max_leverage ?? null;
  const discountUpside = detail?.discount_upside ?? null;
  const isClosed =
    detail?.lead.status === "won" || detail?.lead.status === "lost";
  const daysOpen =
    pipeline.items.find((item) => item.lead_id === lead?.id)?.days_open ?? null;

  if (error) {
    return (
      <div>
        <Link
          to="/previsioni"
          className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
        >
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Torna alla coda pipeline
        </Link>
        <PageHeader
          eyebrow="Lead 360"
          title="Iniziativa non presente nella coda"
          subtitle={error}
        />
        <Card className="p-6">
          <p className="text-[12.5px] text-muted">
            La coda contiene solo le iniziative aperte. Selezionarne un'altra
            dalla pipeline - i dati di esempio corrispondono all'elenco lead del contratto.
          </p>
          <Link to="/previsioni" className={buttonPrimary + " mt-5"}>
            Torna alla pipeline
          </Link>
        </Card>
      </div>
    );
  }

  if (!detail || !company || !lead || !score) {
    return (
      <div>
        <Link
          to="/previsioni"
          className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
        >
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Torna alla coda pipeline
        </Link>
        <PageHeader eyebrow="Lead 360" title="Caricamento analisi Lead 360 in corso..." />
        <Card className="p-6">
          <p className="text-[12.5px] text-muted">
            Richiesta al servizio di scoring per questa iniziativa. I dati di esempio
            vengono aperti immediatamente.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <Link
        to="/previsioni"
        className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
      >
        <ArrowLeftIcon className="h-3.5 w-3.5" />
        Torna alla coda pipeline
      </Link>

      <div className="mt-4 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-muted">
            Lead 360 · {regionLabel(company.region)}
          </p>
          <h1 className="mt-2 max-w-3xl font-display text-[34px] leading-[1.05] tracking-[-0.01em] text-ink md:text-[46px]">
            {company.name}
          </h1>
          <p className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted">
            <span>{company.industry}</span>
            <span className="text-line">·</span>
            <span className="inline-flex items-center gap-1">
              <UsersIcon className="h-3.5 w-3.5" />
              {company.employees.toLocaleString("it-IT")} dipendenti
            </span>
            <span className="text-line">·</span>
            <span>{statusLabel(lead.status)}</span>
            <span className="text-line">·</span>
            <span className="inline-flex items-center gap-1">
              <CalendarIcon className="h-3.5 w-3.5" />
              {isClosed
                ? `Chiusa${lead.closed_at ? ` ${formatDate(lead.closed_at)}` : ""}`
                : daysOpen !== null
                  ? `${daysOpen} giorni aperta`
                  : "aperta"}
            </span>
            {dormant ? (
              <span className="rounded-[4px] bg-[#FDECEA] px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-risk-high">
                Inattiva
              </span>
            ) : null}
          </p>
        </div>

        {isClosed ? (
          <span className="inline-flex items-center gap-2 rounded-[4px] border border-line bg-surface px-4 py-2.5 text-[12px] font-medium text-muted">
            Iniziativa chiusa - nessuna leva disponibile
          </span>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Link to={`/previsioni/leads/${lead.id}/lever`} className={buttonPrimary}>
              <BoltIcon className="h-4 w-4" />
              Testa una leva
            </Link>
            <Link to={`/previsioni/act/${lead.id}`} className={buttonSecondary}>
              Registra un'azione
            </Link>
          </div>
        )}
      </div>

      {isClosed ? null : <LeadTabs leadId={lead.id} active="overview" />}

      <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1.62fr)_minmax(270px,0.78fr)]">
        <div className="space-y-7">
          <Card className="grid gap-6 p-6 sm:grid-cols-[240px_minmax(0,1fr)] sm:items-center">
            <ProbabilityDial
              probability={score.probability}
              band={score.band}
              benchmark={prevalence}
            />
            <div className="sm:border-l sm:border-line sm:pl-7">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                  Punteggio corrente
                </span>
                <BandPill band={score.band} />
                {rank ? (
                  <span className="rounded-[4px] border border-line px-2 py-0.5 text-[10px] font-medium text-muted">
                    #{rank} nella coda per valore atteso
                  </span>
                ) : null}
              </div>
              <p className="mt-3 max-w-md text-[12.5px] leading-relaxed text-muted">
                Circa un'iniziativa su tre di questo tipo viene convertita. Questa si
                colloca{" "}
                {score.probability >= prevalence ? "al di sopra" : "al di sotto"} della
                media di portafoglio del{" "}
                {formatPercent(prevalence, 2)}.{" "}
                {isClosed
                  ? "I tre fattori determinanti spiegano il punteggio finale; l'iniziativa è chiusa, pertanto non è disponibile alcuna leva."
                  : "I tre fattori determinanti spiegano il punteggio, in ordine di influenza - la leva indica il valore di una modifica."}
              </p>

              <div className="mt-5 grid grid-cols-2 gap-5">
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted">
                    Valore atteso
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    {formatEUR(score.expected_value)}
                  </p>
                </div>
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted">
                    ARR proposto
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    {formatEUR(lead.amount_arr ?? 0)}
                  </p>
                </div>
              </div>

              {maxLeverage !== null ? (
                <Link
                  to={`/previsioni/leads/${lead.id}/lever`}
                  className="mt-4 inline-flex items-center gap-2 rounded-[4px] bg-accent-soft px-3 py-1.5 text-[11px] font-semibold text-accent-deep transition hover:bg-[#D4E8E0]"
                >
                  <BoltIcon className="h-3.5 w-3.5" />
                  Leva massima {formatPoints(maxLeverage)} - vedi la mossa
                </Link>
              ) : null}
              {discountUpside !== null && discountUpside > 0 ? (
                <p className="mt-2 text-[10px] leading-relaxed text-muted">
                  Simulazione sconto {formatPoints(discountUpside)} - non impegnabile,
                  non inclusa nel calcolo della leva.
                </p>
              ) : null}

              <p className="mt-5 border-t border-line pt-3 text-[10.5px] text-muted">
                Punteggio attribuito il {formatDateTime(score.scored_at)} · {score.model_version} ·
                elaborazione notturna
              </p>
            </div>
          </Card>

          <section>
            <SectionHeading
              label="Tre fattori determinanti"
              title={`Perché ${formatPercent(score.probability, 0)}?`}
              hint="Tre segnali effettivamente appresi dal modello, in ordine di influenza. Ciascuno è un dato di business, non un termine tecnico del modello."
            />
            <div className="grid gap-3 lg:grid-cols-3">
              {drivers.map((driver, index) => {
                const increases = driver.direction === "increases";
                const width = Math.max(
                  8,
                  (Math.abs(driver.contribution) / maxContribution) * 100,
                );
                return (
                  <Card
                    key={`${driver.feature}-${index}`}
                    className="flex h-full flex-col p-5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-display text-[13px] text-muted">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-[4px] px-2 py-1 text-[9.5px] font-semibold uppercase tracking-[0.08em]",
                          increases
                            ? "bg-[#CBE4FB] text-[#00499D]"
                            : "bg-[#FDECEA] text-[#912018]",
                        )}
                      >
                        {increases ? (
                          <TrendUpIcon className="h-3 w-3" />
                        ) : (
                          <TrendDownIcon className="h-3 w-3" />
                        )}
                        {increases ? "Aumenta il punteggio" : "Riduce il punteggio"}
                      </span>
                    </div>

                    <p className="mt-4 font-display text-[21px] leading-[1.24] text-ink">
                      {driverValue(driver.value)}
                    </p>
                    <p className="mt-3 flex-1 text-[11.5px] leading-relaxed text-muted">
                      {driverNarrative(driver.feature)}
                    </p>

                    <div className="mt-4 border-t border-line pt-3">
                      <div className="flex items-center justify-between text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                        <span>{driverLabel(driver.label)}</span>
                        <span>Influenza</span>
                      </div>
                      <div className="mt-2 h-1 overflow-hidden rounded-[4px] bg-[#DBE2E8]">
                        <div
                          className={cn(
                            "h-full rounded-[4px]",
                            increases ? "bg-risk-low" : "bg-risk-high",
                          )}
                          style={{ width: `${width}%` }}
                        />
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </section>

          <section>
            <SectionHeading
              label="Contesto aziendale"
              title="Le iniziative precedenti"
              hint={`${counts.won} vinte · ${counts.lost} perse · ${formatEUR(lifetimeWon)} ARR vinto nel corso del rapporto. Il rapporto prosegue solo se qualcuno propone la prossima iniziativa.`}
            />
            <Card className="divide-y divide-line">
              {history.map((initiative) => {
                const won = initiative.status === "won";
                return (
                  <div
                    key={initiative.id}
                    className="flex items-center gap-4 px-5 py-4"
                  >
                    <span
                      className={cn(
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-[4px] text-[10px] font-semibold",
                        won
                          ? "bg-[#CBE4FB] text-risk-low"
                          : "bg-[#FDECEA] text-risk-high",
                      )}
                    >
                      {won ? "V" : "P"}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12.5px] font-medium text-ink">
                        {statusLabel(initiative.status)} ·{" "}
                        {formatEUR(initiative.amount_arr ?? 0)}
                        {initiative.lost_reason ? (
                          <span className="ml-2 text-[11px] font-normal text-muted">
                            ({lostReasonLabel(initiative.lost_reason)})
                          </span>
                        ) : null}
                      </p>
                      <p className="mt-0.5 text-[10.5px] text-muted">
                        {formatDate(initiative.created_at)}
                        {initiative.closed_at
                          ? ` - ${formatDate(initiative.closed_at)}`
                          : ""}
                      </p>
                    </div>
                    <span className="hidden text-[10.5px] text-muted sm:block">
                      {sourceLabel(initiative.source)}
                    </span>
                  </div>
                );
              })}
            </Card>
          </section>
        </div>

        <aside className="space-y-4">
          <Card className="p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              Rapporto
            </p>
            <h2 className="mt-1.5 font-display text-[21px] text-ink">
              {company.name}
            </h2>
            <dl className="mt-4 divide-y divide-line border-t border-line">
              <MetaRow
                label="ARR vinto totale"
                value={formatEUR(lifetimeWon)}
              />
              <MetaRow
                label="Iniziative"
                value={`${counts.won} vinte · ${counts.lost} perse`}
              />
              <MetaRow
                label="Ultima iniziativa"
                value={
                  lastInitiative
                    ? `${formatDate(lastInitiative.created_at)}${
                        daysSinceLast !== null ? ` · ${daysSinceLast}g fa` : ""
                      }`
                    : "Nessuna registrata"
                }
              />
              <MetaRow
                label="Stato attività"
                value={
                  dormant ? (
                    <span className="font-medium text-risk-high">Inattiva</span>
                  ) : (
                    "Attiva"
                  )
                }
              />
              <MetaRow
                label="Regione"
                value={regionLabel(company.region)}
              />
            </dl>
            <p className="mt-3 text-[10.5px] leading-relaxed text-muted">
              {isClosed
                ? "Iniziativa chiusa. Il rapporto prosegue solo se qualcuno propone la prossima iniziativa."
                : dormant
                  ? "Nessuna nuova iniziativa da oltre 180 giorni. L'inattività è un segnale del rapporto, non l'obiettivo del modello."
                  : "Un'iniziativa è aperta, quindi il rapporto è attivo. L'inattività viene segnalata dopo 180 giorni senza nuove iniziative."}
            </p>
          </Card>

          <Card className="p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              Questa iniziativa
            </p>
            <dl className="mt-3 divide-y divide-line border-t border-line">
              <MetaRow label="Fase" value={statusLabel(lead.status)} />
              <MetaRow label="Fonte" value={sourceLabel(lead.source)} />
              <MetaRow
                label={isClosed ? "Chiusa il" : "Giorni aperti"}
                value={
                  isClosed
                    ? lead.closed_at
                      ? formatDate(lead.closed_at)
                      : "—"
                    : `${daysOpen} giorni`
                }
              />
              <MetaRow
                label="Sconto"
                value={`${(lead.discount_pct ?? 0).toFixed(1)}%`}
              />
              <MetaRow
                label="Valore atteso"
                value={formatEURCompact(score.expected_value)}
              />
            </dl>
            {isClosed ? (
              <p className="mt-3 border-t border-line pt-3 text-[10.5px] leading-relaxed text-muted">
                Iniziativa chiusa. <code>max_leverage</code> è nullo, quindi
                il punteggio non ha leva e non è possibile registrare azioni.
              </p>
            ) : null}
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                Azioni aperte
              </p>
              <span className="rounded-[4px] bg-ink/[0.05] px-2 py-0.5 text-[10px] tabular-nums text-muted">
                {detail.open_actions.length}
              </span>
            </div>

            {detail.open_actions.length ? (
              <div className="mt-3 space-y-3">
                {detail.open_actions.map((action) => (
                  <div
                    key={action.id}
                    className="rounded-[4px] border border-line bg-[#F7FAFD] p-3"
                  >
                    <p className="text-[11.5px] font-semibold text-ink">
                      {actionKindLabel(action.kind)}
                    </p>
                    <p className="mt-1 text-[10.5px] text-muted">
                      {action.created_by} ·{" "}
                      {formatDateTime(action.created_at)}
                    </p>
                    {action.note ? (
                      <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted">
                        {action.note}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-[11.5px] leading-relaxed text-muted">
                {isClosed
                  ? "Iniziativa chiusa. La cronologia delle azioni è definitiva."
                  : "Nessuna azione aperta. La coda si riordina non appena viene registrata un'azione."}
              </p>
            )}

            {isClosed ? null : (
              <Link
                to={`/previsioni/act/${lead.id}`}
                className="mt-4 inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-accent transition hover:text-accent-deep"
              >
                Registra un'azione
                <ArrowUpRightIcon className="h-3.5 w-3.5" />
              </Link>
            )}
          </Card>

          <InlineNotice>
            I driver sono valori SHAP relativi alle variabili effettivamente
            osservate dal modello. La fase è mostrata, ma non è un driver: i lead
            chiusi vengono etichettati alla qualifica, quindi l'effetto di avanzamento
            di fase non è apprendibile.
          </InlineNotice>
        </aside>
      </div>
    </div>
  );
}
