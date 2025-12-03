@echo off
REM RetinaDetachNet Installation Script for Windows
REM This script creates a conda environment and installs all dependencies
REM
REM Recommended: Miniforge (https://github.com/conda-forge/miniforge)

echo ==============================================
echo   RetinaDetachNet Installation
echo   Automated TUNEL ^& Nuclei Quantification
echo ==============================================
echo.

REM Check for mamba first (faster), then conda
where mamba >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Found: mamba (fast conda alternative)
    set CONDA_CMD=mamba
    goto :found_conda
)

where conda >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Found: conda
    set CONDA_CMD=conda
    goto :found_conda
)

echo ERROR: Neither conda nor mamba found!
echo.
echo Please install Miniforge (recommended):
echo   https://github.com/conda-forge/miniforge#download
echo.
echo Or Miniconda:
echo   https://docs.conda.io/en/latest/miniconda.html
echo.
echo After installation, open a new Anaconda Prompt and run this script again.
pause
exit /b 1

:found_conda
echo.

REM Check if environment already exists
conda env list | findstr /B "retinadetachnet " >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Environment 'retinadetachnet' already exists.
    set /p REPLY="Do you want to remove and recreate it? (y/n): "
    if /i "%REPLY%"=="y" (
        echo Removing existing environment...
        conda env remove -n retinadetachnet -y
    ) else (
        echo Installation cancelled. To update, run:
        echo   conda activate retinadetachnet ^&^& pip install -r requirements.txt
        pause
        exit /b 0
    )
)

echo Creating environment from environment.yml...
echo (This may take several minutes)
echo.

REM Create environment from environment.yml
%CONDA_CMD% env create -f environment.yml

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Environment creation failed!
    echo Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo ==============================================
echo   Installation Complete!
echo ==============================================
echo.
echo To run RetinaDetachNet:
echo.
echo   1. Open Anaconda Prompt (or Miniforge Prompt)
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
echo To update later:
echo      cd RetinaDetachNet ^&^& git pull
echo.
echo ==============================================
pause
