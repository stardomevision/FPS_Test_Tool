# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件 - 星穹视界帧率测试 (Windows x64 · onedir + COLLECT 模式)
版本: v2.2.2
在 Windows 机器上执行 (PowerShell / CMD):
    cd 源代码
    pyinstaller --noconfirm --clean "星穹视界帧率测试_Windows.spec"
或直接双击  构建_Windows版.bat  一键完成
"""

import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# ============================================================
# pymobiledevice3 全家桶：解决 "No package metadata was found for xxx"
# ============================================================
_PMD3_DEPS = [
    "pymobiledevice3",
    "apple_compress", "apple_gmux", "apple_hfs", "apple_iboot", "apple_img4", "apple_pbp",
    "mbdb", "pd_pylzss",
    "construct", "construct_typing",
    "opack2",
    "pmd_net_addr", "pmd_net_proto", "pmd_pytcp",
    "pylzss", "pyusb",
    "sslpsk_pmd3",
    "cryptography", "Crypto",
    "pyimg4", "ipsw_parser", "pykdebugparser",
    "parameter_decorators", "typer_injector",
    "developer_disk_image", "pygnuutils",
    "pytun_pmd3",
    "bpylist2", "hexdump",
]

_pymod_datas = []
_pymod_binaries = []
_pymod_hidden = []
for _pkg in _PMD3_DEPS:
    try:
        _ret = collect_all(_pkg, include_py_files=True)
        if len(_ret) == 3:
            _datas, _bins, _hiddens = _ret
        else:
            _datas, _bins, _hiddens = _ret[0], _ret[1], _ret[2]
        _pymod_datas.extend(_datas)
        _pymod_binaries.extend(_bins)
        _pymod_hidden.extend(_hiddens)
    except Exception as _e:
        print(f"[spec v2.2.2] collect_all({_pkg}) skipped: {_e}")

# ============================================================
# 资源目录定位（platform-tools + resources）
#   场景 A:  双击 构建_Windows版.bat → 构建脚本已 xcopy 源代码到根目录
#           → platform-tools / resources 均直接在 SPEC 同级
#   场景 B:  在 源代码/ 目录手动执行 pyinstaller
#           → platform-tools 在 ..\资源文件\platform-tools
# ============================================================
_spec_dir = os.path.dirname(os.path.abspath(SPEC))

def _locate_dir(name: str) -> str:
    for cand in (
        os.path.join(_spec_dir, name),
        os.path.join(_spec_dir, '..', '资源文件', name),
        os.path.join(_spec_dir, '..', 'resources', name),
    ):
        if os.path.isdir(cand):
            return cand
    return os.path.join(_spec_dir, name)

_platform_tools_dir = _locate_dir('platform-tools')
_resources_dir      = _locate_dir('resources')

# 收集 platform-tools 目录下所有文件 (adb.exe / AdbWinApi.dll / AdbWinUsbApi.dll / lib64/* 等)
_platform_tools_datas = []
if os.path.isdir(_platform_tools_dir):
    for root, dirs, files in os.walk(_platform_tools_dir):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(root, _spec_dir)
            dst = rel
            _platform_tools_datas.append((src, dst))
            print(f"[spec v2.2.2] platform-tools => {os.path.join(rel, f)}")
else:
    print(f"[spec v2.2.2] ⚠️ 未找到 platform-tools 目录（Windows 版构建脚本会自动下载）")

# 收集 resources 下的图标/PNG
_resources_datas = []
if os.path.isdir(_resources_dir):
    for root, dirs, files in os.walk(_resources_dir):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.ico', '.icns')):
                src = os.path.join(root, f)
                rel = os.path.relpath(root, _spec_dir)
                dst = rel
                _resources_datas.append((src, dst))
                print(f"[spec v2.2.2] 资源 => {os.path.join(rel, f)}")

# Windows 图标：优先 .ico，无则用 jpg/png（PyInstaller 会尝试转换）
_icon_path = None
for _cand in ('app_icon.ico', 'app_icon.png', 'app_icon.jpg', 'app_icon.icns'):
    p = os.path.join(_resources_dir, _cand)
    if os.path.isfile(p):
        _icon_path = p
        print(f"[spec v2.2.2] EXE 图标 = {p}")
        break
if _icon_path is None:
    print(f"[spec v2.2.2] ⚠️ 未找到图标文件")

# ============================================================
# iOS DDI (Developer Disk Image)：Windows 路径 %USERPROFILE%\.pymobiledevice3\...
# ============================================================
_user_profile = os.environ.get('USERPROFILE', os.path.expanduser('~'))
_ddi_cache_dir = os.path.join(_user_profile, '.pymobiledevice3', 'Xcode_iOS_DDI_Personalized')
_ddi_datas = []
if os.path.isdir(_ddi_cache_dir):
    for f in os.listdir(_ddi_cache_dir):
        src = os.path.join(_ddi_cache_dir, f)
        if os.path.isfile(src):
            _ddi_datas.append((src, 'Xcode_iOS_DDI_Personalized'))
            print(f"[spec v2.2.2] DDI 文件已打包: {f}")
else:
    print(f"[spec v2.2.2] 提示: DDI 缓存目录不存在(首次启动会自动下载)：{_ddi_cache_dir}")

# ============================================================
# hiddenimports
# ============================================================
hiddenimports = [
    # PyQt5
    'PyQt5.sip', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
    # pyqtgraph
    'pyqtgraph', 'pyqtgraph.graphicsItems',
    'pyqtgraph.PlotWidget', 'pyqtgraph.ViewBox', 'pyqtgraph.PlotItem', 'pyqtgraph.PlotDataItem',
    'pyqtgraph.GradientEditorItem', 'pyqtgraph.LegendItem', 'pyqtgraph.InfiniteLine', 'pyqtgraph.BarGraphItem',
    'pyqtgraph.graphicsItems.ViewBox', 'pyqtgraph.graphicsItems.PlotItem',
    'pyqtgraph.graphicsItems.PlotDataItem', 'pyqtgraph.graphicsItems.InfiniteLine',
    'pyqtgraph.graphicsItems.BarGraphItem', 'pyqtgraph.graphicsItems.LegendItem',
    'pyqtgraph.graphicsItems.GradientEditorItem', 'pyqtgraph.graphicsItems.AxisItem',
    'pyqtgraph.graphicsItems.LabelItem', 'pyqtgraph.graphicsItems.LinearRegionItem',
    'pyqtgraph.exporters', 'pyqtgraph.exporters.CSVExporter',
    'pyqtgraph.exporters.ImageExporter', 'pyqtgraph.exporters.SVGExporter',
    # numpy
    'numpy', 'numpy.core._multiarray_umath', 'numpy.core.multiarray',
    'numpy.core.numeric', 'numpy.core.umath',
    'numpy.random', 'numpy.random.mtrand',
    # 标准库
    'csv', 'statistics', 'dataclasses',
    # pymobiledevice3 模块
    'pymobiledevice3', 'pymobiledevice3.lockdown', 'pymobiledevice3.usbmux',
    'pymobiledevice3.exceptions', 'pymobiledevice3.services',
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
    'construct', 'construct_typing',
    'pycryptodome', 'Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES',
    'Crypto.Cipher.PKCS1', 'Crypto.PublicKey', 'Crypto.PublicKey.RSA',
    'cryptography', 'sslpsk_pmd3', 'pyusb', 'usb', 'qh3',
    'bpylist2', 'asn1', 'hexdump', 'pykdebugparser',
    'developer_disk_image', 'ipsw_parser', 'pyimg4',
    'apple_compress', 'opack2',
    'pmd_net_addr', 'pmd_net_proto', 'pmd_pytcp',
    'pytun_pmd3', 'pylzss', 'pygnuutils',
    'parameter_decorators', 'typer_injector',
] + _pymod_hidden

# ============================================================
# Analysis / PYZ / EXE / COLLECT (Windows onedir 模式，无 BUNDLE)
# ============================================================
a = Analysis(
    ['main.py'],
    pathex=[_spec_dir],
    binaries=_pymod_binaries,
    datas=_platform_tools_datas + _resources_datas + _ddi_datas + _pymod_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5.QtWebEngine', 'PyQt5.QtWebEngineCore', 'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtQml', 'PyQt5.QtQuick', 'PyQt5.QtQuickWidgets',
        'PyQt5.QtSql', 'PyQt5.QtBluetooth',
        'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtNetwork', 'PyQt5.QtOpenGL', 'PyQt5.QtPositioning',
        'PyQt5.QtSensors', 'PyQt5.QtSerialPort', 'PyQt5.QtTest',
        'PyQt5.QtWebChannel', 'PyQt5.QtWebSockets',
        'PyQt5.QtXml', 'PyQt5.QtXmlPatterns',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ---- onedir 模式：EXE 只保留引导，binaries/datas 交给 COLLECT 输出 ----
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

# Windows 不生成 BUNDLE（仅 macOS 使用）
print(f"[spec v2.2.2] ✅ 配置加载完成。产物目录: dist\\星穹视界帧率测试\\ (onedir)")
