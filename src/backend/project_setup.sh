#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status


# Upgrade pip and install poetry
pip install --upgrade pip
pip install poetry

# Install dependencies without the project itself
poetry install --no-root

# Update the lock file if necessary
poetry lock

# Install dependencies and the project
poetry install

# Create and install the IPython kernel for the project
# list all kernels: jupyter kernelspec list
# delete a kernel: jupyter kernelspec uninstall CRv3
# poetry run python -m python -m ipykernel install --user --name=crv3 --display-name "Clever Routing v3"
# poetry run python -m ipykernel install --sys-prefix --name=CRv3 --display-name "CRv3"
python -m ipykernel install --user --name=OptionsStrat --display-name "OptionsStrat" # install globally outside of poetry

echo "Jupyter kernel 'OptionsStrat' has been installed."


echo "Project setup complete!"