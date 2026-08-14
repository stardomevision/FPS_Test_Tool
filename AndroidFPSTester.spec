# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件 - 安卓帧率测试工具
构建命令: pyinstaller AndroidFPSTester.spec
"""

import sys
import os

block_cipher = None

# 定位项目根目录下的 platform-tools（内置 ADB）
_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_platform_tools_dir = os.path.join(_spec_dir, 'platform-tools')

# 收集 platform-tools 目录中的所有文件作为数据资源
_platform_tools_datas = []
if os.path.isdir(_platform_tools_dir):
    for root, dirs, files in os.walk(_platform_tools_dir):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(root, _spec_dir)
            dst = rel  # 保持 platform-tools/ 相对路径
            _platform_tools_datas.append((src, dst))

# 隐藏导入：PyQt5 + pyqtgraph 需要的动态加载模块
hiddenimports = [
    # PyQt5 核心
    'PyQt5.sip',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    # pyqtgraph 及其后端
    'pyqtgraph',
    'pyqtgraph.graphicsItems',
    'pyqtgraph.PlotWidget',
    'pyqtgraph.ViewBox',
    'pyqtgraph.PlotItem',
    'pyqtgraph.PlotDataItem',
    'pyqtgraph.GradientEditorItem',
    'pyqtgraph.LegendItem',
    'pyqtgraph.InfiniteLine',
    'pyqtgraph.BarGraphItem',
    'pyqtgraph.graphicsItems.ViewBox',
    'pyqtgraph.graphicsItems.PlotItem',
    'pyqtgraph.graphicsItems.PlotDataItem',
    'pyqtgraph.graphicsItems.InfiniteLine',
    'pyqtgraph.graphicsItems.BarGraphItem',
    'pyqtgraph.graphicsItems.LegendItem',
    'pyqtgraph.graphicsItems.GradientEditorItem',
    'pyqtgraph.graphicsItems.AxisItem',
    'pyqtgraph.graphicsItems.LabelItem',
    'pyqtgraph.graphicsItems.LinearRegionItem',
    'pyqtgraph.exporters',
    'pyqtgraph.exporters.CSVExporter',
    'pyqtgraph.exporters.ImageExporter',
    'pyqtgraph.exporters.SVGExporter',
    # numpy 相关
    'numpy',
    'numpy.core._multiarray_umath',
    'numpy.core.multiarray',
    'numpy.core.numeric',
    'numpy.core.umath',
    'numpy.random',
    'numpy.random.mtrand',
    # 标准库辅助
    'csv',
    'statistics',
    'dataclasses',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=_platform_tools_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的Qt模块以减小体积
        'PyQt5.QtWebEngine',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtQml',
        'PyQt5.QtQuick',
        'PyQt5.QtQuickWidgets',
        'PyQt5.QtSql',
        'PyQt5.QtBluetooth',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtNetwork',
        'PyQt5.QtOpenGL',
        'PyQt5.QtPositioning',
        'PyQt5.QtSensors',
        'PyQt5.QtSerialPort',
        'PyQt5.QtTest',
        'PyQt5.QtWebChannel',
        'PyQt5.QtWebSockets',
        'PyQt5.QtXml',
        'PyQt5.QtXmlPatterns',
    ],
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
    name='AndroidFPSTester',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

app = BUNDLE(
    exe,
    name='安卓帧率测试.app',
    icon=None,
    bundle_identifier='com.fpstester.app',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSUIElement': False,
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleDisplayName': '安卓帧率测试',
        'CFBundleName': 'AndroidFPSTester',
        'NSHumanReadableCopyright': 'Copyright © 2026',
        'LSMinimumSystemVersion': '11.0',
    },
)
