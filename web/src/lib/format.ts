import type { LeadStatus, Region, Source } from "./types";

export const REGIONS: Region[] = [
  "nord-ovest",
  "nord-est",
  "centro",
  "sud",
  "isole",
];

const REGION_LABELS: Record<Region, string> = {
  "nord-ovest": "Nord-Ovest",
  "nord-est": "Nord-Est",
  centro: "Centro",
  sud: "Sud",
  isole: "Isole",
};

const SOURCE_LABELS: Record<Source, string> = {
  inbound: "In entrata",
  outbound: "In uscita",
  referral: "Segnalazione",
  partner: "Partner",
  event: "Evento",
};

const STATUS_LABELS: Record<LeadStatus, string> = {
  new: "Nuovo",
  contacted: "Contattato",
  qualified: "Qualificato",
  proposal: "Proposta",
  won: "Vinta",
  lost: "Persa",
};

export const regionLabel = (r: Region) => REGION_LABELS[r];
export const sourceLabel = (s: Source) => SOURCE_LABELS[s];
// PipelineItem.status is a free-form string in the contract; lead statuses are
// an enum. Fall back to the raw value so an unexpected status is still legible.
export const statusLabel = (s: string) =>
  STATUS_LABELS[s as LeadStatus] ?? s;

const DRIVER_LABELS: Record<string, string> = {
  "Proposed ARR": "ARR proposto",
  "Referral partner": "Partner segnalatore",
};

export function driverLabel(label: string): string {
  return DRIVER_LABELS[label] ?? label;
}

export function formatEUR(value: number, fractionDigits = 0): string {
  const number = new Intl.NumberFormat("it-IT", {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(value);
  return `€${number}`;
}

// Intl's en-GB compact notation renders "€205.2m" and "€122.4k" in lower case.
// Executives read the pitch in uppercase units, so format them deliberately.
export function formatEURCompact(value: number): string {
  const sign = value < 0 ? "−" : "";
  const abs = Math.abs(value);
  const compact = (divisor: number, suffix: string) => {
    const scaled = abs / divisor;
    return `${sign}€${scaled.toFixed(1).replace(/\.0$/, "").replace(".", ",")}${suffix}`;
  };

  if (abs >= 1_000_000_000) return compact(1_000_000_000, "B");
  if (abs >= 1_000_000) return compact(1_000_000, "M");
  if (abs >= 1_000) return compact(1_000, "K");
  return `${sign}€${Math.round(abs)}`;
}

export function formatPercent(value: number, fractionDigits = 0): string {
  return new Intl.NumberFormat("it-IT", {
    style: "percent",
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(value);
}

export function formatPoints(value: number, digits = 1): string {
  const pts = value * 100;
  const sign = pts > 0 ? "+" : pts < 0 ? "−" : "";
  return `${sign}${Math.abs(pts).toFixed(digits).replace(".", ",")} pt`;
}

export function formatSignedEUR(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${formatEUR(Math.abs(value))}`;
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Rome",
  }).format(new Date(iso));
}

const LOST_REASON_LABELS: Record<string, string> = {
  price: "prezzo",
  no_budget: "budget assente",
  competitor: "concorrente",
  no_fit: "non adatto",
  timing: "tempi",
  silent: "nessuna risposta",
};

export function lostReasonLabel(reason: string | null): string {
  if (!reason) return "";
  return LOST_REASON_LABELS[reason] ?? reason;
}

const ACTION_KIND_LABELS: Record<string, string> = {
  call: "Telefonata",
  exec_sponsor_meeting: "Incontro con sponsor esecutivo",
  discovery_meeting: "Sessione di discovery",
  discount_review: "Revisione sconto",
};

export function actionKindLabel(kind: string): string {
  return ACTION_KIND_LABELS[kind] ?? kind;
}

export function formatOrdinal(rank: number): string {
  return String(rank).padStart(2, "0");
}

export function daysBetween(fromISO: string, toISO: string): number {
  const from = Date.parse(`${fromISO.slice(0, 10)}T00:00:00Z`);
  const to = Date.parse(`${toISO.slice(0, 10)}T00:00:00Z`);
  return Math.round((to - from) / 86_400_000);
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return count === 1 ? one : many;
}
