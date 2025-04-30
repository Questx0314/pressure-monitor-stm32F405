# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

# 1. 手动添加项目资源（model 和 rec 目录）
datas = [
    ('model', 'model'),
    ('rec', 'rec'),
]

# 2. 收集 Cython 所有依赖（包括源码和二进制文件）
cython_datas, cython_binaries, cython_hidden = collect_all('Cython')
datas += cython_datas
binaries = cython_binaries
hiddenimports = ['Cython', 'Cython.Utils', 'Cython.Compiler'] + cython_hidden

# 3. 收集 paddleocr 所有依赖（关键：包含工具和配置文件）
paddleocr_datas, paddleocr_binaries, paddleocr_hidden = collect_all('paddleocr')
datas += paddleocr_datas
binaries += paddleocr_binaries
hiddenimports += ['paddleocr', 'paddleocr.tools', 'paddleocr.ppocr'] + paddleocr_hidden

# 4. 额外修复 paddleocr 的隐式依赖（根据实际报错调整）
hiddenimports += [
    'paddleocr.paddleocr',
    'paddle.utils',
    'paddle.dataset',
]

a = Analysis(
    ['main_window.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PressureMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 保持无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PressureMonitor',
)