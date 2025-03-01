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

# Check if Redis is running
echo -e "${YELLOW}Checking Redis server status...${NC}"
REDIS_RUNNING=false

# For macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
  if pgrep -x "redis-server" > /dev/null; then
    REDIS_RUNNING=true
    echo -e "${GREEN}Redis server is already running${NC}"
  else
    echo -e "${YELLOW}Starting Redis server...${NC}"
    if command -v brew &> /dev/null && brew list redis &> /dev/null; then
      brew services start redis
      REDIS_RUNNING=true
      echo -e "${GREEN}Redis server started using Homebrew${NC}"
    elif command -v redis-server &> /dev/null; then
      redis-server &
      REDIS_RUNNING=true
      echo -e "${GREEN}Redis server started${NC}"
    else
      echo -e "${YELLOW}Redis server not found. Installing Redis would improve performance but is not required.${NC}"
    fi
  fi
# For Linux
else
  if systemctl is-active --quiet redis-server 2>/dev/null || systemctl is-active --quiet redis 2>/dev/null; then
    REDIS_RUNNING=true
    echo -e "${GREEN}Redis server is already running${NC}"
  else
    echo -e "${YELLOW}Starting Redis server...${NC}"
    if command -v redis-server &> /dev/null; then
      redis-server &
      REDIS_RUNNING=true
      echo -e "${GREEN}Redis server started${NC}"
    elif command -v systemctl &> /dev/null; then
      sudo systemctl start redis-server 2>/dev/null || sudo systemctl start redis 2>/dev/null
      if [ $? -eq 0 ]; then
        REDIS_RUNNING=true
        echo -e "${GREEN}Redis server started using systemctl${NC}"
      else
        echo -e "${YELLOW}Redis server not found. Installing Redis would improve performance but is not required.${NC}"
      fi
    else
      echo -e "${YELLOW}Redis server not found. Installing Redis would improve performance but is not required.${NC}"
    fi
  fi
fi

# Check if python-dotenv is installed
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! pip list | grep -q python-dotenv; then
  echo -e "${YELLOW}Installing python-dotenv...${NC}"
  pip install python-dotenv
fi

# If Redis is running, set environment variable
if [ "$REDIS_RUNNING" = true ]; then
  export REDIS_ENABLED=true
  echo -e "${GREEN}Redis caching enabled${NC}"
else
  export REDIS_ENABLED=false
  echo -e "${YELLOW}Redis caching disabled - database fallback will be used${NC}"
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
  
  # Stop Redis if we started it
  if [ "$REDIS_RUNNING" = true ]; then
    echo -e "${YELLOW}Shutting down Redis server...${NC}"
    # For macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
      if command -v brew &> /dev/null && brew list redis &> /dev/null; then
        brew services stop redis
      else
        pkill redis-server
      fi
    # For Linux
    else
      if command -v systemctl &> /dev/null; then
        sudo systemctl stop redis-server 2>/dev/null || sudo systemctl stop redis 2>/dev/null
      else
        pkill redis-server
      fi
    fi
    echo -e "${GREEN}Redis server stopped.${NC}"
  fi
  
  exit 0
}

# Set up trap for cleanup
trap cleanup INT TERM

# Keep script running
wait