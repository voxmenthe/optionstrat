from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import routers
from app.routes import positions, greeks, scenarios, market_data, options

# Create FastAPI app
app = FastAPI(
    title="OptionsStrat API",
    description="Backend API for Options Scenario Analysis & Exploration App",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3003"],  # Frontend URLs
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

# Include routers
app.include_router(positions.router)
app.include_router(greeks.router)
app.include_router(scenarios.router)
app.include_router(market_data.router)
app.include_router(options.router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8003)), reload=True) 