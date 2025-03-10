"""
Debug routes for the API.
Handles logging and debugging endpoints.
"""

import os
import logging
from fastapi import APIRouter, Body, Query, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List

# Create router
router = APIRouter(
    prefix="/debug",
    tags=["debug"],
    responses={404: {"description": "Not found"}},
)

# Set up logger
logger = logging.getLogger(__name__)

# Define log file paths
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
frontend_log_path = os.path.join(log_dir, 'frontend.log')
backend_log_path = os.path.join(log_dir, 'backend.log')

# Ensure log directory exists
os.makedirs(log_dir, exist_ok=True)


class LogRequest(BaseModel):
    """Model for log request body"""
    logs: str
    type: str = "frontend"


@router.post("/log")
async def log_message(log_request: LogRequest = Body(...)):
    """
    Log a message to the appropriate log file
    """
    try:
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Determine log file path
        if log_request.type == "frontend":
            log_file = frontend_log_path
        elif log_request.type == "backend":
            log_file = backend_log_path
        else:
            log_file = None
        
        if not log_file:
            return {"status": "error", "message": f"Invalid log type: {log_request.type}"}
        
        # Append to log file
        with open(log_file, "a") as f:
            f.write(f"{log_request.logs}\n")
        
        return {"status": "success", "message": "Log message recorded"}
    except Exception as e:
        logger.error(f"Error writing to log file: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/clear-logs")
async def clear_logs(type: str = Query("frontend")):
    """
    Clear the specified log file
    """
    try:
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Determine log file path
        if type == "frontend":
            log_file = frontend_log_path
        elif type == "backend":
            log_file = backend_log_path
        else:
            log_file = None
        
        if not log_file:
            return {"status": "error", "message": f"Invalid log type: {type}"}
        
        # Clear log file (open in write mode)
        with open(log_file, "w") as f:
            pass
        
        return {"status": "success", "message": f"{type} logs cleared"}
    except Exception as e:
        logger.error(f"Error clearing log file: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.get("/view-logs/{log_type}", response_class=PlainTextResponse)
async def view_logs(log_type: str, lines: int = Query(100)):
    """
    View the specified log file
    
    Args:
        log_type: Type of log to view (frontend or backend)
        lines: Number of lines to return from the end of the file
    """
    try:
        # Determine log file path
        if log_type == "frontend":
            log_file = frontend_log_path
        elif log_type == "backend":
            log_file = backend_log_path
        else:
            raise HTTPException(status_code=400, detail=f"Invalid log type: {log_type}")
        
        # Check if file exists
        if not os.path.exists(log_file):
            return f"Log file for {log_type} does not exist or is empty."
        
        # Read the last N lines from the file
        with open(log_file, "r") as f:
            # Read all lines and get the last 'lines' number of them
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return "".join(last_lines)
            
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")
