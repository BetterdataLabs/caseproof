const relativeTimeFormatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const dateTimeFormatter = new Intl.DateTimeFormat("en-SG", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const timeFormatter = new Intl.DateTimeFormat("en-SG", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});
const amountFormatter = new Intl.NumberFormat("en-SG", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const diff = Math.round((t - now) / 1000);
  const abs = Math.abs(diff);
  if (abs < 45) return diff < 0 ? "just now" : "in a few seconds";
  if (abs < 3600) return relativeTimeFormatter.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return relativeTimeFormatter.format(Math.round(diff / 3600), "hour");
  return relativeTimeFormatter.format(Math.round(diff / 86400), "day");
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return dateTimeFormatter.format(new Date(iso));
}

export function timeOnly(iso: string | null | undefined): string {
  if (!iso) return "—";
  return timeFormatter.format(new Date(iso));
}

export function sgd(value: unknown): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value ?? "—");
  return "SGD " + amountFormatter.format(n);
}

export function usd(value: unknown, digits = 4): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return "USD " + n.toFixed(digits);
}

export function humanize(code: string | null | undefined): string {
  if (!code) return "";
  return code
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/^\w/, (c) => c.toUpperCase());
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export function bytes(n: number | null | undefined): string {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
