# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件 - 星穹视界帧率测试
构建命令: pyinstaller 星穹视界帧率测试.spec
"""

import sys
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# ============================================================
# 把 pymobiledevice3 及其依赖的 modules / datas(含 dist-info 元数据)
# / binaries 全部纳入打包，解决 "No package metadata was found for xxx"
# ============================================================
_PMD3_DEPS = [
    "pymobiledevice3",
    "apple_compress",
    "apple_gmux",
    "apple_hfs",
    "apple_iboot",
    "apple_img4",
    "apple_pbp",
    "mbdb",
    "pd_pylzss",
    "construct",
    "construct_typing",
    "opack2",
    "pmd_net_addr",
    "pmd_net_proto",
    "pmd_pytcp",
    "pylzss",
    "pyusb",
    "sslpsk_pmd3",
    "cryptography",
    "Crypto",
    "pyimg4",
    "ipsw_parser",
    "pykdebugparser",
    "parameter_decorators",
    "typer_injector",
    "developer_disk_image",
    "pygnuutils",
    "pytun_pmd3",
    "bpylist2",
    "hexdump",
]

_pymod_datas = []
_pymod_binaries = []
_pymod_hidden = []
for _pkg in _PMD3_DEPS:
    try:
        _ret = collect_all(_pkg, include_py_files=True)
        _datas, _bins, _hiddens = _ret if len(_ret) == 3 else (_ret[0], _ret[1], _ret[2])
        _pymod_datas.extend(_datas)
        _pymod_binaries.extend(_bins)
        _pymod_hidden.extend(_hiddens)
    except Exception as _e:
        print(f"[spec] collect_all({_pkg}) skipped: {_e}")

# 定位项目根目录下的 platform-tools（内置 ADB）
_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_platform_tools_dir = os.path.join(_spec_dir, 'platform-tools')
_resources_dir = os.path.join(_spec_dir, 'resources')

# 收集 platform-tools 目录中的所有文件作为数据资源
_platform_tools_datas = []
if os.path.isdir(_platform_tools_dir):
    for root, dirs, files in os.walk(_platform_tools_dir):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(root, _spec_dir)
            dst = rel
            _platform_tools_datas.append((src, dst))

# 收集 resources 目录中的图标/PNG资源
_resources_datas = []
if os.path.isdir(_resources_dir):
    for root, dirs, files in os.walk(_resources_dir):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.ico', '.icns')):
                src = os.path.join(root, f)
                rel = os.path.relpath(root, _spec_dir)
                dst = rel
                _resources_datas.append((src, dst))
                print(f"[spec] 资源文件已纳入: {os.path.join(rel, f)}")

# 图标路径 (macOS .icns)
_icon_path = os.path.join(_resources_dir, 'app_icon.icns')
if not os.path.exists(_icon_path):
    _icon_path = None
    print(f"[spec] ⚠️ 未找到 icns 图标文件")
else:
    print(f"[spec] APP 图标: {_icon_path}")

# ============================================================
# 将 iOS DDI (Developer Disk Image) 打包进 APP，用户无需手动下载
# DDI 缓存目录: ~/.pymobiledevice3/Xcode_iOS_DDI_Personalized/
# 包含: Image.dmg, BuildManifest.plist, Image.dmg.trustcache
# 运行时从 sys._MEIPASS/Xcode_iOS_DDI_Personalized/ 加载
# ============================================================
_ddi_cache_dir = os.path.expanduser('~/.pymobiledevice3/Xcode_iOS_DDI_Personalized')
_ddi_datas = []
if os.path.isdir(_ddi_cache_dir):
    for f in os.listdir(_ddi_cache_dir):
        src = os.path.join(_ddi_cache_dir, f)
        if os.path.isfile(src):
            _ddi_datas.append((src, 'Xcode_iOS_DDI_Personalized'))
            print(f"[spec] DDI 文件已纳入打包: {f}")
else:
    print(f"[spec] ⚠️ DDI 缓存目录不存在: {_ddi_cache_dir}")

hiddenimports = [
    'PyQt5.sip',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
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
    'numpy',
    'numpy.core._multiarray_umath',
    'numpy.core.multiarray',
    'numpy.core.numeric',
    'numpy.core.umath',
    'numpy.random',
    'numpy.random.mtrand',
    'csv',
    'statistics',
    'dataclasses',
    # pymobiledevice3 相关
    'pymobiledevice3',
    'pymobiledevice3.lockdown',
    'pymobiledevice3.usbmux',
    'pymobiledevice3.exceptions',
    'pymobiledevice3.services',
    'pymobiledevice3.services.installation_proxy',
    'pymobiledevice3.services.mobile_image_mounter',
    'pymobiledevice3.services.os_trace',
    'pymobiledevice3.services.dvt',
    'pymobiledevice3.services.dvt.instruments',
    'pymobiledevice3.services.dvt.instruments.dvt_provider',
    'pymobiledevice3.services.dvt.instruments.sysmontap',
    'pymobiledevice3.services.dvt.instruments.graphics',
    'pymobiledevice3.services.dvt.instruments.device_info',
    'pymobiledevice3.services.dvt.instruments.process_control',
    'pymobiledevice3.services.dvt.instruments.application_listing',
    'pymobiledevice3.services.dvt.instruments.core_profile_session_tap',
    # pymobiledevice3 依赖
    'construct',
    'construct_typing',
    'pycryptodome',
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Cipher.AES',
    'Crypto.Cipher.PKCS1',
    'Crypto.PublicKey',
    'Crypto.PublicKey.RSA',
    'cryptography',
    'sslpsk_pmd3',
    'pyusb',
    'usb',
    'qh3',
    'bpylist2',
    'asn1',
    'hexdump',
    'pykdebugparser',
    'developer_disk_image',
    'ipsw_parser',
    'pyimg4',
    'apple_compress',
    'opack2',
    'pmd_net_addr',
    'pmd_net_proto',
    'pmd_pytcp',
    'pytun_pmd3',
    'pylzss',
    'pygnuutils',
    'parameter_decorators',
    'typer_injector',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_pymod_binaries,
    datas=_platform_tools_datas + _resources_datas + _ddi_datas + _pymod_datas,
    hiddenimports=hiddenimports + _pymod_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    [],
    exclude_binaries=True,
    name='星穹视界帧率测试',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='星穹视界帧率测试',
)

app = BUNDLE(
    coll,
    name='星穹视界帧率测试.app',
    icon=_icon_path,
    bundle_identifier='com.stellarvision.fpstester',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSUIElement': False,
        'CFBundleShortVersionString': '2.2.2',
        'CFBundleVersion': '2.2.2',
        'CFBundleDisplayName': '星穹视界帧率测试',
        'CFBundleName': '星穹视界帧率测试',
        'NSHumanReadableCopyright': 'Copyright © 2026',
        'LSMinimumSystemVersion': '11.0',
    },
)
