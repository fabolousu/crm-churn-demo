// Italian locale helpers (spec §14): dd/mm/yyyy HH:mm, Europe/Rome, Italian numbers.

const dateTime = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Rome",
});

const dateOnly = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Europe/Rome",
});

const number = new Intl.NumberFormat("it-IT");

/** `20/02/2026 10:45` */
export function formatDateTimeIt(iso: string): string {
  return dateTime.format(new Date(iso)).replace(",", "");
}

/** `20/02/2026` */
export function formatDateIt(iso: string): string {
  return dateOnly.format(new Date(iso));
}

/** `1.234` */
export function formatNumberIt(value: number): string {
  return number.format(value);
}

export function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}
