import type { Band } from "./types";

// The API's model bands, stated once in ml/train.py:
//   p < 0.20 -> low, < 0.40 -> medium, < 0.60 -> high, otherwise critical.
// These are probability bands, not risk ratings. "Critical" is the highest
// win-probability band, so it is styled as the strongest accent, not as danger.
export function bandForProbability(probability: number): Band {
  if (probability >= 0.6) return "critical";
  if (probability >= 0.4) return "high";
  if (probability >= 0.2) return "medium";
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
    label: "Bassa",
    short: "Bassa",
    dot: "bg-[#98A2B3]",
    pill: "bg-[#F2F4F7] text-[#475467] ring-[#D0D5DD]",
    bar: "bg-[#98A2B3]",
    text: "text-[#475467]",
    hex: "#98A2B3",
  },
  medium: {
    label: "Media",
    short: "Media",
    dot: "bg-copper",
    pill: "bg-[#FDF1E3] text-[#8A3A06] ring-[#F5D0A9]",
    bar: "bg-copper",
    text: "text-[#8A3A06]",
    hex: "#B4693A",
  },
  high: {
    label: "Alta",
    short: "Alta",
    dot: "bg-accent",
    pill: "bg-[#CBE4FB] text-[#00499D] ring-[#A9C7FF]",
    bar: "bg-accent",
    text: "text-accent-deep",
    hex: "#005EB8",
  },
  critical: {
    // The contract calls the highest probability band "critical"; on screen
    // that reads as danger, so present it as the top band.
    label: "Top",
    short: "Top",
    dot: "bg-accent-deep",
    pill: "bg-accent text-paper ring-accent-deep",
    bar: "bg-accent-deep",
    text: "text-accent-deep",
    hex: "#00499D",
  },
};
