from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import importlib
import math
from statistics import median
from typing import Any, Literal

import pandas as pd

from backend.services.sku_mapper import channel_code, is_myntra_channel


MIN_PROPHET_DAYS = 30
DEFAULT_HISTORY_DAYS = 30
DEFAULT_TRAINING_DAYS = 730
BACKTEST_DAYS = 30

ForecastModel = Literal["auto", "prophet", "sarimax", "arima", "baseline"]


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                pass
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def _num(value: Any) -> float:
    try:
        result = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(result) or math.isinf(result):
        return 0.0
    return result


def _qty(value: Any) -> float:
    return max(_num(value), 0.0)


def _source(row: dict[str, Any]) -> str:
    return str(row.get("source") or "").strip().lower()


def _myntra_family(row: dict[str, Any]) -> str | None:
    raw_channel = row.get("channel") or row.get("marketplace")
    code = channel_code(raw_channel)
    if code in {"MYNTRA", "MYNTRAPPMP"}:
        return "MYNTRAPPMP"
    if code in {"MYNTRASJIT", "MYNTRA SJIT", "SJIT"}:
        return "MYNTRASJIT"
    if is_myntra_channel(raw_channel):
        return "MYNTRAPPMP"
    return None


def _source_bucket(source: str) -> str:
    if source == "myntra_orders":
        return "myntra_orders"
    if source == "unicommerce":
        return "unicommerce"
    if source == "sales_master":
        return "sales_master"
    return "other"


def _source_label(bucket: str) -> str:
    return {
        "myntra_orders": "Myntra report",
        "unicommerce": "Unicommerce MYNTRAPPMP fallback",
        "sales_master": "Sales_Master fallback",
        "other": "Other Myntra source",
    }.get(bucket, bucket)


def _round_money(value: float) -> float:
    return round(max(value, 0.0), 2)


def _round_qty(value: float) -> int:
    return int(round(max(value, 0.0)))


def _add_sales_row(totals: dict[date, dict[str, float]], row: dict[str, Any]) -> None:
    day = _as_date(row.get("date"))
    if not day:
        return
    qty = _qty(row.get("qty") or 1)
    totals[day]["sales_value"] += _num(row.get("selling_price")) * max(qty, 1.0)
    totals[day]["sales_qty"] += qty


