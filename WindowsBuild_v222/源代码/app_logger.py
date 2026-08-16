"""
APP 全局日志模块：
- 日志文件位置：~/Library/Logs/星穹视界帧率测试/app_YYYYMMDD.log（按日滚动，单文件 5MB，保留 10 份）
- 同时输出到 stderr（PyInstaller windowed 模式下 stderr 丢弃，不影响）
- 接管 sys.excepthook / threading.excepthook / PyQt QtMessageHandler，捕获全部未处理异常和 Qt 警告
- 提供 get_logger(name) / log_exception(exc, context) 快捷接口
- shutdown()：显式关闭文件句柄，避免 closeEvent 后 I/O on closed file
"""

from __future__ import annotations

import os
import sys
import logging
import logging.handlers
import threading
import traceback
from datetime import datetime
from typing import Optional

_LOG_DIR_MACOS = os.path.expanduser("~/Library/Logs/星穹视界帧率测试")


def _get_platform_log_dir() -> str:
    """返回平台相关的日志目录"""
    if sys.platform == "darwin":
        return _LOG_DIR_MACOS
    elif sys.platform == "win32":
        # Windows: %APPDATA%/星穹视界帧率测试/logs
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "星穹视界帧率测试", "logs")
    else:
        # Linux: ~/.local/share/星穹视界帧率测试/logs
        return os.path.join(os.path.expanduser("~"), ".local", "share", "星穹视界帧率测试", "logs")


_LOG_DIR = _get_platform_log_dir()
_LOG_NAME = "fps_tester"

_initialized = False
_shutdown = False
_logger: Optional[logging.Logger] = None
_file_handler: Optional[logging.handlers.RotatingFileHandler] = None
_old_excepthook = None
_old_threading_excepthook = None
_old_qt_handler_installed = False


def get_log_dir() -> str:
    """返回日志目录，确保存在"""
    os.makedirs(_LOG_DIR, exist_ok=True)
    return _LOG_DIR


def get_log_file_path() -> str:
    """返回今天的日志文件路径"""
    date_str = datetime.now().strftime("%Y%m%d")
    return os.path.join(get_log_dir(), f"app_{date_str}.log")


