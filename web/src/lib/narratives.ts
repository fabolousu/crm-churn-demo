// One-line, executive-safe interpretations of the SHAP features the model
// actually learned. The headline sentence comes from the API's Driver.value;
// this adds the "so what" without inventing a new number.

const NARRATIVES: Record<string, string> = {
  first_response_hours:
    "Speed of first reply is the strongest lever the rep controls. Slower than the reference world pulls the score down.",
  prior_lost_initiatives:
    "Lost initiatives in the recent history are evidence about this relationship, so they lower the score.",
  prior_won_initiatives:
    "Initiatives won together are the clearest evidence this company finishes what it starts.",
  days_since_last_initiative:
    "Long gaps between initiatives are how this relationship decays. Dormancy is a symptom, not the target.",
  meetings_before_scoring:
    "Meetings held are real engagement. The model rewards time already spent with the buyer.",
  owner_win_rate_180d:
    "The assigning rep's recent win rate is part of the score: who runs the initiative matters.",
  amount_arr:
    "Larger initiatives are harder to close in this world, so size pulls the probability down.",
  discount_pct:
    "A larger proposed discount is a signal of friction. It lowers the score rather than buying the win.",
  tickets_90d:
    "Support friction in the last 90 days is a negative signal about the relationship.",
  nps_last:
    "Relationship health, as last measured, is a positive signal when the NPS is strong.",
  source:
    "Where the initiative came from carries a base-rate effect: referrals and partners convert better than outbound.",
  region:
    "Regional base rates differ, and the model carries the region as a feature.",
};

export function driverNarrative(feature: string): string {
  return (
    NARRATIVES[feature] ??
    "This feature moved the score under the same model that scored every initiative."
  );
}
