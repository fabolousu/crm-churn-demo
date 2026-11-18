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
              : "That initiative could not be opened.",
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
          to="/"
          className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
        >
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Back to the queue
        </Link>
        <PageHeader
          eyebrow="Lead 360"
          title="That initiative is not in the queue"
          subtitle={error}
        />
        <Card className="p-6">
          <p className="text-[12.5px] text-muted">
            The queue only carries open initiatives. Pick another one from the
            pipeline; the fixtures match the contract's lead list.
          </p>
          <Link to="/" className={buttonPrimary + " mt-5"}>
            Return to the pipeline
          </Link>
        </Card>
      </div>
    );
  }

  if (!detail || !company || !lead || !score) {
    return (
      <div>
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
        >
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Back to the queue
        </Link>
        <PageHeader eyebrow="Lead 360" title="Opening the initiative" />
        <Card className="p-6">
          <p className="text-[12.5px] text-muted">
            Asking the scoring service for this initiative. The fixture build
            opens it immediately.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-[11.5px] font-medium text-muted transition hover:text-ink"
      >
        <ArrowLeftIcon className="h-3.5 w-3.5" />
        Back to the queue
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
              {company.employees.toLocaleString("en-GB")} employees
            </span>
            <span className="text-line">·</span>
            <span>{statusLabel(lead.status)}</span>
            <span className="text-line">·</span>
            <span className="inline-flex items-center gap-1">
              <CalendarIcon className="h-3.5 w-3.5" />
              {isClosed
                ? `Closed${lead.closed_at ? ` ${formatDate(lead.closed_at)}` : ""}`
                : daysOpen !== null
                  ? `${daysOpen} days open`
                  : "open"}
            </span>
            {dormant ? (
              <span className="rounded-full bg-[#FDECEA] px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-risk-high">
                Dormant
              </span>
            ) : null}
          </p>
        </div>

        {isClosed ? (
          <span className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2.5 text-[12px] font-medium text-muted">
            Closed initiative · no lever
          </span>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Link to={`/leads/${lead.id}/lever`} className={buttonPrimary}>
              <BoltIcon className="h-4 w-4" />
              Test a lever
            </Link>
            <Link to={`/act/${lead.id}`} className={buttonSecondary}>
              Log an action
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
                  Current score
                </span>
                <BandPill band={score.band} />
                {rank ? (
                  <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-medium text-muted">
                    Rank #{rank} by expected value
                  </span>
                ) : null}
              </div>
              <p className="mt-3 max-w-md text-[12.5px] leading-relaxed text-muted">
                About one in three comparable initiatives win. This one sits{" "}
                {score.probability >= prevalence ? "above" : "below"} the{" "}
                {formatPercent(prevalence, 2)} portfolio average.{" "}
                {isClosed
                  ? "The three drivers below explain the final score; this initiative is closed, so no lever is offered."
                  : "The three drivers below explain the score, in order of influence — and the lever shows what changing one is worth."}
              </p>

              <div className="mt-5 grid grid-cols-2 gap-5">
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted">
                    Expected value
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    {formatEUR(score.expected_value)}
                  </p>
                </div>
                <div>
                  <p className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-muted">
                    Proposed ARR
                  </p>
                  <p className="mt-1 font-display text-[30px] leading-none tabular-nums text-ink">
                    {formatEUR(lead.amount_arr ?? 0)}
                  </p>
                </div>
              </div>

              {maxLeverage !== null ? (
                <Link
                  to={`/leads/${lead.id}/lever`}
                  className="mt-4 inline-flex items-center gap-2 rounded-full bg-accent-soft px-3 py-1.5 text-[11px] font-semibold text-accent-deep transition hover:bg-[#D4E8E0]"
                >
                  <BoltIcon className="h-3.5 w-3.5" />
                  Best committable lever {formatPoints(maxLeverage)} · see the
                  move
                </Link>
              ) : null}
              {discountUpside !== null && discountUpside > 0 ? (
                <p className="mt-2 text-[10px] leading-relaxed text-muted">
                  Discount what-if {formatPoints(discountUpside)} — not
                  committable, not part of the leverage ranking.
                </p>
              ) : null}

              <p className="mt-5 border-t border-line pt-3 text-[10.5px] text-muted">
                Scored {formatDateTime(score.scored_at)} · {score.model_version} ·
                nightly batch
              </p>
            </div>
          </Card>

          <section>
            <SectionHeading
              label="The three drivers"
              title={`Why ${formatPercent(score.probability, 0)}?`}
              hint="Three signals the model actually learned, in order of influence. Each is a business fact, not a model term."
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
                      <span className="font-display text-[13px] text-muted/70">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2 py-1 text-[9.5px] font-semibold uppercase tracking-[0.08em]",
                          increases
                            ? "bg-[#E7F4EC] text-[#05603A]"
                            : "bg-[#FDECEA] text-[#912018]",
                        )}
                      >
                        {increases ? (
                          <TrendUpIcon className="h-3 w-3" />
                        ) : (
                          <TrendDownIcon className="h-3 w-3" />
                        )}
                        {increases ? "Raises the score" : "Lowers the score"}
                      </span>
                    </div>

                    <p className="mt-4 font-display text-[21px] leading-[1.24] text-ink">
                      {driver.value}
                    </p>
                    <p className="mt-3 flex-1 text-[11.5px] leading-relaxed text-muted">
                      {driverNarrative(driver.feature)}
                    </p>

                    <div className="mt-4 border-t border-line pt-3">
                      <div className="flex items-center justify-between text-[9.5px] font-semibold uppercase tracking-[0.13em] text-muted">
                        <span>{driver.label}</span>
                        <span>Influence</span>
                      </div>
                      <div className="mt-2 h-1 overflow-hidden rounded-full bg-[#EEE9DF]">
                        <div
                          className={cn(
                            "h-full rounded-full",
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
              label="Company context"
              title="The initiatives before this one"
              hint={`${counts.won} won · ${counts.lost} lost · ${formatEUR(lifetimeWon)} lifetime won ARR. The relationship continues only if someone proposes the next initiative.`}
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
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                        won
                          ? "bg-[#E7F4EC] text-risk-low"
                          : "bg-[#FDECEA] text-risk-high",
                      )}
                    >
                      {won ? "W" : "L"}
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
                          ? ` → ${formatDate(initiative.closed_at)}`
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
              Relationship
            </p>
            <h2 className="mt-1.5 font-display text-[21px] text-ink">
              {company.name}
            </h2>
            <dl className="mt-4 divide-y divide-line border-t border-line">
              <MetaRow
                label="Lifetime won ARR"
                value={formatEUR(lifetimeWon)}
              />
              <MetaRow
                label="Initiatives"
                value={`${counts.won} won · ${counts.lost} lost`}
              />
              <MetaRow
                label="Last initiative"
                value={
                  lastInitiative
                    ? `${formatDate(lastInitiative.created_at)}${
                        daysSinceLast !== null ? ` · ${daysSinceLast}d ago` : ""
                      }`
                    : "None on record"
                }
              />
              <MetaRow
                label="Dormancy"
                value={
                  dormant ? (
                    <span className="font-medium text-risk-high">Dormant</span>
                  ) : (
                    "Active"
                  )
                }
              />
              <MetaRow
                label="Region"
                value={regionLabel(company.region)}
              />
            </dl>
            <p className="mt-3 text-[10.5px] leading-relaxed text-muted">
              {isClosed
                ? "This initiative is closed. The relationship continues only if someone proposes the next initiative."
                : dormant
                  ? "No new initiative for 180+ days. Dormancy is a symptom of the relationship, not the model target."
                  : "An initiative is open, so the relationship is active. Dormancy is flagged at 180 days without a new initiative."}
            </p>
          </Card>

          <Card className="p-5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
              This initiative
            </p>
            <dl className="mt-3 divide-y divide-line border-t border-line">
              <MetaRow label="Stage" value={statusLabel(lead.status)} />
              <MetaRow label="Source" value={sourceLabel(lead.source)} />
              <MetaRow
                label={isClosed ? "Closed" : "Days open"}
                value={
                  isClosed
                    ? lead.closed_at
                      ? formatDate(lead.closed_at)
                      : "—"
                    : `${daysOpen} days`
                }
              />
              <MetaRow
                label="Discount"
                value={`${(lead.discount_pct ?? 0).toFixed(1)}%`}
              />
              <MetaRow
                label="Expected value"
                value={formatEURCompact(score.expected_value)}
              />
            </dl>
            {isClosed ? (
              <p className="mt-3 border-t border-line pt-3 text-[10.5px] leading-relaxed text-muted">
                Closed initiative. <code>max_leverage</code> is null, so the
                score has no lever and no action can be logged.
              </p>
            ) : null}
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">
                Open actions
              </p>
              <span className="rounded-full bg-ink/[0.05] px-2 py-0.5 text-[10px] tabular-nums text-muted">
                {detail.open_actions.length}
              </span>
            </div>

            {detail.open_actions.length ? (
              <div className="mt-3 space-y-3">
                {detail.open_actions.map((action) => (
                  <div
                    key={action.id}
                    className="rounded-lg border border-line bg-[#FAF8F3] p-3"
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
                  ? "This initiative is closed. Its action history is final."
                  : "No action open yet. The queue re-ranks the moment one is logged."}
              </p>
            )}

            {isClosed ? null : (
              <Link
                to={`/act/${lead.id}`}
                className="mt-4 inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-accent transition hover:text-accent-deep"
              >
                Log an action
                <ArrowUpRightIcon className="h-3.5 w-3.5" />
              </Link>
            )}
          </Card>

          <InlineNotice>
            Drivers are SHAP values for the features the model actually saw. The
            stage is shown, but it is not a driver: closed leads are labelled at
            qualification, so a stage-advance effect is unlearnable.
          </InlineNotice>
        </aside>
      </div>
    </div>
  );
}
