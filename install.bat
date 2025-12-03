@echo off
REM RetinaDetachNet Installation Script for Windows
REM This script creates a conda environment and installs all dependencies

echo ==============================================
echo   RetinaDetachNet Installation
echo   Automated TUNEL ^& Nuclei Quantification
echo ==============================================
echo.

REM Check for conda
where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Conda not found!
    echo.
    echo Please install Miniconda first:
    echo   https://docs.conda.io/en/latest/miniconda.html
    echo.
    echo After installation, open Anaconda Prompt and run this script again.
    pause
    exit /b 1
)

echo Conda found. Creating environment...
echo.

REM Create conda environment with Python 3.10
call conda create -n retinadetachnet python=3.10 -y

echo.
echo Activating environment...

REM Activate the environment
call conda activate retinadetachnet

echo.
echo Installing dependencies...
echo (This may take several minutes)
echo.

REM Install PyTorch first (for proper GPU detection)
pip install torch torchvision

REM Install remaining dependencies
pip install -r requirements.txt

echo.
echo ==============================================
echo   Installation Complete!
echo ==============================================
echo.
echo To run RetinaDetachNet:
echo.
echo   1. Open Anaconda Prompt
echo.
echo   2. Activate the environment:
echo      conda activate retinadetachnet
echo.
echo   3. Navigate to this folder:
echo      cd %~dp0
echo.
echo   4. Run the application:
echo      python RetinaDetachNet.py
echo.
echo ==============================================
pause
