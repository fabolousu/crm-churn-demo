import type { Portfolio } from "./types";

export type StabilityBreakdown = {
  trainMean: number;
  holdoutMean: number;
  trainWinRate: number;
  holdoutWinRate: number;
};

// The four stability fields are optional in the contract: a labelled
// population that cannot be split leaves them out. Returning null is the
// signal for the panel's "not measurable" state — never a constant fallback.
export function stabilityBreakdown(
  drift: Portfolio["drift"],
): StabilityBreakdown | null {
  const { train_mean, holdout_mean, train_win_rate, holdout_win_rate } = drift;
  if (
    typeof train_mean !== "number" ||
    typeof holdout_mean !== "number" ||
    typeof train_win_rate !== "number" ||
    typeof holdout_win_rate !== "number"
  ) {
    return null;
  }
  return {
    trainMean: train_mean,
    holdoutMean: holdout_mean,
    trainWinRate: train_win_rate,
    holdoutWinRate: holdout_win_rate,
  };
}
