# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec-файл для сборки агента PC-Guardian в один exe.

Сборка:
    pyinstaller build_agent.spec
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

# Убедимся, что корень проекта в sys.path, чтобы импортировать __version__
sys.path.insert(0, os.path.abspath("."))
from __version__ import __version__

# Имя образа можно задать через переменную окружения IMAGE_NAME (по умолчанию PCGuardianAgent)
IMAGE_NAME = os.getenv("IMAGE_NAME", "PCGuardianAgent")
APP_NAME = f"{IMAGE_NAME}_{__version__}"

block_cipher = None

kafka_hiddenimports = collect_submodules('kafka')
system_hiddenimports = collect_submodules('system')
agent_core_hiddenimports = collect_submodules('agent_core')

a = Analysis(
    ['agent.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Пример: положить пример конфига рядом с exe
        ('config.json.example', '.'),
        ('system\\*.py', 'system'),
    ],
    hiddenimports=[
        # WMI и COM
        'wmi',
        'win32com',
        'win32com.client',
        # kafka-python - все подмодули собираются автоматически
    ] + kafka_hiddenimports + system_hiddenimports + agent_core_hiddenimports + [
        # Версия агента
        '__version__',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Не показывать консольное окно при запуске
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)


