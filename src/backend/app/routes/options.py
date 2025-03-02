"""
Options API Routes

This module provides API endpoints for retrieving option chain data.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from app.models.database import get_db
from app.models.schemas import OptionContract, OptionExpiration
from app.services.option_chain_service import OptionChainService
from app.services.market_data import MarketDataService

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/options",
    tags=["options"],
    responses={404: {"description": "Not found"}},
)

# Dependency functions
def get_option_chain_service():
    """Dependency to get the option chain service."""
    market_data_service = MarketDataService()
    return OptionChainService(market_data_service)

@router.get("/chains/{ticker}", response_model=List[OptionContract])
def get_options_chain(
    ticker: str,
    expiration_date: Optional[str] = None,
    option_type: Optional[str] = Query(None, regex="^(call|put)$"),
    min_strike: Optional[float] = None,
    max_strike: Optional[float] = None,
    db: Session = Depends(get_db),
    option_chain_service: OptionChainService = Depends(get_option_chain_service)
):
    """
    Get options chain for a ticker with optional filtering.
    
    Args:
        ticker: Ticker symbol
        expiration_date: Optional expiration date in YYYY-MM-DD format
        option_type: Optional option type filter ('call' or 'put')
        min_strike: Optional minimum strike price filter
        max_strike: Optional maximum strike price filter
        
    Returns:
        List of option contracts
    """
    try:
        # Convert expiration_date string to datetime if provided
        exp_date = None
        if expiration_date:
            try:
                exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid expiration date format: {expiration_date}. Use YYYY-MM-DD format."
                )
        
        # Get option chain
        option_chain = option_chain_service.get_option_chain(
            ticker, 
            exp_date, 
            option_type,
            min_strike,
            max_strike
        )
        
        return option_chain
    except Exception as e:
        logger.error(f"Error fetching option chain: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve option chain: {str(e)}"
        )

@router.get("/chains/{ticker}/expirations", response_model=List[OptionExpiration])
def get_option_expirations(
    ticker: str,
    db: Session = Depends(get_db),
    option_chain_service: OptionChainService = Depends(get_option_chain_service)
):
    """
    Get available expiration dates for options on a ticker.
    
    Args:
        ticker: Ticker symbol
        
    Returns:
        List of expiration dates with metadata
    """
    try:
        # Get expiration dates
        expirations = option_chain_service.get_expirations(ticker)
        
        # Format the response
        formatted_expirations = [
            {"date": exp, "formatted_date": exp.strftime("%Y-%m-%d")}
            for exp in expirations
        ]
        
        return formatted_expirations
    except Exception as e:
        logger.error(f"Error fetching option expirations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve option expirations: {str(e)}"
        )

@router.get("/chains/{ticker}/{expiration_date}", response_model=List[OptionContract])
def get_options_for_expiration(
    ticker: str,
    expiration_date: str,
    option_type: Optional[str] = Query(None, regex="^(call|put)$"),
    min_strike: Optional[float] = None,
    max_strike: Optional[float] = None,
    db: Session = Depends(get_db),
    option_chain_service: OptionChainService = Depends(get_option_chain_service)
):
    """
    Get options for a specific ticker and expiration date with optional filtering.
    
    Args:
        ticker: Ticker symbol
        expiration_date: Expiration date in YYYY-MM-DD format
        option_type: Optional option type filter ('call' or 'put')
        min_strike: Optional minimum strike price filter
        max_strike: Optional maximum strike price filter
        
    Returns:
        List of option contracts
    """
    try:
        # Convert expiration_date string to datetime
        try:
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid expiration date format: {expiration_date}. Use YYYY-MM-DD format."
            )
        
        # Get option chain for specific expiration
        option_chain = option_chain_service.get_option_chain(
            ticker, 
            exp_date, 
            option_type,
            min_strike,
            max_strike
        )
        
        return option_chain
    except Exception as e:
        logger.error(f"Error fetching options for expiration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve options for expiration: {str(e)}"
        )

@router.get("/search/{query}", response_model=List[str])
def search_tickers(
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db),
    market_data_service: MarketDataService = Depends(lambda: MarketDataService())
):
    """
    Search for ticker symbols matching a query.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        
    Returns:
        List of matching ticker symbols with basic metadata
    """
    try:
        # Search for tickers
        results = market_data_service.search_tickers(query)
        
        # Limit the number of results
        limited_results = results[:limit] if limit else results
        
        return limited_results
    except Exception as e:
        logger.error(f"Error searching tickers: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search tickers: {str(e)}"
        )
