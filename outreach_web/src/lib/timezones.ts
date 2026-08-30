const FALLBACK_TIMEZONES = [
  "UTC",
  "Africa/Casablanca",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Phoenix",
  "America/Toronto",
  "Europe/London",
  "Europe/Paris",
  "Asia/Dubai",
];

type IntlWithTimeZones = typeof Intl & {
  supportedValuesOf?: (key: "timeZone") => string[];
};

export function supportedTimeZones(): string[] {
  const supported = (Intl as IntlWithTimeZones).supportedValuesOf?.("timeZone") ?? FALLBACK_TIMEZONES;
  return Array.from(new Set(["UTC", ...supported])).sort((left, right) => left.localeCompare(right));
}

function zonedParts(date: Date, timeZone: string): Record<string, string> {
  return Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(date)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value])
  );
}

export function toZonedDateTimeInput(value: string, timeZone: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  try {
    const parts = zonedParts(date, timeZone);
    return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
  } catch {
    return "";
  }
}

export function naiveDateTimePayload(value: string): string | null {
  if (!value) return null;
  return value.length === 16 ? `${value}:00` : value;
}

function wallTimeToUtc(value: string, timeZone: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [, year, month, day, hour, minute] = match;
  const wallClockAsUtc = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute)
  );
  let instant = wallClockAsUtc;
  try {
    for (let pass = 0; pass < 3; pass += 1) {
      const parts = zonedParts(new Date(instant), timeZone);
      const displayedAsUtc = Date.UTC(
        Number(parts.year),
        Number(parts.month) - 1,
        Number(parts.day),
        Number(parts.hour),
        Number(parts.minute),
        Number(parts.second)
      );
      instant = wallClockAsUtc - (displayedAsUtc - instant);
    }
    return new Date(instant);
  } catch {
    return null;
  }
}

export function formatViewerConversion(
  wallTime: string,
  campaignTimeZone: string,
  viewerTimeZone: string
): string | null {
  const instant = wallTimeToUtc(wallTime, campaignTimeZone);
  if (!instant) return null;
  try {
    return new Intl.DateTimeFormat("en", {
      timeZone: viewerTimeZone,
      dateStyle: "medium",
      timeStyle: "short",
    }).format(instant);
  } catch {
    return null;
  }
}

/** Resolve a campaign-local time, rejecting invalid dates and DST gaps. */
export function campaignWallTimeInstant(value: string, timeZone: string): Date | null {
  const instant = wallTimeToUtc(value, timeZone);
  return instant && toZonedDateTimeInput(instant.toISOString(), timeZone) === value ? instant : null;
}

export function formatTimeZoneLabel(timeZone: string): string {
  try {
    const zoneName = new Intl.DateTimeFormat("en", {
      timeZone,
      timeZoneName: "shortOffset",
    })
      .formatToParts(new Date())
      .find((part) => part.type === "timeZoneName")?.value;
    return zoneName ? `${timeZone} · ${zoneName}` : timeZone;
  } catch {
    return timeZone;
  }
}

/** Display a campaign day's window in the viewer's timezone, including date changes. */
export function formatViewerWindow(start: string, end: string, campaignZone: string, viewerZone: string) {
  const now = new Date();
  const day = toZonedDateTimeInput(now.toISOString(), campaignZone).slice(0, 10);
  const startInstant = wallTimeToUtc(`${day}T${start}`, campaignZone);
  const endInstant = wallTimeToUtc(`${day}T${end}`, campaignZone);
  if (!startInstant || !endInstant) return null;
  try {
    const time = new Intl.DateTimeFormat("en", { timeZone: viewerZone, hour: "numeric", minute: "2-digit" });
    const date = new Intl.DateTimeFormat("en", { timeZone: viewerZone, month: "short", day: "numeric" });
    const startDate = date.format(startInstant);
    const endDate = date.format(endInstant);
    return {
      range: `${time.format(startInstant)}–${time.format(endInstant)}`,
      date: startDate !== endDate ? `${startDate}–${endDate}` : startDate === date.format(now) ? "today" : startDate,
    };
  } catch { return null; }
}
