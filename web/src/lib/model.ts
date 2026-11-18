// Book-level context that the API does not expose as an aggregate. These are
// the measured committable-leverage distribution (exec / discovery only):
// median 0.43 pts, p90 3.41; 2,845 of 19,752 leads have no positive committable
// move. Russo is a tail case, not a typical one.
export const LEVERAGE_BOOK = {
  median: 0.00425,
  p90: 0.0341,
  noPositive: 2845,
  leads: 19752,
} as const;

// Fallback when the generated portfolio fixture/API does not include the
// labelled prevalence. In fixture mode portfolio.win_prevalence is generated
// from lead_outcomes; this open-weighted value is only a fallback.
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
