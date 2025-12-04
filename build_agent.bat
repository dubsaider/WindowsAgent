@echo off
REM Сборка PC-Guardian Agent в один exe через PyInstaller

setlocal

REM Путь к виртуальному окружению (при необходимости измените)
set VENV_DIR=%~dp0venv

if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo [WARN] venv не найден по пути "%VENV_DIR%". Убедитесь, что зависимости установлены в активном Python.
)

python -m pip install --upgrade pip
python -m pip install pyinstaller

pyinstaller build_agent.spec

echo.
echo Сборка завершена. EXE-файл будет в папке "dist".

endlocal


