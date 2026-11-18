// Facts from the build that the API contract does not carry.
//
// `ml/artifacts/metrics.json` is the source of the discrimination and
// calibration numbers. `/api/portfolio` carries the calibration bins and the
// drift PSI, but not AUC, ECE or the latent ceiling, and it has no proposed-ARR
// total. These constants keep the Portfolio screen honest until the contract
// grows those fields (see web/README.md, "What the contract does not carry").

export const MODEL_METRICS = {
  auc: 0.773,
  calibrationError: 0.0104,
  latentAuc: 0.789,
} as const;

// data/generator.py CALIBRATED_Z.amount_arr: the fixed reference mean of the
// proposed ARR in the synthetic world. Used only to turn open-lead counts into
// an ARR total, never shown as a model output.
export const MEAN_PROPOSED_ARR = 36_246.04918124;

export const OPEN_LEADS = 19_752;
export const WIN_PREVALENCE = 0.2866;
export const SNAPSHOT_DATE = "2026-11-18";

// Across the whole open book: the median best lever is +4.19 points and the
// 90th percentile is +16.9. L057056's executive-sponsor lever is +17.27, which
// is why it is the demo lead rather than a typical one.
export const LEVERAGE_BOOK = {
  median: 0.0419,
  p90: 0.169,
} as const;

export const OPEN_PIPELINE_ARR = OPEN_LEADS * MEAN_PROPOSED_ARR;

export function pipelineAtRisk(totalExpectedValue: number): number {
  return Math.max(0, OPEN_PIPELINE_ARR - totalExpectedValue);
}

export function winPrevalence(
  byRegion: Array<{ open_leads: number; win_rate: number }>,
): number {
  const open = byRegion.reduce((sum, region) => sum + region.open_leads, 0);
  if (open === 0) return 0;
  const wins = byRegion.reduce(
    (sum, region) => sum + region.open_leads * region.win_rate,
    0,
  );
  return wins / open;
}
