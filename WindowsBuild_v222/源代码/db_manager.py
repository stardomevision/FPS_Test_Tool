#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 数据库管理模块（单例）

负责持久化：
  - devices              设备信息
  - test_sessions        测试会话
  - fps_samples          帧率采样（每秒一条）
  - fps_summary          帧率测试汇总
  - hw_monitor_samples   硬件监测采样
  - load_test_samples    负载测试采样
  - load_test_summary    负载测试汇总

数据库文件位置：
  - macOS:  ~/Library/Application Support/StellarVision/fps_tester.db
  - 开发环境 fallback: 项目目录 ./fps_tester.db
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Union

from app_logger import get_logger, log_exception

logger = get_logger("db_manager")

# 设备信息表的字段集合（用于 get_or_create_device 动态写入）
_DEVICE_COLUMNS: List[str] = [
    "brand", "model", "manufacturer", "device_name",
    "os_version", "sdk_version", "build_number", "hardware",
    "soc_model", "soc_manufacturer", "board_platform", "cpu_abi",
    "cpu_cores", "screen_resolution", "screen_density",
    "ram_total_mb", "gpu_info", "kernel_version",
]


def _get_default_db_path() -> str:
    """
    返回默认数据库路径：
      - macOS:  ~/Library/Application Support/StellarVision/fps_tester.db
      - 其它平台或不可写时 fallback 到项目目录
    """
    # macOS 标准位置
    app_support = os.path.expanduser("~/Library/Application Support/StellarVision")
    try:
        os.makedirs(app_support, exist_ok=True)
        # 验证目录可写
        test_file = os.path.join(app_support, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return os.path.join(app_support, "fps_tester.db")
    except Exception as e:
        # fallback：项目目录（脚本所在目录）
        project_dir = os.path.dirname(os.path.abspath(__file__))
        log_exception(e, "db_path_macos_unavailable")
        logger.warning("回退到项目目录存放数据库: %s", project_dir)
        return os.path.join(project_dir, "fps_tester.db")


class DatabaseManager:
    """SQLite 数据库管理器（单例）"""

    _instance: Optional["DatabaseManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        # __init__ 可能因单例被多次调用，只初始化一次
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.db_path = db_path or _get_default_db_path()
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None

        try:
            # 确保父目录存在
            parent_dir = os.path.dirname(self.db_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # check_same_thread=False：允许跨线程访问（配合 RLock 保证线程安全）
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=10.0,
            )
            # 开启 WAL 模式，提升并发读写性能
            try:
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA synchronous=NORMAL;")
                self._conn.execute("PRAGMA foreign_keys=ON;")
            except Exception as e:
                log_exception(e, "db_pragma")

            # row_factory 让查询结果支持 dict 风格访问
            self._conn.row_factory = sqlite3.Row

            self._create_tables()
            self._create_indexes()
            logger.info("数据库已就绪: %s", self.db_path)
        except Exception as e:
            log_exception(e, "db_init")
            logger.error("数据库初始化失败，所有写入操作将被跳过")

    # ==================== 内部工具 ====================

    @property
    def conn(self) -> Optional[sqlite3.Connection]:
        return self._conn

    def _execute(self, sql: str, params: Any = ()) -> Optional[sqlite3.Cursor]:
        """执行单条 SQL（带异常处理与锁）"""
        if self._conn is None:
            logger.warning("数据库未连接，跳过执行: %s", sql[:80])
            return None
        try:
            with self._lock:
                cur = self._conn.execute(sql, params)
                self._conn.commit()
                return cur
        except Exception as e:
            log_exception(e, "db_execute")
            try:
                self._conn.rollback()
            except Exception:
                pass
            return None

    def _executemany(self, sql: str, params_list: List[Any]) -> Optional[sqlite3.Cursor]:
        """批量执行"""
        if self._conn is None or not params_list:
            return None
        try:
            with self._lock:
                cur = self._conn.executemany(sql, params_list)
                self._conn.commit()
                return cur
        except Exception as e:
            log_exception(e, "db_executemany")
            try:
                self._conn.rollback()
            except Exception:
                pass
            return None

    def _query_all(self, sql: str, params: Any = ()) -> List[sqlite3.Row]:
        """查询多条记录"""
        if self._conn is None:
            return []
        try:
            with self._lock:
                cur = self._conn.execute(sql, params)
                return cur.fetchall()
        except Exception as e:
            log_exception(e, "db_query_all")
            return []

    def _query_one(self, sql: str, params: Any = ()) -> Optional[sqlite3.Row]:
        """查询单条记录"""
        if self._conn is None:
            return None
        try:
            with self._lock:
                cur = self._conn.execute(sql, params)
                return cur.fetchone()
        except Exception as e:
            log_exception(e, "db_query_one")
            return None

    # ==================== 建表 / 索引 ====================

    def _create_tables(self) -> None:
        """创建所有数据表"""
        statements = [
            # 1. devices 设备信息
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_serial TEXT NOT NULL,
                platform TEXT NOT NULL,
                brand TEXT DEFAULT '',
                model TEXT DEFAULT '',
                manufacturer TEXT DEFAULT '',
                device_name TEXT DEFAULT '',
                os_version TEXT DEFAULT '',
                sdk_version TEXT DEFAULT '',
                build_number TEXT DEFAULT '',
                hardware TEXT DEFAULT '',
                soc_model TEXT DEFAULT '',
                soc_manufacturer TEXT DEFAULT '',
                board_platform TEXT DEFAULT '',
                cpu_abi TEXT DEFAULT '',
                cpu_cores INTEGER DEFAULT 0,
                screen_resolution TEXT DEFAULT '',
                screen_density TEXT DEFAULT '',
                ram_total_mb INTEGER DEFAULT 0,
                gpu_info TEXT DEFAULT '',
                kernel_version TEXT DEFAULT '',
                first_seen TEXT DEFAULT (datetime('now','localtime')),
                last_seen TEXT DEFAULT (datetime('now','localtime'))
            );
            """,
            # 2. test_sessions 测试会话
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                test_type TEXT NOT NULL,
                app_package TEXT DEFAULT '',
                refresh_rate INTEGER DEFAULT 60,
                poll_interval REAL DEFAULT 1.0,
                start_time TEXT DEFAULT (datetime('now','localtime')),
                end_time TEXT,
                duration_sec REAL DEFAULT 0,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            );
            """,
            # 3. fps_samples 帧率采样
            """
            CREATE TABLE IF NOT EXISTS fps_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp REAL DEFAULT 0,
                instant_fps REAL DEFAULT 0,
                avg_fps REAL DEFAULT 0,
                min_fps REAL DEFAULT 0,
                max_fps REAL DEFAULT 0,
                low_1_fps REAL DEFAULT 0,
                low_01_fps REAL DEFAULT 0,
                std_fps REAL DEFAULT 0,
                jank_count INTEGER DEFAULT 0,
                total_frames INTEGER DEFAULT 0,
                jank_rate REAL DEFAULT 0,
                p95_frame_ms REAL DEFAULT 0,
                p99_frame_ms REAL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id)
            );
            """,
            # 4. fps_summary 帧率汇总
            """
            CREATE TABLE IF NOT EXISTS fps_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL UNIQUE,
                duration_sec REAL DEFAULT 0,
                total_frames INTEGER DEFAULT 0,
                avg_fps REAL DEFAULT 0,
                min_fps REAL DEFAULT 0,
                max_fps REAL DEFAULT 0,
                low_1_fps REAL DEFAULT 0,
                low_01_fps REAL DEFAULT 0,
                std_fps REAL DEFAULT 0,
                jank_count INTEGER DEFAULT 0,
                jank_rate REAL DEFAULT 0,
                p95_frame_ms REAL DEFAULT 0,
                p99_frame_ms REAL DEFAULT 0,
                fps_drop_count INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id)
            );
            """,
            # 5. hw_monitor_samples 硬件监测采样
            """
            CREATE TABLE IF NOT EXISTS hw_monitor_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp REAL DEFAULT 0,
                cpu_freqs_json TEXT DEFAULT '',
                cpu_usage REAL,
                cpu_temp REAL,
                gpu_freq REAL,
                gpu_load_p50 REAL,
                gpu_load_p90 REAL,
                gpu_load_p95 REAL,
                gpu_load_p99 REAL,
                mem_total_mb REAL,
                mem_avail_mb REAL,
                mem_used_mb REAL,
                mem_pct REAL,
                gpu_mem TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES test_sessions(id)
            );
            """,
            # 6. load_test_samples 负载测试采样
            """
            CREATE TABLE IF NOT EXISTS load_test_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp REAL DEFAULT 0,
                cpu_pct REAL,
                gpu_pct REAL,
                mem_mb REAL,
                cpu_temp REAL,
                battery REAL,
                FOREIGN KEY (session_id) REFERENCES test_sessions(id)
            );
            """,
            # 7. load_test_summary 负载测试汇总
            """
            CREATE TABLE IF NOT EXISTS load_test_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL UNIQUE,
                rating TEXT DEFAULT '',
                duration_sec REAL DEFAULT 0,
                cpu_avg REAL, cpu_max REAL, cpu_min REAL,
                gpu_avg REAL, gpu_max REAL, gpu_min REAL,
                mem_avg REAL, mem_max REAL, mem_min REAL,
                temp_avg REAL, temp_max REAL, temp_min REAL,
                errors INTEGER DEFAULT 0,
                conclusion_json TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES test_sessions(id)
            );
            """,
            # 8. performance_evaluation 性能评价（帧率测试结束后生成）
            """
            CREATE TABLE IF NOT EXISTS performance_evaluation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                device_serial TEXT DEFAULT '',
                platform TEXT DEFAULT '',
                app_package TEXT DEFAULT '',
                start_time TEXT DEFAULT (datetime('now','localtime')),
                duration_sec REAL DEFAULT 0,
                total_score REAL DEFAULT 0,
                rating TEXT DEFAULT '',
                rating_color TEXT DEFAULT '',
                fps_score REAL DEFAULT 0,
                stability_score REAL DEFAULT 0,
                lowfps_score REAL DEFAULT 0,
                drop_score REAL DEFAULT 0,
                chipset_tier TEXT DEFAULT '',
                chip_detail TEXT DEFAULT '',
                analysis_json TEXT DEFAULT '',
                summary_json TEXT DEFAULT '',
                FOREIGN KEY (session_id) REFERENCES test_sessions(id)
            );
            """,
        ]
        for stmt in statements:
            self._execute(stmt)

    def _create_indexes(self) -> None:
        """创建常用查询索引"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_sessions_device_id ON test_sessions(device_id);",
            "CREATE INDEX IF NOT EXISTS idx_sessions_test_type ON test_sessions(test_type);",
            "CREATE INDEX IF NOT EXISTS idx_fps_samples_session_id ON fps_samples(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_hw_monitor_samples_session_id ON hw_monitor_samples(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_load_test_samples_session_id ON load_test_samples(session_id);",
        ]
        for idx in indexes:
            self._execute(idx)

    # ==================== 设备 ====================

    def get_or_create_device(
        self,
        device_serial: str,
        platform: str,
        info_dict: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        设备存在则更新 last_seen 及可变字段，不存在则插入，返回 device_id。
        :param device_serial: ADB 序列号 / iOS UDID
        :param platform:      'android' / 'ios'
        :param info_dict:     设备硬件信息字典（key 与 _DEVICE_COLUMNS 对应）
        :return:              device_id，失败返回 0
        """
        if not device_serial or not platform:
            logger.warning("get_or_create_device 参数缺失: serial=%s platform=%s",
                           device_serial, platform)
            return 0

        info_dict = info_dict or {}

        try:
            row = self._query_one(
                "SELECT id FROM devices WHERE device_serial = ? AND platform = ?;",
                (device_serial, platform),
            )

            if row is not None:
                device_id = int(row["id"])
                # 动态更新变化的硬件字段
                updates: List[str] = []
                params: List[Any] = []
                for col in _DEVICE_COLUMNS:
                    if col in info_dict and info_dict[col] is not None:
                        updates.append(f"{col} = ?")
                        params.append(info_dict[col])
                # 永远更新 last_seen
                updates.append("last_seen = datetime('now','localtime')")
                if updates:
                    params.append(device_id)
                    sql = f"UPDATE devices SET {', '.join(updates)} WHERE id = ?;"
                    self._execute(sql, tuple(params))
                logger.debug("设备已存在，更新 last_seen: id=%s serial=%s", device_id, device_serial)
                return device_id
            else:
                # 新设备插入
                cols = ["device_serial", "platform"]
                vals: List[Any] = [device_serial, platform]
                for col in _DEVICE_COLUMNS:
                    cols.append(col)
                    vals.append(info_dict.get(col, ""))
                placeholders = ", ".join(["?"] * len(cols))
                col_str = ", ".join(cols)
                sql = f"INSERT INTO devices ({col_str}) VALUES ({placeholders});"
                cur = self._execute(sql, tuple(vals))
                if cur is not None:
                    device_id = int(cur.lastrowid)
                    logger.info("新设备已入库: id=%s serial=%s platform=%s",
                                device_id, device_serial, platform)
                    return device_id
                return 0
        except Exception as e:
            log_exception(e, "get_or_create_device")
            return 0

    # ==================== 会话 ====================

    def create_session(
        self,
        device_id: int,
        platform: str,
        test_type: str,
        app_package: str = "",
        refresh_rate: int = 60,
        poll_interval: float = 1.0,
    ) -> int:
        """
        创建测试会话，返回 session_id。
        :return: 失败返回 0
        """
        if not device_id or not platform or not test_type:
            logger.warning("create_session 参数缺失: device_id=%s platform=%s test_type=%s",
                           device_id, platform, test_type)
            return 0

        sql = (
            "INSERT INTO test_sessions "
            "(device_id, platform, test_type, app_package, refresh_rate, poll_interval) "
            "VALUES (?, ?, ?, ?, ?, ?);"
        )
        cur = self._execute(sql, (device_id, platform, test_type, app_package,
                                  int(refresh_rate), float(poll_interval)))
        if cur is not None:
            session_id = int(cur.lastrowid)
            logger.info("创建会话: id=%s device_id=%s type=%s pkg=%s",
                        session_id, device_id, test_type, app_package)
            return session_id
        return 0

    def finish_session(self, session_id: int, duration_sec: float = 0) -> bool:
        """标记会话结束"""
        if not session_id:
            return False
        sql = (
            "UPDATE test_sessions "
            "SET end_time = datetime('now','localtime'), duration_sec = ? "
            "WHERE id = ?;"
        )
        cur = self._execute(sql, (float(duration_sec), int(session_id)))
        ok = cur is not None
        if ok:
            logger.info("结束会话: id=%s duration=%.1fs", session_id, duration_sec)
        return ok

    # ==================== FPS 采样 / 汇总 ====================

    def _fps_stats_to_dict(self, stats: Any) -> Dict[str, Any]:
        """把 FPSStats 对象或 dict 统一为 fps_samples 字段 dict"""
        if isinstance(stats, dict):
            d = dict(stats)
        else:
            # 假定是 FPSStats dataclass 实例
            d = {}
            for attr in ("timestamp", "fps", "avg_fps", "min_fps", "max_fps",
                         "low_1_fps", "low_01_fps", "std_fps", "jank_count",
                         "total_frames", "jank_rate", "percentile_95",
                         "percentile_99"):
                if hasattr(stats, attr):
                    d[attr] = getattr(stats, attr)

        # 字段别名映射（兼容 dict 风格）
        def _pick(*keys, default=0):
            for k in keys:
                if k in d and d[k] is not None:
                    return d[k]
            return default

        return {
            "timestamp":   _pick("timestamp", default=0),
            "instant_fps": _pick("instant_fps", "fps", default=0),
            "avg_fps":     _pick("avg_fps", default=0),
            "min_fps":     _pick("min_fps", default=0),
            "max_fps":     _pick("max_fps", default=0),
            "low_1_fps":   _pick("low_1_fps", default=0),
            "low_01_fps":  _pick("low_01_fps", default=0),
            "std_fps":     _pick("std_fps", default=0),
            "jank_count":  _pick("jank_count", default=0),
            "total_frames": _pick("total_frames", default=0),
            "jank_rate":   _pick("jank_rate", default=0),
            "p95_frame_ms": _pick("p95_frame_ms", "percentile_95", default=0),
            "p99_frame_ms": _pick("p99_frame_ms", "percentile_99", default=0),
        }

    def insert_fps_sample(self, session_id: int, stats: Any) -> int:
        """
        插入一条帧率采样。stats 可为 FPSStats 对象或 dict。
        :return: 新插入行 id，失败返回 0
        """
        if not session_id:
            return 0
        try:
            d = self._fps_stats_to_dict(stats)
            sql = (
                "INSERT INTO fps_samples "
                "(session_id, timestamp, instant_fps, avg_fps, min_fps, max_fps, "
                " low_1_fps, low_01_fps, std_fps, jank_count, total_frames, "
                " jank_rate, p95_frame_ms, p99_frame_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
            )
            params = (
                int(session_id), float(d["timestamp"]), float(d["instant_fps"]),
                float(d["avg_fps"]), float(d["min_fps"]), float(d["max_fps"]),
                float(d["low_1_fps"]), float(d["low_01_fps"]), float(d["std_fps"]),
                int(d["jank_count"]), int(d["total_frames"]), float(d["jank_rate"]),
                float(d["p95_frame_ms"]), float(d["p99_frame_ms"]),
            )
            cur = self._execute(sql, params)
            return int(cur.lastrowid) if cur is not None else 0
        except Exception as e:
            log_exception(e, "insert_fps_sample")
            return 0

    def insert_fps_summary(self, session_id: int, summary_dict: Dict[str, Any]) -> int:
        """
        插入或替换帧率汇总（session_id 唯一）。
        :return: 行 id，失败返回 0
        """
        if not session_id or not summary_dict:
            return 0
        try:
            d = summary_dict
            sql = (
                "INSERT OR REPLACE INTO fps_summary "
                "(session_id, duration_sec, total_frames, avg_fps, min_fps, max_fps, "
                " low_1_fps, low_01_fps, std_fps, jank_count, jank_rate, "
                " p95_frame_ms, p99_frame_ms, fps_drop_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
            )
            params = (
                int(session_id),
                float(d.get("duration_sec", 0)),
                int(d.get("total_frames", 0)),
                float(d.get("avg_fps", 0)),
                float(d.get("min_fps", 0)),
                float(d.get("max_fps", 0)),
                float(d.get("low_1_fps", 0)),
                float(d.get("low_01_fps", 0)),
                float(d.get("std_fps", 0)),
                int(d.get("jank_count", 0)),
                float(d.get("jank_rate", 0)),
                float(d.get("p95_frame_ms", d.get("percentile_95", 0))),
                float(d.get("p99_frame_ms", d.get("percentile_99", 0))),
                int(d.get("fps_drop_count", 0)),
            )
            cur = self._execute(sql, params)
            row_id = int(cur.lastrowid) if cur is not None else 0
            logger.info("写入 fps_summary: session=%s avg_fps=%.1f jank_rate=%.2f%%",
                        session_id, float(d.get("avg_fps", 0)), float(d.get("jank_rate", 0)))
            return row_id
        except Exception as e:
            log_exception(e, "insert_fps_summary")
            return 0

    # ==================== 硬件监测采样 ====================

    def insert_hw_sample(self, session_id: int, timestamp: float,
                         data_dict: Dict[str, Any]) -> int:
        """
        插入一条硬件监测采样。
        data_dict 字段建议：
          cpu_freqs (dict) -> 序列化为 json 存入 cpu_freqs_json
          cpu_usage, cpu_temp, gpu_freq,
          gpu_load_p50/p90/p95/p99,
          mem_total_mb, mem_avail_mb, mem_used_mb, mem_pct,
          gpu_mem
        :return: 行 id，失败返回 0
        """
        if not session_id or not data_dict:
            return 0
        try:
            d = data_dict
            # cpu_freqs 序列化
            cpu_freqs = d.get("cpu_freqs")
            if isinstance(cpu_freqs, (dict, list)):
                cpu_freqs_json = json.dumps(cpu_freqs, ensure_ascii=False)
            elif isinstance(cpu_freqs, str):
                cpu_freqs_json = cpu_freqs
            else:
                cpu_freqs_json = d.get("cpu_freqs_json", "")

            def _num(key, default=None):
                v = d.get(key, default)
                if v is None or v == "":
                    return None
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return default

            sql = (
                "INSERT INTO hw_monitor_samples "
                "(session_id, timestamp, cpu_freqs_json, cpu_usage, cpu_temp, "
                " gpu_freq, gpu_load_p50, gpu_load_p90, gpu_load_p95, gpu_load_p99, "
                " mem_total_mb, mem_avail_mb, mem_used_mb, mem_pct, gpu_mem) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
            )
            params = (
                int(session_id), float(timestamp if timestamp is not None else 0),
                cpu_freqs_json,
                _num("cpu_usage"), _num("cpu_temp"), _num("gpu_freq"),
                _num("gpu_load_p50"), _num("gpu_load_p90"),
                _num("gpu_load_p95"), _num("gpu_load_p99"),
                _num("mem_total_mb"), _num("mem_avail_mb"), _num("mem_used_mb"),
                _num("mem_pct"),
                d.get("gpu_mem", "") or "",
            )
            cur = self._execute(sql, params)
            return int(cur.lastrowid) if cur is not None else 0
        except Exception as e:
            log_exception(e, "insert_hw_sample")
            return 0

    # ==================== 负载测试采样 / 汇总 ====================

    def insert_load_test_sample(self, session_id: int, timestamp: float,
                                snap_dict: Dict[str, Any]) -> int:
        """
        插入一条负载测试采样。
        snap_dict 字段建议：cpu_pct, gpu_pct, mem_mb, cpu_temp, battery
        :return: 行 id，失败返回 0
        """
        if not session_id or not snap_dict:
            return 0
        try:
            d = snap_dict

            def _num(key, default=None):
                v = d.get(key, default)
                if v is None or v == "":
                    return None
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return default

            sql = (
                "INSERT INTO load_test_samples "
                "(session_id, timestamp, cpu_pct, gpu_pct, mem_mb, cpu_temp, battery) "
                "VALUES (?, ?, ?, ?, ?, ?, ?);"
            )
            params = (
                int(session_id), float(timestamp if timestamp is not None else 0),
                _num("cpu_pct"), _num("gpu_pct"), _num("mem_mb"),
                _num("cpu_temp"), _num("battery"),
            )
            cur = self._execute(sql, params)
            return int(cur.lastrowid) if cur is not None else 0
        except Exception as e:
            log_exception(e, "insert_load_test_sample")
            return 0

    def insert_load_test_summary(self, session_id: int,
                                 summary_dict: Dict[str, Any]) -> int:
        """
        插入或替换负载测试汇总（session_id 唯一）。
        summary_dict 字段建议：
          rating, duration_sec,
          cpu_avg/max/min, gpu_avg/max/min, mem_avg/max/min, temp_avg/max/min,
          errors, conclusion (list[str] 或 str)
        :return: 行 id，失败返回 0
        """
        if not session_id or not summary_dict:
            return 0
        try:
            d = summary_dict

            # conclusion 序列化
            conclusion = d.get("conclusion", d.get("conclusion_json", ""))
            if isinstance(conclusion, (list, dict)):
                conclusion_json = json.dumps(conclusion, ensure_ascii=False)
            elif isinstance(conclusion, str):
                # 若已经是 JSON 字符串则原样保存，否则包装为单元素数组
                conclusion_json = conclusion if conclusion.strip().startswith(("[", "{")) \
                    else json.dumps([conclusion], ensure_ascii=False)
            else:
                conclusion_json = ""

            def _num(key, default=None):
                v = d.get(key, default)
                if v is None or v == "":
                    return None
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return default

            sql = (
                "INSERT OR REPLACE INTO load_test_summary "
                "(session_id, rating, duration_sec, "
                " cpu_avg, cpu_max, cpu_min, gpu_avg, gpu_max, gpu_min, "
                " mem_avg, mem_max, mem_min, temp_avg, temp_max, temp_min, "
                " errors, conclusion_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
            )
            params = (
                int(session_id),
                str(d.get("rating", "")),
                float(d.get("duration_sec", 0)),
                _num("cpu_avg"), _num("cpu_max"), _num("cpu_min"),
                _num("gpu_avg"), _num("gpu_max"), _num("gpu_min"),
                _num("mem_avg"), _num("mem_max"), _num("mem_min"),
                _num("temp_avg"), _num("temp_max"), _num("temp_min"),
                int(d.get("errors", 0) or 0),
                conclusion_json,
            )
            cur = self._execute(sql, params)
            row_id = int(cur.lastrowid) if cur is not None else 0
            logger.info("写入 load_test_summary: session=%s rating=%s",
                        session_id, d.get("rating", ""))
            return row_id
        except Exception as e:
            log_exception(e, "insert_load_test_summary")
            return 0

    # ==================== 查询接口 ====================

    def get_recent_sessions(self, test_type: Optional[str] = None,
                            limit: int = 20) -> List[sqlite3.Row]:
        """
        查询最近 N 条会话（按 start_time 倒序）。
        :param test_type: 可选过滤 'fps' / 'hw_monitor' / 'load_test'
        :param limit:     返回条数
        """
        if test_type:
            sql = (
                "SELECT s.*, d.device_serial, d.brand, d.model "
                "FROM test_sessions s "
                "LEFT JOIN devices d ON s.device_id = d.id "
                "WHERE s.test_type = ? "
                "ORDER BY s.start_time DESC LIMIT ?;"
            )
            return self._query_all(sql, (test_type, int(limit)))
        else:
            sql = (
                "SELECT s.*, d.device_serial, d.brand, d.model "
                "FROM test_sessions s "
                "LEFT JOIN devices d ON s.device_id = d.id "
                "ORDER BY s.start_time DESC LIMIT ?;"
            )
            return self._query_all(sql, (int(limit),))

    def get_fps_samples(self, session_id: int) -> List[sqlite3.Row]:
        """查询某会话的全部帧率采样（按时间升序）"""
        if not session_id:
            return []
        sql = (
            "SELECT * FROM fps_samples "
            "WHERE session_id = ? ORDER BY timestamp ASC;"
        )
        return self._query_all(sql, (int(session_id),))

    def get_hw_samples(self, session_id: int) -> List[sqlite3.Row]:
        """查询某会话的全部硬件监测采样（按时间升序）"""
        if not session_id:
            return []
        sql = (
            "SELECT * FROM hw_monitor_samples "
            "WHERE session_id = ? ORDER BY timestamp ASC;"
        )
        return self._query_all(sql, (int(session_id),))

    def get_load_test_samples(self, session_id: int) -> List[sqlite3.Row]:
        """查询某会话的全部负载测试采样（按时间升序）"""
        if not session_id:
            return []
        sql = (
            "SELECT * FROM load_test_samples "
            "WHERE session_id = ? ORDER BY timestamp ASC;"
        )
        return self._query_all(sql, (int(session_id),))

    # ==================== 性能评价 ====================

    def insert_evaluation(self, eval_dict: Dict[str, Any]) -> int:
        """
        插入一条性能评价记录。eval_dict 字段：
          session_id(可选), device_serial, platform, app_package, start_time(datetime或str),
          duration_sec, total_score, rating, rating_color,
          scores: {fps, stability, lowfps, drop},
          chipset_tier, chip_detail,
          analysis_lines (list[str]), summary (dict)
        :return: 行 id，失败返回 0
        """
        if not eval_dict:
            return 0
        try:
            d = eval_dict
            scores = d.get("scores") or {}
            analysis = d.get("analysis_lines") or []
            summary = d.get("summary") or {}

            def _s(key, default=""):
                v = d.get(key, default)
                return default if v is None else str(v)

            def _f(key, default=0.0):
                v = d.get(key, default)
                try:
                    return float(v) if v is not None else default
                except (TypeError, ValueError):
                    return default

            start_time = d.get("start_time")
            if hasattr(start_time, "strftime"):
                start_time_s = start_time.strftime("%Y-%m-%d %H:%M:%S")
            elif start_time:
                start_time_s = str(start_time)
            else:
                start_time_s = None

            sql = (
                "INSERT INTO performance_evaluation "
                "(session_id, device_serial, platform, app_package, start_time, duration_sec, "
                " total_score, rating, rating_color, "
                " fps_score, stability_score, lowfps_score, drop_score, "
                " chipset_tier, chip_detail, analysis_json, summary_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
            )
            params = (
                d.get("session_id") or None,
                _s("device_serial"),
                _s("platform"),
                _s("app_package"),
                start_time_s,
                _f("duration_sec"),
                _f("total_score"),
                _s("rating"),
                _s("rating_color"),
                float(scores.get("fps", 0) or 0),
                float(scores.get("stability", 0) or 0),
                float(scores.get("lowfps", 0) or 0),
                float(scores.get("drop", 0) or 0),
                _s("chipset_tier"),
                _s("chip_detail"),
                json.dumps(analysis, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False) if isinstance(summary, (dict, list)) else "",
            )
            cur = self._execute(sql, params)
            row_id = int(cur.lastrowid) if cur is not None else 0
            logger.info("写入 performance_evaluation: id=%s score=%.1f rating=%s",
                        row_id, _f("total_score"), _s("rating"))
            return row_id
        except Exception as e:
            log_exception(e, "insert_evaluation")
            return 0

    def get_recent_evaluations(self, limit: int = 20) -> List[sqlite3.Row]:
        """查询最近 N 条性能评价（按 start_time 倒序）"""
        sql = "SELECT * FROM performance_evaluation ORDER BY start_time DESC LIMIT ?;"
        return self._query_all(sql, (int(limit),))

    def get_recent_load_summaries(self, limit: int = 20) -> List[sqlite3.Row]:
        """查询最近 N 条负载测试汇总（含会话与设备信息）"""
        sql = (
            "SELECT ls.*, s.start_time, s.end_time, s.duration_sec AS sess_duration, "
            "       s.device_id, s.platform, s.app_package, "
            "       d.device_serial, d.brand, d.model "
            "FROM load_test_summary ls "
            "LEFT JOIN test_sessions s ON ls.session_id = s.id "
            "LEFT JOIN devices d ON s.device_id = d.id "
            "ORDER BY s.start_time DESC LIMIT ?;"
        )
        return self._query_all(sql, (int(limit),))

    # ==================== 关闭 ====================

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn is not None:
            try:
                with self._lock:
                    self._conn.commit()
                    self._conn.close()
                logger.info("数据库连接已关闭: %s", self.db_path)
            except Exception as e:
                log_exception(e, "db_close")
            finally:
                self._conn = None
                # 重置单例，允许后续重新初始化
                with DatabaseManager._instance_lock:
                    DatabaseManager._instance = None
                    self._initialized = False


# ==================== 模块级便捷函数 ====================

def get_db() -> DatabaseManager:
    """获取 DatabaseManager 单例"""
    return DatabaseManager()
