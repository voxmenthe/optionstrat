"""
Options API Routes

This module provides API endpoints for retrieving option chain data.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from ..models.schemas import OptionContract, OptionExpiration
from ..services.option_chain_service import OptionChainService
from ..services.market_data import MarketDataService
from ..dependencies import get_option_chain_service, get_market_data_service
import logging

router = APIRouter(prefix="/options", tags=["options"])
logger = logging.getLogger(__name__)

@router.get("/search/{query}", response_model=List[str])
def search_ticker(
    query: str, 
    limit: int = 10,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """
    Search for ticker symbols.
    """
    logger.info(f"Received ticker search request for query: {query}, limit: {limit}")
    logger.info(f"Calling market_data_service.search_tickers with query: {query}")
    
    results = market_data_service.search_tickers(query)
    logger.info(f"Received results from market_data_service: {results}")
    
    # Limit results
    limited_results = results[:limit] if limit else results
    logger.info(f"Returning limited results: {limited_results}")
    
    return limited_results

@router.get("/chains/{ticker}/expirations", response_model=List[OptionExpiration])
def get_expirations(
    ticker: str,
    option_chain_service: OptionChainService = Depends(get_option_chain_service)
):
    """
    Get available expiration dates for a ticker.
    """
    logger.info(f"Getting expirations for ticker: {ticker}")
    try:
        expirations = option_chain_service.get_expirations(ticker)
        logger.info(f"Found {len(expirations)} expirations for {ticker}")
        
        # Get current date for days to expiration calculation
        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Convert to OptionExpiration objects with days to expiration
        result = []
        for exp in expirations:
            days_to_exp = (exp - current_date).days
            logger.info(f"Expiration: {exp}, days to expiration: {days_to_exp}")
            result.append(OptionExpiration(
                date=exp,
                formatted_date=exp.strftime("%Y-%m-%d"),
                days_to_expiration=days_to_exp
            ))
        
        return result
    except Exception as e:
        logger.error(f"Error getting expirations for {ticker}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting expirations: {str(e)}")

@router.get("/chains/{ticker}/{expiration_date}", response_model=List[OptionContract])
def get_options_for_expiration(
    ticker: str,
    expiration_date: str,
    option_type: Optional[str] = Query(None, pattern="^(call|put)$"),
    min_strike: Optional[float] = None,
    max_strike: Optional[float] = None,
    option_chain_service: OptionChainService = Depends(get_option_chain_service)
):
    """
    Get options chain for a specific expiration date.
    """
    logger.info(f"Getting options for ticker: {ticker}, expiration: {expiration_date}, type: {option_type}")
    
    try:
        # Parse the expiration date
        try:
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid expiration date format: {expiration_date}")
            raise HTTPException(status_code=400, detail="Invalid expiration date format. Use YYYY-MM-DD")
        
        # Get the option chain
        options = option_chain_service.get_option_chain(ticker, exp_date)
        logger.info(f"Found {len(options)} options for {ticker} expiring on {expiration_date}")
        
        # Apply filters
        filtered_options = options
        
        if option_type:
            filtered_options = [opt for opt in filtered_options 
                               if opt.get("option_type", "").lower() == option_type.lower()]
            
        if min_strike is not None:
            filtered_options = [opt for opt in filtered_options 
                               if opt.get("strike", 0) >= min_strike]
            
        if max_strike is not None:
            filtered_options = [opt for opt in filtered_options 
                               if opt.get("strike", 0) <= max_strike]
        
        logger.info(f"Returning {len(filtered_options)} options after filtering")
        return filtered_options
        
    except Exception as e:
        logger.error(f"Error getting options for {ticker} expiring on {expiration_date}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting options: {str(e)}")
