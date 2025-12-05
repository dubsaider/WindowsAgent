@echo off
REM PC-Guardian Agent - Build EXE with PyInstaller

setlocal EnableDelayedExpansion

REM Virtual environment path
set VENV_DIR=%~dp0venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
set PIP_EXE=%VENV_DIR%\Scripts\pip.exe

echo ========================================
echo PC-Guardian Agent - Building EXE
echo ========================================
echo.

REM Check if venv exists
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Virtual environment found: %VENV_DIR%
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo [INFO] Virtual environment not found. Creating new one...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
    call "%VENV_DIR%\Scripts\activate.bat"
    echo [INFO] Virtual environment created
)

echo.
echo [INFO] Updating pip...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [WARN] Failed to upgrade pip, continuing...
)

echo [INFO] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    exit /b 1
)

echo [INFO] Installing PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller
    exit /b 1
)

echo.
echo [INFO] Building with PyInstaller...
pyinstaller build_agent.spec --clean
if errorlevel 1 (
    echo [ERROR] Build failed
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo EXE file: dist\PCGuardianAgent.exe
echo ========================================

endlocal