def _log_app_environment(logger: logging.Logger):
    """APP 启动时写入环境信息，便于排查"""
    logger.info("=" * 70)
    logger.info(f"APP 启动 - {datetime.now().isoformat(timespec='seconds')}")
    logger.info(f"  Python  : {sys.version.splitlines()[0]}")
    logger.info(f"  Executable: {sys.executable}")
    logger.info(f"  Frozen  : {getattr(sys, 'frozen', False)} (MEIPASS={getattr(sys, '_MEIPASS', None)})")
    logger.info(f"  Platform: {sys.platform}")
    logger.info(f"  PID     : {os.getpid()}")
    logger.info(f"  Log Dir : {get_log_dir()}")
    logger.info(f"  Log File: {get_log_file_path()}")
    logger.info("-" * 70)


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """初始化全局日志，重复调用安全（只初始化一次）"""
    global _initialized, _logger, _file_handler
    global _old_excepthook, _old_threading_excepthook, _old_qt_handler_installed

    if _initialized:
        return _logger

    log_dir = get_log_dir()
    log_file = get_log_file_path()

    logger = logging.getLogger("fps_tester")
    logger.setLevel(level)
    logger.propagate = False

    # 避免重复添加 handler
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1) 文件 handler：RotatingFileHandler 5MB × 10 份
    try:
        _file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=10,
            encoding="utf-8",
        )
        _file_handler.setLevel(level)
        _file_handler.setFormatter(fmt)
        logger.addHandler(_file_handler)
    except Exception as e:
        # 日志目录写不进去也要让 APP 能启动（降级到 stderr）
        sys.stderr.write(f"[logger] 文件日志初始化失败: {e}\n")
        _file_handler = None

    # 2) 控制台 handler（windowed 模式下 /dev/null，不影响）
    try:
        stream = logging.StreamHandler(stream=sys.stderr)
        stream.setLevel(logging.INFO)
        stream.setFormatter(fmt)
        logger.addHandler(stream)
    except Exception:
        pass

    _logger = logger
    _log_app_environment(logger)

    # ==================== 接管未处理异常 ====================
    _old_excepthook = sys.excepthook

    def _excepthook(exc_type, exc, tb):
        try:
            if not _shutdown:
                logger.critical(
                    "未处理的主线程异常: %s: %s\n%s",
                    exc_type.__name__, exc,
                    "".join(traceback.format_exception(exc_type, exc, tb)).rstrip(),
                )
        except Exception:
            pass
        # 回落到默认 excepthook
        if _old_excepthook:
            try:
                _old_excepthook(exc_type, exc, tb)
            except Exception:
                pass

    sys.excepthook = _excepthook

    # threading excepthook (Python 3.8+)
    if hasattr(threading, "excepthook"):
        _old_threading_excepthook = threading.excepthook

        def _threading_hook(args):
            try:
                exc_type, exc, tb, _thread_name = (
                    args.exc_type, args.exc_value, args.exc_traceback, args.thread
                )
                if not _shutdown:
                    logger.critical(
                        "未处理的子线程异常 [%s]: %s: %s\n%s",
                        args.thread, exc_type.__name__, exc,
                        "".join(traceback.format_exception(exc_type, exc, tb)).rstrip(),
                    )
            except Exception:
                pass
            if _old_threading_excepthook:
                try:
                    _old_threading_excepthook(args)
                except Exception:
                    pass

        threading.excepthook = _threading_hook

    # 安装 Qt 消息处理（PyQt5/PySide2 风格）
    try:
        from PyQt5.QtCore import QtInstallMessageHandler, QtMsgType
        _old_qt_handler_installed = True

        def _qt_msg_handler(mode, context, message):
            if _shutdown:
                return
            level_map = {
                QtMsgType.QtDebugMsg: logging.DEBUG,
                QtMsgType.QtInfoMsg: logging.INFO,
                QtMsgType.QtWarningMsg: logging.WARNING,
                QtMsgType.QtCriticalMsg: logging.ERROR,
                QtMsgType.QtFatalMsg: logging.CRITICAL,
            }
            lvl = level_map.get(mode, logging.WARNING)
            file = context.file or "<qt>"
            func = context.function or ""
            line = context.line or 0
            text = f"[Qt] {message}  ({file}:{line} {func})"
            # 写日志（对 Fatal/Critical/Error/Warning 高优先级，Debug 低频）
            if lvl >= logging.WARNING:
                logger.log(lvl, text)
            else:
                logger.log(logging.DEBUG, text)
        try:
            QtInstallMessageHandler(_qt_msg_handler)
        except Exception:
            _old_qt_handler_installed = False
    except Exception:
        pass

    _initialized = True
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """获取命名子 logger；子 logger 继承 file+stream handler"""
    if not _initialized:
        setup_logging()
    if name:
        return _logger.getChild(name) if _logger else logging.getLogger(f"fps_tester.{name}")
    return _logger or logging.getLogger("fps_tester")


def log_exception(exc: BaseException, context: str = "", logger: logging.Logger = None) -> None:
    """在 except 块内调用：统一格式记录已捕获的异常 + 调用栈"""
    lg = logger or get_logger()
    prefix = f"[{context}] " if context else ""
    lg.error(
        "%s异常: %s: %s\n%s",
        prefix,
        type(exc).__name__, str(exc),
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip(),
    )


def shutdown_logging() -> None:
    """显式关闭：closeEvent 里调用，防止退出时写入已关闭句柄"""
    global _shutdown, _file_handler, _logger
    if _shutdown:
        return
    _shutdown = True
    try:
        if _logger:
            _logger.info(f"APP 正常退出 - {datetime.now().isoformat(timespec='seconds')}")
            _logger.info("=" * 70 + "\n")
    except Exception:
        pass
    if _file_handler:
        try:
            _file_handler.flush()
        except Exception:
            pass
        try:
            _file_handler.close()
        except Exception:
            pass
        try:
            if _logger and _file_handler in _logger.handlers:
                _logger.removeHandler(_file_handler)
        except Exception:
            pass
        _file_handler = None
