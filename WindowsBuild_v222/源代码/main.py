#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安卓帧率测试工具 - Android FPS Tester
通过ADB连接安卓手机，实时采集游戏/应用的帧率数据

使用方法:
1. 安装依赖: pip install -r requirements.txt
2. 安装Android SDK Platform-Tools (包含adb命令)
3. 手机开启USB调试并连接电脑
4. 运行: python main.py
"""

import sys
import os
import traceback

# ==================== 日志先于一切初始化 ====================
# 先在 main.py 入口激活 app_logger，确保启动阶段（含 PyInstaller frozen 初始化、
# 所有 import 等）可能抛出的异常都能被 excepthook 捕捉到磁盘
try:
    from app_logger import setup_logging, get_logger, log_exception
    setup_logging()
    logger = get_logger("main")
except Exception as _e:
    # 连 logger 初始化都失败，只能写临时文件兜底
    try:
        if sys.platform == "darwin":
            _log_dir = os.path.expanduser("~/Library/Logs/星穹视界帧率测试")
        elif sys.platform == "win32":
            _log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "星穹视界帧率测试", "logs")
        else:
            _log_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "星穹视界帧率测试", "logs")
        os.makedirs(_log_dir, exist_ok=True)
        _fallback = os.path.join(_log_dir, "startup_fallback.log")
        with open(_fallback, "a", encoding="utf-8") as _fp:
            _fp.write(f"[FATAL] logger 初始化失败: {_e}\n")
    except Exception:
        pass
    logger = None


def main():
    if logger:
        logger.info("创建 QApplication 实例...")
    try:
        from PyQt5.QtWidgets import QApplication
    except Exception as e:
        if logger:
            log_exception(e, "导入 PyQt5 失败")
        raise

    # [macOS] 在创建 QApplication 之前先用原生 API 强制设置进程名
    # 这样 菜单栏 / 活动监视器 / 关于窗口 都会优先显示「星穹视界帧率测试」而非 Python
    if sys.platform == "darwin":
        try:
            import ctypes
            # 设置进程名称（CFBundleName / NSProcessInfo）
            _lib = ctypes.CDLL(None)
            try:
                # setprogname 用于在 unix 级别设置进程名
                _setprogname = _lib.setprogname
                _setprogname.restype = None
                _setprogname.argtypes = [ctypes.c_char_p]
                _setprogname(b"XingQiongShiJieZhenLvCeShi")
            except Exception:
                pass
            try:
                # NSAppleEvents 注册主菜单名
                from Cocoa import NSProcessInfo
                NSProcessInfo.processInfo().setProcessName_("星穹视界帧率测试")
            except Exception:
                pass
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置 APP 级元信息（供 Settings/QStandardPaths / macOS 菜单 等使用）
    # 在 macOS 上确保 菜单栏 / Activity Monitor / 关于面板 显示「星穹视界帧率测试」而非 Python
    app.setApplicationName("星穹视界帧率测试")
    app.setApplicationDisplayName("星穹视界帧率测试")
    app.setOrganizationName("StellarVision")
    app.setOrganizationDomain("stellarvision.com")
    app.setApplicationVersion("2.1.0")
    try:
        # Qt >= 5.7：桌面文件名，macOS 菜单会参考该标识
        app.setDesktopFileName("com.stellarvision.fpstester")
    except Exception:
        pass
    # macOS：将菜单栏 "About Python" 改为「关于 星穹视界帧率测试」
    try:
        from PyQt5.QtCore import Qt
        app.setAttribute(Qt.AA_MacPluginApplication, False)
    except Exception:
        pass

    # 设置全局字体
    from PyQt5.QtGui import QFont
    default_font = QFont("PingFang SC", 11)
    app.setFont(default_font)

    # 创建主窗口：失败时弹 QMessageBox + 写日志
    try:
        from main_window import MainWindow
        window = MainWindow()
    except Exception as e:
        if logger:
            log_exception(e, "MainWindow 构造失败")
        try:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                None, "启动失败",
                f"主窗口初始化失败，请查看日志。\n\n{e}\n\n日志目录:\n"
                f"{os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), '星穹视界帧率测试', 'logs') if sys.platform == 'win32' else os.path.expanduser('~/Library/Logs/星穹视界帧率测试')}"
            )
        except Exception:
            pass
        raise

    try:
        # 开屏阶段最大化，撑满屏幕以展示完整星空动画；用户欢迎页阶段会恢复到窗口大小
        window.showMaximized()
    except Exception as e:
        if logger:
            log_exception(e, "window.showMaximized() 失败，退回普通 show()")
        try:
            window.show()
        except Exception as e2:
            if logger:
                log_exception(e2, "window.show() 失败")
            raise

    if logger:
        logger.info("进入 QApplication 事件循环")
    exit_code = app.exec_()
    if logger:
        logger.info(f"事件循环退出，exit_code={exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — 这里是最后一道兜底
        # sys.excepthook 已接管主线程；此分支仅作兜底（例如 excepthook 之前）
        try:
            if logger:
                logger.critical(
                    "main() 最外层兜底异常: %s: %s\n%s",
                    type(exc).__name__, exc,
                    traceback.format_exc().rstrip(),
                )
        except Exception:
            pass
        try:
            from PyQt5.QtWidgets import QMessageBox, QApplication
            if QApplication.instance():
                QMessageBox.critical(
                    None, "程序异常退出",
                    f"发生未处理异常：{type(exc).__name__}: {exc}\n\n"
                    f"日志目录：\n{os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), '星穹视界帧率测试', 'logs') if sys.platform == 'win32' else os.path.expanduser('~/Library/Logs/星穹视界帧率测试')}"
                )
        except Exception:
            pass
        sys.exit(1)
