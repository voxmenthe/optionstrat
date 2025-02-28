#!/bin/bash

# Run tests with mocked API key for the OptionsStrat backend
# Usage: ./run_test_with_mock.sh [test_path] [-v|--verbose]
#   test_path: Optional path to specific test file or module
#   -v, --verbose: Show verbose output with full tracebacks

# Set the working directory to the script's directory
cd "$(dirname "$0")"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running tests with mocked Polygon API key...${NC}"

# Set a mock Polygon API key for testing
export POLYGON_API_KEY="test_api_key_for_mocking"

# Default values
VERBOSE=false
TEST_PATH="tests/"

# Parse arguments
for arg in "$@"; do
    if [[ "$arg" == "--verbose" || "$arg" == "-v" ]]; then
        VERBOSE=true
    elif [[ "$arg" != --* && "$arg" != -* ]]; then
        TEST_PATH="$arg"
    fi
done

# Show what we're testing
if [ "$TEST_PATH" = "tests/" ]; then
    echo -e "${YELLOW}Running all tests...${NC}"
else
    echo -e "${YELLOW}Running specified test: $TEST_PATH${NC}"
fi

# Build the pytest command
if [ "$VERBOSE" = true ]; then
    echo -e "${YELLOW}Using verbose output mode${NC}"
    PYTEST_CMD="python -m pytest ${TEST_PATH} -v --cov=app"
else
    echo -e "${YELLOW}Using concise output mode (use -v for more details)${NC}"
    PYTEST_CMD="python -m pytest ${TEST_PATH} -v --tb=short --cov=app"
fi

# Run the tests
eval $PYTEST_CMD

# Store the exit code
TEST_EXIT_CODE=$?

# Check if the tests passed
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo
    echo -e "${GREEN}Tests completed successfully!${NC}"
    
    # Show coverage summary
    echo
    echo -e "${YELLOW}Coverage summary:${NC}"
    coverage report | grep "TOTAL"
    
    echo
    echo -e "${YELLOW}For detailed coverage report, run:${NC}"
    echo -e "${GREEN}./run_tests.sh${NC}"
    
    exit 0
else
    echo
    echo -e "${RED}Test failed. Please check the output above for details.${NC}"
    exit 1
fi 