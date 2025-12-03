#!/bin/bash
# RetinaDetachNet Installation Script for macOS/Linux
# This script creates a conda environment and installs all dependencies

set -e  # Exit on error

echo "=============================================="
echo "  RetinaDetachNet Installation"
echo "  Automated TUNEL & Nuclei Quantification"
echo "=============================================="
echo ""

# Check for conda
if ! command -v conda &> /dev/null; then
    echo "ERROR: Conda not found!"
    echo ""
    echo "Please install Miniconda first:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    echo ""
    echo "After installation, restart your terminal and run this script again."
    exit 1
fi

echo "Conda found. Creating environment..."
echo ""

# Create conda environment with Python 3.10
conda create -n retinadetachnet python=3.10 -y

echo ""
echo "Activating environment..."

# Activate the environment
eval "$(conda shell.bash hook)"
conda activate retinadetachnet

echo ""
echo "Installing dependencies..."
echo "(This may take several minutes)"
echo ""

# Install PyTorch first (for proper GPU/MPS detection)
# On macOS with Apple Silicon, this enables MPS acceleration
pip install torch torchvision

# Install remaining dependencies
pip install -r requirements.txt

echo ""
echo "=============================================="
echo "  Installation Complete!"
echo "=============================================="
echo ""
echo "To run RetinaDetachNet:"
echo ""
echo "  1. Activate the environment:"
echo "     conda activate retinadetachnet"
echo ""
echo "  2. Run the application:"
echo "     python RetinaDetachNet.py"
echo ""
echo "=============================================="
