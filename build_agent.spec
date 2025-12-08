# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec-файл для сборки агента PC-Guardian в один exe.

Сборка:
    pyinstaller build_agent.spec
"""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Автоматический сбор всех подмодулей kafka
kafka_hiddenimports = collect_submodules('kafka')

a = Analysis(
    ['agent.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Пример: положить пример конфига рядом с exe
        ('config.json.example', '.'),
    ],
    hiddenimports=[
        # WMI и COM
        'wmi',
        'win32com',
        'win32com.client',
        # kafka-python - все подмодули собираются автоматически
    ] + kafka_hiddenimports + [
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
    name='PCGuardianAgent',
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


