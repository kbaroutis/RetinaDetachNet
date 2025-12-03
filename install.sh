#!/bin/bash
# RetinaDetachNet Installation Script for macOS/Linux
# This script creates a conda environment and installs all dependencies
#
# Supports: macOS (Intel & Apple Silicon M1/M2/M3), Linux
# Recommended: Miniforge (https://github.com/conda-forge/miniforge)

set -e  # Exit on error

echo "=============================================="
echo "  RetinaDetachNet Installation"
echo "  Automated TUNEL & Nuclei Quantification"
echo "=============================================="
echo ""

# Detect operating system and architecture
OS="$(uname -s)"
ARCH="$(uname -m)"
APPLE_SILICON=false

if [[ "$OS" == "Darwin" && "$ARCH" == "arm64" ]]; then
    APPLE_SILICON=true
    echo "Detected: macOS Apple Silicon ($ARCH)"
elif [[ "$OS" == "Darwin" ]]; then
    echo "Detected: macOS Intel ($ARCH)"
elif [[ "$OS" == "Linux" ]]; then
    echo "Detected: Linux ($ARCH)"
else
    echo "Detected: $OS ($ARCH)"
fi
echo ""

# Check for conda or mamba
CONDA_CMD=""
if command -v mamba &> /dev/null; then
    CONDA_CMD="mamba"
    echo "Found: mamba (fast conda alternative)"
elif command -v conda &> /dev/null; then
    CONDA_CMD="conda"
    echo "Found: conda"
else
    echo "ERROR: Neither conda nor mamba found!"
    echo ""
    echo "Please install Miniforge (recommended):"
    echo "  https://github.com/conda-forge/miniforge#download"
    echo ""
    echo "Or Miniconda:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    echo ""
    echo "After installation, restart your terminal and run this script again."
    exit 1
fi
echo ""

# Check if environment already exists
if conda env list | grep -q "^retinadetachnet "; then
    echo "Environment 'retinadetachnet' already exists."
    read -p "Do you want to remove and recreate it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing environment..."
        conda env remove -n retinadetachnet -y
    else
        echo "Installation cancelled. To update, run:"
        echo "  conda activate retinadetachnet && pip install -r requirements.txt"
        exit 0
    fi
fi

echo "Creating environment from environment.yml..."
echo "(This may take several minutes)"
echo ""

# Create environment from environment.yml
$CONDA_CMD env create -f environment.yml

echo ""
echo "Activating environment for post-install setup..."

# Activate the environment
eval "$(conda shell.bash hook)"
conda activate retinadetachnet

# Apple Silicon specific: Install optimized TensorFlow if needed
if [[ "$APPLE_SILICON" == true ]]; then
    echo ""
    echo "Apple Silicon detected: Checking TensorFlow Metal support..."

    # Check if tensorflow-metal is available
    if ! pip show tensorflow-metal &> /dev/null; then
        echo "Installing TensorFlow Metal for GPU acceleration..."
        pip install tensorflow-metal 2>/dev/null || echo "Note: tensorflow-metal optional, CPU will be used"
    else
        echo "TensorFlow Metal already installed."
    fi
fi

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
if [[ "$APPLE_SILICON" == true ]]; then
echo "  Note: Your Apple Silicon Mac will use Metal GPU acceleration."
echo ""
fi
echo "To update later:"
echo "     cd RetinaDetachNet && git pull"
echo ""
echo "=============================================="
