import os
import uvicorn
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file
load_dotenv()

# Set up logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configure the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Clear all handlers to ensure we don't duplicate logs
for handler in root_logger.handlers[:]: 
    root_logger.removeHandler(handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root_logger.addHandler(console_handler)

# File handler - overwrite on restart
backend_log_path = os.path.join(log_dir, 'backend.log')
file_handler = logging.FileHandler(backend_log_path, mode='w')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)
logger.info(f"Backend logging initialized. Log file: {backend_log_path}")

# Import routers
from app.routes import positions, greeks, scenarios, market_data, options, debug

# Create FastAPI app
app = FastAPI(
    title="OptionsStrat API",
    description="Backend API for Options Scenario Analysis & Exploration App",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins during development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint for health check
@app.get("/")
async def root():
    return {"status": "healthy", "message": "OptionsStrat API is running"}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Debug endpoint to help diagnose connectivity issues
@app.get("/debug")
async def debug_info(request: Request):
    return {
        "status": "debug",
        "headers": dict(request.headers),
        "client_host": request.client.host if request.client else None,
        "client_port": request.client.port if request.client else None,
        "method": request.method,
        "url": str(request.url),
        "cors_origins": app.state.cors_origins if hasattr(app.state, 'cors_origins') 
            else ["http://localhost:3000", "http://localhost:3003"],
        "server_port": os.environ.get("PORT", 8003)
    }

# Include routers
app.include_router(positions.router)
app.include_router(greeks.router)
app.include_router(scenarios.router)
app.include_router(market_data.router)
app.include_router(options.router)
app.include_router(debug.router)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=int(os.environ.get("PORT", 8003)), 
        reload=True
    )