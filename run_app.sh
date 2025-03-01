#!/bin/bash

# Options Scenario Analysis & Exploration App Startup Script
# This script starts both the backend and frontend servers

# Set colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== OptionsStrat App Startup ===${NC}"

# Check for and kill existing processes using the required ports
echo -e "${YELLOW}Checking for existing processes on ports 8003 and 3003...${NC}"

# For macOS (darwin)
if [[ "$OSTYPE" == "darwin"* ]]; then
  BACKEND_PID=$(lsof -ti:8003)
  FRONTEND_PID=$(lsof -ti:3003)
  
  if [ ! -z "$BACKEND_PID" ]; then
    echo -e "${YELLOW}Killing existing process on port 8003 (PID: $BACKEND_PID)${NC}"
    kill -9 $BACKEND_PID
  fi
  
  if [ ! -z "$FRONTEND_PID" ]; then
    echo -e "${YELLOW}Killing existing process on port 3003 (PID: $FRONTEND_PID)${NC}"
    kill -9 $FRONTEND_PID
  fi
# For Linux
else
  BACKEND_PID=$(netstat -tulpn 2>/dev/null | grep 8003 | awk '{print $7}' | cut -d'/' -f1)
  FRONTEND_PID=$(netstat -tulpn 2>/dev/null | grep 3003 | awk '{print $7}' | cut -d'/' -f1)
  
  if [ ! -z "$BACKEND_PID" ]; then
    echo -e "${YELLOW}Killing existing process on port 8003 (PID: $BACKEND_PID)${NC}"
    kill -9 $BACKEND_PID
  fi
  
  if [ ! -z "$FRONTEND_PID" ]; then
    echo -e "${YELLOW}Killing existing process on port 3003 (PID: $FRONTEND_PID)${NC}"
    kill -9 $FRONTEND_PID
  fi
fi

# Small delay to ensure ports are released
sleep 1

# Check if python-dotenv is installed
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! pip list | grep -q python-dotenv; then
  echo -e "${YELLOW}Installing python-dotenv...${NC}"
  pip install python-dotenv
fi

# Start the backend server
echo -e "${YELLOW}Starting backend server on port 8003...${NC}"
cd src/backend
python -m app.main &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${YELLOW}Waiting for backend to initialize...${NC}"
sleep 5

# Check if backend is running
if ps -p $BACKEND_PID > /dev/null; then
  echo -e "${GREEN}Backend server started successfully!${NC}"
else
  echo -e "${RED}Failed to start backend server. Please check for errors.${NC}"
  exit 1
fi

# Start the frontend server
echo -e "${YELLOW}Starting frontend server on port 3003...${NC}"
cd ../frontend
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
echo -e "${YELLOW}Waiting for frontend to initialize...${NC}"
sleep 5

echo -e "${GREEN}=== OptionsStrat App is now running ===${NC}"
echo -e "${GREEN}Backend: http://localhost:8003${NC}"
echo -e "${GREEN}Frontend: http://localhost:3003${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"

# Handle graceful shutdown
cleanup() {
  echo -e "${YELLOW}Shutting down servers...${NC}"
  
  # Kill the backend and frontend processes
  if ps -p $BACKEND_PID > /dev/null; then
    kill $BACKEND_PID
    echo -e "${GREEN}Backend server stopped.${NC}"
  fi
  
  if ps -p $FRONTEND_PID > /dev/null; then
    kill $FRONTEND_PID
    echo -e "${GREEN}Frontend server stopped.${NC}"
  fi
  
  exit 0
}

# Set up trap for cleanup
trap cleanup INT TERM

# Keep script running
wait 