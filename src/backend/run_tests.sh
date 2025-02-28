#!/bin/bash

# Run tests and generate coverage report for the OptionsStrat backend
# Usage: ./run_tests.sh [test_path] [-v|--verbose]
#   test_path: Optional path to specific test file or module
#   -v, --verbose: Show verbose output with full tracebacks

# Set the working directory to the script's directory
cd "$(dirname "$0")"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running tests for OptionsStrat backend...${NC}"
echo

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed. Please install it with:${NC}"
    echo "pip install pytest pytest-cov"
    exit 1
fi

# Check if coverage is installed
if ! python -c "import coverage" &> /dev/null; then
    echo -e "${RED}Error: coverage is not installed. Please install it with:${NC}"
    echo "pip install coverage pytest-cov"
    exit 1
fi

# Set a mock Polygon API key for testing
export POLYGON_API_KEY="test_api_key_for_mocking"
echo -e "${YELLOW}Using mock Polygon API key for tests${NC}"

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
    PYTEST_CMD="pytest --cov=app ${TEST_PATH} -v"
else
    echo -e "${YELLOW}Using concise output mode (use -v for more details)${NC}"
    PYTEST_CMD="pytest --cov=app ${TEST_PATH} -v --tb=short"
fi

# Run the tests with coverage
echo -e "${YELLOW}Running tests with coverage...${NC}"
eval $PYTEST_CMD

# Store the exit code
TEST_EXIT_CODE=$?

# Generate HTML coverage report
echo
echo -e "${YELLOW}Generating HTML coverage report...${NC}"
pytest --cov=app --cov-report=html "$TEST_PATH" > /dev/null 2>&1

# Check if the tests passed
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo
    echo -e "${GREEN}All tests passed!${NC}"
    echo -e "${GREEN}Coverage report generated in htmlcov/ directory${NC}"
    echo -e "${YELLOW}Open htmlcov/index.html in your browser to view the report${NC}"
    
    # Calculate overall coverage
    coverage_report=$(coverage report)
    total_coverage=$(echo "$coverage_report" | grep "TOTAL" | awk '{print $NF}' | tr -d '%')
    
    echo
    echo -e "${YELLOW}Overall coverage: ${GREEN}${total_coverage}%${NC}"
    
    # Show coverage by module
    echo
    echo -e "${YELLOW}Coverage by module:${NC}"
    echo "$coverage_report" | grep -v "TOTAL" | sort -k 5 -r | head -10
    
    exit 0
else
    echo
    echo -e "${RED}Some tests failed. Please fix the issues before proceeding.${NC}"
    exit 1
fi 