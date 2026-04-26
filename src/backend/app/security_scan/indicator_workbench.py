from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.security_scan.data_fetcher import MarketDataFetcher
from app.security_scan.indicator_adapters import (
    IndicatorDashboardAdapter,
    IndicatorDataError,
    IndicatorDashboardInput,
    IndicatorPanel,
    IndicatorParameter,
    IndicatorSettingsError,
    IndicatorTrace,
    TracePoint,
    get_dashboard_adapters,
)
from app.services.market_data import MarketDataService


class IndicatorWorkbenchError(Exception):
    status_code = 400


class IndicatorNotFoundError(IndicatorWorkbenchError):
    status_code = 404


class IndicatorNoDataError(IndicatorWorkbenchError):
    status_code = 404


class IndicatorSettingsValidationError(IndicatorWorkbenchError):
    status_code = 422


class IndicatorParameterResponse(BaseModel):
    key: str
    label: str
    type: str
    default: Any
    required: bool = True
    min: int | float | None = None
    max: int | float | None = None
    description: str | None = None
    item_type: str | None = None


class IndicatorMetadataResponse(BaseModel):
    id: str
    label: str
    description: str
    default_settings: dict[str, Any]
    parameters: list[IndicatorParameterResponse]
    requires_benchmarks: bool
    supported_intervals: list[str]


class IndicatorMetadataListResponse(BaseModel):
    indicators: list[IndicatorMetadataResponse]


class IndicatorDashboardComputeRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    indicator_id: str = Field(..., min_length=1)
    settings: dict[str, Any] = Field(default_factory=dict)
    start_date: date
    end_date: date
    interval: Literal["day"] = "day"
    benchmark_tickers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not ticker:
            raise ValueError("ticker must be a non-empty symbol")
        return ticker

    @field_validator("indicator_id")
    @classmethod
    def normalize_indicator_id(cls, value: str) -> str:
        indicator_id = value.strip().lower()
        if not indicator_id:
            raise ValueError("indicator_id must be non-empty")
        return indicator_id

    @field_validator("benchmark_tickers")
    @classmethod
    def normalize_benchmark_tickers(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            ticker = value.strip().upper()
            if ticker:
                normalized.append(ticker)
        return normalized

    @model_validator(mode="after")
    def validate_date_order(self) -> "IndicatorDashboardComputeRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class DateRangeResponse(BaseModel):
    start_date: date
    end_date: date
    interval: str


class SeriesPointResponse(BaseModel):
    date: str
    value: float


class PriceSeriesResponse(BaseModel):
    label: str
    points: list[SeriesPointResponse]


class IndicatorTraceResponse(BaseModel):
    key: str
    label: str
    points: list[SeriesPointResponse]
    color: str | None = None


class IndicatorPanelResponse(BaseModel):
    id: str
    label: str
    traces: list[IndicatorTraceResponse]
    reference_lines: list[float] = Field(default_factory=list)


class IndicatorPanelGroupResponse(BaseModel):
    panels: list[IndicatorPanelResponse]


class IndicatorDashboardSignalResponse(BaseModel):
    date: str
    type: str
    label: str
    target_trace: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndicatorDashboardDiagnosticsResponse(BaseModel):
    price_points: int
    indicator_points: int
    benchmark_tickers_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class IndicatorDashboardComputeResponse(BaseModel):
    ticker: str
    indicator_id: str
    resolved_settings: dict[str, Any]
    date_range: DateRangeResponse
    price: PriceSeriesResponse
    indicator: IndicatorPanelGroupResponse
    signals: list[IndicatorDashboardSignalResponse]
    diagnostics: IndicatorDashboardDiagnosticsResponse


def _parameter_to_response(
    parameter: IndicatorParameter,
) -> IndicatorParameterResponse:
    return IndicatorParameterResponse(
        key=parameter.key,
        label=parameter.label,
        type=parameter.type,
        default=parameter.default,
        required=parameter.required,
        min=parameter.min,
        max=parameter.max,
        description=parameter.description,
        item_type=parameter.item_type,
    )


def _adapter_to_metadata(
    adapter: IndicatorDashboardAdapter,
) -> IndicatorMetadataResponse:
    return IndicatorMetadataResponse(
        id=adapter.id,
        label=adapter.label,
        description=adapter.description,
        default_settings=dict(adapter.default_settings),
        parameters=[
            _parameter_to_response(parameter) for parameter in adapter.parameters
        ],
        requires_benchmarks=adapter.requires_benchmarks,
        supported_intervals=list(adapter.supported_intervals),
    )


def list_indicator_metadata() -> IndicatorMetadataListResponse:
    adapters = get_dashboard_adapters()
    return IndicatorMetadataListResponse(
        indicators=[_adapter_to_metadata(adapter) for adapter in adapters.values()]
    )


def _resolve_adapter(indicator_id: str) -> IndicatorDashboardAdapter:
    adapter = get_dashboard_adapters().get(indicator_id)
    if adapter is None:
        raise IndicatorNotFoundError(f"Unsupported dashboard indicator: {indicator_id}")
    return adapter


def _date_range_to_datetimes(start: date, end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end + timedelta(days=1), time.min)
    return start_dt, end_dt


def _resolve_requested_benchmark_tickers(
    adapter: IndicatorDashboardAdapter,
    request_benchmark_tickers: list[str],
) -> list[str]:
    if not adapter.requires_benchmarks:
        return []

    tickers = request_benchmark_tickers or list(adapter.default_benchmark_tickers)
    if adapter.required_benchmark_count is not None and len(tickers) != adapter.required_benchmark_count:
        raise IndicatorSettingsValidationError(
            f"{adapter.id} requires exactly {adapter.required_benchmark_count} benchmark tickers."
        )

    unique_tickers: list[str] = []
    for ticker in tickers:
        if ticker not in unique_tickers:
            unique_tickers.append(ticker)

    if adapter.required_benchmark_count is not None and len(unique_tickers) != adapter.required_benchmark_count:
        raise IndicatorSettingsValidationError(
            f"{adapter.id} requires {adapter.required_benchmark_count} unique benchmark tickers."
        )

    return unique_tickers


def _price_points_from_prices(
    prices: list[dict[str, Any]],
) -> list[SeriesPointResponse]:
    points: list[SeriesPointResponse] = []
    for row in sorted(prices, key=lambda item: item.get("date") or ""):
        row_date = row.get("date")
        close = row.get("close")
        if not row_date or close is None:
            continue
        points.append(SeriesPointResponse(date=str(row_date), value=float(close)))
    return points


def _trace_point_to_response(point: TracePoint) -> SeriesPointResponse:
    return SeriesPointResponse(date=point.date, value=point.value)


def _trace_to_response(trace: IndicatorTrace) -> IndicatorTraceResponse:
    return IndicatorTraceResponse(
        key=trace.key,
        label=trace.label,
        points=[_trace_point_to_response(point) for point in trace.points],
        color=trace.color,
    )


def _panel_to_response(panel: IndicatorPanel) -> IndicatorPanelResponse:
    return IndicatorPanelResponse(
        id=panel.id,
        label=panel.label,
        traces=[_trace_to_response(trace) for trace in panel.traces],
        reference_lines=list(panel.reference_lines),
    )


def compute_indicator_dashboard(
    request: IndicatorDashboardComputeRequest,
    market_data_service: MarketDataService,
) -> IndicatorDashboardComputeResponse:
    adapter = _resolve_adapter(request.indicator_id)
    if request.interval not in adapter.supported_intervals:
        supported = ", ".join(adapter.supported_intervals)
        raise IndicatorSettingsValidationError(
            f"{adapter.id} supports intervals: {supported}"
        )

    fetcher = MarketDataFetcher(market_data_service=market_data_service)
    start_dt, end_dt = _date_range_to_datetimes(request.start_date, request.end_date)
    prices = fetcher.fetch_historical_prices(
        ticker=request.ticker,
        start_date=start_dt,
        end_date=end_dt,
        interval=request.interval,
    )
    price_points = _price_points_from_prices(prices)
    if not price_points:
        raise IndicatorNoDataError(
            f"No usable historical close prices found for {request.ticker}."
        )

    resolved_benchmark_tickers = _resolve_requested_benchmark_tickers(
        adapter,
        request.benchmark_tickers,
    )
    benchmark_prices_by_ticker: dict[str, list[dict[str, Any]]] = {}
    if adapter.requires_benchmarks:
        for benchmark_ticker in resolved_benchmark_tickers:
            benchmark_prices = fetcher.fetch_historical_prices(
                ticker=benchmark_ticker,
                start_date=start_dt,
                end_date=end_dt,
                interval=request.interval,
            )
            if not _price_points_from_prices(benchmark_prices):
                raise IndicatorNoDataError(
                    f"No usable historical close prices found for benchmark {benchmark_ticker}."
                )
            benchmark_prices_by_ticker[benchmark_ticker] = benchmark_prices

    try:
        adapter_output = adapter.compute(
            IndicatorDashboardInput(
                ticker=request.ticker,
                prices=prices,
                settings=request.settings,
                benchmark_tickers=resolved_benchmark_tickers,
                benchmark_prices_by_ticker=benchmark_prices_by_ticker,
            )
        )
    except IndicatorSettingsError as exc:
        raise IndicatorSettingsValidationError(str(exc)) from exc
    except IndicatorDataError as exc:
        raise IndicatorNoDataError(str(exc)) from exc

    diagnostics = dict(adapter_output.diagnostics)
    diagnostics.setdefault("price_points", len(price_points))
    diagnostics.setdefault("indicator_points", 0)
    diagnostics.setdefault("benchmark_tickers_used", list(resolved_benchmark_tickers))
    diagnostics.setdefault("warnings", [])

    return IndicatorDashboardComputeResponse(
        ticker=request.ticker,
        indicator_id=adapter.id,
        resolved_settings=adapter_output.resolved_settings,
        date_range=DateRangeResponse(
            start_date=request.start_date,
            end_date=request.end_date,
            interval=request.interval,
        ),
        price=PriceSeriesResponse(
            label=f"{request.ticker} Close",
            points=price_points,
        ),
        indicator=IndicatorPanelGroupResponse(
            panels=[_panel_to_response(panel) for panel in adapter_output.panels]
        ),
        signals=[
            IndicatorDashboardSignalResponse(
                date=signal.date,
                type=signal.type,
                label=signal.label,
                target_trace=signal.target_trace,
                metadata=dict(signal.metadata),
            )
            for signal in adapter_output.signals
        ],
        diagnostics=IndicatorDashboardDiagnosticsResponse(**diagnostics),
    )


__all__ = [
    "IndicatorDashboardComputeRequest",
    "IndicatorDashboardComputeResponse",
    "IndicatorMetadataListResponse",
    "IndicatorNoDataError",
    "IndicatorNotFoundError",
    "IndicatorSettingsValidationError",
    "IndicatorWorkbenchError",
    "compute_indicator_dashboard",
    "list_indicator_metadata",
]
