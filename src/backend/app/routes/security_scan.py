from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_market_data_service
from app.security_scan.indicator_workbench import (
    IndicatorDashboardComputeRequest,
    IndicatorDashboardComputeResponse,
    IndicatorMetadataListResponse,
    IndicatorWorkbenchError,
    compute_indicator_dashboard,
    list_indicator_metadata,
)
from app.services.market_data import MarketDataService

router = APIRouter(
    prefix="/security-scan",
    tags=["security-scan"],
    responses={404: {"description": "Not found"}},
)


@router.get("/indicators", response_model=IndicatorMetadataListResponse)
def get_security_scan_indicators() -> IndicatorMetadataListResponse:
    return list_indicator_metadata()


@router.post(
    "/indicator-dashboard/compute",
    response_model=IndicatorDashboardComputeResponse,
)
def compute_security_scan_indicator_dashboard(
    request: IndicatorDashboardComputeRequest,
    market_data_service: MarketDataService = Depends(get_market_data_service),
) -> IndicatorDashboardComputeResponse:
    try:
        return compute_indicator_dashboard(
            request=request,
            market_data_service=market_data_service,
        )
    except IndicatorWorkbenchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
