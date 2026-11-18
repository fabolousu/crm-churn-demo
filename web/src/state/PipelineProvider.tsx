import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  DEFAULT_ACT_LEAD_ID,
  fetchHealth,
  fetchLead,
  fetchPipeline,
  fetchPortfolio,
  initialHealth,
  initialLeadDetail,
  initialPipeline,
  initialPortfolio,
  isLiveApi,
  postAction,
  postCounterfactual,
  rebaseAction,
  rebaseCounterfactual,
} from "../lib/api";
import { bandForProbability } from "../lib/bands";
import type {
  ActionRequest,
  ActionResponse,
  CounterfactualRequest,
  CounterfactualResponse,
  Health,
  LeadDetail,
  PipelineResponse,
  Portfolio,
} from "../lib/types";

type QueueData = {
  pipeline: PipelineResponse;
  portfolio: Portfolio;
  health: Health;
};

type PipelineContextValue = {
  pipeline: PipelineResponse;
  portfolio: Portfolio;
  health: Health;
  live: boolean;
  error: string | null;
  defaultActLeadId: string;
  currentProbability: (leadId: string) => number | null;
  rankOf: (leadId: string) => number | null;
  loadLead: (leadId: string) => Promise<LeadDetail>;
  counterfactual: (
    leadId: string,
    request: CounterfactualRequest,
  ) => Promise<CounterfactualResponse>;
  logAction: (leadId: string, request: ActionRequest) => Promise<ActionResponse>;
};

const PipelineContext = createContext<PipelineContextValue | null>(null);

function initialData(): QueueData | null {
  const pipeline = initialPipeline();
  const portfolio = initialPortfolio();
  const health = initialHealth();
  if (!pipeline || !portfolio || !health) return null;
  return { pipeline, portfolio, health };
}

export function PipelineProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<QueueData | null>(initialData);
  const [updated, setUpdated] = useState<Record<string, true>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLiveApi) return;
    let cancelled = false;

    Promise.all([fetchPipeline(), fetchPortfolio(), fetchHealth()])
      .then(([pipeline, portfolio, health]) => {
        if (cancelled) return;
        setData({ pipeline, portfolio, health });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "The scoring service could not be reached.",
        );
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const applyProbability = useCallback((leadId: string, probability: number) => {
    setData((previous) => {
      if (!previous) return previous;
      return {
        ...previous,
        pipeline: {
          ...previous.pipeline,
          items: previous.pipeline.items.map((item) =>
            item.lead_id === leadId
              ? {
                  ...item,
                  probability,
                  band: bandForProbability(probability),
                  expected_value: Math.round(probability * item.amount_arr),
                }
              : item,
          ),
        },
      };
    });
    setUpdated((previous) => ({ ...previous, [leadId]: true }));
  }, []);

  const loadLead = useCallback(
    async (leadId: string): Promise<LeadDetail> => {
      const detail = await fetchLead(leadId);
      const item = data?.pipeline.items.find((entry) => entry.lead_id === leadId);
      if (!updated[leadId] || !item) return detail;
      return {
        ...detail,
        score: {
          ...detail.score,
          probability: item.probability,
          band: item.band,
          expected_value: item.expected_value,
        },
      };
    },
    [data, updated],
  );

  const currentProbability = useCallback(
    (leadId: string): number | null => {
      const item = data?.pipeline.items.find((entry) => entry.lead_id === leadId);
      return item ? item.probability : null;
    },
    [data],
  );

  const rankOf = useCallback(
    (leadId: string): number | null => {
      if (!data) return null;
      const ranked = [...data.pipeline.items].sort(
        (a, b) => b.expected_value - a.expected_value,
      );
      const index = ranked.findIndex((item) => item.lead_id === leadId);
      return index === -1 ? null : index + 1;
    },
    [data],
  );

  const counterfactual = useCallback(
    async (
      leadId: string,
      request: CounterfactualRequest,
    ): Promise<CounterfactualResponse> => {
      const response = await postCounterfactual(leadId, request);
      if (isLiveApi) return response;
      const current = currentProbability(leadId);
      return current === null
        ? response
        : rebaseCounterfactual(response, current);
    },
    [currentProbability],
  );

  const logAction = useCallback(
    async (leadId: string, request: ActionRequest): Promise<ActionResponse> => {
      const current = currentProbability(leadId);
      const response = await postAction(leadId, request);

      if (!isLiveApi && current !== null) {
        // Fixture responses are precomputed from the original score. If the
        // lead has already been re-scored on this screen, keep the action's
        // logit effect and rebase it on the current probability.
        const original =
          initialLeadDetail(leadId)?.score.probability ??
          response.probability_after;
        const adjusted = rebaseAction(response, current, original);
        applyProbability(leadId, adjusted.probability_after);
        return adjusted;
      }

      applyProbability(leadId, response.probability_after);
      return response;
    },
    [applyProbability, currentProbability],
  );

  const value = useMemo<PipelineContextValue | null>(() => {
    if (!data) return null;
    return {
      pipeline: data.pipeline,
      portfolio: data.portfolio,
      health: data.health,
      live: isLiveApi,
      error,
      defaultActLeadId:
        data.pipeline.items.find((item) => item.lead_id === DEFAULT_ACT_LEAD_ID)
          ?.lead_id ??
        data.pipeline.items[0]?.lead_id ??
        DEFAULT_ACT_LEAD_ID,
      currentProbability,
      rankOf,
      loadLead,
      counterfactual,
      logAction,
    };
  }, [
    data,
    error,
    currentProbability,
    rankOf,
    loadLead,
    counterfactual,
    logAction,
  ]);

  if (!value) {
    return <BootScreen error={error} />;
  }

  return (
    <PipelineContext.Provider value={value}>{children}</PipelineContext.Provider>
  );
}

export function usePipeline(): PipelineContextValue {
  const context = useContext(PipelineContext);
  if (!context) {
    throw new Error("usePipeline must be used inside PipelineProvider");
  }
  return context;
}

// Live mode only: fixtures never hit this path. Deliberately no spinner — the
// demo must never show a loading state.
function BootScreen({ error }: { error: string | null }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-6">
      <div className="w-full max-w-md border-t-2 border-accent bg-surface p-8 shadow-card">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">
          Iniziativa
        </p>
        <h1 className="mt-3 font-display text-3xl text-ink">
          {error ? "The scoring service is not answering" : "Opening the queue"}
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          {error ??
            "Connecting to the model service. The fixture build never waits here."}
        </p>
        {error ? (
          <p className="mt-6 border-l-2 border-risk-high pl-3 text-xs text-muted">
            Check `VITE_API_BASE` and that the API is running on its configured
            port, then reload.
          </p>
        ) : null}
      </div>
    </div>
  );
}
