"""
Options API Routes

This module provides routes for retrieving options chain data, expirations, and options information.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict
from datetime import datetime, date
import logging
from dateutil import parser

from app.services.market_data import MarketDataService
from app.services.option_pricing import OptionPricer

router = APIRouter(
    prefix="/options",
    tags=["options"],
    responses={404: {"description": "Not found"}},
)

# Dependency functions
def get_market_data_service():
    """Dependency to get the market data service."""
    return MarketDataService()

def get_option_pricer():
    """Dependency to get the option pricer service."""
    return OptionPricer()

@router.get("/chains/{ticker}", response_model=List[Dict])
async def get_options_chain(
    ticker: str,
    expiration_date: Optional[str] = None,
    option_type: Optional[str] = Query(None, regex="^(call|put)$"),
    min_strike: Optional[float] = None,
    max_strike: Optional[float] = None,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """
    Get options chain data for a ticker.
    
    Args:
        ticker: The ticker symbol
        expiration_date: Optional expiration date filter in ISO format (YYYY-MM-DD)
        option_type: Optional filter for option type ('call' or 'put')
        min_strike: Optional minimum strike price filter
        max_strike: Optional maximum strike price filter
        
    Returns:
        List of option contracts
    """
    try:
        # Validate and parse expiration_date if provided
        exp_date = None
        if expiration_date:
            try:
                exp_date = parser.parse(expiration_date).date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid expiration date format")
        
        # Fetch option chain data from market data service
        option_chain = market_data_service.get_option_chain(
            ticker=ticker,
            expiration_date=exp_date
        )
        
        # Apply filters if provided
        filtered_chain = []
        for option in option_chain:
            # Check option type filter
            if option_type and option.get("option_type") != option_type:
                continue
                
            # Check strike price range filters
            strike = option.get("strike")
            if min_strike is not None and strike < min_strike:
                continue
            if max_strike is not None and strike > max_strike:
                continue
                
            filtered_chain.append(option)
        
        return filtered_chain
        
    except Exception as e:
        logging.error(f"Error fetching options chain for {ticker}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error fetching options chain: {str(e)}"
        )

@router.get("/chains/{ticker}/expirations", response_model=List[Dict])
async def get_expiration_dates(
    ticker: str,
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """
    Get available expiration dates for options on a ticker.
    
    Args:
        ticker: The ticker symbol
        
    Returns:
        List of expiration dates
    """
    try:
        # Fetch expiration dates from market data service
        expirations = market_data_service.get_option_expirations(ticker)
        
        # Format response
        formatted_expirations = []
        for exp_date in expirations:
            formatted_expirations.append({
                "date": exp_date.isoformat(),
                "formatted_date": exp_date.strftime("%b %d, %Y")
            })
        
        return formatted_expirations
        
    except Exception as e:
        logging.error(f"Error fetching expiration dates for {ticker}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error fetching expiration dates: {str(e)}"
        )

@router.get("/chains/{ticker}/{expiration_date}", response_model=List[Dict])
async def get_options_for_expiration(
    ticker: str,
    expiration_date: str,
    option_type: Optional[str] = Query(None, regex="^(call|put)$"),
    min_strike: Optional[float] = None,
    max_strike: Optional[float] = None,
    market_data_service: MarketDataService = Depends(get_market_data_service),
    option_pricer: OptionPricer = Depends(get_option_pricer)
):
    """
    Get options for a specific ticker and expiration date.
    
    Args:
        ticker: The ticker symbol
        expiration_date: Expiration date in ISO format (YYYY-MM-DD)
        option_type: Optional filter for option type ('call' or 'put')
        min_strike: Optional minimum strike price filter
        max_strike: Optional maximum strike price filter
        
    Returns:
        List of option contracts for the specified expiration date
    """
    try:
        # Parse expiration date
        try:
            exp_date = parser.parse(expiration_date).date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid expiration date format")
        
        # Get the current stock price
        stock_price = market_data_service.get_stock_price(ticker)
        
        # Get options chain for this expiration
        option_chain = market_data_service.get_option_chain(
            ticker=ticker,
            expiration_date=exp_date
        )
        
        # Apply filters and add additional data
        filtered_chain = []
        for option in option_chain:
            # Check option type filter
            if option_type and option.get("option_type") != option_type:
                continue
                
            # Check strike price range filters
            strike = option.get("strike")
            if min_strike is not None and strike < min_strike:
                continue
            if max_strike is not None and strike > max_strike:
                continue
            
            # Add underlying price to each option
            option["underlying_price"] = stock_price
            
            # Check if option is in-the-money
            is_call = option.get("option_type") == "call"
            option["in_the_money"] = (is_call and stock_price > strike) or (not is_call and stock_price < strike)
            
            # If Greeks are missing, calculate them
            if not all(key in option for key in ["delta", "gamma", "theta", "vega", "rho"]):
                try:
                    # Use default volatility or get from market data if available
                    volatility = option.get("implied_volatility", 0.3)
                    
                    # Calculate option Greeks
                    greeks = option_pricer.price_option(
                        option_type=option.get("option_type"),
                        strike=strike,
                        expiration_date=exp_date,
                        spot_price=stock_price,
                        volatility=volatility
                    )
                    
                    # Add Greeks to option data
                    option["delta"] = greeks.get("delta")
                    option["gamma"] = greeks.get("gamma")
                    option["theta"] = greeks.get("theta")
                    option["vega"] = greeks.get("vega")
                    option["rho"] = greeks.get("rho")
                except Exception as e:
                    logging.warning(f"Error calculating Greeks for {ticker} option: {str(e)}")
            
            filtered_chain.append(option)
        
        return filtered_chain
        
    except Exception as e:
        logging.error(f"Error fetching options for {ticker} with expiration {expiration_date}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error fetching options: {str(e)}"
        )

@router.get("/search/{query}", response_model=List[str])
async def search_tickers(
    query: str,
    limit: int = Query(10, ge=1, le=100),
    market_data_service: MarketDataService = Depends(get_market_data_service)
):
    """
    Search for ticker symbols matching a query.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        
    Returns:
        List of matching ticker symbols
    """
    try:
        # Search for tickers using market data service
        results = market_data_service.search_tickers(query)
        
        # Limit results if necessary
        return results[:limit] if limit < len(results) else results
        
    except Exception as e:
        logging.error(f"Error searching tickers with query {query}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error searching tickers: {str(e)}"
        )
