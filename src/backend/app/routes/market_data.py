from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from app.services.market_data import MarketDataService

router = APIRouter(
    prefix="/market-data",
    tags=["market-data"],
    responses={404: {"description": "Not found"}},
)

market_data_service = MarketDataService()


@router.get("/ticker/{ticker}")
def get_ticker_details(ticker: str):
    """
    Get details for a ticker symbol.
    """
    try:
        return market_data_service.get_ticker_details(ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching ticker details: {str(e)}")


@router.get("/price/{ticker}")
def get_stock_price(ticker: str):
    """
    Get the latest price for a stock.
    """
    try:
        price = market_data_service.get_stock_price(ticker)
        return {"ticker": ticker, "price": price}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stock price: {str(e)}")


@router.get("/option-chain/{ticker}")
def get_option_chain(
    ticker: str,
    expiration_date: Optional[str] = None
):
    """
    Get the option chain for a ticker.
    
    Args:
        ticker: Ticker symbol
        expiration_date: Option expiration date (YYYY-MM-DD)
    """
    try:
        # Convert expiration date string to datetime if provided
        exp_date = None
        if expiration_date:
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
        
        # Get option chain
        options = market_data_service.get_option_chain(ticker, exp_date)
        
        return {"ticker": ticker, "options": options}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching option chain: {str(e)}")


@router.get("/option-price/{option_symbol}")
def get_option_price(option_symbol: str):
    """
    Get the latest price for an option.
    
    Args:
        option_symbol: Option symbol (e.g., O:AAPL230616C00150000)
    """
    try:
        price_data = market_data_service.get_option_price(option_symbol)
        return {"symbol": option_symbol, **price_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching option price: {str(e)}")


@router.get("/historical-prices/{ticker}")
def get_historical_prices(
    ticker: str,
    from_date: str,
    to_date: Optional[str] = None,
    timespan: str = "day"
):
    """
    Get historical price data for a ticker.
    
    Args:
        ticker: Ticker symbol
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD), defaults to today
        timespan: Time interval (minute, hour, day, week, month, quarter, year)
    """
    try:
        # Convert date strings to datetime
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        
        if to_date:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        else:
            to_dt = datetime.now()
        
        # Get historical prices
        prices = market_data_service.get_historical_prices(
            ticker=ticker,
            from_date=from_dt,
            to_date=to_dt,
            timespan=timespan
        )
        
        return {
            "ticker": ticker,
            "from_date": from_date,
            "to_date": to_date or datetime.now().strftime("%Y-%m-%d"),
            "timespan": timespan,
            "prices": prices
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching historical prices: {str(e)}")


@router.get("/implied-volatility/{ticker}")
def get_implied_volatility(ticker: str):
    """
    Get the implied volatility for a ticker.
    """
    try:
        iv = market_data_service.get_implied_volatility(ticker)
        return {"ticker": ticker, "implied_volatility": iv}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching implied volatility: {str(e)}")


@router.get("/expirations/{ticker}")
def get_option_expirations(ticker: str):
    """
    Get available expiration dates for options on a ticker.
    """
    try:
        # Get option chain without specifying expiration
        options = market_data_service.get_option_chain(ticker)
        
        # Extract unique expiration dates
        expirations = set()
        for option in options:
            if "expiration_date" in option:
                expirations.add(option["expiration_date"])
        
        return {"ticker": ticker, "expirations": sorted(list(expirations))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching option expirations: {str(e)}")


@router.get("/strikes/{ticker}")
def get_option_strikes(
    ticker: str,
    expiration_date: str,
    option_type: Optional[str] = None
):
    """
    Get available strike prices for options on a ticker.
    
    Args:
        ticker: Ticker symbol
        expiration_date: Option expiration date (YYYY-MM-DD)
        option_type: Option type (call or put), if None, returns both
    """
    try:
        # Convert expiration date string to datetime
        exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
        
        # Get option chain for the specified expiration
        options = market_data_service.get_option_chain(ticker, exp_date)
        
        # Filter by option type if specified
        if option_type:
            options = [opt for opt in options if opt.get("type") == option_type]
        
        # Extract unique strike prices
        strikes = set()
        for option in options:
            if "strike_price" in option:
                strikes.add(option["strike_price"])
        
        return {
            "ticker": ticker,
            "expiration_date": expiration_date,
            "option_type": option_type,
            "strikes": sorted(list(strikes))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching option strikes: {str(e)}") 