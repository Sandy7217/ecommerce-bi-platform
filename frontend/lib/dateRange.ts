export type DateRangePreset = "mtd" | "7" | "15" | "30" | "60" | "90" | "custom";

export type DateRangeValue = {
  preset: DateRangePreset;
  fromDate: string;
  toDate: string;
};

export const DATE_RANGE_PRESETS: { value: DateRangePreset; label: string }[] = [
  { value: "mtd", label: "MTD" },
  { value: "7", label: "7 days" },
  { value: "15", label: "15 days" },
  { value: "30", label: "30 days" },
  { value: "60", label: "60 days" },
  { value: "90", label: "90 days" },
  { value: "custom", label: "Custom" },
];

type SearchParamsLike = Record<string, string | string[] | undefined>;

function firstParam(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export function formatDateInput(date: Date) {
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 10);
}

export function presetDateRange(preset: Exclude<DateRangePreset, "custom">, today = new Date()): DateRangeValue {
  const end = new Date(today);

  if (preset === "mtd") {
    end.setDate(end.getDate() - 1);
    const start = new Date(end);
    start.setDate(1);
    return {
      preset,
      fromDate: formatDateInput(start),
      toDate: formatDateInput(end),
    };
  } else {
    const start = new Date(end);
    const days = Number(preset);
    start.setDate(end.getDate() - days + 1);
    return {
      preset,
      fromDate: formatDateInput(start),
      toDate: formatDateInput(end),
    };
  }
}

export function resolveDateRange(searchParams?: SearchParamsLike, today = new Date()): DateRangeValue {
  const rawPreset = firstParam(searchParams?.range);
  const rawFrom = firstParam(searchParams?.from_date);
  const rawTo = firstParam(searchParams?.to_date);
  const preset = DATE_RANGE_PRESETS.some((item) => item.value === rawPreset) ? (rawPreset as DateRangePreset) : "mtd";

  if (preset === "custom" && rawFrom && rawTo) {
    return { preset, fromDate: rawFrom, toDate: rawTo };
  }

  if (preset !== "custom") {
    return presetDateRange(preset, today);
  }

  return presetDateRange("mtd", today);
}

export function withDateRange(path: string, range: DateRangeValue) {
  const params = new URLSearchParams({
    from_date: range.fromDate,
    to_date: range.toDate,
  });
  return `${path}${path.includes("?") ? "&" : "?"}${params.toString()}`;
}
