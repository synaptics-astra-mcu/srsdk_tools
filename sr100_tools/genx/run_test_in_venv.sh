#!/bin/bash

# Virtual environment name
virtualenv_name="genx"

# Check for Python 3.10 or later
python_version=$(python3 --version | cut -d " " -f 2)
required_version="3.10"

# Function to compare versions
version_gt() { test "$(printf '%s\n' "$@" | sort -V | head -n 1)" != "$1"; }

# Check if the installed Python version is >= 3.10
if version_gt $required_version $python_version; then
    echo "Python 3.10 or later is required. Installed version is $python_version."
    exit 1
fi

# Check if python3.10-venv is installed (Debian/Ubuntu)
if ! dpkg -s python3.10-venv &> /dev/null; then
    echo "python3.10-venv package is not installed. Install it with: apt-get install python3.10-venv."
    exit 1
fi

# Check for pip3
if ! command -v pip3 &> /dev/null; then
    echo "pip3 could not be found. Please install it."
    exit 1
fi

# Check if virtual environment already exists
if [ -d "$virtualenv_name" ]; then
    echo "Virtual environment $virtualenv_name already exists."
else
    # Create a new virtual environment
    python3 -m venv $virtualenv_name
    
fi

# Activate virtual environment
# source $virtualenv_name/bin/activate
source ./$virtualenv_name/bin/activate
# # Install or update requirements
pip3 install --upgrade -r requirements.txt

# # Run your program (replace with your script name)
python3 test.py

# # Deactivate virtual environment
deactivate
