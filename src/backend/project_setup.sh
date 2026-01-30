#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

if ! command -v uv &> /dev/null; then
  echo "Error: uv is not installed."
  echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# Install dependencies (dev group included by default)
uv sync

# Create and install the IPython kernel for the project
# list all kernels: jupyter kernelspec list
# delete a kernel: jupyter kernelspec uninstall CRv3
# uv run python -m python -m ipykernel install --user --name=crv3 --display-name "Clever Routing v3"
# uv run python -m ipykernel install --sys-prefix --name=CRv3 --display-name "CRv3"
if uv run python -c "import ipykernel" &> /dev/null; then
  uv run python -m ipykernel install --user --name=OptionsStrat --display-name "OptionsStrat"
  echo "Jupyter kernel 'OptionsStrat' has been installed."
else
  echo "ipykernel is not installed. Add it with: uv add --dev ipykernel"
fi

echo "Project setup complete!"
