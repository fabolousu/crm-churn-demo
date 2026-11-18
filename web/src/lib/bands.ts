import type { Band } from "./types";

// The OpenAPI Band enum does not define thresholds. In this product a band is
// a *risk* band, so a low band means a healthy win probability. The cut points
// live here, are used to re-band a re-scored lead, and are documented in the
// README.
//
//   probability < 0.15  -> critical
//   probability < 0.30  -> high
//   probability < 0.50  -> medium
//   otherwise           -> low
export function bandForProbability(probability: number): Band {
  if (probability < 0.15) return "critical";
  if (probability < 0.3) return "high";
  if (probability < 0.5) return "medium";
  return "low";
}

type BandStyle = {
  label: string;
  short: string;
  dot: string;
  pill: string;
  bar: string;
  text: string;
  hex: string;
};

export const BAND_STYLES: Record<Band, BandStyle> = {
  low: {
    label: "Low risk",
    short: "Low",
    dot: "bg-risk-low",
    pill: "bg-[#E7F4EC] text-[#05603A] ring-[#B7E1C6]",
    bar: "bg-risk-low",
    text: "text-risk-low",
    hex: "#067647",
  },
  medium: {
    label: "Medium risk",
    short: "Medium",
    dot: "bg-risk-medium",
    pill: "bg-[#FDF1E3] text-[#8A3A06] ring-[#F5D0A9]",
    bar: "bg-risk-medium",
    text: "text-risk-medium",
    hex: "#B54708",
  },
  high: {
    label: "High risk",
    short: "High",
    dot: "bg-risk-high",
    pill: "bg-[#FDECEA] text-[#912018] ring-[#F5C2BC]",
    bar: "bg-risk-high",
    text: "text-risk-high",
    hex: "#B42318",
  },
  critical: {
    label: "Critical risk",
    short: "Critical",
    dot: "bg-risk-critical",
    pill: "bg-[#FCE9E5] text-[#6B1F15] ring-[#EDB8AD]",
    bar: "bg-risk-critical",
    text: "text-risk-critical",
    hex: "#7A271A",
  },
};