def _aggregate_daily_sales_with_metadata(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    totals: dict[date, dict[str, float]] = defaultdict(lambda: {"sales_value": 0.0, "sales_qty": 0.0})
    myntra_rows: dict[tuple[date, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        day = _as_date(row.get("date"))
        if not day:
            continue
        family = _myntra_family(row)
        if family:
            myntra_rows[(day, family)][_source_bucket(_source(row))].append(row)
            continue
        _add_sales_row(totals, row)

    source_dates: dict[str, set[str]] = defaultdict(set)
    for (day, _family), buckets in myntra_rows.items():
        for bucket in ("myntra_orders", "unicommerce", "sales_master", "other"):
            selected_rows = buckets.get(bucket)
            if not selected_rows:
                continue
            for row in selected_rows:
                _add_sales_row(totals, row)
            source_dates[bucket].add(day.isoformat())
            break

    source_counts = {_source_label(bucket): len(dates) for bucket, dates in sorted(source_dates.items())}
    source_summary = "; ".join(f"{label}: {count} dates" for label, count in source_counts.items()) or "No Myntra-family rows"
    return [
        {
            "date": day.isoformat(),
            "sales_value": _round_money(values["sales_value"]),
            "sales_qty": _round_qty(values["sales_qty"]),
        }
        for day, values in sorted(totals.items())
    ], {"myntra_source_used": source_summary, "myntra_source_counts": source_counts}


def aggregate_daily_sales(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _aggregate_daily_sales_with_metadata(rows)[0]


def aggregate_daily_returns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[date, dict[str, float]] = defaultdict(lambda: {"return_value": 0.0, "return_qty": 0.0})
    for row in rows:
        day = _as_date(row.get("date"))
        if not day:
            continue
        totals[day]["return_value"] += _num(row.get("return_value"))
        totals[day]["return_qty"] += _qty(row.get("qty"))
    return [
        {
            "date": day.isoformat(),
            "return_value": _round_money(values["return_value"]),
            "return_qty": _round_qty(values["return_qty"]),
        }
        for day, values in sorted(totals.items())
    ]


def _completed(rows: list[dict[str, Any]], as_of_date: date) -> list[dict[str, Any]]:
    completed_rows = []
    for row in rows:
        day = _as_date(row.get("date"))
        if day and day <= as_of_date:
            completed_rows.append(row)
    return sorted(completed_rows, key=lambda item: str(item["date"]))


def _series_values(rows: list[dict[str, Any]], metric: str) -> list[float]:
    return [_num(row.get(metric)) for row in rows if row.get(metric) is not None]


def _positive_series_values(rows: list[dict[str, Any]], metric: str) -> list[float]:
    return [_num(row.get(metric)) for row in rows if _num(row.get(metric)) > 0]


def _weighted_average(values: list[float]) -> float:
    if not values:
        return 0.0
    weights = list(range(1, len(values) + 1))
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def _date_range(start: date, end: date) -> list[date]:
    if end < start:
        return []
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _latest_row_date(rows: list[dict[str, Any]], cap: date) -> date | None:
    dates = [day for row in rows if (day := _as_date(row.get("date"))) and day <= cap]
    return max(dates) if dates else None


def _first_row_date(rows: list[dict[str, Any]]) -> date | None:
    dates = [day for row in rows if (day := _as_date(row.get("date")))]
    return min(dates) if dates else None


def _fill_calendar(rows: list[dict[str, Any]], start: date, end: date, metrics: tuple[str, ...]) -> list[dict[str, Any]]:
    by_date = {str(row.get("date")): row for row in rows if row.get("date")}
    filled: list[dict[str, Any]] = []
    for day in _date_range(start, end):
        key = day.isoformat()
        source = by_date.get(key, {})
        item: dict[str, Any] = {"date": key}
        for metric in metrics:
            item[metric] = _num(source.get(metric))
        filled.append(item)
    return filled


def _observed_days(rows: list[dict[str, Any]], metrics: tuple[str, ...]) -> int:
    return sum(1 for row in rows if any(_num(row.get(metric)) > 0 for metric in metrics))


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[int(index)]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def _recent_baseline(values: list[float]) -> float:
    recent = values[-28:] if len(values) > 28 else values
    if not recent:
        return 0.0
    med = median(recent)
    if med <= 0:
        return _weighted_average(recent)
    clipped = [min(value, med * 2.5) for value in recent]
    return _weighted_average(clipped)


def _guardrails(values: list[float], history: list[float]) -> list[float]:
    baseline = _recent_baseline(history)
    if baseline <= 0:
        return [max(value, 0.0) for value in values]
    recent = history[-60:] if len(history) > 60 else history
    q10 = _percentile(recent, 0.10)
    q90 = _percentile(recent, 0.90)
    lower = max(0.0, min(q10 * 0.75, baseline * 0.55))
    upper = max(q90 * 1.35, baseline * 1.55)
    return [min(max(value, lower), upper) for value in values]


def _weekday_factor(rows: list[dict[str, Any]], metric: str, weekday: int, overall: float) -> float:
    if overall <= 0:
        return 1.0
    same_weekday = [
        _num(row.get(metric))
        for row in rows[-120:]
        if (day := _as_date(row.get("date"))) and day.weekday() == weekday and _num(row.get(metric)) > 0
    ]
    if len(same_weekday) < 3:
        return 1.0
    factor = _recent_baseline(same_weekday) / overall
    return min(max(factor, 0.75), 1.25)


def _fallback_forecast(rows: list[dict[str, Any]], metric: str, start_date: date, horizon_days: int) -> list[float]:
    values = _series_values(rows, metric)
    baseline = _recent_baseline(values)
    if baseline <= 0:
        return [0.0] * horizon_days
    recent = values[-7:]
    previous = values[-14:-7]
    recent_avg = sum(recent) / len(recent) if recent else baseline
    previous_avg = sum(previous) / len(previous) if previous else recent_avg
    daily_growth = 0.0
    if previous_avg > 0 and recent_avg > 0:
        daily_growth = min(max((recent_avg - previous_avg) / previous_avg / 14, -0.012), 0.012)

    forecast = []
    for offset in range(horizon_days):
        future_day = start_date + timedelta(days=offset)
        factor = _weekday_factor(rows, metric, future_day.weekday(), baseline)
        value = baseline * factor * ((1 + daily_growth) ** offset)
        forecast.append(value)
    return _guardrails(forecast, values)


def _prophet_forecast(rows: list[dict[str, Any]], metric: str, start_date: date, horizon_days: int) -> list[float]:
    values = [(row["date"], _num(row.get(metric))) for row in rows if row.get(metric) is not None]
    if len(values) < MIN_PROPHET_DAYS or len(_positive_series_values(rows, metric)) < 7:
        raise RuntimeError("insufficient_history")
    prophet_module = importlib.import_module("prophet")
    prophet_class = getattr(prophet_module, "Prophet")
    frame = pd.DataFrame({"ds": [item[0] for item in values], "y": [item[1] for item in values]})
    yearly = len(frame) >= 365
    model = prophet_class(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=yearly,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.08,
        interval_width=0.8,
    )
    model.fit(frame)
    future = pd.DataFrame({"ds": pd.date_range(start=start_date, periods=horizon_days, freq="D")})
    predicted = model.predict(future)
    return _guardrails([_num(value) for value in predicted["yhat"].tolist()], [value for _day, value in values])


def _arima_forecast(rows: list[dict[str, Any]], metric: str, start_date: date, horizon_days: int) -> list[float]:
    values = [(row["date"], _num(row.get(metric))) for row in rows if row.get(metric) is not None]
    if len(values) < MIN_PROPHET_DAYS or len(_positive_series_values(rows, metric)) < 7:
        raise RuntimeError("insufficient_history")
    sarimax_module = importlib.import_module("statsmodels.tsa.statespace.sarimax")
    sarimax_class = getattr(sarimax_module, "SARIMAX")
    series = pd.Series(
        [item[1] for item in values],
        index=pd.to_datetime([item[0] for item in values]),
        dtype="float64",
    ).sort_index()
    series = series.asfreq("D")
    series = series.interpolate(method="time").ffill().bfill().clip(lower=0)
    seasonal_order = (1, 0, 1, 7) if len(series) >= 35 else (0, 0, 0, 0)
    model = sarimax_class(
        series,
        order=(1, 1, 1),
        seasonal_order=seasonal_order,
        trend="c",
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(disp=False, maxiter=100)
    predicted = fitted.forecast(steps=horizon_days)
    return _guardrails([_num(value) for value in predicted.tolist()], [value for _day, value in values])


def _model_forecast(method: str, rows: list[dict[str, Any]], metric: str, start_date: date, horizon_days: int) -> list[float]:
    if method == "prophet":
        return _prophet_forecast(rows, metric, start_date, horizon_days)
    if method in {"sarimax", "arima"}:
        return _arima_forecast(rows, metric, start_date, horizon_days)
    return _fallback_forecast(rows, metric, start_date, horizon_days)


def _wape(actual: list[float], predicted: list[float]) -> float:
    if not actual or not predicted:
        return 100.0
    numerator = sum(abs(left - right) for left, right in zip(actual, predicted))
    denominator = sum(abs(value) for value in actual)
    if denominator <= 0:
        return 0.0 if numerator <= 0 else 100.0
    return round(numerator * 100 / denominator, 2)


def _backtest_score(rows: list[dict[str, Any]], metric: str, method: str) -> float | None:
    positive_values = _positive_series_values(rows, metric)
    if len(rows) < 45 or len(positive_values) < 14:
        return None
    validation_days = min(BACKTEST_DAYS, max(7, len(rows) // 5))
    train_rows = rows[:-validation_days]
    validation_rows = rows[-validation_days:]
    if not train_rows or not validation_rows:
        return None
    last_train_day = _as_date(train_rows[-1].get("date"))
    if not last_train_day:
        return None
    try:
        predicted = _model_forecast(method, train_rows, metric, last_train_day + timedelta(days=1), validation_days)
    except Exception:
        return None
    actual = [_num(row.get(metric)) for row in validation_rows]
    return _wape(actual, predicted)


def _forecast_metric(
    rows: list[dict[str, Any]],
    metric: str,
    start_date: date,
    horizon_days: int,
    model: ForecastModel = "auto",
) -> tuple[list[float], str, float | None]:
    requested = "sarimax" if model == "arima" else model
    candidates = ["prophet", "sarimax", "baseline"] if requested == "auto" else [requested]
    scored: list[tuple[float, str]] = []
    for candidate in candidates:
        score = _backtest_score(rows, metric, candidate)
        if score is not None:
            scored.append((score, candidate))
    selected = min(scored, key=lambda item: item[0])[1] if scored else (requested if requested != "auto" else "baseline")
    score = min((item[0] for item in scored if item[1] == selected), default=None)
    try:
        return _model_forecast(selected, rows, metric, start_date, horizon_days), selected, score
    except Exception:
        return _fallback_forecast(rows, metric, start_date, horizon_days), "baseline", _backtest_score(rows, metric, "baseline")


def _combined_method(methods: set[str]) -> str:
    normalized = {"sarimax" if method == "arima" else "baseline" if method == "weighted_fallback" else method for method in methods}
    methods = normalized
    if methods == {"prophet"}:
        return "prophet"
    if methods == {"sarimax"}:
        return "sarimax"
    if "prophet" in methods and "sarimax" in methods:
        return "prophet_sarimax_with_baseline" if "baseline" in methods else "prophet_sarimax"
    if "prophet" in methods:
        return "prophet_with_baseline"
    if "sarimax" in methods:
        return "sarimax_with_baseline"
    if methods == {"arima"}:
        return "arima"
    if "arima" in methods:
        return "arima_with_fallback"
    return "baseline"


def _combined_score(scores: dict[str, float | None]) -> float | None:
    valid = [score for score in scores.values() if score is not None]
    if not valid:
        return None
    return round(sum(valid) / len(valid), 2)


def _confidence_level(sales_days: int, return_days: int, score: float | None) -> str:
    if sales_days < 60 or return_days < 30:
        return "Low"
    if score is None:
        return "Medium" if sales_days >= 180 else "Low"
    if sales_days >= 365 and return_days >= 180 and score <= 18:
        return "High"
    if score <= 35:
        return "Medium"
    return "Low"


def _band_pct(score: float | None, confidence: str) -> float:
    if score is None:
        return {"High": 0.10, "Medium": 0.18}.get(confidence, 0.30)
    return min(max(score / 100, 0.08), 0.35)


def _rate_baseline(rows: list[dict[str, Any]], numerator: str, denominator: str, lookback_days: int = 120) -> float | None:
    rates = [
        _num(row.get(numerator)) / _num(row.get(denominator))
        for row in rows[-lookback_days:]
        if _num(row.get(denominator)) > 0 and _num(row.get(numerator)) >= 0
    ]
    if not rates:
        return None
    clipped = [min(max(rate, 0.0), 0.85) for rate in rates]
    return _weighted_average(clipped)


def _blend_with_sales_linked_returns(
    independent: list[float],
    sales_forecast: list[float],
    rate: float | None,
    history: list[float],
) -> list[float]:
    if rate is None:
        return independent
    blended = []
    for return_value, sales_value in zip(independent, sales_forecast):
        linked = sales_value * rate
        blended.append((return_value * 0.55) + (linked * 0.45))
    return _guardrails(blended, history)


def _history_points(
    sales_history: list[dict[str, Any]],
    return_history: list[dict[str, Any]],
    history_days: int = DEFAULT_HISTORY_DAYS,
) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for row in sales_history[-history_days:]:
        by_date.setdefault(row["date"], {"date": row["date"], "sales_value": 0.0, "sales_qty": 0, "return_value": 0.0, "return_qty": 0})
        by_date[row["date"]]["sales_value"] = row["sales_value"]
        by_date[row["date"]]["sales_qty"] = row["sales_qty"]
    for row in return_history[-history_days:]:
        by_date.setdefault(row["date"], {"date": row["date"], "sales_value": 0.0, "sales_qty": 0, "return_value": 0.0, "return_qty": 0})
        by_date[row["date"]]["return_value"] = row["return_value"]
        by_date[row["date"]]["return_qty"] = row["return_qty"]
    result = []
    for day, row in sorted(by_date.items()):
        sales_value = _num(row["sales_value"])
        return_value = _num(row["return_value"])
        sales_qty = _qty(row["sales_qty"])
        return_qty = _qty(row["return_qty"])
        result.append(
            {
                "date": day,
                "sales_value": _round_money(sales_value),
                "sales_qty": _round_qty(sales_qty),
                "return_value": _round_money(return_value),
                "return_qty": _round_qty(return_qty),
                "net_sales": _round_money(sales_value - return_value),
                "return_pct": round(return_qty * 100 / max(sales_qty, 1), 2),
            }
        )
    return result


def build_sales_returns_forecast(
    sales_rows: list[dict[str, Any]],
    return_rows: list[dict[str, Any]],
    *,
    today: date | None = None,
    as_of_date: date | None = None,
    horizon_days: int = 30,
    history_days: int = DEFAULT_HISTORY_DAYS,
    training_requested_days: int = DEFAULT_TRAINING_DAYS,
    model: ForecastModel = "auto",
    include_diagnostics: bool = True,
) -> dict[str, Any]:
    today_date = today or date.today()
    horizon = min(max(int(horizon_days), 1), 90)
    training_days = min(max(int(training_requested_days or DEFAULT_TRAINING_DAYS), 32), DEFAULT_TRAINING_DAYS)
    daily_sales, sales_metadata = _aggregate_daily_sales_with_metadata(sales_rows)
    daily_returns = aggregate_daily_returns(return_rows)

    data_cap = today_date - timedelta(days=1)
    requested_cap = min(as_of_date, data_cap) if as_of_date else data_cap
    latest_sales_date = _latest_row_date(daily_sales, requested_cap)
    latest_return_date = _latest_row_date(daily_returns, requested_cap)
    effective_as_of = latest_sales_date or latest_return_date or requested_cap
    effective_as_of = min(effective_as_of, requested_cap)
    start_limit = effective_as_of - timedelta(days=training_days - 1)

    sales_observed = [row for row in _completed(daily_sales, effective_as_of) if (day := _as_date(row.get("date"))) and day >= start_limit]
    return_observed = [row for row in _completed(daily_returns, effective_as_of) if (day := _as_date(row.get("date"))) and day >= start_limit]
    first_sales_date = _first_row_date(sales_observed)
    first_return_date = _first_row_date(return_observed)
    history_start = min([item for item in [first_sales_date, first_return_date, start_limit] if item is not None])
    sales_history = _fill_calendar(sales_observed, history_start, effective_as_of, ("sales_value", "sales_qty"))
    return_history = _fill_calendar(return_observed, history_start, effective_as_of, ("return_value", "return_qty"))
    start_date = effective_as_of + timedelta(days=1)

    sales_values, sales_method, sales_score = _forecast_metric(sales_history, "sales_value", start_date, horizon, model)
    sales_qty_values, sales_qty_method, sales_qty_score = _forecast_metric(sales_history, "sales_qty", start_date, horizon, model)
    independent_return_values, return_method, return_score = _forecast_metric(return_history, "return_value", start_date, horizon, model)
    independent_return_qty_values, return_qty_method, return_qty_score = _forecast_metric(return_history, "return_qty", start_date, horizon, model)

    joined_history = _history_points(sales_history, return_history, len(sales_history))
    return_value_rate = _rate_baseline(joined_history, "return_value", "sales_value")
    return_qty_rate = _rate_baseline(joined_history, "return_qty", "sales_qty")
    return_values = _blend_with_sales_linked_returns(
        independent_return_values,
        sales_values,
        return_value_rate,
        _series_values(return_history, "return_value"),
    )
    return_qty_values = _blend_with_sales_linked_returns(
        independent_return_qty_values,
        sales_qty_values,
        return_qty_rate,
        _series_values(return_history, "return_qty"),
    )

    scores = {
        "sales_value": sales_score,
        "sales_qty": sales_qty_score,
        "return_value": return_score,
        "return_qty": return_qty_score,
    }
    combined_score = _combined_score(scores)
    sales_observed_days = _observed_days(sales_observed, ("sales_value", "sales_qty"))
    return_observed_days = _observed_days(return_observed, ("return_value", "return_qty"))
    confidence = _confidence_level(sales_observed_days, return_observed_days, combined_score)
    band_pct = _band_pct(combined_score, confidence)

    forecast = []
    for offset in range(horizon):
        sales_value = _round_money(sales_values[offset])
        return_value = _round_money(return_values[offset])
        sales_qty = _round_qty(sales_qty_values[offset])
        return_qty = _round_qty(return_qty_values[offset])
        sales_low = _round_money(sales_value * (1 - band_pct))
        sales_high = _round_money(sales_value * (1 + band_pct))
        return_low = _round_money(return_value * (1 - band_pct))
        return_high = _round_money(return_value * (1 + band_pct))
        forecast.append(
            {
                "date": (start_date + timedelta(days=offset)).isoformat(),
                "sales_value": sales_value,
                "sales_value_low": sales_low,
                "sales_value_high": sales_high,
                "sales_qty": sales_qty,
                "return_value": return_value,
                "return_value_low": return_low,
                "return_value_high": return_high,
                "return_qty": return_qty,
                "net_sales": _round_money(sales_value - return_value),
                "net_sales_low": _round_money(sales_low - return_high),
                "net_sales_high": _round_money(sales_high - return_low),
                "return_pct": round(return_qty * 100 / max(sales_qty, 1), 2),
            }
        )

    history = _history_points(sales_history, return_history, history_days)
    recent_history = history[-min(history_days, len(history)) :]
    recent_sales = sum(_num(row["sales_value"]) for row in recent_history)
    recent_returns = sum(_num(row["return_value"]) for row in recent_history)
    forecast_sales = sum(_num(row["sales_value"]) for row in forecast)
    forecast_returns = sum(_num(row["return_value"]) for row in forecast)
    forecast_sales_qty = sum(_qty(row["sales_qty"]) for row in forecast)
    forecast_return_qty = sum(_qty(row["return_qty"]) for row in forecast)

    selected_models = {
        "sales_value": sales_method,
        "sales_qty": sales_qty_method,
        "return_value": f"{return_method}+sales_linked_rate" if return_value_rate is not None else return_method,
        "return_qty": f"{return_qty_method}+sales_linked_rate" if return_qty_rate is not None else return_qty_method,
    }
    methods = {sales_method, sales_qty_method, return_method, return_qty_method}
    method = _combined_method(methods)
    history_dates = [row["date"] for row in history]
    result = {
        "history": history,
        "forecast": forecast,
        "summary": {
            "recent_sales_value": _round_money(recent_sales),
            "recent_return_value": _round_money(recent_returns),
            "forecast_sales_value": _round_money(forecast_sales),
            "forecast_return_value": _round_money(forecast_returns),
            "forecast_net_sales": _round_money(forecast_sales - forecast_returns),
            "forecast_sales_qty": _round_qty(forecast_sales_qty),
            "forecast_return_qty": _round_qty(forecast_return_qty),
            "forecast_return_pct": round(forecast_return_qty * 100 / max(forecast_sales_qty, 1), 2),
            "history_start": history_dates[0] if history_dates else None,
            "history_end": history_dates[-1] if history_dates else None,
            "as_of_date": effective_as_of.isoformat(),
            "forecast_start_date": start_date.isoformat(),
            "training_requested_days": training_days,
            "training_calendar_days": len(sales_history),
            "sales_training_days": sales_observed_days,
            "return_training_days": return_observed_days,
            "myntra_source_used": sales_metadata["myntra_source_used"],
            "selected_models": selected_models,
            "backtest_wape": combined_score,
            "backtest_wape_by_metric": scores,
            "confidence_level": confidence,
            "return_value_rate": round(return_value_rate * 100, 2) if return_value_rate is not None else None,
            "return_qty_rate": round(return_qty_rate * 100, 2) if return_qty_rate is not None else None,
            "excluded_current_day": today_date.isoformat(),
        },
        "method": method,
        "model": "Auto-selected Prophet/SARIMAX/baseline with rolling backtest, sales-linked return rate, and confidence bands",
        "horizon_days": horizon,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    if include_diagnostics:
        result["diagnostics"] = {
            "latest_sales_date": latest_sales_date.isoformat() if latest_sales_date else None,
            "latest_return_date": latest_return_date.isoformat() if latest_return_date else None,
            "myntra_source_counts": sales_metadata["myntra_source_counts"],
            "band_pct": round(band_pct * 100, 2),
        }
    return result
