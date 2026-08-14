import sys
import os
import csv
import time
import tempfile
import shutil
import webbrowser
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from collections import deque, defaultdict
from statistics import stdev as statistics_stdev

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QGridLayout,
    QTextEdit, QFileDialog, QMessageBox, QProgressBar, QSplitter,
    QCheckBox, QTabWidget, QFrame, QScrollArea, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView,
    QStackedWidget, QDialog, QPlainTextEdit, QMenu, QDialogButtonBox, QAction
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QEvent, QSize, QPointF, QRectF, QSettings, QUrl
from PyQt5.QtGui import QFont, QColor, QPalette, QPixmap, QIcon, QPainter, QPen, QBrush, QRadialGradient, QLinearGradient

import pyqtgraph as pg
from pyqtgraph import PlotWidget, mkPen

from adb_client import ADBClient
from fps_analyzer import FPSAnalyzer, FPSStats
from ios_client import IOSClient, IOSMonitor, IOSFPSCollector
from app_logger import get_logger, log_exception, get_log_dir, shutdown_logging
from db_manager import DatabaseManager

_logger = get_logger("main_window")


# ============================================================
# 多语言翻译表 — 覆盖欢迎页 / 设备选择页 / 窗口标题 / 帮助菜单
# 默认 zh-CN，缺失翻译时回落到 key 对应的中文原文
# ============================================================
_TRANSLATIONS: dict = {
    "zh-CN": {
        "app_title": "星穹视界帧率测试 - Stellar Vision FPS Tester",
        "welcome_title": "星穹视界测试工具",
        "welcome_subtitle": "专业移动设备性能测试平台",
        "welcome_features": "帧率测试  ·  CPU/GPU 监测  ·  数据分析",
        "welcome_start": "▶  开始测试",
        "lang_label": "🌐",
        "select_device_title": "请选择设备类型",
        "select_back_home": "←  返回首页",
        "android_card_title": "Android",
        "android_card_sub": "安卓设备",
        "ios_card_title": "iOS",
        "ios_card_sub": "苹果设备",
        "init_progress_title": "正在初始化测试环境...",
        "init_progress_sub": "扫描设备 · 建立连接 · 加载驱动",
        "help_menu": "帮助(&H)",
        "help_view_log": "📄 查看日志内容...",
        "help_open_log_dir": "📂 打开日志目录...",
        "help_reveal_log": "📋 在访达中显示当前日志文件...",
        "help_about": "ℹ️ 关于",
        "tab_fps": "🎮 帧率测试",
        "tab_hw": "📊 CPU/GPU 监测",
        "tab_history": "📜 CSV 历史记录",
        "tab_device_info": "📱 手机信息",
        "tab_load_test": "🔥 负载测试",
        # ---- 返回/导航按钮 ----
        "btn_back_select": "←  返回设备选择",
        "btn_back_history": "←  返回历史记录",
        # ---- 帧率测试页：设备与应用设置 ----
        "grp_device_settings": "设备与应用设置",
        "lbl_device": "设备:",
        "btn_refresh_device": "🔄 刷新设备",
        "lbl_app": "测试应用:",
        "btn_get_app": "📱 获取当前应用",
        "btn_list_apps": "📋 列出已安装应用",
        "lbl_refresh_rate": "屏幕刷新率:",
        "lbl_interval": "采集间隔(秒):",
        "lbl_device_info": "设备信息: 未连接",
        "btn_start_test": "▶ 开始测试",
        "btn_stop_test": "■ 停止测试",
        "btn_export": "📊 导出报告",
        "btn_clear": "🗑 清空数据",
        "lbl_duration": "测试时长: 00:00",
        # ---- 图表 ----
        "chart_fps_title": "FPS 实时曲线",
        "chart_frame_title": "帧时间分布 (最近采样)",
        "chart_fps_left": "FPS",
        "chart_fps_bottom": "时间 (秒)",
        "chart_frame_left": "帧时间 (ms)",
        "chart_frame_bottom": "帧序号",
        "curve_instant_fps": "瞬时FPS",
        "curve_avg_fps": "平均FPS",
        "lbl_jank_threshold": "卡顿阈值 (16.67ms)",
        # ---- 统计面板 ----
        "grp_realtime_stats": "📊 实时统计",
        "stat_current_fps": "当前FPS",
        "stat_avg_fps": "平均FPS",
        "stat_min_fps": "最低FPS",
        "stat_max_fps": "最高FPS",
        "stat_low_1": "1% Low",
        "stat_low_01": "0.1% Low",
        "stat_std_fps": "FPS标准差",
        "stat_jank_count": "卡顿帧数",
        "stat_total_frames": "总帧数",
        "stat_jank_rate": "卡顿率",
        "stat_p95": "P95帧时(ms)",
        "stat_p99": "P99帧时(ms)",
        # ---- 卡顿率指示 ----
        "grp_jank_indicator": "卡顿率指示",
        "lbl_jank_hint": "💚 优秀 < 2%   💛 良好 2-5%   ❤️ 较差 > 5%",
        # ---- 日志输出 ----
        "grp_log_output": "📝 日志输出",
        # ---- CPU/GPU 监测页 ----
        "lbl_monitor_device": "监测设备:",
        "lbl_interval_short": "间隔:",
        "tip_hw_interval": "CPU/GPU 数据采样间隔（秒）",
        "tip_hw_interval_ios": "CPU/GPU/内存 数据采样间隔（秒）",
        "btn_start_monitor": "▶ 开始监测",
        "btn_stop_monitor": "■ 停止监测",
        "lbl_status": "状态: 待机",
        "lbl_ios_note": "ℹ️ iOS 系统限制：仅支持 CPU 使用率与内存监测，不提供 CPU/GPU 频率。需挂载开发者镜像 (DDI)，iOS 17+ 需先运行 RSD 隧道。",
        "grp_cpu_usage": "🖥 CPU 使用率",
        "grp_gpu_usage": "🎨 GPU 利用率",
        "grp_memory": "💾 内存",
        "lbl_core_count": "核心数: --",
        "lbl_renderer": "渲染器:",
        "lbl_tiler": "平铺器:",
        "grp_prime": "🚀 CPU 超大核 (Prime)",
        "lbl_prime_max": "最大: -- MHz",
        "lbl_prime_cores": "核心: --",
        "grp_cpu_clusters": "📊 CPU 全部集群频率",
        "grp_cpu_temp_usage": "🌡 CPU 利用率 / 温度",
        "lbl_cpu_temp": "CPU 温度:",
        "grp_gpu_freq": "🎮 GPU 频率",
        "lbl_gpu_max": "最大: -- MHz",
        "grp_gpu_load": "📈 GPU 渲染负载 (gfxinfo 百分位)",
        "grp_mem_gpu": "💾 内存 / GPU 显存",
        "lbl_gpu_mem": "GPU 显存: --",
        "chart_hw_freq_title": "CPU / GPU 频率实时曲线 (MHz)",
        "chart_hw_freq_left": "频率 (MHz)",
        "chart_temp_title": "🌡 CPU 温度实时曲线 (°C)",
        "chart_temp_left": "温度 (°C)",
        "chart_usage_title": "📊 CPU 使用率 / 内存使用率实时曲线 (%)",
        "chart_usage_left": "使用率 (%)",
        "chart_ios_hw_title": "CPU / GPU / 内存 使用率曲线",
        "chart_usage_left_ios": "使用率 (%)",
        # ---- 设备信息页 ----
        "lbl_select_device": "选择设备:",
        "btn_get_info": "📡 获取设备信息",
        "grp_device_info": "📋 设备基础信息",
        "header_item": "项目",
        "header_detail": "详情",
        # ---- CSV 历史记录页 ----
        "lbl_history_tip": "保留最近 5 次 帧率测试 / CPU-GPU 监测 完整数据，点击左侧条目查看详情",
        "btn_export_csv": "📦 导出选中 CSV",
        "btn_contact": "📧 联系作者",
        "btn_contact_report": "📧 联系作者 · 上报问题",
        "grp_fps_history": "🎮 帧率测试记录 (最近 5 次)",
        "grp_hw_history": "🔧 CPU/GPU 监测记录 (最近 5 次)",
        "grp_detail_summary": "📋 详情摘要",
        "grp_stats_data": "📊 统计数据",
        "grp_time_series": "📈 时间序列曲线",
        "header_metric": "指标",
        "header_value": "数值",
        "lbl_temp_axis": "温度 (°C)",
        # ---- 负载测试页 ----
        "btn_start_load": "▶  开始负载测试",
        "btn_stop_load": "■  停止",
        "btn_export_load": "📤 导出报告",
        "btn_retest_load": "🔄 重新测试",
        "lbl_remain_time": "⏱  已运行时长",
        "lbl_elapsed": "已运行 00:00:00",
        "lbl_load_cpu": "🔥 CPU 使用率",
        "lbl_load_gpu": "🎨 GPU 利用率",
        "lbl_load_mem": "💾 内存使用",
        "lbl_load_temp": "🌡 CPU 温度",
        "chart_load_temp_title": "🌡 CPU 温度实时曲线 (°C)",
        "chart_load_temp_left": "CPU 温度",
        "chart_load_temp_bottom": "时间 (样本秒)",
        "grp_realtime_log": "📝 实时日志",
        "lbl_conclusion": "📋 稳定性结论",
        "lbl_waiting": "等待测试开始...",
        # ---- iOS 识别前台应用按钮 ----
        "btn_foreground_app": "📱 识别前台应用",
        "btn_ddi_status": "🔍 DDI 状态",
        # ---- 状态文本 ----
        "status_idle": "状态: 待机",
        "status_monitoring": "状态: 🟢 监测中...",
        "status_connecting": "状态: 🟡 连接中...",
        "status_stopped": "状态: ⏸ 已停止",
        "status_cleared": "状态: 🧹 已清空数据",
        "status_exported": "状态: ✅ 报告已导出",
        "status_html_exported": "状态: ✅ HTML 报告已导出",
        "status_start_failed": "状态: ❌ 启动失败",
        "status_export_failed": "状态: ❌ 导出失败",
        "status_error_prefix": "状态: ❌ ",
        # ---- 下拉项 ----
        "combo_no_device": "未检测到设备",
        "combo_no_device_tip": "未检测到设备，请连接手机并开启USB调试",
        "combo_no_ios_device_tip": "未检测到 iOS 设备，请连接并信任此电脑",
        "combo_no_app_list": "未检测到设备",
        # ---- 联系页 ----
        "grp_contact_title": "📧 联系作者 · 问题反馈",
        "lbl_contact_desc": "如在使用中遇到任何问题或有改进建议，欢迎发送邮件反馈",
        "btn_copy": "复制",
        "btn_open_mail": "📨 打开邮件客户端",
        "lbl_contact_tip": "💡 提示：点击邮箱地址或「复制」按钮可快速复制邮箱到剪贴板",
        "msg_email_copied": "作者邮箱已复制到剪贴板:\nstardomevision@outlook.com",
        "msg_copied": "已复制",
        # ---- 免责声明 ----
        "msg_disclaimer_title": "⚠️ 使用须知与免责",
        "txt_disclaimer": "本性能测试仅作爱好者性能对比参考。高负载渲染会拉高设备温度，老旧设备可能出现卡顿、过热降频、闪退。\n\n测试结果受系统、浏览器、散热条件影响，数值仅供参考，不作为硬件质检、商业宣传依据。\n\n因运行压力测试造成设备损耗，由使用者自行承担风险。\n\n点击「同意并继续」即代表同意以上条款。",
        "btn_agree": "同意并继续",
        "btn_reject": "拒绝",
        # ---- 关于对话框 ----
        "msg_about_title": "关于 星穹视界帧率测试",
        "msg_about_body": "星穹视界帧率测试\n版本: 2.1.0\n\n功能: Android / iOS 游戏帧率、CPU/GPU 占用率监测\n\n",
        # ---- 日志对话框 ----
        "msg_log_content_title": "日志内容",
        "btn_refresh": "🔄 刷新",
        "btn_close": "关闭",
        "msg_log_dir": "日志目录",
        "msg_log_dir_body": "日志目录路径：\n{path}\n\n请手动在访达中打开。",
        # ---- 提示框文本 ----
        "msg_no_data": "提示",
        "msg_no_fps_data": "暂无帧率数据可导出，请先运行测试",
        "msg_no_hw_data": "暂无硬件监测数据可导出，请先开始监测",
        "msg_no_export_data": "暂无可导出数据，请先运行测试",
        "msg_no_hw_export_data": "暂无监测数据可导出，请先开始监测",
        "msg_select_history": "请先在左侧选择一条记录",
        "msg_select_history_ios": "请先选择一条历史记录",
        "msg_select_device": "请先选择设备",
        "msg_select_device_connect": "请先选择设备并连接",
        "msg_select_app": "请输入或选择要测试的应用包名",
        "msg_select_ios_device": "请先选择 iOS 设备",
        "msg_select_ios_device_monitor": "请先选择要监测的 iOS 设备",
        "msg_select_device_monitor": "请先选择要监测的设备",
        "msg_select_device_load": "请先选择设备",
        "msg_test_running": "测试进行中无法清空，请先停止测试",
        "msg_monitor_running": "监测进行中无法清空，请先停止监测",
        "msg_confirm_clear": "确认清空",
        "msg_confirm_clear_body": "确定要清空当前所有测试数据吗？此操作不可撤销。",
        "msg_load_confirm": "负载测试确认",
        "msg_load_confirm_body": "即将启动满负载稳定性测试（倒计时 1 小时，可随时点击停止按钮提前结束）。\n\n⚠️ 测试期间设备将高负荷工作，可能出现高溫、降频、风扇狂转。\n⚠️ 请确保散热良好、电量充足，必要时连接电源。\n\n是否继续？",
        "msg_load_finish_first": "请先完成或停止负载测试以生成报告",
        "load_principle_title": "📋 负载测试原理",
        "load_principle_body": "负载测试通过在设备端持续施加高负载（多核 CPU 满载算术循环），模拟长时间高强度的实际使用场景，监测 CPU 使用率、内存占用与核心温度的变化趋势，评估设备的散热能力与降频控制策略。\n\n测试为 1 小时倒计时（可随时点击停止按钮提前结束）。每秒采集一次设备硬件快照，结束后生成稳定性评级（良好 / 中 / 差）与完整趋势报告。",
        "load_risk_title": "⚠️ 风险提示",
        "load_risk_body": "1. 测试期间设备将高负荷运行，CPU 温度可能显著升高，属于正常现象。\n2. 老旧或散热不佳的设备可能出现降频、卡顿甚至自动关机，请注意散热。\n3. 建议测试期间连接电源，避免电量耗尽导致测试中断。\n4. 测试数据仅供性能参考，不作为硬件质量评判的唯一依据。\n5. 因测试造成的设备损耗由用户自行承担风险。",
        "btn_load_confirm_start": "✅ 确认并开始测试",
        "load_running_title": "🚀 测试进行中",
        "load_running_hint_anim": "设备端正在持续高负载运行，请保持设备散热良好",
        "load_test_complete_title": "✅ 测试已完成",
        "load_test_complete_msg": "负载测试已完成，正在生成稳定性报告...",
        "load_result_title": "📊 测试结果",
        "chart_load_cpu_usage": "CPU 使用率曲线 (%)",
        "chart_load_mem_usage": "内存使用曲线 (MB)",
        "chart_load_temp_result": "CPU 温度曲线 (°C)",
        "tbl_load_cpu_stats": "CPU 使用率统计",
        "tbl_load_col_samples": "样本数",
        "tbl_load_col_avg": "平均值",
        "tbl_load_col_max": "最大值",
        "tbl_load_col_min": "最小值",
        "grp_load_detail_table": "📋 详细统计",
        "grp_load_result_charts": "📈 趋势曲线",
        "load_metric_cpu": "CPU 使用率(%)",
        "load_metric_gpu": "GPU 利用率(%)",
        "load_metric_mem": "内存(MB)",
        "load_metric_cpu_temp": "CPU 温度(°C)",
        "lbl_rating": "评级",
        "lbl_duration_short": "时长",
        "lbl_errors": "异常",
        "lbl_cpu_avg_pct": "CPU均(%)",
        "lbl_cpu_peak_pct": "CPU峰(%)",
        "lbl_mem_avg_mb": "内存均(MB)",
        "lbl_mem_peak_mb": "内存峰(MB)",
        "lbl_temp_avg_c": "温度均(°C)",
        "lbl_temp_peak_c": "温度峰(°C)",
        "rating_good": "良好",
        "rating_warn": "中",
        "rating_bad": "差",
        "platform_android": "安卓",
        "platform_ios": "iOS",
        "load_con_duration": "测试时长：{min} 分 {sec} 秒（共 {total} 秒）",
        "load_con_samples": "采样点（CPU/GPU/内存/CPU温度）：{cpu} / {gpu} / {mem} / {temp}",
        "load_con_cpu": "CPU 使用率：平均 {avg:.1f}%  /  峰值 {max:.1f}%  /  谷值 {min:.1f}%",
        "load_con_cpu_na": "CPU 使用率：未采集",
        "load_con_gpu": "GPU 利用率：平均 {avg:.1f}%  /  峰值 {max:.1f}%  /  谷值 {min:.1f}%",
        "load_con_gpu_na": "GPU 利用率：未采集",
        "load_con_mem": "内存使用：平均 {avg:.0f} MB  /  峰值 {max:.0f} MB",
        "load_con_mem_na": "内存使用：未采集",
        "load_con_temp": "CPU 温度：平均 {avg:.1f}°C  /  峰值 {max:.1f}°C  /  谷值 {min:.1f}°C",
        "load_con_temp_na": "CPU 温度：未采集",
        "load_con_errors": "⚠️ 异常中断次数：{count}",
        "load_con_issues_found": "⚠️ 发现问题 {count} 项：",
        "load_con_no_issues": "✅ 未发现明显异常点",
        "load_con_rating": "稳定性评级：【{rating}】",
        "load_con_good": "→ 结论：该设备持续高负载运行过程中CPU温度与资源占用表现稳定，散热设计与降频控制良好，可认为通过稳定性测试。",
        "load_con_warn": "→ 结论：该设备满载时CPU温度偏高，但未触发明显降频 / 闪退临界线，属于常规性能机器的中等表现，需要注意使用环境散热。",
        "load_con_bad": "→ 结论：该设备在持续高负载下CPU温度明显超标或存在频繁采集异常，表明温控 / 降频策略可能无法承受持续压力，建议排查散热条件或降低游戏画质后重试。",
        "load_issue_crash": "采集异常中断 {count} 次",
        "load_issue_temp_peak": "CPU 温度峰值 {temp:.1f}°C，超过安全阈值",
        "load_issue_temp_high": "CPU 温度峰值 {temp:.1f}°C，属于高温边缘",
        "load_issue_cpu_avg": "CPU 平均负载 {avg:.1f}%，持续满载",
        "load_issue_cpu_peak": "CPU 峰值 {max:.1f}%，处于降频风险",
        "load_csv_report_title": "{platform}负载测试报告",
        "load_csv_conclusion": "=== 结论 ===",
        "load_csv_stats": "=== 统计数据 ===",
        "load_csv_trend": "=== 趋势采样（秒级）===",
        "load_csv_metric": "指标",
        "load_csv_seconds": "秒数",
        "load_csv_duration_sec": "实际时长 (秒)",
        "load_csv_export_time": "导出时间",
        "load_csv_device_id": "设备 ID",
        "load_html_stability_conclusion": "📋 稳定性结论",
        "load_html_resource_trend": "资源占用趋势（CPU / GPU / 内存）",
        "load_html_temp_curve": "CPU 温度实时曲线",
        "load_html_sample_sec": "采样秒数",
        "load_html_cpu_avg": "CPU 均值",
        "load_html_gpu_avg": "GPU 均值",
        "load_html_temp_avg": "CPU 温度均值",
        "load_html_cpu_peak": "CPU 峰值",
        "load_html_gpu_peak": "GPU 峰值",
        "load_html_temp_peak": "CPU 温度峰值",
        "load_html_chart_snapshot": "📊 曲线图快照",
        "load_html_per_sec": "每 1 秒 1 采样",
        "load_html_draggable": "可拖拽缩放",
        "load_html_cpu_core_temp": "CPU 核心 thermal_zone 最高温",
        "load_html_threshold_bad": ">65°C 判定为『差』",
        "load_html_mem_div100": "内存使用/100(%)",
        "load_html_device_platform": "设备平台",
        "load_html_test_duration": "测试时长",
        "load_html_error_count": "异常中断次数",
        "load_jpg_no_screenshot": "无法获取结果页截图",
        "load_metric_power": "设备功率(mW)",
        "chart_power_title": "⚡ 设备功率实时曲线 (mW)",
        "chart_power_left": "功率 (mW)",
        "legend_power": "设备功率",
        "stat_avg_fps_large": "🎯 平均 FPS",
        "msg_export_success_jpg": "JPG 图片已导出到:\n{path}",
        "msg_export_failed_jpg": "导出 JPG 失败:\n{err}",
        "fps_eval_title": "🏆 综合性能评价",
        "fps_eval_score": "综合评分",
        "fps_eval_rating": "性能等级",
        "fps_eval_chipset": "芯片分析",
        "fps_eval_analysis": "详细分析",
        "fps_eval_fps_score": "帧率达标度",
        "fps_eval_stability_score": "稳定性",
        "fps_eval_lowfps_score": "Low FPS 表现",
        "fps_eval_drop_score": "掉帧控制",
        "fps_eval_excellent": "⭐ 优秀",
        "fps_eval_good": "✅ 良好",
        "fps_eval_fair": "🔶 中等",
        "fps_eval_poor": "⚠️ 较差",
        "fps_eval_bad": "❌ 差",
        "fps_eval_chipset_flagship": "旗舰级芯片",
        "fps_eval_chipset_highend": "高端芯片",
        "fps_eval_chipset_midrange": "中端芯片",
        "fps_eval_chipset_budget": "入门级芯片",
        "fps_eval_chipset_unknown": "未知芯片",
        "fps_eval_no_data": "数据不足，无法评价",
        "fps_eval_close": "关闭",
        "msg_usb_debug_title": "USB 调试确认",
        "msg_usb_debug_body": "是否已打开 USB 调试？\n\n请在手机「设置 → 开发者选项」中开启 USB 调试，\n并通过数据线连接电脑。",
        "msg_dev_mode_title": "开发者模式确认",
        "msg_dev_mode_body": "是否已打开开发者模式？\n\n请在 iPhone「设置 → 隐私与安全性 → 开发者模式」中开启，\n并通过数据线连接电脑并信任此电脑。",
        "msg_export_success": "导出成功",
        "msg_export_failed": "导出失败",
        "msg_export_success_csv": "CSV 报告已保存到:\n{path}",
        "msg_export_success_html": "HTML 报告已导出至:\n{path}",
        "msg_export_success_report": "报告已导出至:\n{path}",
        "msg_export_success_html_report": "HTML 报告已保存到:\n{path}",
        "msg_export_success_hw_html": "HTML 监测报告已导出到:\n{path}",
        "msg_export_success_monitor": "监测报告已导出到:\n{path}",
        "msg_export_success_fps_history": "帧率历史已导出到:\n{path}",
        "msg_export_success_hw_history": "CPU/GPU 监测历史已导出到:\n{path}",
        "msg_export_failed_csv": "导出 CSV 失败:\n{err}",
        "msg_export_failed_html": "导出 HTML 失败:\n{err}",
        "msg_export_failed_simple": "导出失败: {err}",
        "msg_failed": "失败",
        "msg_success": "成功",
        "msg_error": "错误",
        "msg_adb_error": "ADB错误",
        "msg_start_test_failed": "开始测试失败:\n{err}",
        "msg_start_ios_fps_failed": "启动 iOS 帧率测试失败:\n{err}",
        "msg_start_ios_hw_failed": "启动 iOS 硬件监测失败:\n{err}",
        "msg_start_hw_failed": "启动硬件监测失败:\n{err}",
        "msg_get_info_failed": "获取设备信息失败:\n{err}",
        "msg_get_info_failed_ios": "获取设备信息失败:\n{info_err}",
        "msg_ios_foreground_none": "未检测到前台应用，设备可能处于主屏幕",
        "msg_ios_foreground_failed": "识别失败",
        "msg_ios_foreground_failed_body": "错误:\n{err}",
        "msg_ios_foreground_title": "前台应用",
        "msg_ddi_title": "DDI 状态",
        "msg_ddi_check_failed": "检查 DDI 状态失败:\n{err}",
        "msg_ios_monitor_failed": "启动 iOS 硬件监测失败:\n{err}",
        "msg_startup_error": "启动错误",
        "msg_disclaimer_failed": "免责声明弹窗显示失败：\n{err}",
        "msg_save_failed": "保存失败",
        "msg_select_android_device": "请先连接并选择一个安卓设备",
        # ---- 导出菜单 ----
        "menu_csv_export": "📄  CSV 导出",
        "menu_html_export": "🌐  HTML 导出",
        # ---- 设备信息表项 ----
        "info_phone_name": "📱 手机名称",
        "info_chip_name": "🔧 芯片名称",
        "info_unknown": "未知",
        "info_unknown_device": "未知设备",
        # ---- 进度页文案 ----
        "prog_entering": "正在进入 {name} 测试环境...",
        "prog_scanning": "扫描设备中...",
        "prog_connecting": "建立 USB / 网络连接...",
        "prog_loading_driver": "加载驱动与权限校验...",
        "prog_ready": "准备就绪，正在进入...",
        "prog_phase_prefix": "{n} / 4  {text}",
        "prog_complete": "✅ 完成！即将进入...",
        # ---- 历史摘要行 ----
        "hist_rec_type": "记录类型",
        "hist_start_time": "开始时间",
        "hist_end_time": "结束时间",
        "hist_device": "设备",
        "hist_test_duration": "测试时长",
        "hist_monitor_duration": "监测时长",
        "hist_test_app": "测试应用",
        "hist_avg_fps": "平均FPS",
        "hist_low_1": "1% Low",
        "hist_low_01": "0.1% Low",
        "hist_jank_rate": "卡顿率",
        "hist_rec_type_fps": "🎮 帧率测试",
        "hist_rec_type_hw": "🔧 CPU/GPU 监测",
        "hist_cpu_clusters": "CPU 集群数",
        "hist_gpu_samples": "GPU 采样点",
        "hist_total_samples": "总采样点",
        "hist_usage": "使用率",
        # ---- 导出预览对话框 ----
        "btn_cancel": "取消",
        "btn_save_html": "💾 保存为 HTML",
        "btn_save_csv": "💾 保存为 CSV",
        "lbl_html_preview_tip": "以下为 HTML 报告预览（ECharts 图表需联网 CDN，保存后双击文件即可正常查看）",
        "lbl_csv_preview_tip": "以下为 CSV 报告预览（为便于阅读，文本格式化为表格），确认后点击保存。",
        "msg_save_html_title": "保存 HTML 报告",
        "msg_save_csv_title": "保存 CSV 报告",
        "dlg_export_history": "导出历史记录 CSV",
        "fmt_html_filter": "HTML 文件 (*.html)",
        "fmt_csv_filter": "CSV 文件 (*.csv)",
        "lbl_column": "列",
        "lbl_load_device": "设备:",
        "lbl_empty_history": "👈 请选择左侧一条历史记录查看详情",
        "combo_error_prefix": "错误: ",
        "msg_about_log_dir": "日志目录:\n{path}",
        "msg_log_file": "日志文件",
        "msg_log_file_body": "日志文件路径：\n{path}",
        "msg_ios_monitor_start_failed_title": "iOS 监测启动失败",
        "msg_ios_monitor_start_failed_text": "无法启动 iOS DVT 监测会话。",
        # ---- 运行时状态文案 ----
        "stat_device_disconnected": "设备信息: 未连接",
        "stat_duration_zero": "测试时长: 00:00",
        "stat_start_failed": "状态: ❌ 启动失败",
        "stat_connecting": "状态: 🟡 连接中...",
        "stat_monitoring": "状态: 🟢 监测中...",
        "stat_stopped": "状态: ⏸ 已停止",
        "stat_cleared": "状态: 🧹 已清空数据",
        "stat_html_exported": "状态: ✅ HTML 报告已导出",
        "stat_report_exported": "状态: ✅ 报告已导出",
        "stat_export_failed": "状态: ❌ 导出失败",
        "stat_cpu_cores_na": "核心数: --",
        "stat_max_na": "最大: -- MHz",
        "stat_cores_na": "核心: --",
        "stat_gpu_mem_na": "GPU 显存: --",
        "note_gpu_freq_selinux": "⚠ GPU 频率受 Android SELinux 限制无法读取（非 root），请参考下方 GPU 渲染负载",
        "load_running_hint": "测试进行中，结束后将自动生成结论...",
        # ---- 导出预览对话框标题 ----
        "preview_ios_fps_csv": "iOS 帧率 CSV 预览",
        "preview_ios_hw_csv": "iOS 硬件 CSV 预览",
        "preview_android_fps_html": "安卓帧率 HTML 预览",
        "preview_android_hw_html": "安卓 CPU/GPU HTML 预览",
        "preview_ios_fps_html": "iOS 帧率 HTML 预览",
        "preview_ios_hw_html": "iOS 硬件 HTML 预览",
        "preview_android_fps_csv": "安卓帧率 CSV 预览",
        "preview_android_hw_csv": "安卓 CPU/GPU CSV 预览",
        "preview_load_csv": "{platform}负载测试 CSV 预览",
        "preview_load_jpg": "{platform}负载测试 JPG 预览",
        # ---- HTML 报告标题 ----
        "report_title_android_fps": "安卓帧率测试报告",
        "report_title_hw": "CPU/GPU 监测报告",
        "report_title_ios_fps": "iOS 帧率测试报告",
        "report_title_ios_hw": "iOS 硬件监测报告",
        "lbl_samples": "采样点",
        "preview_load_html": "{platform}负载测试 HTML 预览",
        "report_title_load": "{platform} 负载测试报告",
        "lbl_stability_rating": "稳定性评级",
        # ---- CSV 历史记录新增组 ----
        "grp_load_history": "📈 负载测试记录（最近 5 次）",
        "grp_eval_history": "🏆 性能评价记录（最近 5 次）",
        # ---- 导出菜单 ----
        "menu_jpg_export": "📷 导出 JPG 图片",
        "fmt_jpg_filter": "JPEG 图片 (*.jpg *.jpeg)",
        "msg_save_jpg_title": "保存 JPG 图片",
        # ---- 动态格式文案 ----
        "dlg_log_content_title": "日志内容 — {name}",
        "chart_ios_fps_series": "🎮 FPS 时间序列 — {time}",
        "chart_ios_hw_series": "🔧 CPU/GPU/内存 使用率曲线 — {time}",
        "combo_no_ios_device": "未检测到 iOS 设备，请连接并信任此电脑",
        "combo_no_app_list": "未获取到应用列表",
        "fmt_duration_hms": "测试时长: {h:02d}:{m:02d}:{s:02d}",
        "fmt_duration_ms": "测试时长: {m:02d}:{s:02d}",
        "fmt_cpu_cores": "核心数: {n}",
        "combo_no_device": "未检测到设备",
        "combo_no_device_usb": "未检测到设备，请连接手机并开启USB调试",
        "fmt_error_prefix": "错误: {err}",
        "fmt_elapsed": "已运行 {time}",
        "fmt_device_info_full": "设备信息: {model} | Android {version} | ID: {id}",
        "fmt_device_info_id": "设备信息: {id}",
        "fmt_status_error": "状态: ❌ {msg}",
        "fmt_max_mhz": "最大: {val} MHz",
        "fmt_cores_cpu": "核心: CPU {cores}",
        "fmt_gpu_avail": "可用档位: {avail}",
        "fmt_mem_detail": "总计 {total} MB | 可用 {avail} MB | 已用 {pct}%",
        "fmt_gpu_mem": "GPU 显存: {val} MB",
        "lbl_axis_time": "时间 (秒)",
        "lbl_axis_usage": "使用率 (%)",
        "fmt_jank_rate": "卡顿率: {val}%",
        "fmt_jank_rate_zero": "卡顿率: 0.00%",
        # ---- 图例名称 ----
        "legend_instant_fps": "瞬时FPS",
        "legend_avg_fps": "平均FPS",
        "legend_cpu_usage_pct": "CPU 使用率(%)",
        "legend_gpu_usage_pct": "GPU 利用率(%)",
        "legend_mem_usage_pct": "内存 使用率(%)",
        "legend_cpu_usage": "CPU 使用率",
        "legend_gpu_usage": "GPU 利用率",
        "legend_mem_usage": "内存使用率",
        "legend_gpu_freq": "GPU 频率",
        "legend_cpu_temp": "CPU 温度",
        # ---- DDI 状态消息 ----
        "ddi_mounted": "✅ DDI 已挂载 ({mount_type})\n\n可以直接开始监测。\n缓存目录: {cache_dir}\n缓存文件: {cache_status}",
        "ddi_not_mounted_err": "⚠️ DDI 未挂载 (连接错误: {err})\n\n缓存目录: {cache_dir}\n缓存文件: {cache_status}\n\n如果缓存文件齐全,启动监测时会自动从本地挂载。\n否则需要手动下载 DDI 文件放到上述目录。",
        "ddi_not_mounted": "⚠️ DDI 未挂载\n\n缓存目录: {cache_dir}\n缓存文件: {cache_status}\n\n如果缓存文件齐全,启动监测时会自动从本地挂载。\n否则需要手动下载 DDI 文件放到上述目录:\n  - Image.dmg\n  - BuildManifest.plist\n  - Image.trustcache\n\n下载地址: https://github.com/doronz88/DeveloperDiskImage\n(路径: PersonalizedImages/Xcode_iOS_DDI_Personalized/)",
        "lbl_cache_ok": "齐全 ✓",
        "lbl_cache_missing": "缺失 ✗",
        # ---- 电池/功率卡片 ----
        "grp_battery_power": "🔋 电池 / 功率",
        "lbl_voltage": "电压",
        "lbl_current": "电流",
        "lbl_capacity": "电量",
        "lbl_battery_temp": "电池温度",
        "bat_discharging": "放电中",
        "bat_charging": "充电中",
        "bat_not_charging": "已连接未充电",
        "bat_full": "已充满",
        # ---- 功率曲线 ----
        "chart_power_title": "设备功率曲线 (mW)",
        "chart_power_left": "功率 (mW)",
        "legend_power_mw": "瞬时功率",
        # ---- 平均帧率 ----
        "lbl_avg_fps_tip": "测试开始至今的累计平均帧率",
    },
    "en": {
        "app_title": "Stellar Vision FPS Tester",
        "welcome_title": "Stellar Vision Tester",
        "welcome_subtitle": "Professional Mobile Performance Testing Platform",
        "welcome_features": "FPS Test  ·  CPU/GPU Monitor  ·  Data Analysis",
        "welcome_start": "▶  Start Test",
        "lang_label": "🌐",
        "select_device_title": "Select Device Type",
        "select_back_home": "←  Back to Home",
        "android_card_title": "Android",
        "android_card_sub": "Android Device",
        "ios_card_title": "iOS",
        "ios_card_sub": "Apple Device",
        "init_progress_title": "Initializing test environment...",
        "init_progress_sub": "Scanning devices · Establishing connection · Loading driver",
        "help_menu": "&Help",
        "help_view_log": "📄 View Log Contents...",
        "help_open_log_dir": "📂 Open Log Directory...",
        "help_reveal_log": "📋 Reveal Current Log in Finder...",
        "help_about": "ℹ️ About",
        "tab_fps": "🎮 FPS Test",
        "tab_hw": "📊 CPU/GPU Monitor",
        "tab_history": "📜 CSV History",
        "tab_device_info": "📱 Device Info",
        "tab_load_test": "🔥 Load Test",
        # ---- Back / navigation buttons ----
        "btn_back_select": "←  Back to Device Select",
        "btn_back_history": "←  Back to History",
        # ---- FPS test page: device & app settings ----
        "grp_device_settings": "Device & App Settings",
        "lbl_device": "Device:",
        "btn_refresh_device": "🔄 Refresh Device",
        "lbl_app": "Test App:",
        "btn_get_app": "📱 Get Current App",
        "btn_list_apps": "📋 List Installed Apps",
        "lbl_refresh_rate": "Screen Refresh Rate:",
        "lbl_interval": "Sampling Interval (s):",
        "lbl_device_info": "Device Info: Not Connected",
        "btn_start_test": "▶ Start Test",
        "btn_stop_test": "■ Stop Test",
        "btn_export": "📊 Export Report",
        "btn_clear": "🗑 Clear Data",
        "lbl_duration": "Duration: 00:00",
        # ---- Charts ----
        "chart_fps_title": "FPS Realtime Curve",
        "chart_frame_title": "Frame Time Distribution (Latest Samples)",
        "chart_fps_left": "FPS",
        "chart_fps_bottom": "Time (s)",
        "chart_frame_left": "Frame Time (ms)",
        "chart_frame_bottom": "Frame Index",
        "curve_instant_fps": "Instant FPS",
        "curve_avg_fps": "Average FPS",
        "lbl_jank_threshold": "Jank Threshold (16.67ms)",
        # ---- Stats panel ----
        "grp_realtime_stats": "📊 Realtime Stats",
        "stat_current_fps": "Current FPS",
        "stat_avg_fps": "Avg FPS",
        "stat_min_fps": "Min FPS",
        "stat_max_fps": "Max FPS",
        "stat_low_1": "1% Low",
        "stat_low_01": "0.1% Low",
        "stat_std_fps": "FPS Std Dev",
        "stat_jank_count": "Jank Frames",
        "stat_total_frames": "Total Frames",
        "stat_jank_rate": "Jank Rate",
        "stat_p95": "P95 Frame (ms)",
        "stat_p99": "P99 Frame (ms)",
        # ---- Jank indicator ----
        "grp_jank_indicator": "Jank Rate Indicator",
        "lbl_jank_hint": "💚 Excellent < 2%   💛 Good 2-5%   ❤️ Poor > 5%",
        # ---- Log output ----
        "grp_log_output": "📝 Log Output",
        # ---- CPU/GPU monitor page ----
        "lbl_monitor_device": "Monitor Device:",
        "lbl_interval_short": "Interval:",
        "tip_hw_interval": "CPU/GPU sampling interval (seconds)",
        "tip_hw_interval_ios": "CPU/GPU/Memory sampling interval (seconds)",
        "btn_start_monitor": "▶ Start Monitor",
        "btn_stop_monitor": "■ Stop Monitor",
        "lbl_status": "Status: Idle",
        "lbl_ios_note": "ℹ️ iOS limitation: only CPU usage and memory monitoring are supported; CPU/GPU frequency is unavailable. Requires Developer Disk Image (DDI); iOS 17+ needs RSD tunnel first.",
        "grp_cpu_usage": "🖥 CPU Usage",
        "grp_gpu_usage": "🎨 GPU Usage",
        "grp_memory": "💾 Memory",
        "lbl_core_count": "Cores: --",
        "lbl_renderer": "Renderer:",
        "lbl_tiler": "Tiler:",
        "grp_prime": "🚀 CPU Prime Core",
        "lbl_prime_max": "Max: -- MHz",
        "lbl_prime_cores": "Cores: --",
        "grp_cpu_clusters": "📊 All CPU Cluster Frequencies",
        "grp_cpu_temp_usage": "🌡 CPU Usage / Temperature",
        "lbl_cpu_temp": "CPU Temp:",
        "grp_gpu_freq": "🎮 GPU Frequency",
        "lbl_gpu_max": "Max: -- MHz",
        "grp_gpu_load": "📈 GPU Render Load (gfxinfo percentiles)",
        "grp_mem_gpu": "💾 Memory / GPU Memory",
        "lbl_gpu_mem": "GPU Memory: --",
        "chart_hw_freq_title": "CPU / GPU Frequency Realtime Curve (MHz)",
        "chart_hw_freq_left": "Frequency (MHz)",
        "chart_temp_title": "🌡 CPU Temperature Realtime Curve (°C)",
        "chart_temp_left": "Temperature (°C)",
        "chart_usage_title": "📊 CPU / Memory Usage Realtime Curve (%)",
        "chart_usage_left": "Usage (%)",
        "chart_ios_hw_title": "CPU / GPU / Memory Usage Curve",
        "chart_usage_left_ios": "Usage (%)",
        # ---- Device info page ----
        "lbl_select_device": "Select Device:",
        "btn_get_info": "📡 Get Device Info",
        "grp_device_info": "📋 Device Basic Info",
        "header_item": "Item",
        "header_detail": "Detail",
        # ---- CSV history page ----
        "lbl_history_tip": "Keeps the last 5 FPS test / CPU-GPU monitor full datasets. Click an item on the left to view details.",
        "btn_export_csv": "📦 Export Selected CSV",
        "btn_contact": "📧 Contact Author",
        "btn_contact_report": "📧 Contact Author · Report Issue",
        "grp_fps_history": "🎮 FPS Test Records (Last 5)",
        "grp_hw_history": "🔧 CPU/GPU Monitor Records (Last 5)",
        "grp_detail_summary": "📋 Detail Summary",
        "grp_stats_data": "📊 Stats Data",
        "grp_time_series": "📈 Time Series Curve",
        "header_metric": "Metric",
        "header_value": "Value",
        "lbl_temp_axis": "Temperature (°C)",
        # ---- Load test page ----
        "btn_start_load": "▶  Start Load Test",
        "btn_stop_load": "■  Stop",
        "btn_export_load": "📤 Export Report",
        "btn_retest_load": "🔄 Retest",
        "lbl_remain_time": "⏱  Elapsed Time",
        "lbl_elapsed": "Elapsed 00:00:00",
        "lbl_load_cpu": "🔥 CPU Usage",
        "lbl_load_gpu": "🎨 GPU Usage",
        "lbl_load_mem": "💾 Memory Usage",
        "lbl_load_temp": "🌡 CPU Temp",
        "chart_load_temp_title": "🌡 CPU Temperature Realtime Curve (°C)",
        "chart_load_temp_left": "CPU Temp",
        "chart_load_temp_bottom": "Time (sample seconds)",
        "grp_realtime_log": "📝 Realtime Log",
        "lbl_conclusion": "📋 Stability Conclusion",
        "lbl_waiting": "Waiting for test to start...",
        # ---- iOS detect foreground app button ----
        "btn_foreground_app": "📱 Detect Foreground App",
        "btn_ddi_status": "🔍 DDI Status",
        # ---- Status text ----
        "status_idle": "Status: Idle",
        "status_monitoring": "Status: 🟢 Monitoring...",
        "status_connecting": "Status: 🟡 Connecting...",
        "status_stopped": "Status: ⏸ Stopped",
        "status_cleared": "Status: 🧹 Data Cleared",
        "status_exported": "Status: ✅ Report Exported",
        "status_html_exported": "Status: ✅ HTML Report Exported",
        "status_start_failed": "Status: ❌ Start Failed",
        "status_export_failed": "Status: ❌ Export Failed",
        "status_error_prefix": "Status: ❌ ",
        # ---- Combo items ----
        "combo_no_device": "No device detected",
        "combo_no_device_tip": "No device detected. Please connect your phone and enable USB debugging",
        "combo_no_ios_device_tip": "No iOS device detected. Please connect and trust this computer",
        "combo_no_app_list": "No device detected",
        # ---- Contact page ----
        "grp_contact_title": "📧 Contact Author · Feedback",
        "lbl_contact_desc": "If you encounter any issues or have suggestions, feel free to send an email",
        "btn_copy": "Copy",
        "btn_open_mail": "📨 Open Mail Client",
        "lbl_contact_tip": "💡 Tip: Click the email address or the \"Copy\" button to copy it to the clipboard",
        "msg_email_copied": "Author email copied to clipboard:\nstardomevision@outlook.com",
        "msg_copied": "Copied",
        # ---- Disclaimer ----
        "msg_disclaimer_title": "⚠️ Notice & Disclaimer",
        "txt_disclaimer": "This performance test is for enthusiast benchmarking only. High-load rendering raises device temperature; older devices may stutter, throttle, or crash.\n\nResults are affected by the OS, browser, and cooling conditions, and are for reference only — not for hardware QA or commercial promotion.\n\nUsers bear the risk of any device wear caused by stress testing.\n\nClicking \"Agree & Continue\" means you accept the above terms.",
        "btn_agree": "Agree & Continue",
        "btn_reject": "Reject",
        # ---- About dialog ----
        "msg_about_title": "About Stellar Vision FPS Tester",
        "msg_about_body": "Stellar Vision FPS Tester\nVersion: 2.1.0\n\nFeatures: Android / iOS game FPS and CPU/GPU usage monitoring\n\n",
        # ---- Log dialog ----
        "msg_log_content_title": "Log Content",
        "btn_refresh": "🔄 Refresh",
        "btn_close": "Close",
        "msg_log_dir": "Log Directory",
        "msg_log_dir_body": "Log directory path:\n{path}\n\nPlease open it manually in Finder.",
        # ---- Message box text ----
        "msg_no_data": "Notice",
        "msg_no_fps_data": "No FPS data to export. Please run a test first.",
        "msg_no_hw_data": "No hardware monitoring data to export. Please start monitoring first.",
        "msg_no_export_data": "No data to export. Please run a test first.",
        "msg_no_hw_export_data": "No monitoring data to export. Please start monitoring first.",
        "msg_select_history": "Please select a record on the left first",
        "msg_select_history_ios": "Please select a history record first",
        "msg_select_device": "Please select a device first",
        "msg_select_device_connect": "Please select and connect a device first",
        "msg_select_app": "Please enter or select an app package name to test",
        "msg_select_ios_device": "Please select an iOS device first",
        "msg_select_ios_device_monitor": "Please select an iOS device to monitor first",
        "msg_select_device_monitor": "Please select a device to monitor first",
        "msg_select_device_load": "Please select a device first",
        "msg_test_running": "Cannot clear while a test is running. Please stop the test first.",
        "msg_monitor_running": "Cannot clear while monitoring is running. Please stop monitoring first.",
        "msg_confirm_clear": "Confirm Clear",
        "msg_confirm_clear_body": "Are you sure you want to clear all current test data? This action cannot be undone.",
        "msg_load_confirm": "Load Test Confirmation",
        "msg_load_confirm_body": "A full-load stability test is about to start (1-hour countdown, click Stop to end early).\n\n⚠️ The device will work under high load during the test. It may heat up, throttle, or spin fans aggressively.\n⚠️ Ensure good cooling and sufficient battery; connect to power if needed.\n\nContinue?",
        "msg_load_finish_first": "Please complete or stop the load test first to generate a report",
        "load_principle_title": "📋 Load Test Principle",
        "load_principle_body": "The load test applies sustained high load on the device (multi-core CPU full-load arithmetic loops) to simulate prolonged intensive usage, monitoring CPU usage, memory consumption, and core temperature trends to evaluate the device's thermal dissipation and throttling control strategy.\n\nThe test runs as a 1-hour countdown (click Stop to end early). Samples hardware snapshots every second, then generates a stability rating (Good / Fair / Poor) and a full trend report upon completion.",
        "load_risk_title": "⚠️ Risk Warning",
        "load_risk_body": "1. The device will run under high load during the test; CPU temperature may rise significantly, which is normal.\n2. Older or poorly cooled devices may throttle, stutter, or even shut down automatically. Ensure adequate cooling.\n3. It is recommended to connect to power during the test to avoid interruption due to battery depletion.\n4. Test data is for performance reference only and should not be the sole basis for hardware quality assessment.\n5. Users bear the risk of any device wear caused by stress testing.",
        "btn_load_confirm_start": "✅ Confirm & Start",
        "load_running_title": "🚀 Test Running",
        "load_running_hint_anim": "The device is running under sustained high load. Please keep it well-cooled.",
        "load_test_complete_title": "✅ Test Complete",
        "load_test_complete_msg": "Load test complete. Generating stability report...",
        "load_result_title": "📊 Test Results",
        "chart_load_cpu_usage": "CPU Usage Curve (%)",
        "chart_load_mem_usage": "Memory Usage Curve (MB)",
        "chart_load_temp_result": "CPU Temperature Curve (°C)",
        "tbl_load_cpu_stats": "CPU Usage Statistics",
        "tbl_load_col_samples": "Samples",
        "tbl_load_col_avg": "Average",
        "tbl_load_col_max": "Max",
        "tbl_load_col_min": "Min",
        "grp_load_detail_table": "📋 Detailed Statistics",
        "grp_load_result_charts": "📈 Trend Charts",
        "load_metric_cpu": "CPU Usage(%)",
        "load_metric_gpu": "GPU Util(%)",
        "load_metric_mem": "Memory(MB)",
        "load_metric_cpu_temp": "CPU Temp(°C)",
        "lbl_rating": "Rating",
        "lbl_duration_short": "Duration",
        "lbl_errors": "Errors",
        "lbl_cpu_avg_pct": "CPU Avg(%)",
        "lbl_cpu_peak_pct": "CPU Peak(%)",
        "lbl_mem_avg_mb": "Mem Avg(MB)",
        "lbl_mem_peak_mb": "Mem Peak(MB)",
        "lbl_temp_avg_c": "Temp Avg(°C)",
        "lbl_temp_peak_c": "Temp Peak(°C)",
        "rating_good": "Good",
        "rating_warn": "Fair",
        "rating_bad": "Poor",
        "platform_android": "Android",
        "platform_ios": "iOS",
        "load_con_duration": "Test duration: {min}m {sec}s ({total}s total)",
        "load_con_samples": "Samples (CPU/GPU/Mem/CPUTemp): {cpu} / {gpu} / {mem} / {temp}",
        "load_con_cpu": "CPU Usage: Avg {avg:.1f}%  /  Peak {max:.1f}%  /  Min {min:.1f}%",
        "load_con_cpu_na": "CPU Usage: Not collected",
        "load_con_gpu": "GPU Util: Avg {avg:.1f}%  /  Peak {max:.1f}%  /  Min {min:.1f}%",
        "load_con_gpu_na": "GPU Util: Not collected",
        "load_con_mem": "Memory Usage: Avg {avg:.0f} MB  /  Peak {max:.0f} MB",
        "load_con_mem_na": "Memory Usage: Not collected",
        "load_con_temp": "CPU Temp: Avg {avg:.1f}°C  /  Peak {max:.1f}°C  /  Min {min:.1f}°C",
        "load_con_temp_na": "CPU Temp: Not collected",
        "load_con_errors": "⚠️ Exception count: {count}",
        "load_con_issues_found": "⚠️ {count} issue(s) found:",
        "load_con_no_issues": "✅ No obvious anomalies detected",
        "load_con_rating": "Stability Rating: [{rating}]",
        "load_con_good": "→ Conclusion: The device maintained stable CPU temperature and resource usage under sustained high load, with good thermal design and throttling control. It passes the stability test.",
        "load_con_warn": "→ Conclusion: CPU temperature is on the high side under full load but has not triggered obvious throttling or crash thresholds. This is an average performance level; ensure adequate cooling.",
        "load_con_bad": "→ Conclusion: CPU temperature is significantly exceeded under sustained load or frequent collection anomalies exist, indicating that thermal/throttling strategies may not withstand sustained pressure. Check cooling conditions or reduce game quality and retry.",
        "load_issue_crash": "Collection interrupted {count} time(s)",
        "load_issue_temp_peak": "CPU temp peak {temp:.1f}°C exceeds safe threshold",
        "load_issue_temp_high": "CPU temp peak {temp:.1f}°C is near the high-temperature edge",
        "load_issue_cpu_avg": "CPU avg load {avg:.1f}%, sustained full load",
        "load_issue_cpu_peak": "CPU peak {max:.1f}%, at throttling risk",
        "load_csv_report_title": "{platform} Load Test Report",
        "load_csv_conclusion": "=== Conclusion ===",
        "load_csv_stats": "=== Statistics ===",
        "load_csv_trend": "=== Trend Samples (per second) ===",
        "load_csv_metric": "Metric",
        "load_csv_seconds": "Seconds",
        "load_csv_duration_sec": "Duration (sec)",
        "load_csv_export_time": "Export Time",
        "load_csv_device_id": "Device ID",
        "load_html_stability_conclusion": "📋 Stability Conclusion",
        "load_html_resource_trend": "Resource Usage Trend (CPU / GPU / Memory)",
        "load_html_temp_curve": "CPU Temperature Real-time Curve",
        "load_html_sample_sec": "Sample Seconds",
        "load_html_cpu_avg": "CPU Avg",
        "load_html_gpu_avg": "GPU Avg",
        "load_html_temp_avg": "CPU Temp Avg",
        "load_html_cpu_peak": "CPU Peak",
        "load_html_gpu_peak": "GPU Peak",
        "load_html_temp_peak": "CPU Temp Peak",
        "load_html_chart_snapshot": "📊 Chart Snapshot",
        "load_html_per_sec": "1 sample per second",
        "load_html_draggable": "Draggable & zoomable",
        "load_html_cpu_core_temp": "CPU core thermal_zone max temp",
        "load_html_threshold_bad": ">65°C rated as 'Poor'",
        "load_html_mem_div100": "Mem Usage/100(%)",
        "load_html_device_platform": "Device Platform",
        "load_html_test_duration": "Test Duration",
        "load_html_error_count": "Exception Count",
        "load_jpg_no_screenshot": "Cannot capture result page screenshot",
        "load_metric_power": "Device Power(mW)",
        "chart_power_title": "⚡ Device Power Curve (mW)",
        "chart_power_left": "Power (mW)",
        "legend_power": "Device Power",
        "stat_avg_fps_large": "🎯 Avg FPS",
        "msg_export_success_jpg": "JPG image exported to:\n{path}",
        "msg_export_failed_jpg": "JPG export failed:\n{err}",
        "fps_eval_title": "🏆 Performance Evaluation",
        "fps_eval_score": "Overall Score",
        "fps_eval_rating": "Performance Tier",
        "fps_eval_chipset": "Chipset Analysis",
        "fps_eval_analysis": "Detailed Analysis",
        "fps_eval_fps_score": "FPS Achievement",
        "fps_eval_stability_score": "Stability",
        "fps_eval_lowfps_score": "Low FPS Performance",
        "fps_eval_drop_score": "Frame Drop Control",
        "fps_eval_excellent": "⭐ Excellent",
        "fps_eval_good": "✅ Good",
        "fps_eval_fair": "🔶 Fair",
        "fps_eval_poor": "⚠️ Poor",
        "fps_eval_bad": "❌ Bad",
        "fps_eval_chipset_flagship": "Flagship Chipset",
        "fps_eval_chipset_highend": "High-end Chipset",
        "fps_eval_chipset_midrange": "Mid-range Chipset",
        "fps_eval_chipset_budget": "Budget Chipset",
        "fps_eval_chipset_unknown": "Unknown Chipset",
        "fps_eval_no_data": "Insufficient data for evaluation",
        "fps_eval_close": "Close",
        "msg_usb_debug_title": "USB Debugging Confirmation",
        "msg_usb_debug_body": "Have you enabled USB debugging?\n\nEnable it in \"Settings → Developer Options\" on your phone,\nand connect it to the computer via a USB cable.",
        "msg_dev_mode_title": "Developer Mode Confirmation",
        "msg_dev_mode_body": "Have you enabled Developer Mode?\n\nEnable it in iPhone \"Settings → Privacy & Security → Developer Mode\",\nconnect via USB cable, and trust this computer.",
        "msg_export_success": "Export Succeeded",
        "msg_export_failed": "Export Failed",
        "msg_export_success_csv": "CSV report saved to:\n{path}",
        "msg_export_success_html": "HTML report exported to:\n{path}",
        "msg_export_success_report": "Report exported to:\n{path}",
        "msg_export_success_html_report": "HTML report saved to:\n{path}",
        "msg_export_success_hw_html": "HTML monitoring report exported to:\n{path}",
        "msg_export_success_monitor": "Monitoring report exported to:\n{path}",
        "msg_export_success_fps_history": "FPS history exported to:\n{path}",
        "msg_export_success_hw_history": "CPU/GPU monitor history exported to:\n{path}",
        "msg_export_failed_csv": "Failed to export CSV:\n{err}",
        "msg_export_failed_html": "Failed to export HTML:\n{err}",
        "msg_export_failed_simple": "Export failed: {err}",
        "msg_failed": "Failed",
        "msg_success": "Success",
        "msg_error": "Error",
        "msg_adb_error": "ADB Error",
        "msg_start_test_failed": "Failed to start test:\n{err}",
        "msg_start_ios_fps_failed": "Failed to start iOS FPS test:\n{err}",
        "msg_start_ios_hw_failed": "Failed to start iOS hardware monitor:\n{err}",
        "msg_start_hw_failed": "Failed to start hardware monitor:\n{err}",
        "msg_get_info_failed": "Failed to get device info:\n{err}",
        "msg_get_info_failed_ios": "Failed to get device info:\n{info_err}",
        "msg_ios_foreground_none": "No foreground app detected. The device may be on the home screen.",
        "msg_ios_foreground_failed": "Detection Failed",
        "msg_ios_foreground_failed_body": "Error:\n{err}",
        "msg_ios_foreground_title": "Foreground App",
        "msg_ddi_title": "DDI Status",
        "msg_ddi_check_failed": "Failed to check DDI status:\n{err}",
        "msg_ios_monitor_failed": "Failed to start iOS hardware monitor:\n{err}",
        "msg_startup_error": "Startup Error",
        "msg_disclaimer_failed": "Failed to show disclaimer dialog:\n{err}",
        "msg_save_failed": "Save Failed",
        "msg_select_android_device": "Please connect and select an Android device first",
        # ---- Export menu ----
        "menu_csv_export": "📄  CSV Export",
        "menu_html_export": "🌐  HTML Export",
        # ---- Device info table items ----
        "info_phone_name": "📱 Phone Name",
        "info_chip_name": "🔧 Chip Name",
        "info_unknown": "Unknown",
        "info_unknown_device": "Unknown Device",
        # ---- Progress page text ----
        "prog_entering": "Entering {name} test environment...",
        "prog_scanning": "Scanning devices...",
        "prog_connecting": "Establishing USB / network connection...",
        "prog_loading_driver": "Loading driver & verifying permissions...",
        "prog_ready": "Ready, entering...",
        "prog_phase_prefix": "{n} / 4  {text}",
        "prog_complete": "✅ Done! Entering...",
        # ---- History summary rows ----
        "hist_rec_type": "Record Type",
        "hist_start_time": "Start Time",
        "hist_end_time": "End Time",
        "hist_device": "Device",
        "hist_test_duration": "Test Duration",
        "hist_monitor_duration": "Monitor Duration",
        "hist_test_app": "Test App",
        "hist_avg_fps": "Avg FPS",
        "hist_low_1": "1% Low",
        "hist_low_01": "0.1% Low",
        "hist_jank_rate": "Jank Rate",
        "hist_rec_type_fps": "🎮 FPS Test",
        "hist_rec_type_hw": "🔧 CPU/GPU Monitor",
        "hist_cpu_clusters": "CPU Clusters",
        "hist_gpu_samples": "GPU Samples",
        "hist_total_samples": "Total Samples",
        "hist_usage": "Usage",
        # ---- Export preview dialog ----
        "btn_cancel": "Cancel",
        "btn_save_html": "💾 Save as HTML",
        "btn_save_csv": "💾 Save as CSV",
        "lbl_html_preview_tip": "HTML report preview (ECharts charts require internet CDN; double-click the saved file to view properly)",
        "lbl_csv_preview_tip": "CSV report preview (formatted as a table for readability). Click Save to confirm.",
        "msg_save_html_title": "Save HTML Report",
        "msg_save_csv_title": "Save CSV Report",
        "dlg_export_history": "Export History CSV",
        "fmt_html_filter": "HTML Files (*.html)",
        "fmt_csv_filter": "CSV Files (*.csv)",
        "lbl_column": "Column",
        "lbl_load_device": "Device:",
        "lbl_empty_history": "👈 Select a record on the left to view details",
        "combo_error_prefix": "Error: ",
        "msg_about_log_dir": "Log Directory:\n{path}",
        "msg_log_file": "Log File",
        "msg_log_file_body": "Log file path:\n{path}",
        "msg_ios_monitor_start_failed_title": "iOS Monitor Start Failed",
        "msg_ios_monitor_start_failed_text": "Failed to start iOS DVT monitor session.",
        # ---- Runtime status text ----
        "stat_device_disconnected": "Device Info: Not Connected",
        "stat_duration_zero": "Test Duration: 00:00",
        "stat_start_failed": "Status: ❌ Start Failed",
        "stat_connecting": "Status: 🟡 Connecting...",
        "stat_monitoring": "Status: 🟢 Monitoring...",
        "stat_stopped": "Status: ⏸ Stopped",
        "stat_cleared": "Status: 🧹 Data Cleared",
        "stat_html_exported": "Status: ✅ HTML Report Exported",
        "stat_report_exported": "Status: ✅ Report Exported",
        "stat_export_failed": "Status: ❌ Export Failed",
        "stat_cpu_cores_na": "Cores: --",
        "stat_max_na": "Max: -- MHz",
        "stat_cores_na": "Cores: --",
        "stat_gpu_mem_na": "GPU Memory: --",
        "note_gpu_freq_selinux": "⚠ GPU frequency cannot be read due to Android SELinux restrictions (non-root). Please refer to the GPU render load below.",
        "load_running_hint": "Test in progress, conclusion will be generated automatically when finished...",
        # ---- Export preview dialog titles ----
        "preview_ios_fps_csv": "iOS FPS CSV Preview",
        "preview_ios_hw_csv": "iOS Hardware CSV Preview",
        "preview_android_fps_html": "Android FPS HTML Preview",
        "preview_android_hw_html": "Android CPU/GPU HTML Preview",
        "preview_ios_fps_html": "iOS FPS HTML Preview",
        "preview_ios_hw_html": "iOS Hardware HTML Preview",
        "preview_android_fps_csv": "Android FPS CSV Preview",
        "preview_android_hw_csv": "Android CPU/GPU CSV Preview",
        "preview_load_csv": "{platform} Load Test CSV Preview",
        "preview_load_jpg": "{platform} Load Test JPG Preview",
        # ---- HTML report titles ----
        "report_title_android_fps": "Android FPS Test Report",
        "report_title_hw": "CPU/GPU Monitor Report",
        "report_title_ios_fps": "iOS FPS Test Report",
        "report_title_ios_hw": "iOS Hardware Monitor Report",
        "lbl_samples": "samples",
        "preview_load_html": "{platform} Load Test HTML Preview",
        "report_title_load": "{platform} Load Test Report",
        "lbl_stability_rating": "Stability Rating",
        # ---- CSV history groups ----
        "grp_load_history": "📈 Load Test Records (Last 5)",
        "grp_eval_history": "🏆 Performance Evaluation Records (Last 5)",
        # ---- Export menu ----
        "menu_jpg_export": "📷 Export JPG Image",
        "fmt_jpg_filter": "JPEG Image (*.jpg *.jpeg)",
        "msg_save_jpg_title": "Save JPG Image",
        # ---- Dynamic format text ----
        "dlg_log_content_title": "Log Content — {name}",
        "chart_ios_fps_series": "🎮 FPS Time Series — {time}",
        "chart_ios_hw_series": "🔧 CPU/GPU/Memory Usage Curve — {time}",
        "combo_no_ios_device": "No iOS device detected. Please connect and trust this computer.",
        "combo_no_app_list": "No app list available",
        "fmt_duration_hms": "Test Duration: {h:02d}:{m:02d}:{s:02d}",
        "fmt_duration_ms": "Test Duration: {m:02d}:{s:02d}",
        "fmt_cpu_cores": "Cores: {n}",
        "combo_no_device": "No device detected",
        "combo_no_device_usb": "No device detected. Please connect a phone and enable USB debugging.",
        "fmt_error_prefix": "Error: {err}",
        "fmt_elapsed": "Elapsed {time}",
        "fmt_device_info_full": "Device Info: {model} | Android {version} | ID: {id}",
        "fmt_device_info_id": "Device Info: {id}",
        "fmt_status_error": "Status: ❌ {msg}",
        "fmt_max_mhz": "Max: {val} MHz",
        "fmt_cores_cpu": "Cores: CPU {cores}",
        "fmt_gpu_avail": "Available levels: {avail}",
        "fmt_mem_detail": "Total {total} MB | Available {avail} MB | Used {pct}%",
        "fmt_gpu_mem": "GPU Memory: {val} MB",
        "lbl_axis_time": "Time (sec)",
        "lbl_axis_usage": "Usage (%)",
        "fmt_jank_rate": "Jank Rate: {val}%",
        "fmt_jank_rate_zero": "Jank Rate: 0.00%",
        # ---- Legend names ----
        "legend_instant_fps": "Instant FPS",
        "legend_avg_fps": "Avg FPS",
        "legend_cpu_usage_pct": "CPU Usage (%)",
        "legend_gpu_usage_pct": "GPU Utilization (%)",
        "legend_mem_usage_pct": "Memory Usage (%)",
        "legend_cpu_usage": "CPU Usage",
        "legend_gpu_usage": "GPU Utilization",
        "legend_mem_usage": "Memory Usage",
        "legend_gpu_freq": "GPU Frequency",
        "legend_cpu_temp": "CPU Temperature",
        # ---- DDI status messages ----
        "ddi_mounted": "✅ DDI Mounted ({mount_type})\n\nMonitoring can start now.\nCache dir: {cache_dir}\nCache files: {cache_status}",
        "ddi_not_mounted_err": "⚠️ DDI Not Mounted (connection error: {err})\n\nCache dir: {cache_dir}\nCache files: {cache_status}\n\nIf cache files are complete, monitoring will auto-mount from local cache on start.\nOtherwise, manually download DDI files to the directory above.",
        "ddi_not_mounted": "⚠️ DDI Not Mounted\n\nCache dir: {cache_dir}\nCache files: {cache_status}\n\nIf cache files are complete, monitoring will auto-mount from local cache on start.\nOtherwise, manually download DDI files to the directory above:\n  - Image.dmg\n  - BuildManifest.plist\n  - Image.trustcache\n\nDownload URL: https://github.com/doronz88/DeveloperDiskImage\n(Path: PersonalizedImages/Xcode_iOS_DDI_Personalized/)",
        "lbl_cache_ok": "Complete ✓",
        "lbl_cache_missing": "Missing ✗",
        # ---- Battery / Power card ----
        "grp_battery_power": "🔋 Battery / Power",
        "lbl_voltage": "Voltage",
        "lbl_current": "Current",
        "lbl_capacity": "Capacity",
        "lbl_battery_temp": "Battery Temp",
        "bat_discharging": "Discharging",
        "bat_charging": "Charging",
        "bat_not_charging": "Plugged Not Charging",
        "bat_full": "Fully Charged",
        # ---- Power curve ----
        "chart_power_title": "Device Power Curve (mW)",
        "chart_power_left": "Power (mW)",
        "legend_power_mw": "Instant Power",
        # ---- Average FPS ----
        "lbl_avg_fps_tip": "Cumulative average FPS since test start",
    },
}

# 中文原文回退映射（zh-CN 条目即为原文）
_FALLBACK_ZH = _TRANSLATIONS["zh-CN"]

# 语言显示名称列表（与 lang_combo 顺序一致）
_LANG_OPTIONS = [
    ("zh-CN", "简体中文"),
    ("en", "English"),
]


# ============================================================
# 资源路径工具：打包后从 sys._MEIPASS/resources 读取，
# 开发环境从项目根目录的 resources/ 读取
# ============================================================
def _app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _resource_path(*parts: str) -> str:
    """返回资源文件绝对路径（优先打包目录，其次项目resources）"""
    # 1. 打包目录下的 resources
    meip = getattr(sys, "_MEIPASS", None)
    if meip:
        p1 = os.path.join(meip, "resources", *parts)
        if os.path.exists(p1):
            return p1
        p2 = os.path.join(meip, *parts)
        if os.path.exists(p2):
            return p2
    # 2. 项目根目录下的 resources
    proj = os.path.dirname(os.path.abspath(__file__))
    p3 = os.path.join(proj, "resources", *parts)
    if os.path.exists(p3):
        return p3
    # 3. 兜底：按字面路径返回
    return os.path.join(proj, "resources", *parts)


def _logo_pixmap(size_px: int = 128) -> Optional[QPixmap]:
    """加载 APP logo QPixmap；失败返回 None"""
    mapping = {
        24:  "logo_24.png", 32: "logo_32.png", 48: "logo_48.png",
        64:  "logo_64.png", 96: "logo_96.png", 128: "logo_128.png",
    }
    # 选择最接近的不小于 size_px 的文件
    picked = None
    for s in sorted(mapping.keys()):
        picked = s
        if s >= size_px:
            break
    fname = mapping.get(picked, "logo.png")
    path = _resource_path(fname)
    if not os.path.exists(path):
        # 兜底
        path = _resource_path("logo.png")
    if not os.path.exists(path):
        _logger.warning("logo 资源不存在: %s", path)
        return None
    pm = QPixmap(path)
    if pm.isNull():
        _logger.warning("logo 加载失败: %s", path)
        return None
    return pm.scaled(size_px, size_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _app_icon() -> Optional[QIcon]:
    """加载 APP QIcon（用于窗口标题栏/Tab/Dock）"""
    pm = _logo_pixmap(64)
    if pm is None:
        return None
    icon = QIcon()
    for sz in [16, 24, 32, 48, 64, 96, 128]:
        p = _logo_pixmap(sz)
        if p is not None:
            icon.addPixmap(p)
    if icon.isNull():
        icon.addPixmap(pm)
    return icon


class FPSCollectorThread(QThread):
    """后台线程：采集帧率数据 + CPU/GPU 硬件监控"""
    stats_ready = pyqtSignal(object)  # FPSStats
    hw_info_ready = pyqtSignal(dict)  # CPU/GPU 硬件信息
    log_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, adb_client: ADBClient, device_id: str, package_name: str,
                 analyzer: FPSAnalyzer, poll_interval: float = 1.0):
        super().__init__()
        self.adb_client = adb_client
        self.device_id = device_id
        self.package_name = package_name
        self.analyzer = analyzer
        self.poll_interval = poll_interval
        self._running = False
        self._hw_counter = 0

    def stop(self):
        self._running = False

    def _precise_sleep(self, seconds: float) -> None:
        """高精度可中断 sleep（扣除采集耗时后每 20ms 检查一次 running，适配 0.1/0.3s 短间隔）"""
        if seconds is None or seconds <= 0:
            return
        total = max(0.0, float(seconds))
        tick = 0.02  # 20ms 粒度
        ticks_needed = int(total / tick)
        frac = total - ticks_needed * tick
        # 先按 tick 粒度 msleep（QThread 原生可中断）
        ms_tick = int(tick * 1000)
        for _ in range(ticks_needed):
            if not self._running:
                return
            self.msleep(ms_tick)
        # 再补足余数（<20ms）
        if self._running and frac > 0:
            self.msleep(max(1, int(frac * 1000)))

    def run(self):
        self._running = True
        try:
            self.analyzer.reset()
            self.analyzer.start_time = time.time()

            # 优先使用 SurfaceFlinger 帧计数方案
            self.log_message.emit(f"正在连接 SurfaceFlinger 获取 {self.package_name} 的帧数据...")
            last_frame = self.adb_client.get_sf_frame_number(self.device_id, self.package_name)

            if last_frame is not None:
                self.log_message.emit(f"✅ SurfaceFlinger 帧计数模式已启动 (初始帧: {last_frame})")
                self._run_sf_mode(last_frame)
            else:
                # 回退到 gfxinfo 方案
                self.log_message.emit("⚠️ SurfaceFlinger 未找到帧数据，回退到 gfxinfo 模式")
                self._run_gfxinfo_mode()

        except Exception as e:
            self.error_occurred.emit(f"采集线程错误: {e}")
        finally:
            self.finished_signal.emit()

    def _collect_hw_info(self):
        """采集 CPU/GPU 硬件信息（每3轮采集一次以减少开销）"""
        self._hw_counter += 1
        if self._hw_counter % 3 != 0:
            return
        try:
            hw = {
                "cpu_freqs": self.adb_client.get_cpu_freqs(self.device_id),
                "cpu_usage": self.adb_client.get_cpu_usage(self.device_id),
                "cpu_temp": self.adb_client.get_cpu_temp(self.device_id),
                "gpu_info": self.adb_client.get_gpu_info(self.device_id, self.package_name),
                "mem_info": self.adb_client.get_mem_info(self.device_id),
            }
            self.hw_info_ready.emit(hw)
        except Exception:
            pass

    def _run_sf_mode(self, initial_frame: int):
        """SurfaceFlinger 帧计数采集模式"""
        last_frame = initial_frame
        last_time = time.time()
        no_data_count = 0
        sample_count = 0

        while self._running:
            if not self._running:
                break
            loop_start = time.time()

            try:
                current_frame = self.adb_client.get_sf_frame_number(
                    self.device_id, self.package_name
                )
                current_time = time.time()

                if current_frame is None:
                    no_data_count += 1
                    if no_data_count <= 2:
                        self.log_message.emit("警告: 未获取到帧数据，应用可能已退出前台")
                    elapsed = time.time() - loop_start
                    self._precise_sleep(max(0.0, float(self.poll_interval) - elapsed))
                    continue
                no_data_count = 0

                frame_delta = current_frame - last_frame
                time_delta = current_time - last_time

                if frame_delta > 0 and time_delta > 0:
                    # 计算平均帧时间（毫秒）
                    avg_frame_time_ms = (time_delta * 1000.0) / frame_delta
                    # 计算瞬时 FPS（帧计数 / 秒），用于 EMA 平滑后显示
                    instant_fps = frame_delta / time_delta
                    self.analyzer.observe_instant_fps(instant_fps)
                    # 限制单次添加数量避免内存暴涨，但同步修正总帧数
                    frames_to_add = min(frame_delta, 300)
                    synthetic_times = [avg_frame_time_ms] * frames_to_add
                    self.analyzer.add_frames(synthetic_times)
                    if frame_delta > frames_to_add:
                        self.analyzer.total_frame_count += (frame_delta - frames_to_add)

                    if sample_count == 0:
                        self.log_message.emit(
                            f"📊 首次数据: FPS≈{instant_fps:.1f}, "
                            f"帧差={frame_delta}, 间隔={time_delta:.2f}s"
                        )

                elif frame_delta < 0:
                    # 帧计数器重置（应用重启），重新基线
                    last_frame = current_frame
                    last_time = current_time
                    elapsed = time.time() - loop_start
                    self._precise_sleep(max(0.0, float(self.poll_interval) - elapsed))
                    continue

                elif frame_delta == 0:
                    # 应用未渲染新帧
                    self.analyzer.add_frames([time_delta * 1000.0])

                # 采样统计数据（强制首次采样不被节流）
                stats = self._force_sample(sample_count == 0)
                if stats:
                    sample_count += 1
                    self.stats_ready.emit(stats)

                # 采集 CPU/GPU 硬件信息
                self._collect_hw_info()

                last_frame = current_frame
                last_time = current_time

            except TimeoutError as e:
                self.log_message.emit(f"警告: {e}")
            except Exception as e:
                self.log_message.emit(f"采集异常: {e}")

            # 高精度 sleep：扣除采集耗时，短间隔 0.1/0.3s 真实有效
            elapsed = time.time() - loop_start
            self._precise_sleep(max(0.0, float(self.poll_interval) - elapsed))

    def _force_sample(self, force: bool = False) -> Optional[FPSStats]:
        """采样统计数据，force=True 时跳过节流"""
        if force:
            self.analyzer.last_sample_time = None
        return self.analyzer.sample()

    def _run_gfxinfo_mode(self):
        """gfxinfo 采集模式（回退方案）"""
        self.adb_client.reset_gfxinfo(self.device_id, self.package_name)
        self.log_message.emit(f"已重置应用 {self.package_name} 的gfxinfo数据")

        while self._running:
            loop_start = time.time()
            try:
                gfxinfo = self.adb_client.get_gfxinfo(self.device_id, self.package_name)
                frame_times = self.adb_client.parse_frame_durations(gfxinfo)

                if frame_times:
                    self.analyzer.add_frames(frame_times)
                    self.adb_client.reset_gfxinfo(self.device_id, self.package_name)

                stats = self.analyzer.sample()
                if stats:
                    self.stats_ready.emit(stats)

                # 采集 CPU/GPU 硬件信息
                self._collect_hw_info()

            except TimeoutError as e:
                self.log_message.emit(f"警告: {e}")
            except Exception as e:
                self.log_message.emit(f"采集异常: {e}")

            # 高精度 sleep：扣除采集耗时，短间隔 0.1/0.3s 真实有效
            elapsed = time.time() - loop_start
            self._precise_sleep(max(0.0, float(self.poll_interval) - elapsed))


class HWMonitorThread(QThread):
    """独立的 CPU/GPU 硬件监测线程（不依赖帧率测试，供监测页面使用）"""
    hw_data_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, adb_client: ADBClient, device_id: str, poll_interval: float = 1.0):
        super().__init__()
        self.adb_client = adb_client
        self.device_id = device_id
        self.poll_interval = poll_interval
        self._running = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        # 获取前台应用包名（用于 GPU 渲染负载采集，避免 dumpsys gfxinfo 不带包名时全量输出卡死）
        package_name = ""
        try:
            package_name = self.adb_client.get_current_package(self.device_id) or ""
        except Exception:
            pass
        pkg_refresh_counter = 0

        while self._running:
            loop_start = time.time()
            try:
                # 每 10 轮刷新一次前台包名
                pkg_refresh_counter += 1
                if pkg_refresh_counter % 10 == 0:
                    try:
                        package_name = self.adb_client.get_current_package(self.device_id) or ""
                    except Exception:
                        pass

                data = {
                    "cpu_freqs": self.adb_client.get_cpu_freqs(self.device_id),
                    "cpu_usage": self.adb_client.get_cpu_usage(self.device_id),
                    "cpu_temp": self.adb_client.get_cpu_temp(self.device_id),
                    "gpu_freq": self.adb_client.get_gpu_freq(self.device_id),
                    "gpu_info": self.adb_client.get_gpu_info(self.device_id, package_name),
                    "mem_info": self.adb_client.get_mem_info(self.device_id),
                    "battery_power": self.adb_client.get_battery_power(self.device_id),
                    "package_name": package_name,
                    "timestamp": time.time(),
                }
                self.hw_data_ready.emit(data)
            except Exception as e:
                self.error_occurred.emit(f"硬件监测错误: {e}")
            # 高精度分段等待（扣除采集耗时，确保短间隔真实有效；每 20ms 检查一次 stop）
            elapsed = time.time() - loop_start
            remaining = max(0.0, float(self.poll_interval) - elapsed)
            tick = 0.02  # 20ms 粒度，stop 响应快于 50ms
            ticks_needed = int(remaining / tick)
            frac = remaining - ticks_needed * tick
            for _ in range(ticks_needed):
                if not self._running:
                    break
                time.sleep(tick)
            if self._running and frac > 0:
                time.sleep(frac)


class IOSHWMonitorThread(QThread):
    """iOS 硬件监测线程 — 通过 IOSMonitor 持续采集 CPU/GPU 使用率与内存"""
    hw_data_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    started_ok = pyqtSignal()
    start_failed = pyqtSignal(str)

    def __init__(self, ios_client: IOSClient, udid: str, poll_interval: float = 1.0):
        super().__init__()
        self.ios_client = ios_client
        self.udid = udid
        self.poll_interval = poll_interval
        self._running = False
        self._monitor: Optional[IOSMonitor] = None

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        self._monitor = self.ios_client.create_monitor(self.udid)
        ok, err = self._monitor.start()
        if not ok:
            self.start_failed.emit(err or "iOS 监测会话启动失败")
            return
        self.started_ok.emit()

        while self._running:
            loop_start = time.time()
            try:
                latest = self._monitor.get_latest()
                if latest:
                    self.hw_data_ready.emit(latest)
            except Exception as e:
                self.error_occurred.emit(f"iOS 监测读取错误: {e}")
            # 高精度分段等待（扣除采集耗时，确保短间隔真实有效；每 20ms 检查一次 stop）
            elapsed = time.time() - loop_start
            remaining = max(0.0, float(self.poll_interval) - elapsed)
            tick = 0.02  # 20ms 粒度，stop 响应快于 50ms
            ticks_needed = int(remaining / tick)
            frac = remaining - ticks_needed * tick
            for _ in range(ticks_needed):
                if not self._running:
                    break
                time.sleep(tick)
            if self._running and frac > 0:
                time.sleep(frac)

        self._monitor.stop()


class IOSFPSCollectorThread(QThread):
    """iOS 帧率采集线程 — 通过 IOSFPSCollector 采集 FPS，喂入 FPSAnalyzer"""
    stats_ready = pyqtSignal(object)
    log_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished_signal = pyqtSignal()
    started_ok = pyqtSignal()
    start_failed = pyqtSignal(str)

    def __init__(self, ios_client: IOSClient, udid: str, analyzer: FPSAnalyzer,
                 refresh_rate: int = 60, poll_interval: float = 1.0):
        super().__init__()
        self.ios_client = ios_client
        self.udid = udid
        self.analyzer = analyzer
        self.refresh_rate = refresh_rate
        self.poll_interval = poll_interval
        self._running = False
        self._collector: Optional[IOSFPSCollector] = None

    def stop(self):
        self._running = False

    def _precise_sleep(self, seconds: float) -> None:
        """高精度可中断 sleep（每 20ms 粒度检查 running，适配 0.1/0.3s 短间隔）"""
        if seconds is None or seconds <= 0:
            return
        total = max(0.0, float(seconds))
        tick = 0.02  # 20ms 粒度
        ticks_needed = int(total / tick)
        frac = total - ticks_needed * tick
        ms_tick = int(tick * 1000)
        for _ in range(ticks_needed):
            if not self._running:
                return
            self.msleep(ms_tick)
        if self._running and frac > 0:
            self.msleep(max(1, int(frac * 1000)))

    def run(self):
        self._running = True
        self.analyzer.reset()
        self.analyzer.start_time = time.time()

        self._collector = self.ios_client.create_fps_collector(self.udid, self.refresh_rate)
        ok, err = self._collector.start()
        if not ok:
            self.log_message.emit(f"⚠️ Graphics 服务启动失败: {err}")
            self.log_message.emit("ℹ️ 回退到屏幕刷新率估算模式")
            self._run_estimation_mode()
        else:
            self.started_ok.emit()
            self.log_message.emit(f"✅ iOS FPS 采集已启动 (Graphics 服务)")
            self._run_graphics_mode()

        self.finished_signal.emit()

    def _run_graphics_mode(self):
        """通过 Graphics 服务采集 FPS。

        interval=0.0（每个事件=一帧）：
        - 帧间时间差 = 真实帧时间(ms)，由 collector 直接计算
        - 事件计数法 = 每秒事件数 = 真实 FPS
        - consume_frame_times() 返回真实的每帧帧时间列表
        - 若无帧时间但有有效 FPS，回退用 FPS 生成合成帧
        """
        sample_count = 0
        last_ts = time.time()
        while self._running:
            loop_start = time.time()
            try:
                now_ts = time.time()
                dt = max(now_ts - last_ts, 0.001)
                last_ts = now_ts

                fps = self._collector.get_fps()
                # 注入瞬时 FPS 观测值（用 EMA 平滑后作为 UI 显示的 current_fps）
                if fps > 0:
                    self.analyzer.observe_instant_fps(fps)

                # 取出并清空已累积的真实帧时间
                frame_times = self._collector.consume_frame_times()

                if frame_times:
                    # 直接添加真实帧时间
                    self.analyzer.add_frames(frame_times)
                elif fps > 0:
                    # 回退：无帧时间但有有效 FPS，按 FPS 补合成帧
                    n = max(1, round(fps * dt))
                    self.analyzer.add_frames([1000.0 / fps] * min(n, 300))

                stats = self.analyzer.sample()
                if stats:
                    if sample_count == 0:
                        self.log_message.emit(f"📊 首次数据: FPS≈{fps:.1f}")
                    sample_count += 1
                    self.stats_ready.emit(stats)

            except Exception as e:
                self.log_message.emit(f"采集异常: {e}")

            # 高精度 sleep：扣除采集耗时，短间隔 0.1/0.3s 真实有效
            elapsed = time.time() - loop_start
            self._precise_sleep(max(0.0, float(self.poll_interval) - elapsed))

        self._collector.stop()

    def _run_estimation_mode(self):
        """回退模式：使用屏幕刷新率作为估算 FPS"""
        self.log_message.emit(f"📊 估算模式: 屏幕刷新率={self.refresh_rate}Hz")
        sample_count = 0

        while self._running:
            loop_start = time.time()
            try:
                # 以刷新率作为基础 FPS，添加小幅波动模拟真实场景
                base_fps = float(self.refresh_rate)
                # 采集系统负载来判断是否有降帧（尽力而为）
                if self._collector and self._collector.is_running:
                    actual_fps = self._collector.get_fps()
                    if actual_fps > 0:
                        base_fps = actual_fps

                # 生成帧时间数据
                frame_time = 1000.0 / max(base_fps, 1)
                self.analyzer.add_frames([frame_time])

                stats = self.analyzer.sample()
                if stats:
                    if sample_count == 0:
                        self.log_message.emit(f"📊 首次数据: FPS≈{base_fps:.1f} (估算)")
                    sample_count += 1
                    self.stats_ready.emit(stats)

            except Exception as e:
                self.log_message.emit(f"采集异常: {e}")

            # 高精度 sleep：扣除采集耗时，短间隔 0.1/0.3s 真实有效
            elapsed = time.time() - loop_start
            self._precise_sleep(max(0.0, float(self.poll_interval) - elapsed))

        if self._collector:
            self._collector.stop()


class _StarField(QWidget):
    """星空画布：深邃星空背景 + 闪烁星星 + 星环 LOGO + 渐现标题

    用于开屏动画页面，绘制 50+ 颗随机闪烁的星星、中央星环 LOGO、
    以及渐现的「星穹视界」标题文字。进度条满后发射 progress_complete 信号。
    """

    progress_complete = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 尺寸策略：自动跟随父容器拉伸，占满整个开屏页面
        try:
            from PyQt5.QtWidgets import QSizePolicy
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        except Exception:
            pass
        self._stars = []
        self._init_stars()
        self._tick = 0
        self._phase = 0.0
        self._completed = False
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_tick)
        self._anim_timer.start(40)  # ~25fps 足够流畅

    def resizeEvent(self, event):
        """窗口尺寸变化时，保持画布铺满；星星按比例保持相对布局"""
        try:
            super().resizeEvent(event)
        except Exception:
            pass
        self.update()

    def _init_stars(self):
        import random
        self._stars = []
        # 按屏幕面积多放一些星星（数量随显示密度调整——使用固定大基数，效果更均匀）
        base = 160
        for _ in range(base):
            self._stars.append({
                "x": random.uniform(0, 1),
                "y": random.uniform(0, 1),
                "r": random.uniform(0.6, 2.8),
                "speed": random.uniform(0.4, 2.0),
                "phase": random.uniform(0, 6.28),
                "color": random.choice([
                    QColor("#ffffff"), QColor("#b3e5fc"), QColor("#c8e6c9"),
                    QColor("#ffe0b2"), QColor("#f8bbd0"), QColor("#d1c4e9"),
                ]),
            })
        # 8 颗特别明亮的大星
        for _ in range(8):
            self._stars.append({
                "x": random.uniform(0.05, 0.95),
                "y": random.uniform(0.08, 0.92),
                "r": random.uniform(3.5, 5.5),
                "speed": random.uniform(0.3, 0.9),
                "phase": random.uniform(0, 6.28),
                "color": QColor("#ffffff"),
            })
        # 2 颗流动的流星
        self._shooting_stars = []
        for _ in range(2):
            self._shooting_stars.append({
                "born": random.randint(20, 100),
                "length_ratio": random.uniform(0.15, 0.28),
                "angle": random.uniform(-30, -10),
                "speed_ratio": random.uniform(0.004, 0.007),
                "t": random.uniform(0, 1),
            })

    def _on_tick(self):
        self._tick += 1
        self._phase += 0.08
        self.update()
        # 进度条满时发射信号（只发一次，约 5 秒 = 125 帧）
        if not self._completed and self._tick >= 125:
            self._completed = True
            self.progress_complete.emit()

    def paintEvent(self, event):
        import math
        import random
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        t = self._tick

        # 1. 深空渐变背景（四角多色渐变，更有宇宙纵深）
        grad = QRadialGradient(QPointF(w * 0.5, h * 0.45), max(w, h) * 0.8)
        grad.setColorAt(0.0, QColor("#101a3a"))
        grad.setColorAt(0.45, QColor("#0a0e24"))
        grad.setColorAt(1.0, QColor("#04070f"))
        p.fillRect(0, 0, w, h, QBrush(grad))
        # 角落星云（淡色径向叠加）
        for (cx, cy, c, a, s) in [
            (0.08, 0.12, QColor(79, 70, 229, 60), 0.0, 0.45),
            (0.92, 0.88, QColor(14, 165, 233, 55), 0.0, 0.40),
            (0.80, 0.18, QColor(236, 72, 153, 30), 0.0, 0.32),
            (0.18, 0.82, QColor(16, 185, 129, 28), 0.0, 0.28),
        ]:
            neb = QRadialGradient(QPointF(w * cx, h * cy), max(w, h) * s)
            neb.setColorAt(0.0, c)
            neb.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
            p.fillRect(0, 0, w, h, QBrush(neb))

        # 1.5 流星划过
        for ss in getattr(self, "_shooting_stars", []):
            ss["t"] += ss["speed_ratio"]
            if ss["t"] > 1.1:
                ss["t"] = -0.1 - random.random() * 0.3
                ss["born"] = random.randint(20, 100)
                ss["angle"] = random.uniform(-32, -8)
                ss["length_ratio"] = random.uniform(0.15, 0.30)
            tx = ss["t"]
            if 0.0 <= tx <= 1.0:
                sx = (tx - ss["length_ratio"]) * w
                sy = tx * h * 0.6
                ex = tx * w
                ey = (tx + ss["length_ratio"] * 0.2) * h * 0.6
                # 拖尾渐变
                lg = QLinearGradient(sx, sy, ex, ey)
                lg.setColorAt(0.0, QColor(255, 255, 255, 0))
                lg.setColorAt(0.6, QColor(186, 230, 253, 180))
                lg.setColorAt(1.0, QColor(255, 255, 255, 230))
                pen = QPen(QBrush(lg), max(1.5, min(w, h) * 0.003), Qt.SolidLine, Qt.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(sx, sy), QPointF(ex, ey))
                # 流星头小星
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(QColor(255, 255, 255, 230)))
                p.drawEllipse(QPointF(ex, ey), max(2, min(w, h) * 0.004), max(2, min(w, h) * 0.004))

        # 2. 星星闪烁（按当前 w/h 缩放）
        for s in self._stars:
            px = s["x"] * w
            py = s["y"] * h
            tw = 0.5 + 0.5 * math.sin(self._phase * s["speed"] + s["phase"])
            alpha = int(80 + 175 * tw)
            color = QColor(s["color"])
            color.setAlpha(alpha)
            r = s["r"] * (0.8 + 0.4 * tw) * max(1.0, min(w, h) / 1000.0)
            if r < 0.6:
                r = 0.6
            # 发光光晕
            glow = QRadialGradient(QPointF(px, py), r * 4)
            glow.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            glow.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(px, py), r * 4, r * 4)
            # 星心
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(px, py), r, r)

        # 3. 中央星环 LOGO：使用 min(w,h) 动态缩放，在超大屏/小屏下都协调
        scale = max(1.0, min(w, h) / 900.0)
        cx, cy = w / 2, h * 0.45
        logo_r = max(55, 80 * scale)
        ring_phase = self._phase * 0.3

        # 外环光晕（巨大，撑起中心视觉）
        halo_grad = QRadialGradient(QPointF(cx, cy), logo_r * 3.4)
        halo_grad.setColorAt(0.0, QColor(33, 150, 243, 90))
        halo_grad.setColorAt(0.4, QColor(59, 130, 246, 30))
        halo_grad.setColorAt(1.0, QColor(33, 150, 243, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(halo_grad))
        p.drawEllipse(QPointF(cx, cy), logo_r * 3.4, logo_r * 3.4)

        # 星环椭圆（倾斜）
        p.save()
        p.translate(cx, cy)
        p.rotate(-20)
        ring_pen = QPen(QColor(100, 181, 246), max(2, int(3 * scale)))
        p.setPen(ring_pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), logo_r * 1.7, logo_r * 0.58)
        # 内环
        ring_pen2 = QPen(QColor(144, 202, 249), max(1, int(2 * scale)))
        p.setPen(ring_pen2)
        p.drawEllipse(QPointF(0, 0), logo_r * 1.28, logo_r * 0.44)
        # 光环旋转点缀
        p.rotate(ring_phase * 20)
        ring_pen3 = QPen(QColor(191, 219, 254), max(1, int(1.5 * scale)), Qt.DashLine)
        p.setPen(ring_pen3)
        p.drawEllipse(QPointF(0, 0), logo_r * 1.9, logo_r * 0.66)
        p.restore()

        # 中心行星
        planet_grad = QRadialGradient(QPointF(cx - logo_r * 0.15, cy - logo_r * 0.15), logo_r * 0.95)
        planet_grad.setColorAt(0.0, QColor(129, 212, 250))
        planet_grad.setColorAt(0.5, QColor(33, 150, 243))
        planet_grad.setColorAt(1.0, QColor(21, 101, 192))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(planet_grad))
        p.drawEllipse(QPointF(cx, cy), logo_r * 0.58, logo_r * 0.58)

        # 行星高光
        hl_grad = QRadialGradient(QPointF(cx - logo_r * 0.22, cy - logo_r * 0.22), logo_r * 0.4)
        hl_grad.setColorAt(0.0, QColor(255, 255, 255, 190))
        hl_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hl_grad))
        p.drawEllipse(QPointF(cx - logo_r * 0.22, cy - logo_r * 0.22), logo_r * 0.28, logo_r * 0.28)

        # 四角闪光星
        for i, angle in enumerate([0, 72, 144, 216, 288]):
            rad = (angle + ring_phase * 30) * math.pi / 180
            sx = cx + logo_r * 1.75 * math.cos(rad)
            sy = cy + logo_r * 1.75 * math.sin(rad) * 0.58
            star_size = (6 + 3 * math.sin(self._phase + i)) * scale
            self._draw_sparkle(p, sx, sy, star_size, QColor(255, 255, 255, 220))

        # 4. 渐现标题「星穹视界」（自适应字号）
        fade_in = min(1.0, t / 15)
        if fade_in > 0:
            title_alpha = int(255 * fade_in)
            title_y = cy + logo_r * 1.25
            title_fs = max(30, int(min(w / 16, h / 13)))
            p.setPen(Qt.NoPen)
            p.setFont(QFont("PingFang SC", title_fs, QFont.Bold))
            # 多层发光光晕（更大范围）
            glow_layer = [
                (QColor(56, 189, 248, int(30 * fade_in)), 8),
                (QColor(125, 211, 252, int(45 * fade_in)), 5),
                (QColor(255, 255, 255, int(55 * fade_in)), 2),
            ]
            title_rect_h = int(title_fs * 1.4)
            for (pen_c, off) in glow_layer:
                p.setPen(QPen(pen_c, 1))
                for dx in (-off, 0, off):
                    for dy in (-off, 0, off):
                        if dx == 0 and dy == 0:
                            continue
                        p.drawText(QRectF(dx, title_y + dy, w, title_rect_h), Qt.AlignCenter, "星穹视界")
            # 主标题（纯白）
            title_color = QColor(255, 255, 255, title_alpha)
            p.setPen(QPen(title_color, 1))
            p.drawText(QRectF(0, title_y, w, title_rect_h), Qt.AlignCenter, "星穹视界")

            # 副标题（浅白）：字号自适应
            sub_alpha = int(220 * max(0, (fade_in - 0.3) / 0.7))
            if sub_alpha > 0:
                sub_fs = max(13, int(title_fs * 0.36))
                sub_color = QColor(226, 232, 240, sub_alpha)
                p.setPen(QPen(sub_color, 1))
                p.setFont(QFont("PingFang SC", sub_fs))
                p.drawText(QRectF(0, title_y + title_rect_h + int(6 * scale), w, int(sub_fs * 1.8)),
                           Qt.AlignCenter, "Stellar Vision FPS Tester")

        # 5. 底部进度条 + 加载提示（按窗口相对高度放置）
        raw = min(1.0, t / 125.0)
        eased = 1.0 - (1.0 - raw) * (1.0 - raw)
        wobble = 0.012 * math.sin(t * 0.35) * (1.0 - raw)
        progress = max(0.0, min(1.0, eased + wobble))
        bar_w = min(w * 0.55, 560 * scale)
        bar_h = max(6, int(10 * scale))
        bar_x = (w - bar_w) / 2
        bar_y = h - max(80, int(120 * scale))
        bar_r = bar_h / 2

        # 进度槽
        p.setPen(QPen(QColor(255, 255, 255, 55), 1))
        p.setBrush(QBrush(QColor(255, 255, 255, 28)))
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), bar_r, bar_r)

        # 进度填充（双色渐变 + 扫光）
        if progress > 0:
            fill_w = bar_w * progress
            fill_grad = QLinearGradient(0, bar_y, 0, bar_y + bar_h)
            fill_grad.setColorAt(0.0, QColor(125, 211, 252, 240))
            fill_grad.setColorAt(0.5, QColor(59, 130, 246, 245))
            fill_grad.setColorAt(1.0, QColor(79, 70, 229, 230))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(fill_grad))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), bar_r, bar_r)

            # 移动光泽高光
            shine_x = bar_x + fill_w
            shine_w = max(20, int(36 * scale))
            shine_grad = QLinearGradient(shine_x - shine_w, 0, shine_x + shine_w, 0)
            shine_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            shine_grad.setColorAt(0.5, QColor(255, 255, 255, 150))
            shine_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(shine_grad))
            p.save()
            p.setClipRect(QRectF(bar_x, bar_y, fill_w, bar_h))
            p.drawRoundedRect(QRectF(shine_x - shine_w, bar_y, shine_w * 2, bar_h), bar_r, bar_r)
            p.restore()

        # 加载文字 + 百分比（自适应字号）
        load_alpha = int(200 * min(1.0, t / 10))
        if load_alpha > 0:
            if raw < 0.25:
                tip_text = "正在加载核心模块"
            elif raw < 0.5:
                tip_text = "正在初始化设备服务"
            elif raw < 0.75:
                tip_text = "正在连接性能监测引擎"
            elif raw < 0.95:
                tip_text = "正在准备测试环境"
            else:
                tip_text = "即将完成"
            dots = "." * ((t // 6) % 4)
            tip_fs = max(11, int(14 * scale))
            pct_fs = max(11, int(13 * scale))
            # 提示文字
            load_color = QColor(226, 232, 240, load_alpha)
            p.setPen(QPen(load_color, 1))
            p.setFont(QFont("PingFang SC", tip_fs))
            tip_h = int(tip_fs * 1.8)
            p.drawText(QRectF(0, bar_y - tip_h - 4, w, tip_h),
                       Qt.AlignCenter, f"{tip_text}{dots}")
            # 百分比
            pct_color = QColor(255, 255, 255, load_alpha)
            p.setPen(QPen(pct_color, 1))
            p.setFont(QFont("Menlo", pct_fs, QFont.Bold))
            pct_h = int(pct_fs * 1.8)
            p.drawText(QRectF(0, bar_y + bar_h + 6, w, pct_h),
                       Qt.AlignCenter, f"{int(progress * 100)}%")

    def _draw_sparkle(self, p, x, y, size, color):
        """绘制四角闪光星"""
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(color))
        p.drawEllipse(QPointF(x, y), size * 0.3, size * 0.3)
        p.setPen(QPen(color, max(1, size * 0.2)))
        p.drawLine(QPointF(x - size, y), QPointF(x + size, y))
        p.drawLine(QPointF(x, y - size), QPointF(x, y + size))
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 80), max(0.6, size * 0.12)))
        d = size * 0.6
        p.drawLine(QPointF(x - d, y - d), QPointF(x + d, y + d))
        p.drawLine(QPointF(x + d, y - d), QPointF(x - d, y + d))


class LoadTestThread(QThread):
    """负载测试线程 — 在后台设备端持续高负载作业 1 小时，UI 线程不阻塞

    设计原则：
    - 后台线程只做 IO（ADB/指令调用）和定时上报，绝不触碰 UI。
    - 所有 UI 更新都通过 pyqtSignal 走主事件循环。
    - 设备端负载方式：
      - Android：持续高频 CPU 加压（计算密集小脚本循环） + 每 30s 尝试 GC 抖动，并抓电池/温度/CPU 综合状态
      - iOS：1 小时内每 30s 拉一次 CPU/GPU/内存 + 温度指标，通过高频繁检测让接口持续加压，
             真实负载压力需来自被测前台游戏/benchmark；此线程负责监测与判稳
    - 总时长 3600 秒（1 小时），每 1 秒上报一次剩余时间 / 关键采样
    - 结束后 emit 结论文本，供 UI 直接展示
    """

    tick = pyqtSignal(int, int, dict)        # elapsed_sec, remaining_sec, snapshot
    log = pyqtSignal(str)
    finished_summary = pyqtSignal(dict)     # 结论报告
    error_occurred = pyqtSignal(str)

    def __init__(self, platform: str, adb_client=None, device_id=None,
                 ios_client=None, udid=None, duration_sec: int = 3600):
        super().__init__()
        self.platform = platform.lower()
        self.adb_client = adb_client
        self.device_id = device_id
        self.ios_client = ios_client
        self.udid = udid
        self.duration_sec = duration_sec
        self._running = False
        # 样本汇总
        self.samples_cpu = []
        self.samples_gpu = []
        self.samples_mem = []
        self.samples_temp = []
        self.crash_flags = []   # 每次异常记录
        # 已在跑的设备端压力作业进程（安卓用）
        self._android_pressure_proc = None

    def stop(self):
        self._running = False
        self._android_stop_pressure()

    # ================= Android 压力 =================
    def _android_start_pressure(self):
        """在设备端后台启动多核并行 CPU 满载脚本（不阻塞本机线程）

        策略：按 CPU 核心数启动等量后台进程，每个进程跑纯整数算术循环
        持续占满一个核心；限时 3700 秒后自动退出；手机硬件温控会自动
        降频保护，不会损坏 CPU。
        """
        try:
            if not self.adb_client or not self.device_id:
                return False
            # 获取核心数，按核心数启动并行满载进程（上限 8）
            # __LT_PRESS__ 作为 sh -c 的 $0 参数，便于 pkill -f 精确清理
            script = (
                "n=$(grep -c processor /proc/cpuinfo); "
                "[ -z \"$n\" ] && n=4; "
                "[ \"$n\" -gt 8 ] && n=8; "
                "i=0; "
                "while [ $i -lt $n ]; do "
                "  nohup sh -c '"
                "ts=$(date +%s); end=$((ts+3700)); "
                "while [ $(date +%s) -lt $end ]; do "
                "  x=0; k=0; "
                "  while [ $k -lt 50000 ]; do x=$((x+k*k+k)); k=$((k+1)); done; "
                "done"
                "' __LT_PRESS__ >/dev/null 2>&1 < /dev/null & "
                "  i=$((i+1)); "
                "done; "
                "echo LT_PRESS_STARTED_$n"
            )
            out = self.adb_client.raw_shell(self.device_id, script, timeout=8)
            if out and "LT_PRESS_STARTED" in out:
                # 提取启动的进程数
                for line in out.splitlines():
                    if "LT_PRESS_STARTED" in line:
                        cores = line.strip().split("_")[-1]
                        self.log.emit(f"🔥 安卓端 CPU 压力已启动：{cores} 核并行满载")
                        break
                self._android_pressure_proc = True  # 标记已启动
                return True
        except Exception as e:
            self.log.emit(f"⚠️ 安卓压力启动失败（不影响监测）: {e}")
        return False

    def _android_stop_pressure(self):
        """清理安卓端后台压力进程"""
        if self._android_pressure_proc:
            try:
                self.adb_client.raw_shell(self.device_id, "pkill -f __LT_PRESS__", timeout=5)
                self.log.emit("🛑 安卓端 CPU 压力已停止")
            except Exception:
                pass
            self._android_pressure_proc = None

    def _android_snapshot(self) -> dict:
        """安卓端实时快照：CPU 使用率（双采样差值）/ CPU 核心温度 / 内存 / GPU / 电量"""
        snap = {"cpu_pct": None, "gpu_pct": None, "mem_mb": None, "temp": None, "battery": None}
        try:
            # CPU 使用率：用 adb_client 双采样差值法（准确）
            try:
                snap["cpu_pct"] = self.adb_client.get_cpu_usage(self.device_id)
            except Exception:
                pass

            # CPU 核心温度：读取所有 thermal_zone 的 type + temp，只取 type 含 "cpu" 的
            try:
                thermal_out = self.adb_client.raw_shell(self.device_id,
                    'for z in /sys/class/thermal/thermal_zone*; do '
                    't=$(cat $z/type 2>/dev/null); v=$(cat $z/temp 2>/dev/null); '
                    'echo "$t $v"; done', timeout=2)
                cpu_temps = []
                for line in (thermal_out or "").splitlines():
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue
                    zone_type = parts[0].lower()
                    # 只取 CPU 核心温度，过滤掉电池(bcl/vbat/ibat)、PMIC 等
                    if "cpu" not in zone_type:
                        continue
                    try:
                        raw = int(parts[1])
                        if raw > 1000:
                            cpu_temps.append(raw / 1000.0)
                        elif raw > 20:
                            cpu_temps.append(float(raw))
                    except (ValueError, TypeError):
                        pass
                if cpu_temps:
                    snap["temp"] = round(max(cpu_temps), 1)
            except Exception:
                pass

            # 电量
            try:
                bat = self.adb_client.raw_shell(self.device_id,
                    "dumpsys battery | grep level:", timeout=2)
                if bat and ":" in bat:
                    snap["battery"] = int(bat.split(":")[1].strip())
            except Exception:
                pass

            # 内存
            try:
                mem = self.adb_client.raw_shell(self.device_id,
                    "grep -E 'MemTotal|MemAvailable' /proc/meminfo", timeout=2)
                tot, avail = None, None
                for l in (mem or "").splitlines():
                    digits = [p for p in l.split() if p.isdigit()]
                    if "MemTotal:" in l and digits:
                        tot = int(digits[0])
                    if "MemAvailable:" in l and digits:
                        avail = int(digits[0])
                if tot and avail:
                    snap["mem_mb"] = round((tot - avail) / 1024.0, 1)
            except Exception:
                pass

            # GPU 负载
            try:
                gpu = self.adb_client.raw_shell(self.device_id,
                    "cat /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage 2>/dev/null", timeout=2)
                val = (gpu or "").strip().rstrip("%")
                if val.isdigit():
                    snap["gpu_pct"] = int(val)
            except Exception:
                pass
        except Exception as e:
            self.crash_flags.append(str(e))
        return snap

    # ================= iOS 监测（无脚本可控，仅高频采样接口加压）=================
    def _ios_snapshot(self) -> dict:
        snap = {"cpu_pct": None, "gpu_pct": None, "mem_mb": None, "temp": None, "battery": None}
        try:
            if not self.ios_client or not self.udid:
                return snap
            # 调用 ios_client 的 sysmontap/dvt 一次拉取（若不可用则跳过）
            # best-effort：调用已知接口名称，失败则不抛
            try:
                info = self.ios_client.get_device_info(self.udid)
                if info:
                    snap["battery"] = info.get("battery_level")
            except Exception:
                pass
            # 直接抓硬件监测的单次数据
            try:
                snap_obj = self.ios_client._sysmontap_snapshot_once(self.udid) if hasattr(self.ios_client, "_sysmontap_snapshot_once") else None
                if snap_obj and isinstance(snap_obj, dict):
                    if snap_obj.get("cpu_usage") is not None:
                        snap["cpu_pct"] = round(snap_obj["cpu_usage"] * 1.0, 1)
                    if snap_obj.get("gpu_usage") is not None:
                        snap["gpu_pct"] = round(snap_obj["gpu_usage"] * 1.0, 1)
                    if snap_obj.get("mem_usage_mb") is not None:
                        snap["mem_mb"] = round(snap_obj["mem_usage_mb"], 1)
                    if snap_obj.get("temp") is not None:
                        snap["temp"] = round(snap_obj["temp"], 1)
            except Exception as ex:
                self.crash_flags.append(f"iOS_snap:{ex}")
        except Exception as e:
            self.crash_flags.append(str(e))
        return snap

    # ================= 主循环 =================
    def _precise_sleep(self, seconds: float):
        total = max(0.0, seconds)
        tick = 0.05
        ticks = int(total / tick)
        for _ in range(ticks):
            if not self._running:
                return
            self.msleep(int(tick * 1000))
        remain = total - ticks * tick
        if remain > 0 and self._running:
            self.msleep(int(remain * 1000))

    def run(self):
        self._running = True
        try:
            if self.platform == "android":
                self._android_start_pressure()

            start_time = time.time()
            self._actual_elapsed = 0
            # 初始化采样缓冲
            last_snap_time = 0
            last_snap = {"cpu_pct": None, "gpu_pct": None, "mem_mb": None, "temp": None, "battery": None}
            while self._running:
                elapsed = int(time.time() - start_time)
                remaining = max(0, self.duration_sec - elapsed)
                self._actual_elapsed = elapsed
                if elapsed >= self.duration_sec:
                    break

                now = time.time()
                if now - last_snap_time >= 1.0:
                    last_snap_time = now
                    snap = self._android_snapshot() if self.platform == "android" else self._ios_snapshot()
                    if snap.get("cpu_pct") is not None:
                        self.samples_cpu.append(max(0.0, min(100.0, float(snap["cpu_pct"]))))
                    if snap.get("gpu_pct") is not None:
                        self.samples_gpu.append(max(0.0, min(100.0, float(snap["gpu_pct"]))))
                    if snap.get("mem_mb") is not None:
                        self.samples_mem.append(float(snap["mem_mb"]))
                    if snap.get("temp") is not None:
                        self.samples_temp.append(float(snap["temp"]))
                    last_snap = snap

                # 每次循环都发射 tick（~200ms 一次），保证倒计时流畅不延迟
                self.tick.emit(elapsed, remaining, last_snap)

                self._precise_sleep(0.2)

            # 清理安卓压力进程
            self._android_stop_pressure()

            # 生成结论报告
            summary = self._build_summary()
            self.finished_summary.emit(summary)
        except Exception as e:
            self.error_occurred.emit(f"负载测试线程异常: {e}")
        finally:
            self._android_stop_pressure()

    def _build_summary(self) -> dict:
        def _stats(lst):
            if not lst:
                return None, None, None, None
            a = sum(lst) / len(lst)
            return len(lst), a, max(lst), min(lst)
        cn, c_avg, c_max, c_min = _stats(self.samples_cpu)
        gn, g_avg, g_max, g_min = _stats(self.samples_gpu)
        mn, m_avg, m_max, m_min = _stats(self.samples_mem)
        tn, t_avg, t_max, t_min = _stats(self.samples_temp)

        # 稳定性评级（使用 key：good / warn / bad，由 UI 层翻译）
        rating = "good"
        issues = []  # list of (issue_key, params_dict) 供 UI 层翻译
        if self.crash_flags and len(self.crash_flags) > 5:
            issues.append(("load_issue_crash", {"count": len(self.crash_flags)}))
        if t_max is not None and t_max > 65:
            issues.append(("load_issue_temp_peak", {"temp": t_max}))
            rating = "bad"
        elif t_max is not None and t_max > 60:
            issues.append(("load_issue_temp_high", {"temp": t_max}))
            if rating == "good":
                rating = "warn"
        if c_avg is not None and c_avg > 90:
            issues.append(("load_issue_cpu_avg", {"avg": c_avg}))
        if c_max is not None and c_max >= 98:
            issues.append(("load_issue_cpu_peak", {"max": c_max}))

        actual_dur = int(getattr(self, "_actual_elapsed", 0) or self.duration_sec)

        # 时间序列（用于 HTML 趋势图导出）
        n = max(len(self.samples_cpu), len(self.samples_gpu), len(self.samples_mem), len(self.samples_temp))
        time_axis = [round(i, 1) for i in range(n)]  # 按秒计数
        time_series = {
            "time": time_axis,
            "cpu": [round(float(v), 2) if v is not None else None for v in self.samples_cpu] + [None] * (n - len(self.samples_cpu)),
            "gpu": [round(float(v), 2) if v is not None else None for v in self.samples_gpu] + [None] * (n - len(self.samples_gpu)),
            "mem": [round(float(v), 2) if v is not None else None for v in self.samples_mem] + [None] * (n - len(self.samples_mem)),
            "cpu_temp": [round(float(v), 2) if v is not None else None for v in self.samples_temp] + [None] * (n - len(self.samples_temp)),
        }

        return {
            "rating": rating,
            "rating_key": rating,
            "issues": issues,
            "lines": [],  # 由 UI 层 _build_load_conclusion 生成翻译文本
            "duration_sec": actual_dur,
            "stats": {
                "cpu": {"n": cn, "avg": c_avg, "max": c_max, "min": c_min},
                "gpu": {"n": gn, "avg": g_avg, "max": g_max, "min": g_min},
                "mem": {"n": mn, "avg": m_avg, "max": m_max, "min": m_min},
                "temp": {"n": tn, "avg": t_avg, "max": t_max, "min": t_min},
                "cpu_temp": {"n": tn, "avg": t_avg, "max": t_max, "min": t_min},
            },
            "errors": len(self.crash_flags),
            "time_series": time_series,
        }


def _play_ding():
    """播放'叮'提示音（跨平台）"""
    try:
        import platform
        import subprocess
        sys_name = platform.system()
        if sys_name == "Darwin":
            subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys_name == "Windows":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                QApplication.beep()
        else:
            QApplication.beep()
    except Exception:
        try:
            QApplication.beep()
        except Exception:
            pass


class DashboardAnimation(QWidget):
    """汽车仪表盘样式环形转动动画"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.setMinimumSize(280, 280)

    def start(self):
        self._timer.start(30)

    def stop_anim(self):
        self._timer.stop()

    def _rotate(self):
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        cx, cy = w // 2, h // 2
        radius = max(20, min(w, h) // 2 - 24)

        # 外环背景
        bg_pen = QPen(QColor("#e2e8f0"), 14)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
                        0, 360 * 16)

        # 刻度线
        painter.setPen(QPen(QColor("#cbd5e1"), 2))
        for i in range(12):
            import math
            a = math.radians(i * 30 - 90)
            r1 = radius + 18
            r2 = radius + 26
            painter.drawLine(QPointF(cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                             QPointF(cx + r2 * math.cos(a), cy + r2 * math.sin(a)))

        # 旋转主弧（蓝色）
        pen1 = QPen(QColor("#3b82f6"), 14)
        pen1.setCapStyle(Qt.RoundCap)
        painter.setPen(pen1)
        start = self._angle * 16
        painter.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
                        -start, 100 * 16)

        # 旋转副弧（青色）
        pen2 = QPen(QColor("#06b6d4"), 10)
        pen2.setCapStyle(Qt.RoundCap)
        painter.setPen(pen2)
        painter.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
                        -start + 140 * 16, 60 * 16)

        # 中心圆点
        painter.setBrush(QBrush(QColor("#3b82f6")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 8, 8)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        _logger.info("MainWindow.__init__(): 开始构造主窗口")

        # ===== 国际化初始化：先加载持久化语言 =====
        self._lang_settings = QSettings("StellarVision", "FPS_Tester")
        saved_lang = self._lang_settings.value("ui_language", "zh-CN", type=str)
        if saved_lang not in _TRANSLATIONS:
            saved_lang = "zh-CN"
        self._current_lang: str = saved_lang

        # UI 引用（用于切换语言时重新 setText）
        self._i18n_refs: dict = {}

        self.setWindowTitle(self._tr("app_title"))
        # macOS：让菜单栏首项也显示为「星穹视界帧率测试」（替代默认的 Python / APP 名称）
        try:
            from PyQt5.QtWidgets import QMenuBar
            self.setWindowFilePath("星穹视界帧率测试")
        except Exception:
            pass
        self.resize(1400, 900)

        # 初始化组件
        try:
            self.adb_client = ADBClient()
        except Exception as e:
            log_exception(e, "ADBClient 初始化失败")
            self.adb_client = ADBClient.__new__(ADBClient)
        try:
            self.ios_client = IOSClient()
        except Exception as e:
            log_exception(e, "IOSClient 初始化失败")
            self.ios_client = IOSClient.__new__(IOSClient)
        try:
            self.analyzer = FPSAnalyzer(window_size=120, refresh_rate=60)
        except Exception as e:
            log_exception(e, "FPSAnalyzer 初始化失败")
            self.analyzer = FPSAnalyzer(window_size=120, refresh_rate=60)
        self.collector_thread: Optional[FPSCollectorThread] = None
        self.hw_monitor_thread: Optional[HWMonitorThread] = None

        # iOS 专用线程与状态
        self.ios_fps_thread: Optional[IOSFPSCollectorThread] = None
        self.ios_hw_thread: Optional[IOSHWMonitorThread] = None
        self.ios_analyzer = FPSAnalyzer(window_size=120, refresh_rate=60)
        self._ios_history_times = []
        self._ios_history_fps = []
        self._ios_history_avg_fps = []
        self._ios_history_stats = []  # 完整统计记录（用于导出）
        self._ios_hw_history_times = []
        self._ios_hw_history_cpu_usage = []
        self._ios_hw_history_mem = []
        self._ios_hw_history_gpu = []
        self._ios_hw_curves = {}
        self._ios_hw_plot_start_time = 0.0
        self._ios_test_start_time = 0
        self._ios_hw_start_dt = None
        self._ios_fps_test_start_dt = None
        self._ios_hw_monitor_start_dt = None
        # iOS 历史记录（最近 5 次）
        self._ios_fps_reports = deque(maxlen=5)
        self._ios_hw_reports = deque(maxlen=5)
        self._ios_load_reports = deque(maxlen=5)   # iOS 负载测试记录
        self._ios_eval_records = deque(maxlen=5)   # iOS 性能评价记录
        # iOS 联动标志
        self._ios_linking_start = False
        self._ios_linking_stop = False

        # 历史数据（用于绘图和导出）
        self.history_times = []
        self.history_fps = []
        self.history_avg_fps = []
        self.history_stats = []  # 完整统计记录

        # 硬件监测页面历史数据
        self._hw_history_times = []
        self._hw_history_cpu = {}   # {cluster_label: [freqs]}
        self._hw_history_gpu = []
        self._hw_history_cpu_usage = []
        self._hw_history_mem_usage = []
        self._hw_history_temp = []
        self._hw_history_power = []

        # 历史记录（最近 5 次）
        self._fps_reports = deque(maxlen=5)   # 帧率报告列表
        self._hw_reports = deque(maxlen=5)    # 硬件监测报告列表
        self._load_reports = deque(maxlen=5)  # 负载测试记录列表
        self._eval_records = deque(maxlen=5)  # 性能评价记录列表
        # 监测/测试开始时间戳，用于计算时长
        self._fps_test_start_dt = None
        self._hw_monitor_start_dt = None
        # 联动启动标志：防止 _start_test 与 _start_hw_monitor 互相递归调用
        self._linking_start = False
        # 联动停止标志：防止 _stop_test 与 _stop_hw_monitor 互相递归调用
        self._linking_stop = False

        # ===== 数据库 =====
        self._db = DatabaseManager()
        self._db_session_id = None        # 当前FPS测试会话ID
        self._db_hw_session_id = None     # 当前硬件监测会话ID
        self._db_load_session_id = None   # 当前负载测试会话ID
        self._db_device_ids = {}          # {device_serial: device_pk} 缓存

        try:
            # 先设置 APP 图标（窗口标题栏、Dock、Alt+Tab、Tab 页）
            self._app_icon = _app_icon()
            if self._app_icon is not None:
                self.setWindowIcon(self._app_icon)
                if QApplication.instance():
                    QApplication.instance().setWindowIcon(self._app_icon)
                _logger.info("APP 图标已设置")
        except Exception as e:
            log_exception(e, "设置 APP 图标失败")

        try:
            self._apply_light_theme()
            self._init_ui()
            self._setup_plot_style()
            self._add_help_menu()
        except Exception as e:
            log_exception(e, "初始化 UI 失败")
        try:
            self._refresh_devices()
        except Exception as e:
            log_exception(e, "刷新设备(启动)失败")
        _logger.info("MainWindow.__init__(): 构造完成")

    # ============================================================
    # 国际化：翻译 / 切换 / 持久化
    # ============================================================
    def _tr(self, key: str) -> str:
        """按当前语言取翻译，缺失时回落到中文原文"""
        table = _TRANSLATIONS.get(self._current_lang, _FALLBACK_ZH)
        val = table.get(key)
        if val is None:
            val = _FALLBACK_ZH.get(key, key)
        return val

    def _apply_language(self, lang_code: str):
        """切换到指定语言并立即刷新欢迎页 / 设备选择页 / 窗口标题 / 帮助菜单 / Tab 文本"""
        if lang_code == self._current_lang:
            return
        if lang_code not in _TRANSLATIONS:
            return
        self._current_lang = lang_code
        # 持久化到 QSettings
        try:
            self._lang_settings.setValue("ui_language", lang_code)
            self._lang_settings.sync()
        except Exception as e:
            log_exception(e, "保存语言设置失败")

        refs = self._i18n_refs

        # ---- 窗口标题 ----
        self.setWindowTitle(self._tr("app_title"))

        # ---- 欢迎页 ----
        if "welcome_title" in refs:
            refs["welcome_title"].setText(self._tr("welcome_title"))
        if "welcome_subtitle" in refs:
            refs["welcome_subtitle"].setText(self._tr("welcome_subtitle"))
        if "welcome_features" in refs:
            refs["welcome_features"].setText(self._tr("welcome_features"))
        if "welcome_start" in refs:
            refs["welcome_start"].setText(self._tr("welcome_start"))
        if "lang_label" in refs:
            refs["lang_label"].setText(self._tr("lang_label"))

        # ---- 设备选择页 ----
        if "select_title" in refs:
            refs["select_title"].setText(self._tr("select_device_title"))
        if "select_back_home" in refs:
            refs["select_back_home"].setText(self._tr("select_back_home"))
        if "android_sub" in refs:
            refs["android_sub"].setText(self._tr("android_card_sub"))
        if "ios_sub" in refs:
            refs["ios_sub"].setText(self._tr("ios_card_sub"))
        if "prog_title" in refs:
            refs["prog_title"].setText(self._tr("init_progress_title"))
        if "prog_sub" in refs:
            refs["prog_sub"].setText(self._tr("init_progress_sub"))

        # ---- 帮助菜单 ----
        if "help_menu" in refs:
            refs["help_menu"].setTitle(self._tr("help_menu"))
        if "act_view_log" in refs:
            refs["act_view_log"].setText(self._tr("help_view_log"))
        if "act_open_log_dir" in refs:
            refs["act_open_log_dir"].setText(self._tr("help_open_log_dir"))
        if "act_reveal_log" in refs:
            refs["act_reveal_log"].setText(self._tr("help_reveal_log"))
        if "act_about" in refs:
            refs["act_about"].setText(self._tr("help_about"))

        # ---- Android Tab ----
        tw = getattr(self, "tab_widget", None)
        if tw is not None:
            tab_keys_map = [
                (0, "tab_fps"),
                (1, "tab_hw"),
                (2, "tab_history"),
                (3, "tab_device_info"),
                (4, "tab_load_test"),
            ]
            for idx, key in tab_keys_map:
                if idx < tw.count():
                    tw.setTabText(idx, self._tr(key))

        # ---- iOS Tab ----
        ios_tw = getattr(self, "ios_tab_widget", None)
        if ios_tw is not None:
            ios_tab_keys_map = [
                (0, "tab_fps"),
                (1, "tab_hw"),
                (2, "tab_history"),
                (3, "tab_device_info"),
                (4, "tab_load_test"),
            ]
            for idx, key in ios_tab_keys_map:
                if idx < ios_tw.count():
                    ios_tw.setTabText(idx, self._tr(key))

        # ---- 通用刷新：所有未单独处理的 _i18n_refs 条目 ----
        _already_handled = {
            "welcome_title", "welcome_subtitle", "welcome_features",
            "welcome_start", "lang_label", "select_title", "select_back_home",
            "android_sub", "ios_sub", "prog_title", "prog_sub",
            "help_menu", "act_view_log", "act_open_log_dir", "act_reveal_log", "act_about",
        }
        _key_map = {
            "android_back_btn": "btn_back_select",
            "ios_back_btn": "btn_back_select",
            "contact_back_btn": "btn_back_history",
            "contact_title": "grp_contact_title",
            "contact_desc": "lbl_contact_desc",
            "contact_copy_btn": "btn_copy",
            "contact_mailto_btn": "btn_open_mail",
            "contact_tip": "lbl_contact_tip",
            "grp_hist_stats_data": "grp_stats_data",
            "grp_hist_time_series": "grp_time_series",
            "grp_hist_fps_history": "grp_fps_history",
            "grp_hist_hw_history": "grp_hw_history",
            "grp_hist_detail_summary": "grp_detail_summary",
            "hist_lbl_tip": "lbl_history_tip",
            "hist_btn_export_csv": "btn_export_csv",
            "hist_btn_contact": "btn_contact_report",
            "lbl_info_select_device": "lbl_select_device",
            "info_btn_refresh_device": "btn_refresh_device",
            "info_btn_get_info": "btn_get_info",
            "grp_info_device_info": "grp_device_info",
            "hw_lbl_monitor_device": "lbl_monitor_device",
            "hw_lbl_interval_short": "lbl_interval_short",
            "hw_btn_refresh_device": "btn_refresh_device",
            "hw_btn_start_monitor": "btn_start_monitor",
            "hw_btn_stop_monitor": "btn_stop_monitor",
            "hw_btn_clear": "btn_clear",
            "hw_btn_export": "btn_export",
            "hw_lbl_status": "lbl_status",
            "hw_grp_prime": "grp_prime",
            "hw_lbl_prime_max": "lbl_prime_max",
            "hw_lbl_prime_cores": "lbl_prime_cores",
            "hw_grp_cpu_clusters": "grp_cpu_clusters",
            "hw_grp_cpu_stats": "grp_cpu_temp_usage",
            "hw_lbl_cpu_temp": "lbl_cpu_temp",
            "hw_grp_gpu_freq": "grp_gpu_freq",
            "hw_lbl_gpu_max": "lbl_gpu_max",
            "hw_grp_gpu_load": "grp_gpu_load",
            "hw_grp_mem_gpu": "grp_mem_gpu",
            "hw_lbl_gpu_mem": "lbl_gpu_mem",
            "ios_grp_device_settings": "grp_device_settings",
            "ios_lbl_device": "lbl_device",
            "ios_btn_refresh_device": "btn_refresh_device",
            "ios_lbl_app": "lbl_app",
            "ios_btn_list_apps": "btn_list_apps",
            "ios_lbl_refresh_rate": "lbl_refresh_rate",
            "ios_lbl_interval": "lbl_interval",
            "ios_lbl_device_info": "lbl_device_info",
            "ios_btn_start_test": "btn_start_test",
            "ios_btn_stop_test": "btn_stop_test",
            "ios_btn_export": "btn_export",
            "ios_btn_clear": "btn_clear",
            "ios_lbl_duration": "lbl_duration",
            "ios_grp_realtime_stats": "grp_realtime_stats",
            "ios_grp_jank_indicator": "grp_jank_indicator",
            "ios_lbl_jank_hint": "lbl_jank_hint",
            "ios_grp_log_output": "grp_log_output",
            "ios_lbl_monitor_device": "lbl_monitor_device",
            "ios_lbl_interval_short": "lbl_interval_short",
            "ios_hw_btn_refresh_device": "btn_refresh_device",
            "ios_hw_btn_start_monitor": "btn_start_monitor",
            "ios_hw_btn_stop_monitor": "btn_stop_monitor",
            "ios_hw_btn_clear": "btn_clear",
            "ios_hw_btn_export": "btn_export",
            "ios_lbl_status": "lbl_status",
            "ios_grp_cpu_usage": "grp_cpu_usage",
            "ios_lbl_core_count": "lbl_core_count",
            "ios_grp_gpu_usage": "grp_gpu_usage",
            "ios_lbl_renderer": "lbl_renderer",
            "ios_lbl_tiler": "lbl_tiler",
            "ios_grp_memory": "grp_memory",
            "ios_lbl_select_device": "lbl_select_device",
            "ios_info_btn_refresh_device": "btn_refresh_device",
            "ios_info_btn_get_info": "btn_get_info",
            "ios_grp_device_info": "grp_device_info",
            "ios_lbl_history_tip": "lbl_history_tip",
            "ios_btn_export_csv": "btn_export_csv",
            "ios_btn_contact": "btn_contact",
            "ios_grp_fps_history": "grp_fps_history",
            "ios_grp_hw_history": "grp_hw_history",
            "ios_grp_detail_summary": "grp_detail_summary",
            "android_load_btn_refresh": "btn_refresh_device",
            "ios_load_btn_refresh": "btn_refresh_device",
            "android_load_lbl_device": "lbl_load_device",
            "ios_load_lbl_device": "lbl_load_device",
            "android_load_btn_confirm": "btn_load_confirm_start",
            "ios_load_btn_confirm": "btn_load_confirm_start",
            "android_load_btn_stop": "btn_stop_load",
            "ios_load_btn_stop": "btn_stop_load",
            "android_load_btn_export": "btn_export_load",
            "ios_load_btn_export": "btn_export_load",
            "android_load_principle_title": "load_principle_title",
            "ios_load_principle_title": "load_principle_title",
            "android_load_principle_body": "load_principle_body",
            "ios_load_principle_body": "load_principle_body",
            "android_load_risk_title": "load_risk_title",
            "ios_load_risk_title": "load_risk_title",
            "android_load_risk_body": "load_risk_body",
            "ios_load_risk_body": "load_risk_body",
            "android_load_running_title": "load_running_title",
            "ios_load_running_title": "load_running_title",
            "android_load_running_hint": "load_running_hint_anim",
            "ios_load_running_hint": "load_running_hint_anim",
            "android_load_result_title": "load_result_title",
            "ios_load_result_title": "load_result_title",
            "android_load_lbl_conclusion": "lbl_conclusion",
            "ios_load_lbl_conclusion": "lbl_conclusion",
            "android_load_lbl_waiting": "lbl_waiting",
            "ios_load_lbl_waiting": "lbl_waiting",
        }
        for ref_key, widget in list(refs.items()):
            if ref_key in _already_handled:
                continue
            tr_key = _key_map.get(ref_key, ref_key)
            text = self._tr(tr_key)
            try:
                if hasattr(widget, "setTitle"):
                    widget.setTitle(text)
                elif hasattr(widget, "setText"):
                    widget.setText(text)
            except Exception:
                pass

        # ---- 语言切换后：如果已有负载测试结果，重新刷新表头和指标行名 ----
        for prefix in ("android_", "ios_"):
            state_attr = f"_{prefix}load_state"
            if not hasattr(self, state_attr):
                continue
            state = getattr(self, state_attr, None)
            if not state:
                continue
            # 表头
            tbl = state.get("cpu_table")
            if tbl is not None:
                try:
                    tbl.setHorizontalHeaderLabels([
                        self._tr("tbl_load_cpu_stats"),
                        self._tr("tbl_load_col_samples"),
                        self._tr("tbl_load_col_avg"),
                        self._tr("tbl_load_col_max"),
                        self._tr("tbl_load_col_min"),
                    ])
                except Exception:
                    pass
            # 若已有结果 summary，重新按当前语言填充指标行
            summary = state.get("last_summary")
            if summary is not None and tbl is not None:
                try:
                    st = summary.get("stats", {}) or {}
                    _metric_keys = [
                        ("cpu", "load_metric_cpu"),
                        ("gpu", "load_metric_gpu"),
                        ("mem", "load_metric_mem"),
                        ("cpu_temp", "load_metric_cpu_temp"),
                    ]
                    rows_to_set = []
                    for mkey, tr_key in _metric_keys:
                        s = st.get(mkey) or {}
                        if not s:
                            continue
                        mname = self._tr(tr_key)
                        rows_to_set.append((
                            mname,
                            str(s.get("n", "-")),
                            f"{s['avg']:.1f}" if isinstance(s.get("avg"), (int, float)) else "-",
                            f"{s['max']:.1f}" if isinstance(s.get("max"), (int, float)) else "-",
                            f"{s['min']:.1f}" if isinstance(s.get("min"), (int, float)) else "-",
                        ))
                    tbl.setRowCount(len(rows_to_set))
                    for r, row in enumerate(rows_to_set):
                        for cidx, v in enumerate(row):
                            it = QTableWidgetItem(str(v))
                            it.setTextAlignment(Qt.AlignCenter)
                            tbl.setItem(r, cidx, it)
                except Exception:
                    pass
            # 曲线 label
            try:
                pl_cpu = state.get("result_cpu_plot")
                pl_mem = state.get("result_mem_plot")
                pl_temp = state.get("result_temp_plot")
                if pl_cpu is not None:
                    pl_cpu.setLabel("left", self._tr("chart_load_cpu_usage"), color="#ff6b6b")
                    pl_cpu.setLabel("bottom", self._tr("chart_load_temp_bottom"))
                if pl_mem is not None:
                    pl_mem.setLabel("left", self._tr("chart_load_mem_usage"), color="#a78bfa")
                    pl_mem.setLabel("bottom", self._tr("chart_load_temp_bottom"))
                if pl_temp is not None:
                    pl_temp.setLabel("left", self._tr("chart_load_temp_result"), color="#fb923c")
                    pl_temp.setLabel("bottom", self._tr("chart_load_temp_bottom"))
            except Exception:
                pass
            # 语言切换后：重新生成结论文本（如果有 last_summary）
            if summary is not None:
                try:
                    summary["lines"] = self._build_load_conclusion(summary)
                    cc_label = state.get("conclusion_label")
                    if cc_label is None:
                        cc_label = state.get("cc_text")
                    if cc_label is not None:
                        lines = summary.get("lines", []) or []
                        cc_label.setText("\n".join(lines) if lines else "-")
                    # 重新填充摘要卡片（评级/时长等翻译）
                    rating_key = summary.get("rating_key") or summary.get("rating") or "good"
                    rating_label = self._rating_to_label(rating_key)
                    rv = state.get("rating_value")
                    if rv is not None:
                        rv.setText(rating_label)
                        rating_color = {"good": "#16a34a", "warn": "#f59e0b", "bad": "#dc2626"}.get(rating_key, "#0277BD")
                        rv.setStyleSheet(f"color: {rating_color}; font-size: 15px; font-weight: 700;")
                    rel = state.get("result_elapsed_lbl")
                    if rel is not None:
                        elapsed = int(state.get("elapsed_sec") or summary.get("duration_sec") or 0)
                        hrs2, rem2 = divmod(elapsed, 3600)
                        mins2, secs2 = divmod(rem2, 60)
                        rel.setText(f"⏱ {self._tr('lbl_duration_short')} {hrs2:02d}:{mins2:02d}:{secs2:02d}")
                except Exception:
                    pass

    def _apply_tab_icons(self, tab_widget: QTabWidget):
        """给 QTabWidget 的每个 Tab 在左侧添加小尺寸 APP logo（醒目但不抢空间）"""
        try:
            ico = getattr(self, "_app_icon", None)
            if ico is None:
                ico = _app_icon()
            if ico is None or ico.isNull():
                return
            count = tab_widget.count()
            for i in range(count):
                # 20x20 的尺寸，放在 Tab 文本左侧
                tab_widget.setTabIcon(i, ico)
                tab_widget.setIconSize(QSize(20, 20))
        except Exception as e:
            _logger.warning("设置 Tab 图标失败: %s", e)

    def _add_help_menu(self):
        """菜单栏增加 帮助 → 查看日志 / 打开日志目录 / 查看版本"""
        try:
            menubar = self.menuBar()
            help_menu = menubar.addMenu(self._tr("help_menu"))
            self._i18n_refs["help_menu"] = help_menu

            act_view_log = help_menu.addAction(self._tr("help_view_log"))
            act_view_log.setShortcut("Ctrl+Shift+L")
            act_view_log.triggered.connect(self._view_log_content)
            self._i18n_refs["act_view_log"] = act_view_log

            act_log = help_menu.addAction(self._tr("help_open_log_dir"))
            act_log.setShortcut("Ctrl+L")
            act_log.triggered.connect(self._open_log_dir)
            self._i18n_refs["act_open_log_dir"] = act_log

            act_reveal = help_menu.addAction(self._tr("help_reveal_log"))
            act_reveal.triggered.connect(self._reveal_current_log_file)
            self._i18n_refs["act_reveal_log"] = act_reveal

            help_menu.addSeparator()
            act_about = help_menu.addAction(self._tr("help_about"))
            act_about.triggered.connect(self._show_about_dialog)
            self._i18n_refs["act_about"] = act_about
        except Exception as e:
            log_exception(e, "添加帮助菜单失败")

    def _view_log_content(self):
        """在弹出的只读对话框中显示当前日志文件内容（尾部 200 行）"""
        from app_logger import get_log_file_path
        path = get_log_file_path()
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = lines[-200:] if len(lines) > 200 else lines
            content = "".join(tail)
        except Exception as e:
            log_exception(e, "读取日志文件失败")
            content = f"无法读取日志文件:\n{e}\n\n路径: {path}"

        dlg = QDialog(self)
        dlg.setWindowTitle(self._tr("dlg_log_content_title").format(name=os.path.basename(path)))
        dlg.resize(900, 600)
        layout = QVBoxLayout(dlg)
        # 路径提示
        path_label = QLabel(f"📁 {path}")
        path_label.setStyleSheet(f"color: {self._fg_muted()}; font-size: 12px;")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)
        # 日志内容
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(content)
        font = QFont("Menlo", 10)
        text_edit.setFont(font)
        layout.addWidget(text_edit)
        # 按钮
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton(self._tr("btn_refresh"))
        refresh_btn.clicked.connect(lambda: (
            text_edit.setPlainText(
                open(path, "r", encoding="utf-8", errors="replace").read()[-8000:]
            )
        ))
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        close_btn = QPushButton(self._tr("btn_close"))
        close_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        dlg.exec_()

    def _open_log_dir(self):
        log_dir = get_log_dir()
        try:
            import subprocess
            subprocess.Popen(["open", log_dir])
        except Exception as e:
            log_exception(e, "打开日志目录失败")
            QMessageBox.information(
                self, self._tr("msg_log_dir"),
                self._tr("msg_log_dir_body").format(path=log_dir)
            )

    def _reveal_current_log_file(self):
        from app_logger import get_log_file_path
        path = get_log_file_path()
        try:
            import subprocess
            subprocess.Popen(["open", "-R", path])
        except Exception as e:
            log_exception(e, "显示日志文件失败")
            QMessageBox.information(self, self._tr("msg_log_file"), self._tr("msg_log_file_body").format(path=path))

    def _show_about_dialog(self):
        from app_logger import get_log_file_path
        QMessageBox.information(
            self, self._tr("msg_about_title"),
            self._tr("msg_about_body") + self._tr("msg_about_log_dir").format(path=get_log_dir())
        )

    def _init_ui(self):
        """初始化UI"""
        # 使用 QStackedWidget 实现多级页面导航
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        # ===== Page 0: 星穹视界开屏动画页面 =====
        self._init_splash_page()

        # ===== Page 1: 联系作者页面 =====
        self._init_contact_page()

        # ===== Page 2: 欢迎页面 =====
        self._init_welcome_page()

        # ===== Page 3: 设备类型选择页面 =====
        self._init_device_select_page()

        # ===== Page 4: 主测试页面 (QTabWidget) =====
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("QTabWidget { background-color: #f8fafc; }")
        # 返回按钮（放在 Tab 栏右上角，透明风格与首页一致）
        android_back_btn = QPushButton(self._tr("btn_back_select"))
        self._i18n_refs["android_back_btn"] = android_back_btn
        android_back_btn.setFixedSize(140, 32)
        android_back_btn.setCursor(Qt.PointingHandCursor)
        android_back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748b;
                border: none;
                border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(148, 163, 184, 25);
                color: #1e293b;
            }
        """)
        android_back_btn.clicked.connect(lambda: self.central_stack.setCurrentIndex(3))
        self.tab_widget.setCornerWidget(android_back_btn, Qt.TopRightCorner)
        self.central_stack.addWidget(self.tab_widget)  # index = 4

        # ===== Tab 1: 帧率测试页面 =====
        tab1 = QWidget()
        tab1.setStyleSheet("background-color: #f8fafc;")
        main_layout = QVBoxLayout(tab1)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        self.tab_widget.addTab(tab1, self._tr("tab_fps"))

        # ===== 顶部：设备和应用选择 =====
        top_group = QGroupBox(self._tr("grp_device_settings"))
        self._i18n_refs["grp_device_settings"] = top_group
        top_layout = QGridLayout(top_group)

        # 设备选择
        _lbl_device = QLabel(self._tr("lbl_device"))
        self._i18n_refs["lbl_device"] = _lbl_device
        top_layout.addWidget(_lbl_device, 0, 0)
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        top_layout.addWidget(self.device_combo, 0, 1)

        self.refresh_btn = QPushButton(self._tr("btn_refresh_device"))
        self._i18n_refs["btn_refresh_device"] = self.refresh_btn
        self.refresh_btn.clicked.connect(self._refresh_devices)
        top_layout.addWidget(self.refresh_btn, 0, 2)

        # 应用选择
        _lbl_app = QLabel(self._tr("lbl_app"))
        self._i18n_refs["lbl_app"] = _lbl_app
        top_layout.addWidget(_lbl_app, 0, 3)
        self.package_combo = QComboBox()
        self.package_combo.setEditable(True)
        self.package_combo.setMinimumWidth(350)
        top_layout.addWidget(self.package_combo, 0, 4)

        self.current_app_btn = QPushButton(self._tr("btn_get_app"))
        self._i18n_refs["btn_get_app"] = self.current_app_btn
        self.current_app_btn.clicked.connect(self._get_current_app)
        top_layout.addWidget(self.current_app_btn, 0, 5)

        self.refresh_pkg_btn = QPushButton(self._tr("btn_list_apps"))
        self._i18n_refs["btn_list_apps"] = self.refresh_pkg_btn
        self.refresh_pkg_btn.clicked.connect(self._refresh_packages)
        top_layout.addWidget(self.refresh_pkg_btn, 0, 6)

        # 刷新率设置
        _lbl_refresh_rate = QLabel(self._tr("lbl_refresh_rate"))
        self._i18n_refs["lbl_refresh_rate"] = _lbl_refresh_rate
        top_layout.addWidget(_lbl_refresh_rate, 1, 0)
        self.refresh_rate_combo = QComboBox()
        for rate in [60, 90, 120, 144, 165]:
            self.refresh_rate_combo.addItem(f"{rate} Hz", rate)
        self.refresh_rate_combo.setCurrentIndex(0)
        self.refresh_rate_combo.currentIndexChanged.connect(self._on_refresh_rate_changed)
        top_layout.addWidget(self.refresh_rate_combo, 1, 1)

        # 采集间隔
        _lbl_interval = QLabel(self._tr("lbl_interval"))
        self._i18n_refs["lbl_interval"] = _lbl_interval
        top_layout.addWidget(_lbl_interval, 1, 2)
        self.interval_combo = QComboBox()
        for iv in [0.1, 0.3, 0.5, 1.0, 2.0]:
            self.interval_combo.addItem(f"{iv}s", iv)
        self.interval_combo.setCurrentIndex(3)  # 默认 1.0s
        top_layout.addWidget(self.interval_combo, 1, 3)

        # 测试信息
        self.device_info_label = QLabel(self._tr("lbl_device_info"))
        self._i18n_refs["lbl_device_info"] = self.device_info_label
        self.device_info_label.setStyleSheet(f"color: {self._fg_muted()};")
        top_layout.addWidget(self.device_info_label, 1, 4, 1, 3)

        main_layout.addWidget(top_group)

        # ===== 中部：控制按钮与状态 =====
        ctrl_layout = QHBoxLayout()

        self.start_btn = QPushButton(self._tr("btn_start_test"))
        self._i18n_refs["btn_start_test"] = self.start_btn
        self.start_btn.setMinimumHeight(45)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 24px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: rgba(33,150,243,80); color: rgba(226,232,240,120); }
        """)
        self.start_btn.clicked.connect(self._start_test)
        ctrl_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton(self._tr("btn_stop_test"))
        self._i18n_refs["btn_stop_test"] = self.stop_btn
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 24px;
            }
            QPushButton:hover { background-color: #D32F2F; }
            QPushButton:disabled { background-color: rgba(244,67,54,80); color: rgba(226,232,240,120); }
        """)
        self.stop_btn.clicked.connect(self._stop_test)
        ctrl_layout.addWidget(self.stop_btn)

        self.export_btn = QPushButton(self._tr("btn_export"))
        self._i18n_refs["btn_export"] = self.export_btn
        self.export_btn.setMinimumHeight(45)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.export_btn.clicked.connect(self._show_fps_export_menu)
        ctrl_layout.addWidget(self.export_btn)

        self.clear_btn = QPushButton(self._tr("btn_clear"))
        self._i18n_refs["btn_clear"] = self.clear_btn
        self.clear_btn.setMinimumHeight(45)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 14px;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.clear_btn.clicked.connect(self._clear_data)
        ctrl_layout.addWidget(self.clear_btn)

        # 测试时长显示
        self.duration_label = QLabel(self._tr("lbl_duration"))
        self._i18n_refs["lbl_duration"] = self.duration_label
        self.duration_label.setFont(QFont("Menlo", 16, QFont.Bold))
        self.duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ctrl_layout.addWidget(self.duration_label, 1)

        main_layout.addLayout(ctrl_layout)

        # ===== 主区域：图表 + 统计 + 日志 =====
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：图表区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # FPS实时曲线
        self.fps_plot = PlotWidget(title=self._tr("chart_fps_title"))
        self._i18n_refs["fps_plot"] = self.fps_plot
        # 实时曲线：高对比配色（灰底）— 蓝绿色实线 = 即时帧率；暖橙色虚线 = 平均帧率
        self._apply_realtime_plot_styling(self.fps_plot, y_left=self._tr("chart_fps_left"),
                                          y_left_color="#38bdf8", x_label=self._tr("chart_fps_bottom"))
        self.fps_plot.setTitle(self._tr("chart_fps_title"), color="#f8fafc", size="12pt")
        self.fps_plot.addLegend()
        self.fps_curve = self.fps_plot.plot(pen=mkPen('#38bdf8', width=3), name=self._tr("curve_instant_fps"))
        self.avg_curve = self.fps_plot.plot(pen=mkPen('#fb923c', width=2.6, style=Qt.DashLine), name=self._tr("curve_avg_fps"))
        left_layout.addWidget(self.fps_plot, stretch=2)

        # 帧时间分布柱状图
        self.frame_plot = PlotWidget(title=self._tr("chart_frame_title"))
        self._i18n_refs["frame_plot"] = self.frame_plot
        self._apply_realtime_plot_styling(self.frame_plot, y_left=self._tr("chart_frame_left"),
                                          y_left_color="#4ade80", x_label=self._tr("chart_frame_bottom"))
        self.frame_plot.setTitle(self._tr("chart_frame_title"), color="#f8fafc", size="12pt")
        self.frame_bar = pg.BarGraphItem(x=[], height=[], width=0.8, brush='#4ade80', pen=pg.mkPen("#22c55e", width=2))
        self.frame_plot.addItem(self.frame_bar)
        # 添加阈值线（60fps=16.67ms）
        self.threshold_line = pg.InfiniteLine(
            pos=16.67, angle=0, pen=mkPen('#f43f5e', width=2.6, style=Qt.DashLine),
            label=self._tr("lbl_jank_threshold"), labelOpts={'color': '#fecdd3', 'position': 0.8}
        )
        self.frame_plot.addItem(self.threshold_line)
        left_layout.addWidget(self.frame_plot, stretch=1)

        splitter.addWidget(left_widget)

        # 右侧：统计数据 + 日志
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 统计面板
        stats_group = QGroupBox(self._tr("grp_realtime_stats"))
        self._i18n_refs["grp_realtime_stats"] = stats_group
        stats_grid = QGridLayout(stats_group)

        self._stat_labels = {}
        self._stat_title_labels = {}
        stat_items = [
            (self._tr("stat_current_fps"), "stat_current_fps", "fps", "#2196F3"),
            (self._tr("stat_avg_fps"), "stat_avg_fps", "avg_fps", "#4CAF50"),
            (self._tr("stat_min_fps"), "stat_min_fps", "min_fps", "#F44336"),
            (self._tr("stat_max_fps"), "stat_max_fps", "max_fps", "#9C27B0"),
            (self._tr("stat_low_1"), "stat_low_1", "low_1", "#FF6F00"),
            (self._tr("stat_low_01"), "stat_low_01", "low_01", "#D84315"),
            (self._tr("stat_std_fps"), "stat_std_fps", "std_fps", "#FF9800"),
            (self._tr("stat_jank_count"), "stat_jank_count", "jank_count", "#F44336"),
            (self._tr("stat_jank_rate"), "stat_jank_rate", "jank_rate", "#FF5722"),
            (self._tr("stat_p95"), "stat_p95", "p95", "#795548"),
            (self._tr("stat_p99"), "stat_p99", "p99", "#607D8B"),
        ]

        for i, (label_text, i18n_key, key, color) in enumerate(stat_items):
            row = i // 2
            col = (i % 2) * 2
            lbl_title = QLabel(f"{label_text}:")
            lbl_title.setStyleSheet(f"font-size: 13px; color: {self._fg_muted()};")
            stats_grid.addWidget(lbl_title, row, col)
            self._stat_title_labels[i18n_key] = lbl_title

            lbl_value = QLabel("--")
            lbl_value.setFont(QFont("Menlo", 16, QFont.Bold))
            lbl_value.setStyleSheet(f"color: {color};")
            lbl_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            stats_grid.addWidget(lbl_value, row, col + 1)
            self._stat_labels[key] = lbl_value

        right_layout.addWidget(stats_group)

        # 进度条（卡顿率可视化）
        jank_group = QGroupBox(self._tr("grp_jank_indicator"))
        self._i18n_refs["grp_jank_indicator"] = jank_group
        jank_layout = QVBoxLayout(jank_group)
        self.jank_bar = QProgressBar()
        self.jank_bar.setObjectName("jankBar")
        self.jank_bar.setRange(0, 100)
        self.jank_bar.setValue(0)
        self.jank_bar.setFormat(self._tr("fmt_jank_rate_zero"))
        self.jank_bar.setTextVisible(True)
        jank_layout.addWidget(self.jank_bar)
        jank_hint = QLabel(self._tr("lbl_jank_hint"))
        self._i18n_refs["lbl_jank_hint"] = jank_hint
        jank_hint.setStyleSheet(f"font-size: 12px; color: {self._fg_muted()};")
        jank_hint.setAlignment(Qt.AlignCenter)
        jank_layout.addWidget(jank_hint)
        right_layout.addWidget(jank_group)

        # 日志窗口
        log_group = QGroupBox(self._tr("grp_log_output"))
        self._i18n_refs["grp_log_output"] = log_group
        log_group.setStyleSheet(f"""
            QGroupBox {{ font-size: 14px; font-weight: bold; color: #F57F17;
                        border: 2px solid #FF8F00; border-radius: 8px; margin-top: 16px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Menlo", 11))
        self.log_text.setStyleSheet(f"background-color: {self._bg_base()}; color: #1e293b; border: 1px solid rgba(100,116,139,80); border-radius: 6px;")
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(log_group, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([900, 560])

        main_layout.addWidget(splitter, stretch=1)

        # 测试计时器
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self._update_duration)
        self.test_start_time = 0

        # ===== Tab 2: CPU/GPU 监测页面 =====
        self._init_hw_monitor_tab()

        # ===== Tab 3: CSV 历史记录页面 =====
        self._init_history_tab()

        # ===== Tab 4: 手机信息页面 =====
        self._init_device_info_tab()

        # ===== Tab 5: 负载测试（安卓）=====
        self._init_load_test_tab(platform="android")

        # 应用 Tab 图标
        self._apply_tab_icons(self.tab_widget)

        # ===== Page 5: iOS 测试页面 (独立 QTabWidget) =====
        self._init_ios_test_page()

        # ===== Tab 5: 负载测试（iOS）=====
        self._init_load_test_tab(platform="ios")

        # 应用 iOS Tab 图标
        self._apply_tab_icons(self.ios_tab_widget)

        # ===== 开屏动画完成：进入欢迎页（首页）并弹出强制免责声明 =====
        self._splash_canvas.progress_complete.connect(self._enter_welcome_with_disclaimer)

    def _init_splash_page(self):
        """构建星穹视界开屏动画页面 (Page 0)

        设计风格：深邃星空背景 + 闪烁星星动画 + 星环 LOGO + 渐现标题
        占满整个主窗口，开屏阶段最大化显示。
        """
        page = QWidget()
        page.setStyleSheet("background-color: #04070f;")
        page_layout = QVBoxLayout(page)
        # 无任何边距/间距 + 取消居中对齐（让画布铺满）
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        page_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # 星空画布（自定义绘制，Expanding 尺寸策略随窗口拉伸）
        self._splash_canvas = _StarField(self)
        self._splash_canvas.setMinimumSize(800, 600)
        try:
            from PyQt5.QtWidgets import QSizePolicy
            self._splash_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        except Exception:
            pass
        page_layout.addWidget(self._splash_canvas, stretch=1)

        self.central_stack.addWidget(page)  # index = 0

    def _init_contact_page(self):
        """构建联系作者页面 (Page 1)

        显示作者邮箱，支持一键复制和邮件客户端跳转
        """
        page = QWidget()
        page.setStyleSheet("background-color: #f8fafc;")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(40, 30, 40, 30)
        page_layout.setSpacing(16)

        # 顶部返回栏
        top_bar = QHBoxLayout()
        self._contact_back_btn = QPushButton(self._tr("btn_back_history"))
        self._i18n_refs["contact_back_btn"] = self._contact_back_btn
        self._contact_back_btn.setFixedSize(160, 36)
        self._contact_back_btn.setCursor(Qt.PointingHandCursor)
        self._contact_back_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #64748b;
                          border: none; border-radius: 18px; font-size: 13px; }
            QPushButton:hover { background-color: rgba(148, 163, 184, 25); color: #1e293b; }
        """)
        self._contact_back_btn.clicked.connect(self._contact_go_back)
        top_bar.addWidget(self._contact_back_btn)
        top_bar.addStretch()
        page_layout.addLayout(top_bar)

        # 联系卡片
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background-color: white; border: 1px solid #e2e8f0;
                     border-radius: 16px; }
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(48, 40, 48, 40)
        card_lay.setSpacing(20)
        card_lay.setAlignment(Qt.AlignCenter)

        # 标题
        title = QLabel(self._tr("grp_contact_title"))
        self._i18n_refs["contact_title"] = title
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("PingFang SC", 24, QFont.Bold))
        title.setStyleSheet("color: #0f172a;")
        card_lay.addWidget(title)

        # 说明
        desc = QLabel(self._tr("lbl_contact_desc"))
        self._i18n_refs["contact_desc"] = desc
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setFont(QFont("PingFang SC", 13))
        desc.setStyleSheet("color: #64748b;")
        card_lay.addWidget(desc)

        # 邮箱卡片
        email_frame = QFrame()
        email_frame.setStyleSheet("""
            QFrame { background-color: #f1f5f9; border: 2px solid #e2e8f0;
                     border-radius: 12px; }
        """)
        email_lay = QHBoxLayout(email_frame)
        email_lay.setContentsMargins(24, 16, 24, 16)

        email_icon = QLabel("✉️")
        email_icon.setFont(QFont("", 28))
        email_lay.addWidget(email_icon)

        email_text = QLabel("stardomevision@outlook.com")
        email_text.setFont(QFont("Menlo", 20, QFont.Bold))
        email_text.setStyleSheet("color: #0277BD;")
        email_text.setCursor(Qt.PointingHandCursor)
        email_text.mousePressEvent = lambda e: self._copy_email_to_clipboard()
        email_lay.addWidget(email_text, stretch=1)

        copy_btn = QPushButton(self._tr("btn_copy"))
        self._i18n_refs["contact_copy_btn"] = copy_btn
        copy_btn.setFixedSize(80, 36)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; font-size: 13px;
                          font-weight: bold; border-radius: 8px; border: none; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        copy_btn.clicked.connect(self._copy_email_to_clipboard)
        email_lay.addWidget(copy_btn)

        card_lay.addWidget(email_frame)

        # 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        mailto_btn = QPushButton(self._tr("btn_open_mail"))
        self._i18n_refs["contact_mailto_btn"] = mailto_btn
        mailto_btn.setMinimumHeight(40)
        mailto_btn.setCursor(Qt.PointingHandCursor)
        mailto_btn.setStyleSheet("""
            QPushButton { background-color: #0f172a; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 10px; border: none; padding: 8px 20px; }
            QPushButton:hover { background-color: #1e293b; }
        """)
        mailto_btn.clicked.connect(self._open_email_client)
        btn_row.addWidget(mailto_btn)

        card_lay.addLayout(btn_row)

        # 提示
        tip = QLabel(self._tr("lbl_contact_tip"))
        self._i18n_refs["contact_tip"] = tip
        tip.setAlignment(Qt.AlignCenter)
        tip.setFont(QFont("PingFang SC", 11))
        tip.setStyleSheet("color: #94a3b8;")
        card_lay.addWidget(tip)

        page_layout.addWidget(card, stretch=1)
        page_layout.addStretch()

        self.central_stack.addWidget(page)  # index = 1

    def _copy_email_to_clipboard(self):
        """复制作者邮箱到剪贴板"""
        QApplication.clipboard().setText("stardomevision@outlook.com")
        QMessageBox.information(self, self._tr("msg_copied"), self._tr("msg_email_copied"))

    def _open_email_client(self):
        """打开邮件客户端"""
        import webbrowser
        webbrowser.open("mailto:stardomevision@outlook.com?subject=星穹视界 问题反馈")

    def _contact_go_back(self):
        """从联系页返回来源页面"""
        self.central_stack.setCurrentIndex(getattr(self, "_contact_source", 4))

    def _navigate_to_contact(self):
        """导航到联系作者页，记录来源"""
        self._contact_source = self.central_stack.currentIndex()
        self.central_stack.setCurrentIndex(1)

    def _enter_welcome_with_disclaimer(self):
        """开屏动画完成：切到欢迎页（首页），从最大化恢复为窗口尺寸，然后弹出强制免责声明"""
        # 若启动时是最大化状态（showMaximized），在进入欢迎页时还原为正常窗口大小
        try:
            from PyQt5.QtCore import Qt
            if self.isMaximized():
                self.showNormal()
                # 再次设置一个合理的初始窗口尺寸（兼容 showMaximized 覆盖了 resize 的情形）
                try:
                    from PyQt5.QtWidgets import QApplication
                    d = QApplication.desktop() if hasattr(QApplication, "desktop") else None
                    ag = d.availableGeometry(self) if d is not None else None
                    if ag is not None:
                        tw, th = 1440, 900
                        if ag.width() < tw + 60:
                            tw = max(1200, ag.width() - 40)
                        if ag.height() < th + 80:
                            th = max(760, ag.height() - 60)
                        self.resize(tw, th)
                        self.move(ag.center().x() - self.width() // 2,
                                  ag.center().y() - self.height() // 2)
                    else:
                        self.resize(1400, 900)
                except Exception:
                    self.resize(1400, 900)
        except Exception:
            pass
        self.central_stack.setCurrentIndex(2)
        # 让首页先完成绘制
        QApplication.processEvents()
        # 立即弹出，无延迟；异常保护防止被 Qt 静默吞掉
        try:
            self._show_disclaimer_dialog()
        except Exception as e:
            log_exception(e, "免责声明弹窗显示失败")
            QMessageBox.critical(self, self._tr("msg_startup_error"), self._tr("msg_disclaimer_failed").format(err=e))

    def _show_disclaimer_dialog(self):
        """弹出强制免责声明对话框（模态，无关闭按钮，仅两个选项）"""
        dlg = QDialog(self)
        dlg.setWindowTitle(self._tr("msg_disclaimer_title"))
        dlg.setMinimumWidth(520)
        # 移除关闭按钮和帮助按钮，防止绕过
        dlg.setWindowFlags(
            dlg.windowFlags()
            & ~Qt.WindowCloseButtonHint
            & ~Qt.WindowContextHelpButtonHint
            | Qt.WindowStaysOnTopHint
        )
        # 重写 reject：ESC 键也视为拒绝退出
        _orig_reject = dlg.reject
        dlg.reject = lambda: (dlg.done(0), QApplication.instance().quit())

        dlg.setStyleSheet("""
            QDialog { background-color: white; }
            QLabel#dlg_title { font-size: 18px; font-weight: bold; color: #0f172a; }
            QLabel#dlg_body { font-size: 13px; color: #475569; line-height: 1.6; }
            QPushButton#btn_agree { background-color: #2196F3; color: white;
                                    font-size: 15px; font-weight: bold;
                                    border-radius: 10px; padding: 10px 30px; border: none; }
            QPushButton#btn_agree:hover { background-color: #1976D2; }
            QPushButton#btn_refuse { background-color: #f1f5f9; color: #64748b;
                                     font-size: 14px;
                                     border-radius: 10px; padding: 10px 30px;
                                     border: 1px solid #e2e8f0; }
            QPushButton#btn_refuse:hover { background-color: #e2e8f0; color: #334155; }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        title = QLabel(self._tr("msg_disclaimer_title"))
        title.setObjectName("dlg_title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        body_text = self._tr("txt_disclaimer")
        body = QLabel(body_text)
        body.setObjectName("dlg_body")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        body.setMinimumHeight(180)
        layout.addWidget(body, stretch=1)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        refuse_btn = QPushButton(self._tr("btn_reject"))
        refuse_btn.setObjectName("btn_refuse")
        refuse_btn.setCursor(Qt.PointingHandCursor)
        refuse_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(refuse_btn)

        agree_btn = QPushButton(self._tr("btn_agree"))
        agree_btn.setObjectName("btn_agree")
        agree_btn.setCursor(Qt.PointingHandCursor)
        agree_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(agree_btn)

        layout.addLayout(btn_row)

        agree_btn.setDefault(True)

        if dlg.exec_() == QDialog.Accepted:
            # 同意：留在欢迎页（首页），用户可点击"开始测试"进入二级菜单
            pass
        else:
            # 拒绝：直接退出应用
            QApplication.instance().quit()

    def _init_welcome_page(self):
        """构建欢迎页面 (Page 2)

        设计风格：深蓝背景 + 居中圆角卡片 + Logo展示 + 渐变按钮
        """
        # 整页背景：浅灰蓝
        page = QWidget()
        page.setStyleSheet("background-color: #f8fafc;")

        # 居中卡片
        card = QFrame(page)
        card.setObjectName("welcome_card")
        card.setMinimumSize(640, 560)
        card.setMaximumSize(720, 640)
        card.setStyleSheet("""
            QFrame#welcome_card {
                background-color: white;
                border: 1px solid rgba(226, 232, 240, 150);
                border-radius: 24px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(60, 50, 60, 50)
        card_layout.setSpacing(20)
        card_layout.setAlignment(Qt.AlignCenter)

        # ===== Logo 图片 =====
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_pixmap = self._app_icon.pixmap(QSize(120, 120)) if self._app_icon else QPixmap(":/resources/logo.png")
        logo_label.setPixmap(logo_pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        card_layout.addWidget(logo_label)

        # ===== 标题 =====
        title = QLabel(self._tr("welcome_title"))
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("PingFang SC", 38, QFont.Bold))
        title.setStyleSheet("color: #0f172a;")
        self._i18n_refs["welcome_title"] = title
        card_layout.addWidget(title)

        # ===== 副标题 =====
        desc = QLabel(self._tr("welcome_subtitle"))
        desc.setAlignment(Qt.AlignCenter)
        desc.setFont(QFont("PingFang SC", 16))
        desc.setStyleSheet("color: #64748b;")
        self._i18n_refs["welcome_subtitle"] = desc
        card_layout.addWidget(desc)

        # ===== 功能描述 =====
        features = QLabel(self._tr("welcome_features"))
        features.setAlignment(Qt.AlignCenter)
        features.setFont(QFont("PingFang SC", 13))
        features.setStyleSheet("color: #94a3b8; letter-spacing: 2px;")
        self._i18n_refs["welcome_features"] = features
        card_layout.addWidget(features)

        card_layout.addSpacing(16)

        # ===== 语言选择 =====
        lang_row = QHBoxLayout()
        lang_row.setAlignment(Qt.AlignCenter)
        lang_row.setSpacing(8)
        lang_label = QLabel(self._tr("lang_label"))
        lang_label.setFont(QFont("PingFang SC", 16))
        lang_label.setStyleSheet("color: #64748b;")
        self._i18n_refs["lang_label"] = lang_label
        lang_row.addWidget(lang_label)

        self.lang_combo = QComboBox()
        self.lang_combo.setFixedSize(180, 36)
        self.lang_combo.setCursor(Qt.PointingHandCursor)
        self.lang_combo.setStyleSheet("""
            QComboBox {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #e2e8f0;
                border-radius: 18px;
                padding: 0 16px;
                font-size: 14px;
            }
            QComboBox:hover {
                border: 1px solid #cbd5e1;
                background-color: #e2e8f0;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: #1e293b;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                selection-background-color: #3b82f6;
                selection-color: white;
                padding: 4px;
            }
        """)
        # 使用全局语言列表（_LANG_OPTIONS），同时定位到用户上次选择的语言
        default_index = 0
        for i, (lang_code, lang_name) in enumerate(_LANG_OPTIONS):
            self.lang_combo.addItem(lang_name, lang_code)
            if lang_code == self._current_lang:
                default_index = i
        self.lang_combo.setCurrentIndex(default_index)
        # 连接语言切换信号
        try:
            self.lang_combo.currentIndexChanged.connect(self._on_welcome_lang_changed)
        except Exception as e:
            log_exception(e, "连接语言切换信号失败")
        lang_row.addWidget(self.lang_combo)

        lang_container = QWidget()
        lang_container.setLayout(lang_row)
        card_layout.addWidget(lang_container, alignment=Qt.AlignCenter)

        card_layout.addSpacing(12)

        # ===== 开始测试按钮 =====
        start_btn = QPushButton(self._tr("welcome_start"))
        start_btn.setFixedSize(220, 50)
        start_btn.setFont(QFont("PingFang SC", 16, QFont.Bold))
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 25px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #2563eb, stop:1 #1d4ed8);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #1d4ed8, stop:1 #1e40af);
            }
        """)
        start_btn.clicked.connect(lambda: self.central_stack.setCurrentIndex(3))
        self._i18n_refs["welcome_start"] = start_btn
        card_layout.addWidget(start_btn, alignment=Qt.AlignCenter)

        # 用 QGridLayout 居中
        outer_layout = QGridLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(card, 0, 0, Qt.AlignCenter)

        self.central_stack.addWidget(page)  # index = 2

    def _on_welcome_lang_changed(self, index: int):
        """欢迎页语言下拉框切换事件"""
        try:
            lang_code = self.lang_combo.itemData(index) if index >= 0 else None
            if lang_code:
                self._apply_language(str(lang_code))
        except Exception as e:
            log_exception(e, "切换语言失败")

    def _init_device_select_page(self):
        """构建设备类型选择页面 (Page 3)

        设计风格：深蓝背景 + 居中"请选择设备类型"标题 + 两张并排卡片
        右上角返回首页按钮，Android/iOS 卡片内带彩色圆形图标
        """
        # 整页深蓝背景
        page = QWidget()
        page.setStyleSheet("background-color: #f8fafc;")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        # ===== 顶部栏（右上角返回按钮）=====
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(24, 16, 32, 0)
        top_bar.addStretch(1)
        back_btn = QPushButton(self._tr("select_back_home"))
        back_btn.setFixedSize(130, 36)
        back_btn.setFont(QFont("PingFang SC", 13))
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748b;
                border: none;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: rgba(148, 163, 184, 25);
                color: #1e293b;
            }
        """)
        back_btn.clicked.connect(lambda: self.central_stack.setCurrentIndex(2))
        self._i18n_refs["select_back_home"] = back_btn
        top_bar.addWidget(back_btn)
        top_wrap = QWidget()
        top_wrap.setStyleSheet("background: transparent;")
        top_wrap.setLayout(top_bar)
        page_layout.addWidget(top_wrap)

        # ===== 标题 =====
        page_layout.addSpacing(80)
        title = QLabel(self._tr("select_device_title"))
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("PingFang SC", 26, QFont.Bold))
        title.setStyleSheet("color: #0f172a;")
        self._i18n_refs["select_title"] = title
        page_layout.addWidget(title)

        page_layout.addSpacing(50)

        # ===== 两张并排卡片 =====
        card_row = QHBoxLayout()
        card_row.setSpacing(28)
        card_row.setAlignment(Qt.AlignCenter)

        # --- Android 卡片（用 QPushButton，整卡可点击）---
        android_btn = QPushButton()
        android_btn.setFixedSize(360, 240)
        android_btn.setCursor(Qt.PointingHandCursor)
        android_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(226, 232, 240, 220);
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 16px;
            }
            QPushButton:hover {
                border: 2px solid #10b981;
                background-color: rgba(16, 185, 129, 40);
            }
            QPushButton:pressed {
                background-color: rgba(16, 185, 129, 80);
            }
        """)
        android_btn.clicked.connect(lambda: self._on_select_android())
        a_layout = QVBoxLayout(android_btn)
        a_layout.setContentsMargins(20, 40, 20, 40)
        a_layout.setSpacing(18)
        # 绿色圆形 + 安卓手机图标
        a_icon = QLabel("📱")
        a_icon.setAlignment(Qt.AlignCenter)
        a_icon.setFixedSize(72, 72)
        a_icon.setStyleSheet("""
            QLabel {
                background-color: rgba(16, 185, 129, 25);
                color: #10b981;
                border-radius: 36px;
                font-size: 32px;
            }
        """)
        a_layout.addWidget(a_icon, alignment=Qt.AlignCenter)
        a_title = QLabel("Android")
        a_title.setAlignment(Qt.AlignCenter)
        a_title.setFont(QFont("PingFang SC", 18, QFont.Bold))
        a_title.setStyleSheet("color: #0f172a;")
        a_layout.addWidget(a_title)
        a_sub = QLabel(self._tr("android_card_sub"))
        a_sub.setAlignment(Qt.AlignCenter)
        a_sub.setFont(QFont("PingFang SC", 13))
        a_sub.setStyleSheet("color: #64748b;")
        self._i18n_refs["android_sub"] = a_sub
        a_layout.addWidget(a_sub)
        card_row.addWidget(android_btn)

        # --- iOS 卡片 ---
        ios_btn = QPushButton()
        ios_btn.setFixedSize(360, 240)
        ios_btn.setCursor(Qt.PointingHandCursor)
        ios_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(226, 232, 240, 220);
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 16px;
            }
            QPushButton:hover {
                border: 2px solid #64748b;
                background-color: rgba(100, 116, 139, 40);
            }
            QPushButton:pressed {
                background-color: rgba(100, 116, 139, 80);
            }
        """)
        ios_btn.clicked.connect(lambda: self._on_select_ios())
        i_layout = QVBoxLayout(ios_btn)
        i_layout.setContentsMargins(20, 40, 20, 40)
        i_layout.setSpacing(18)
        # 灰色圆形 + 苹果图标
        i_icon = QLabel("🍎")
        i_icon.setAlignment(Qt.AlignCenter)
        i_icon.setFixedSize(72, 72)
        i_icon.setStyleSheet("""
            QLabel {
                background-color: rgba(148, 163, 184, 25);
                color: #cbd5e1;
                border-radius: 36px;
                font-size: 32px;
            }
        """)
        i_layout.addWidget(i_icon, alignment=Qt.AlignCenter)
        i_title = QLabel("iOS")
        i_title.setAlignment(Qt.AlignCenter)
        i_title.setFont(QFont("PingFang SC", 18, QFont.Bold))
        i_title.setStyleSheet("color: #0f172a;")
        i_layout.addWidget(i_title)
        i_sub = QLabel(self._tr("ios_card_sub"))
        i_sub.setAlignment(Qt.AlignCenter)
        i_sub.setFont(QFont("PingFang SC", 13))
        i_sub.setStyleSheet("color: #64748b;")
        self._i18n_refs["ios_sub"] = i_sub
        i_layout.addWidget(i_sub)
        card_row.addWidget(ios_btn)

        cards_wrap = QWidget()
        cards_wrap.setStyleSheet("background: transparent;")
        cards_wrap.setLayout(card_row)
        page_layout.addWidget(cards_wrap, alignment=Qt.AlignHCenter)

        page_layout.addStretch(1)

        # ===== 进入进度条叠层（初始隐藏）=====
        self._select_progress_overlay = QWidget(page)
        self._select_progress_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._select_progress_overlay.hide()
        overlay_lay = QVBoxLayout(self._select_progress_overlay)
        overlay_lay.setContentsMargins(0, 0, 0, 0)
        overlay_lay.setAlignment(Qt.AlignCenter)

        progress_card = QFrame()
        progress_card.setFixedSize(480, 220)
        progress_card.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 20px;
                border: 1px solid #e2e8f0;
                box-shadow: 0 20px 60px rgba(15, 23, 42, 0.15);
            }
        """)
        pcard_lay = QVBoxLayout(progress_card)
        pcard_lay.setContentsMargins(36, 32, 36, 32)
        pcard_lay.setSpacing(18)

        self._select_prog_title = QLabel(self._tr("init_progress_title"))
        self._select_prog_title.setFont(QFont("PingFang SC", 18, QFont.Bold))
        self._select_prog_title.setStyleSheet("color: #0f172a;")
        self._select_prog_title.setAlignment(Qt.AlignCenter)
        self._i18n_refs["prog_title"] = self._select_prog_title
        pcard_lay.addWidget(self._select_prog_title)

        self._select_prog_sub = QLabel(self._tr("init_progress_sub"))
        self._select_prog_sub.setFont(QFont("PingFang SC", 12))
        self._select_prog_sub.setStyleSheet("color: #64748b;")
        self._select_prog_sub.setAlignment(Qt.AlignCenter)
        self._i18n_refs["prog_sub"] = self._select_prog_sub
        pcard_lay.addWidget(self._select_prog_sub)

        self._select_prog_bar = QProgressBar()
        self._select_prog_bar.setRange(0, 1000)
        self._select_prog_bar.setValue(0)
        self._select_prog_bar.setFixedHeight(12)
        self._select_prog_bar.setTextVisible(False)
        self._select_prog_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #e2e8f0;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #60a5fa, stop:0.5 #2196F3, stop:1 #1565C0);
                border-radius: 6px;
            }
        """)
        pcard_lay.addWidget(self._select_prog_bar)

        self._select_prog_pct = QLabel("0%")
        self._select_prog_pct.setFont(QFont("Menlo", 14, QFont.Bold))
        self._select_prog_pct.setStyleSheet("color: #1565C0;")
        self._select_prog_pct.setAlignment(Qt.AlignCenter)
        pcard_lay.addWidget(self._select_prog_pct)

        overlay_lay.addWidget(progress_card)

        # 让叠层覆盖整个页面
        def _resize_overlay(e=None):
            self._select_progress_overlay.setGeometry(0, 0, page.width(), page.height())
        page.resizeEvent = _resize_overlay

        # 进度条仿真定时器（40ms 一次，~5秒 = 125 tick）
        self._select_prog_timer = QTimer(self)
        self._select_prog_timer.setInterval(40)
        self._select_prog_timer.timeout.connect(self._on_select_prog_tick)

        self.central_stack.addWidget(page)  # index = 3 (was 1, shifted by splash+contact pages)

    def _start_select_progress(self, target_index: int, target_name: str):
        """启动仿真进度条：target_index 是 central_stack 目标页索引"""
        self._select_prog_target = target_index
        self._select_prog_bar.setValue(0)
        self._select_prog_pct.setText("0%")
        self._select_prog_title.setText(self._tr("prog_entering").format(name=target_name))
        # 仿真阶段文案
        self._select_prog_phases = [
            (0.22, self._tr("prog_scanning"), target_name),
            (0.48, self._tr("prog_connecting"), target_name),
            (0.75, self._tr("prog_loading_driver"), target_name),
            (0.95, self._tr("prog_ready"), target_name),
        ]
        self._select_prog_sub.setText(self._tr("prog_phase_prefix").format(n=1, text=self._tr("prog_scanning")))
        # 随机抖动参数，使进度条更仿真
        import random
        self._select_prog_seed = [random.uniform(0.85, 1.15) for _ in range(25)]
        self._select_prog_tick_i = 0
        self._select_prog_last_phase = 0
        # 显示叠层
        self._select_progress_overlay.raise_()
        self._select_progress_overlay.show()
        QApplication.processEvents()
        self._select_prog_timer.start()

    def _on_select_prog_tick(self):
        """进度条仿真：非线性，带抖动，约 5 秒完成"""
        self._select_prog_tick_i += 1
        t = self._select_prog_tick_i  # 1..125
        T = 125  # 总帧数

        # 非线性曲线：先快、中慢、末冲刺 + 抖动
        tt = t / T  # 0..1
        # 曲线：f(x) = x^0.65  使前段快后段有冲刺感
        eased = min(1.0, tt ** 0.65)
        # 抖动
        jitter_idx = min(24, int(tt * 24))
        jitter = self._select_prog_seed[jitter_idx] if jitter_idx < len(self._select_prog_seed) else 1.0
        value = eased * jitter * 1000
        if t >= T:
            value = 1000
        value = max(self._select_prog_bar.value(), min(1000, int(value)))
        self._select_prog_bar.setValue(value)
        self._select_prog_pct.setText(f"{value // 10}%")

        # 阶段文案
        pct = value / 1000
        for i, (threshold, text, name) in enumerate(self._select_prog_phases):
            if pct >= threshold and self._select_prog_last_phase < i + 1:
                self._select_prog_last_phase = i + 1
                self._select_prog_sub.setText(self._tr("prog_phase_prefix").format(n=i+1, text=text))
                self._select_prog_title.setText(self._tr("prog_entering").format(name=name))
                break

        if t >= T or value >= 1000:
            self._select_prog_timer.stop()
            self._select_prog_bar.setValue(1000)
            self._select_prog_pct.setText("100%")
            self._select_prog_sub.setText(self._tr("prog_complete"))
            QApplication.processEvents()
            # 跳到目标页 + 触发设备刷新
            self.central_stack.setCurrentIndex(self._select_prog_target)
            # 隐藏叠层
            QTimer.singleShot(120, lambda: self._select_progress_overlay.hide())
            if self._select_prog_target == 4:
                self._refresh_devices()
                self._load_device_info()
            elif self._select_prog_target == 5:
                self._refresh_ios_devices()

    def _on_select_android(self):
        """选择安卓设备 → 询问 USB 调试 → 仿真进度条 → 进入测试页"""
        reply = QMessageBox.question(
            self, self._tr("msg_usb_debug_title"),
            self._tr("msg_usb_debug_body"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self._log("✅ 安卓设备 USB 调试已确认，启动进度条")
            self._start_select_progress(4, "Android")
        else:
            self._log("ℹ️ USB 调试未开启，返回设备选择")

    def _on_select_ios(self):
        """选择 iOS 设备 → 询问开发者模式 → 仿真进度条 → 进入测试页"""
        reply = QMessageBox.question(
            self, self._tr("msg_dev_mode_title"),
            self._tr("msg_dev_mode_body"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self._log("✅ iOS 设备开发者模式已确认，启动进度条")
            self._start_select_progress(5, "iOS")
        else:
            self._log("ℹ️ 开发者模式未开启，返回设备选择")

    # ==================== iOS 测试页面 (Page 5) ====================

    def _init_ios_test_page(self):
        """构建 iOS 测试页面 — 完全对齐安卓端布局"""
        self.ios_tab_widget = QTabWidget()
        self.ios_tab_widget.setStyleSheet("QTabWidget { background-color: #f8fafc; }")
        # 返回按钮（透明风格与安卓端一致）
        ios_back_btn = QPushButton(self._tr("btn_back_select"))
        self._i18n_refs["ios_back_btn"] = ios_back_btn
        ios_back_btn.setFixedSize(140, 32)
        ios_back_btn.setCursor(Qt.PointingHandCursor)
        ios_back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #64748b;
                border: none;
                border-radius: 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(148, 163, 184, 25);
                color: #1e293b;
            }
        """)
        ios_back_btn.clicked.connect(lambda: self.central_stack.setCurrentIndex(3))
        self.ios_tab_widget.setCornerWidget(ios_back_btn, Qt.TopRightCorner)
        self.central_stack.addWidget(self.ios_tab_widget)  # index = 5

        # ===== iOS Tab 1: 帧率测试 =====
        self._init_ios_fps_tab()
        # ===== iOS Tab 2: CPU/GPU 监测 =====
        self._init_ios_hw_tab()
        # ===== iOS Tab 3: CSV 历史记录 =====
        self._init_ios_history_tab()
        # ===== iOS Tab 4: 手机信息 =====
        self._init_ios_info_tab()

        # iOS 测试计时器
        self.ios_test_timer = QTimer()
        self.ios_test_timer.timeout.connect(self._update_ios_duration)

    def _init_ios_fps_tab(self):
        """iOS 帧率测试页 — 完全对齐安卓端帧率测试页"""
        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.ios_tab_widget.addTab(tab, self._tr("tab_fps"))

        # ===== 顶部：设备与应用设置 =====
        top_group = QGroupBox(self._tr("grp_device_settings"))
        self._i18n_refs["ios_grp_device_settings"] = top_group
        top_layout = QGridLayout(top_group)

        _lbl = QLabel(self._tr("lbl_device"))
        self._i18n_refs["ios_lbl_device"] = _lbl
        top_layout.addWidget(_lbl, 0, 0)
        self.ios_device_combo = QComboBox()
        self.ios_device_combo.setMinimumWidth(300)
        top_layout.addWidget(self.ios_device_combo, 0, 1)

        self.ios_refresh_btn = QPushButton(self._tr("btn_refresh_device"))
        self._i18n_refs["ios_btn_refresh_device"] = self.ios_refresh_btn
        self.ios_refresh_btn.clicked.connect(self._refresh_ios_devices)
        top_layout.addWidget(self.ios_refresh_btn, 0, 2)

        _lbl = QLabel(self._tr("lbl_app"))
        self._i18n_refs["ios_lbl_app"] = _lbl
        top_layout.addWidget(_lbl, 0, 3)
        self.ios_app_combo = QComboBox()
        self.ios_app_combo.setEditable(True)
        self.ios_app_combo.setMinimumWidth(350)
        top_layout.addWidget(self.ios_app_combo, 0, 4)

        self.ios_list_apps_btn = QPushButton(self._tr("btn_list_apps"))
        self._i18n_refs["ios_btn_list_apps"] = self.ios_list_apps_btn
        self.ios_list_apps_btn.clicked.connect(self._refresh_ios_apps)
        top_layout.addWidget(self.ios_list_apps_btn, 0, 5)

        self.ios_foreground_btn = QPushButton(self._tr("btn_foreground_app"))
        self._i18n_refs["btn_foreground_app"] = self.ios_foreground_btn
        self.ios_foreground_btn.clicked.connect(self._detect_ios_foreground_app)
        top_layout.addWidget(self.ios_foreground_btn, 0, 6)

        # 刷新率设置
        _lbl = QLabel(self._tr("lbl_refresh_rate"))
        self._i18n_refs["ios_lbl_refresh_rate"] = _lbl
        top_layout.addWidget(_lbl, 1, 0)
        self.ios_refresh_rate_combo = QComboBox()
        for rate in [60, 90, 120, 144]:
            self.ios_refresh_rate_combo.addItem(f"{rate} Hz", rate)
        self.ios_refresh_rate_combo.setCurrentIndex(0)
        self.ios_refresh_rate_combo.currentIndexChanged.connect(self._on_ios_refresh_rate_changed)
        top_layout.addWidget(self.ios_refresh_rate_combo, 1, 1)

        # 采集间隔
        _lbl = QLabel(self._tr("lbl_interval"))
        self._i18n_refs["ios_lbl_interval"] = _lbl
        top_layout.addWidget(_lbl, 1, 2)
        self.ios_interval_combo = QComboBox()
        for iv in [0.1, 0.3, 0.5, 1.0, 2.0]:
            self.ios_interval_combo.addItem(f"{iv}s", iv)
        self.ios_interval_combo.setCurrentIndex(3)  # 默认 1.0s
        top_layout.addWidget(self.ios_interval_combo, 1, 3)

        self.ios_device_info_label = QLabel(self._tr("lbl_device_info"))
        self._i18n_refs["ios_lbl_device_info"] = self.ios_device_info_label
        self.ios_device_info_label.setStyleSheet(f"color: {self._fg_muted()};")
        top_layout.addWidget(self.ios_device_info_label, 1, 4, 1, 3)
        layout.addWidget(top_group)

        # ===== 中部：控制按钮与状态 =====
        ctrl_layout = QHBoxLayout()

        self.ios_start_btn = QPushButton(self._tr("btn_start_test"))
        self._i18n_refs["ios_btn_start_test"] = self.ios_start_btn
        self.ios_start_btn.setMinimumHeight(45)
        self.ios_start_btn.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; font-size: 16px;
                          font-weight: bold; border-radius: 6px; padding: 8px 24px; }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: rgba(33,150,243,80); color: rgba(226,232,240,120); }
        """)
        self.ios_start_btn.clicked.connect(self._start_ios_test)
        ctrl_layout.addWidget(self.ios_start_btn)

        self.ios_stop_btn = QPushButton(self._tr("btn_stop_test"))
        self._i18n_refs["ios_btn_stop_test"] = self.ios_stop_btn
        self.ios_stop_btn.setMinimumHeight(45)
        self.ios_stop_btn.setEnabled(False)
        self.ios_stop_btn.setStyleSheet("""
            QPushButton { background-color: #F44336; color: white; font-size: 16px;
                          font-weight: bold; border-radius: 6px; padding: 8px 24px; }
            QPushButton:hover { background-color: #D32F2F; }
            QPushButton:disabled { background-color: rgba(244,67,54,80); color: rgba(226,232,240,120); }
        """)
        self.ios_stop_btn.clicked.connect(self._stop_ios_test)
        ctrl_layout.addWidget(self.ios_stop_btn)

        self.ios_export_btn = QPushButton(self._tr("btn_export"))
        self._i18n_refs["ios_btn_export"] = self.ios_export_btn
        self.ios_export_btn.setMinimumHeight(45)
        self.ios_export_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-size: 14px;
                          border-radius: 6px; padding: 8px 20px; }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.ios_export_btn.clicked.connect(self._show_ios_fps_export_menu)
        ctrl_layout.addWidget(self.ios_export_btn)

        self.ios_clear_btn = QPushButton(self._tr("btn_clear"))
        self._i18n_refs["ios_btn_clear"] = self.ios_clear_btn
        self.ios_clear_btn.setMinimumHeight(45)
        self.ios_clear_btn.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; font-size: 14px;
                          border-radius: 6px; padding: 8px 20px; }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.ios_clear_btn.clicked.connect(self._clear_ios_fps_data)
        ctrl_layout.addWidget(self.ios_clear_btn)

        self.ios_duration_label = QLabel(self._tr("lbl_duration"))
        self._i18n_refs["ios_lbl_duration"] = self.ios_duration_label
        self.ios_duration_label.setFont(QFont("Menlo", 16, QFont.Bold))
        self.ios_duration_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ctrl_layout.addWidget(self.ios_duration_label, 1)
        layout.addLayout(ctrl_layout)

        # ===== 主区域：图表 + 统计 + 日志 =====
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：图表区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # FPS实时曲线
        self.ios_fps_plot = PlotWidget(title=self._tr("chart_fps_title"))
        self._i18n_refs["ios_fps_plot"] = self.ios_fps_plot
        # iOS FPS：与安卓一致，高对比配色（青蓝实线=即时，暖橙虚线=平均）
        self._apply_realtime_plot_styling(self.ios_fps_plot, y_left=self._tr("chart_fps_left"),
                                          y_left_color="#38bdf8", x_label=self._tr("chart_fps_bottom"))
        self.ios_fps_plot.setTitle(self._tr("chart_fps_title"), color="#f8fafc", size="12pt")
        self.ios_fps_plot.addLegend()
        self.ios_fps_curve = self.ios_fps_plot.plot(pen=mkPen('#38bdf8', width=3), name=self._tr("curve_instant_fps"))
        self.ios_avg_curve = self.ios_fps_plot.plot(pen=mkPen('#fb923c', width=2.6, style=Qt.DashLine), name=self._tr("curve_avg_fps"))
        left_layout.addWidget(self.ios_fps_plot, stretch=2)

        # 帧时间分布柱状图
        self.ios_frame_plot = PlotWidget(title=self._tr("chart_frame_title"))
        self._i18n_refs["ios_frame_plot"] = self.ios_frame_plot
        self._apply_realtime_plot_styling(self.ios_frame_plot, y_left=self._tr("chart_frame_left"),
                                          y_left_color="#4ade80", x_label=self._tr("chart_frame_bottom"))
        self.ios_frame_plot.setTitle(self._tr("chart_frame_title"), color="#f8fafc", size="12pt")
        self.ios_frame_bar = pg.BarGraphItem(x=[], height=[], width=0.8, brush='#4ade80',
                                            pen=pg.mkPen("#22c55e", width=2))
        self.ios_frame_plot.addItem(self.ios_frame_bar)
        self.ios_threshold_line = pg.InfiniteLine(
            pos=16.67, angle=0, pen=mkPen('#f43f5e', width=2.6, style=Qt.DashLine),
            label=self._tr("lbl_jank_threshold"), labelOpts={'color': '#fecdd3', 'position': 0.8}
        )
        self.ios_frame_plot.addItem(self.ios_threshold_line)
        left_layout.addWidget(self.ios_frame_plot, stretch=1)

        splitter.addWidget(left_widget)

        # 右侧：统计数据 + 日志
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 统计面板（12 项，含 P95/P99）
        stats_group = QGroupBox(self._tr("grp_realtime_stats"))
        self._i18n_refs["ios_grp_realtime_stats"] = stats_group
        stats_grid = QGridLayout(stats_group)
        self._ios_stat_labels = {}
        self._ios_stat_title_labels = {}
        stat_items = [
            (self._tr("stat_current_fps"), "stat_current_fps", "fps", "#2196F3"),
            (self._tr("stat_avg_fps"), "stat_avg_fps", "avg_fps", "#4CAF50"),
            (self._tr("stat_min_fps"), "stat_min_fps", "min_fps", "#F44336"),
            (self._tr("stat_max_fps"), "stat_max_fps", "max_fps", "#9C27B0"),
            (self._tr("stat_low_1"), "stat_low_1", "low_1", "#FF6F00"),
            (self._tr("stat_low_01"), "stat_low_01", "low_01", "#D84315"),
            (self._tr("stat_std_fps"), "stat_std_fps", "std_fps", "#FF9800"),
            (self._tr("stat_jank_count"), "stat_jank_count", "jank_count", "#F44336"),
            (self._tr("stat_jank_rate"), "stat_jank_rate", "jank_rate", "#FF5722"),
            (self._tr("stat_p95"), "stat_p95", "p95", "#795548"),
            (self._tr("stat_p99"), "stat_p99", "p99", "#607D8B"),
        ]
        for i, (label_text, i18n_key, key, color) in enumerate(stat_items):
            row = i // 2
            col = (i % 2) * 2
            lbl_title = QLabel(f"{label_text}:")
            lbl_title.setStyleSheet(f"font-size: 13px; color: {self._fg_muted()};")
            stats_grid.addWidget(lbl_title, row, col)
            self._ios_stat_title_labels[i18n_key] = lbl_title
            lbl_value = QLabel("--")
            lbl_value.setFont(QFont("Menlo", 16, QFont.Bold))
            lbl_value.setStyleSheet(f"color: {color};")
            lbl_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            stats_grid.addWidget(lbl_value, row, col + 1)
            self._ios_stat_labels[key] = lbl_value
        right_layout.addWidget(stats_group)

        # 卡顿率进度条
        jank_group = QGroupBox(self._tr("grp_jank_indicator"))
        self._i18n_refs["ios_grp_jank_indicator"] = jank_group
        jank_layout = QVBoxLayout(jank_group)
        self.ios_jank_bar = QProgressBar()
        self.ios_jank_bar.setObjectName("jankBar")
        self.ios_jank_bar.setRange(0, 100)
        self.ios_jank_bar.setValue(0)
        self.ios_jank_bar.setFormat(self._tr("fmt_jank_rate_zero"))
        self.ios_jank_bar.setTextVisible(True)
        self.ios_jank_bar.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }}
        """)
        jank_layout.addWidget(self.ios_jank_bar)
        jank_hint = QLabel(self._tr("lbl_jank_hint"))
        self._i18n_refs["ios_lbl_jank_hint"] = jank_hint
        jank_hint.setStyleSheet(f"font-size: 12px; color: {self._fg_muted()};")
        jank_hint.setAlignment(Qt.AlignCenter)
        jank_layout.addWidget(jank_hint)
        right_layout.addWidget(jank_group)

        # 日志窗口
        log_group = QGroupBox(self._tr("grp_log_output"))
        self._i18n_refs["ios_grp_log_output"] = log_group
        log_group.setStyleSheet(f"""
            QGroupBox {{ font-size: 14px; font-weight: bold; color: #F57F17;
                        border: 2px solid #FF8F00; border-radius: 8px; margin-top: 16px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        log_layout = QVBoxLayout(log_group)
        self.ios_log_text = QTextEdit()
        self.ios_log_text.setReadOnly(True)
        self.ios_log_text.setFont(QFont("Menlo", 11))
        self.ios_log_text.setStyleSheet(f"background-color: {self._bg_base()}; color: #1e293b; border: 1px solid rgba(100,116,139,80); border-radius: 6px;")
        log_layout.addWidget(self.ios_log_text)
        right_layout.addWidget(log_group, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([900, 560])
        layout.addWidget(splitter, stretch=1)

    def _init_ios_hw_tab(self):
        """iOS CPU/GPU 监测页 — 对齐安卓端结构，显示占用率而非频率"""
        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.ios_tab_widget.addTab(tab, self._tr("tab_hw"))

        # ===== 顶部控制栏 =====
        ctrl = QHBoxLayout()
        _lbl = QLabel(self._tr("lbl_monitor_device"))
        self._i18n_refs["ios_lbl_monitor_device"] = _lbl
        ctrl.addWidget(_lbl)
        self.ios_hw_device_combo = QComboBox()
        self.ios_hw_device_combo.setMinimumWidth(280)
        ctrl.addWidget(self.ios_hw_device_combo)

        # 采集间隔（与 FPS 测试页保持一致的选项）
        _lbl = QLabel(self._tr("lbl_interval_short"))
        self._i18n_refs["ios_lbl_interval_short"] = _lbl
        ctrl.addWidget(_lbl)
        self.ios_hw_interval_combo = QComboBox()
        for iv in [0.1, 0.3, 0.5, 1.0, 2.0]:
            self.ios_hw_interval_combo.addItem(f"{iv}s", iv)
        self.ios_hw_interval_combo.setCurrentIndex(3)  # 默认 1.0s
        self.ios_hw_interval_combo.setToolTip(self._tr("tip_hw_interval_ios"))
        ctrl.addWidget(self.ios_hw_interval_combo)

        self.ios_hw_refresh_btn = QPushButton(self._tr("btn_refresh_device"))
        self._i18n_refs["ios_hw_btn_refresh_device"] = self.ios_hw_refresh_btn
        self.ios_hw_refresh_btn.clicked.connect(self._refresh_ios_devices)
        ctrl.addWidget(self.ios_hw_refresh_btn)

        self.ios_hw_start_btn = QPushButton(self._tr("btn_start_monitor"))
        self._i18n_refs["ios_hw_btn_start_monitor"] = self.ios_hw_start_btn
        self.ios_hw_start_btn.setMinimumHeight(40)
        self.ios_hw_start_btn.setStyleSheet("""
            QPushButton { background-color: #7B1FA2; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #6A1B9A; }
            QPushButton:disabled { background-color: rgba(123,31,162,80); color: rgba(226,232,240,120); }
        """)
        self.ios_hw_start_btn.clicked.connect(self._start_ios_hw_monitor)
        ctrl.addWidget(self.ios_hw_start_btn)

        self.ios_hw_stop_btn = QPushButton(self._tr("btn_stop_monitor"))
        self._i18n_refs["ios_hw_btn_stop_monitor"] = self.ios_hw_stop_btn
        self.ios_hw_stop_btn.setMinimumHeight(40)
        self.ios_hw_stop_btn.setEnabled(False)
        self.ios_hw_stop_btn.setStyleSheet("""
            QPushButton { background-color: #F44336; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #D32F2F; }
            QPushButton:disabled { background-color: rgba(244,67,54,80); color: rgba(226,232,240,120); }
        """)
        self.ios_hw_stop_btn.clicked.connect(self._stop_ios_hw_monitor)
        ctrl.addWidget(self.ios_hw_stop_btn)

        self.ios_hw_clear_btn = QPushButton(self._tr("btn_clear"))
        self._i18n_refs["ios_hw_btn_clear"] = self.ios_hw_clear_btn
        self.ios_hw_clear_btn.setMinimumHeight(40)
        self.ios_hw_clear_btn.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.ios_hw_clear_btn.clicked.connect(self._clear_ios_hw_data)
        ctrl.addWidget(self.ios_hw_clear_btn)

        self.ios_hw_export_btn = QPushButton(self._tr("btn_export"))
        self._i18n_refs["ios_hw_btn_export"] = self.ios_hw_export_btn
        self.ios_hw_export_btn.setMinimumHeight(40)
        self.ios_hw_export_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.ios_hw_export_btn.clicked.connect(self._show_ios_hw_export_menu)
        ctrl.addWidget(self.ios_hw_export_btn)

        self.ios_ddi_check_btn = QPushButton(self._tr("btn_ddi_status"))
        self._i18n_refs["btn_ddi_status"] = self.ios_ddi_check_btn
        self.ios_ddi_check_btn.setMinimumHeight(40)
        self.ios_ddi_check_btn.setStyleSheet("""
            QPushButton { background-color: #00838F; color: white; font-size: 13px;
                          font-weight: bold; border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background-color: #006064; }
        """)
        self.ios_ddi_check_btn.clicked.connect(self._check_ios_ddi_status)
        ctrl.addWidget(self.ios_ddi_check_btn)

        self.ios_hw_status_label = QLabel(self._tr("lbl_status"))
        self._i18n_refs["ios_lbl_status"] = self.ios_hw_status_label
        self.ios_hw_status_label.setStyleSheet(f"color: {self._fg_muted()}; font-size: 13px;")
        ctrl.addWidget(self.ios_hw_status_label)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # 说明条
        note = QLabel(self._tr("lbl_ios_note"))
        self._i18n_refs["lbl_ios_note"] = note
        note.setWordWrap(True)
        note.setStyleSheet(f"background-color: {self._note_bg()}; padding: 8px; border-radius: 6px;"
                           f"color: {self._fg()}; font-size: 12px;")
        layout.addWidget(note)

        # ===== 主区域：左右分栏 =====
        hw_splitter = QSplitter(Qt.Horizontal)

        # 左侧：实时数值面板
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # CPU 使用率卡片
        cpu_group = QGroupBox(self._tr("grp_cpu_usage"))
        self._i18n_refs["ios_grp_cpu_usage"] = cpu_group
        cpu_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #1565C0;
                        border: 2px solid #2196F3; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        cpu_layout = QVBoxLayout(cpu_group)
        self.ios_cpu_usage_label = QLabel("-- %")
        self.ios_cpu_usage_label.setFont(QFont("Menlo", 28, QFont.Bold))
        self.ios_cpu_usage_label.setAlignment(Qt.AlignCenter)
        self.ios_cpu_usage_label.setStyleSheet("color: #2196F3;")
        cpu_layout.addWidget(self.ios_cpu_usage_label)

        self.ios_cpu_usage_bar = QProgressBar()
        self.ios_cpu_usage_bar.setRange(0, 100)
        self.ios_cpu_usage_bar.setValue(0)
        self.ios_cpu_usage_bar.setFixedHeight(24)
        self.ios_cpu_usage_bar.setFormat("0.0%")
        self.ios_cpu_usage_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid rgba(100,116,139,80); border-radius: 6px; text-align: center;
                           font-size: 13px; font-weight: bold; background-color: rgba(226,232,240,200); }}
            QProgressBar::chunk {{ background-color: #2196F3; border-radius: 5px; }}
        """)
        cpu_layout.addWidget(self.ios_cpu_usage_bar)
        self.ios_cpu_cores_label = QLabel(self._tr("lbl_core_count"))
        self._i18n_refs["ios_lbl_core_count"] = self.ios_cpu_cores_label
        self.ios_cpu_cores_label.setStyleSheet(f"font-size: 12px; color: {self._fg_muted()};")
        cpu_layout.addWidget(self.ios_cpu_cores_label)
        left_layout.addWidget(cpu_group)

        # GPU 利用率卡片
        gpu_group = QGroupBox(self._tr("grp_gpu_usage"))
        self._i18n_refs["ios_grp_gpu_usage"] = gpu_group
        gpu_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #00838F;
                        border: 2px solid #00838F; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        gpu_layout = QVBoxLayout(gpu_group)
        self.ios_gpu_label = QLabel("-- %")
        self.ios_gpu_label.setFont(QFont("Menlo", 28, QFont.Bold))
        self.ios_gpu_label.setAlignment(Qt.AlignCenter)
        self.ios_gpu_label.setStyleSheet("color: #00838F;")
        gpu_layout.addWidget(self.ios_gpu_label)

        self.ios_gpu_bar = QProgressBar()
        self.ios_gpu_bar.setRange(0, 100)
        self.ios_gpu_bar.setValue(0)
        self.ios_gpu_bar.setFixedHeight(24)
        self.ios_gpu_bar.setFormat("0.0%")
        self.ios_gpu_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid rgba(100,116,139,80); border-radius: 6px; text-align: center;
                           font-size: 13px; font-weight: bold; background-color: rgba(226,232,240,200); }}
            QProgressBar::chunk {{ background-color: #00838F; border-radius: 5px; }}
        """)
        gpu_layout.addWidget(self.ios_gpu_bar)

        # GPU 子项：渲染器/平铺器利用率
        gpu_sub_grid = QGridLayout()
        _lbl = QLabel(self._tr("lbl_renderer"))
        self._i18n_refs["ios_lbl_renderer"] = _lbl
        gpu_sub_grid.addWidget(_lbl, 0, 0)
        self.ios_gpu_renderer_label = QLabel("-- %")
        self.ios_gpu_renderer_label.setFont(QFont("Menlo", 14, QFont.Bold))
        self.ios_gpu_renderer_label.setStyleSheet("color: #00695C;")
        self.ios_gpu_renderer_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gpu_sub_grid.addWidget(self.ios_gpu_renderer_label, 0, 1)
        _lbl = QLabel(self._tr("lbl_tiler"))
        self._i18n_refs["ios_lbl_tiler"] = _lbl
        gpu_sub_grid.addWidget(_lbl, 1, 0)
        self.ios_gpu_tiler_label = QLabel("-- %")
        self.ios_gpu_tiler_label.setFont(QFont("Menlo", 14, QFont.Bold))
        self.ios_gpu_tiler_label.setStyleSheet("color: #F57C00;")
        self.ios_gpu_tiler_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gpu_sub_grid.addWidget(self.ios_gpu_tiler_label, 1, 1)
        gpu_layout.addLayout(gpu_sub_grid)
        left_layout.addWidget(gpu_group)

        # 内存卡片
        mem_group = QGroupBox(self._tr("grp_memory"))
        self._i18n_refs["ios_grp_memory"] = mem_group
        mem_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #2E7D32;
                        border: 2px solid #00695C; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        mem_layout = QVBoxLayout(mem_group)
        self.ios_mem_label = QLabel("-- MB / -- MB")
        self.ios_mem_label.setFont(QFont("Menlo", 18, QFont.Bold))
        self.ios_mem_label.setAlignment(Qt.AlignCenter)
        self.ios_mem_label.setStyleSheet("color: #4CAF50;")
        mem_layout.addWidget(self.ios_mem_label)

        self.ios_mem_bar = QProgressBar()
        self.ios_mem_bar.setRange(0, 100)
        self.ios_mem_bar.setValue(0)
        self.ios_mem_bar.setFixedHeight(24)
        self.ios_mem_bar.setFormat("0.0%")
        self.ios_mem_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid rgba(100,116,139,80); border-radius: 6px; text-align: center;
                           font-size: 13px; font-weight: bold; background-color: rgba(226,232,240,200); }}
            QProgressBar::chunk {{ background-color: #00695C; border-radius: 5px; }}
        """)
        mem_layout.addWidget(self.ios_mem_bar)
        left_layout.addWidget(mem_group)
        left_layout.addStretch()
        hw_splitter.addWidget(left_widget)

        # 右侧：使用率曲线
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.ios_hw_plot = PlotWidget(title=self._tr("chart_ios_hw_title"))
        self._i18n_refs["ios_hw_plot"] = self.ios_hw_plot
        self._apply_realtime_plot_styling(self.ios_hw_plot, y_left=self._tr("chart_usage_left_ios"),
                                          y_left_color="#60a5fa", x_label=self._tr("chart_fps_bottom"))
        self.ios_hw_plot.setTitle(self._tr("chart_ios_hw_title"), color="#f8fafc", size="12pt")
        self.ios_hw_plot.addLegend()
        self._ios_hw_curves = {}
        right_layout.addWidget(self.ios_hw_plot)
        hw_splitter.addWidget(right_widget)

        hw_splitter.setStretchFactor(0, 1)
        hw_splitter.setStretchFactor(1, 2)
        hw_splitter.setSizes([500, 800])
        layout.addWidget(hw_splitter, stretch=1)

    def _init_ios_info_tab(self):
        """iOS 手机信息页"""
        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.ios_tab_widget.addTab(tab, self._tr("tab_device_info"))

        ctrl = QHBoxLayout()
        _lbl = QLabel(self._tr("lbl_select_device"))
        self._i18n_refs["ios_lbl_select_device"] = _lbl
        ctrl.addWidget(_lbl)
        self.ios_info_device_combo = QComboBox()
        self.ios_info_device_combo.setMinimumWidth(300)
        ctrl.addWidget(self.ios_info_device_combo)

        self.ios_info_refresh_btn = QPushButton(self._tr("btn_refresh_device"))
        self._i18n_refs["ios_info_btn_refresh_device"] = self.ios_info_refresh_btn
        self.ios_info_refresh_btn.clicked.connect(self._refresh_ios_devices)
        ctrl.addWidget(self.ios_info_refresh_btn)

        self.ios_info_load_btn = QPushButton(self._tr("btn_get_info"))
        self._i18n_refs["ios_info_btn_get_info"] = self.ios_info_load_btn
        self.ios_info_load_btn.setMinimumHeight(40)
        self.ios_info_load_btn.setStyleSheet("""
            QPushButton { background-color: #00838F; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #006064; }
        """)
        self.ios_info_load_btn.clicked.connect(self._load_ios_device_info)
        ctrl.addWidget(self.ios_info_load_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        info_group = QGroupBox(self._tr("grp_device_info"))
        self._i18n_refs["ios_grp_device_info"] = info_group
        info_group.setStyleSheet(f"""
            QGroupBox {{ font-size: 14px; font-weight: bold; color: #0277BD;
                        border: 2px solid #0288D1; border-radius: 8px; margin-top: 16px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        info_layout = QVBoxLayout(info_group)
        self.ios_info_table = QTableWidget()
        self.ios_info_table.setColumnCount(2)
        self.ios_info_table.setHorizontalHeaderLabels([self._tr("header_item"), self._tr("header_detail")])
        self.ios_info_table.horizontalHeader().setStretchLastSection(True)
        self.ios_info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ios_info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ios_info_table.setFont(QFont("Menlo", 13))
        self.ios_info_table.setAlternatingRowColors(True)
        self.ios_info_table.verticalHeader().setVisible(False)
        self.ios_info_table.setEditTriggers(QTableWidget.NoEditTriggers)
        info_layout.addWidget(self.ios_info_table)
        layout.addWidget(info_group, stretch=1)

    def _init_ios_history_tab(self):
        """iOS CSV 历史记录页 — 对齐安卓端历史记录页"""
        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.ios_tab_widget.addTab(tab, self._tr("tab_history"))

        # 顶部提示条
        tip_bar = QHBoxLayout()
        tip = QLabel(self._tr("lbl_history_tip"))
        self._i18n_refs["ios_lbl_history_tip"] = tip
        tip.setStyleSheet(f"color: {self._fg()}; font-size: 13px; font-weight: bold;")
        tip_bar.addWidget(tip)
        tip_bar.addStretch()

        self.ios_hist_export_btn = QPushButton(self._tr("btn_export_csv"))
        self._i18n_refs["ios_btn_export_csv"] = self.ios_hist_export_btn
        self.ios_hist_export_btn.setMinimumHeight(36)
        self.ios_hist_export_btn.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; font-size: 13px;
                          font-weight: bold; border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.ios_hist_export_btn.clicked.connect(self._ios_history_export_selected)
        tip_bar.addWidget(self.ios_hist_export_btn)

        # 联系作者按钮
        ios_contact_btn = QPushButton(self._tr("btn_contact"))
        self._i18n_refs["ios_btn_contact"] = ios_contact_btn
        ios_contact_btn.setMinimumHeight(36)
        ios_contact_btn.setStyleSheet("""
            QPushButton { background-color: #0f172a; color: white; font-size: 13px;
                          font-weight: bold; border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background-color: #1e293b; }
        """)
        ios_contact_btn.clicked.connect(self._navigate_to_contact)
        tip_bar.addWidget(ios_contact_btn)

        layout.addLayout(tip_bar)

        # 主区域：左右分栏
        body = QSplitter(Qt.Horizontal)

        # 左侧：历史记录列表
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        fps_gb = QGroupBox(self._tr("grp_fps_history"))
        self._i18n_refs["ios_grp_fps_history"] = fps_gb
        fps_gb.setStyleSheet(f"""
            QGroupBox {{ font-size: 14px; font-weight: bold; color: #0277BD;
                        border: 2px solid #0288D1; border-radius: 8px; margin-top: 16px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        fps_lay = QVBoxLayout(fps_gb)
        self.ios_hist_fps_list = QListWidget()
        self.ios_hist_fps_list.itemClicked.connect(self._ios_history_on_fps_clicked)
        fps_lay.addWidget(self.ios_hist_fps_list)
        left_lay.addWidget(fps_gb, stretch=1)

        hw_gb = QGroupBox(self._tr("grp_hw_history"))
        self._i18n_refs["ios_grp_hw_history"] = hw_gb
        hw_gb.setStyleSheet(f"""
            QGroupBox {{ font-size: 14px; font-weight: bold; color: #7B1FA2;
                        border: 2px solid #7B1FA2; border-radius: 8px; margin-top: 16px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        hw_lay = QVBoxLayout(hw_gb)
        self.ios_hist_hw_list = QListWidget()
        self.ios_hist_hw_list.itemClicked.connect(self._ios_history_on_hw_clicked)
        hw_lay.addWidget(self.ios_hist_hw_list)
        left_lay.addWidget(hw_gb, stretch=1)

        body.addWidget(left)

        # 右侧：详情 + 图表
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)

        # 详情摘要
        self.ios_hist_summary_gb = QGroupBox(self._tr("grp_detail_summary"))
        self._i18n_refs["ios_grp_detail_summary"] = self.ios_hist_summary_gb
        self.ios_hist_summary_gb.setStyleSheet(f"""
            QGroupBox {{ font-size: 14px; font-weight: bold; color: {self._fg()};
                        border: 2px solid #90A4AE; border-radius: 8px; margin-top: 16px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        self.ios_hist_summary_layout = QGridLayout(self.ios_hist_summary_gb)
        right_lay.addWidget(self.ios_hist_summary_gb)

        # 统计数值表格
        table_gb = QGroupBox(self._tr("grp_stats_data"))
        self._i18n_refs["grp_hist_stats_data"] = table_gb
        table_lay = QVBoxLayout(table_gb)
        self.ios_hist_table = QTableWidget()
        self.ios_hist_table.setColumnCount(2)
        self.ios_hist_table.setHorizontalHeaderLabels([self._tr("header_metric"), self._tr("header_value")])
        self.ios_hist_table.horizontalHeader().setStretchLastSection(True)
        self.ios_hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ios_hist_table.setFont(QFont("Menlo", 12))
        self.ios_hist_table.setAlternatingRowColors(True)
        self.ios_hist_table.verticalHeader().setVisible(False)
        self.ios_hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        table_lay.addWidget(self.ios_hist_table)
        right_lay.addWidget(table_gb, stretch=1)

        # 图表
        chart_gb = QGroupBox(self._tr("grp_time_series"))
        self._i18n_refs["grp_hist_time_series"] = chart_gb
        chart_lay = QVBoxLayout(chart_gb)
        self.ios_hist_plot = PlotWidget()
        self.ios_hist_plot.addLegend()
        self.ios_hist_plot.showGrid(x=True, y=True, alpha=0.3)
        chart_lay.addWidget(self.ios_hist_plot)
        right_lay.addWidget(chart_gb, stretch=1)

        body.addWidget(right)
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 3)
        body.setSizes([520, 880])

        layout.addWidget(body, stretch=1)

        # 初始化右侧空状态
        self._ios_history_clear_details()
        self._ios_history_refresh_lists()

    # ==================== iOS CSV 导出 ====================

    def _export_ios_csv(self):
        """导出 iOS 帧率测试 CSV 报告（含预览功能）"""
        if not self._ios_history_stats:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_no_fps_data"))
            return
        default_name = f"ios_fps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        default_path = os.path.expanduser(f"~/Desktop/{default_name}")
        try:
            udid = self._get_ios_selected_device() or ""
            app_name = self.ios_app_combo.currentText().strip() or "未知应用"
            csv_rows: list[list] = []
            csv_rows.append(["# iOS 帧率测试报告"])
            csv_rows.append(["# 导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            csv_rows.append(["# 设备 UDID", udid])
            csv_rows.append(["# 测试应用", app_name])
            csv_rows.append([])
            summary = self.ios_analyzer.get_summary()
            csv_rows.append(["# ===== 测试摘要 ====="])
            for k, v in summary.items():
                csv_rows.append([f"# {k}", v])
            csv_rows.append([])
            csv_rows.append(["# ===== 时间序列数据 ====="])
            csv_rows.append(["时间(秒)", "瞬时FPS", "平均FPS"])
            for i in range(len(self._ios_history_times)):
                csv_rows.append([
                    f"{self._ios_history_times[i]:.2f}",
                    f"{self._ios_history_fps[i]:.1f}",
                    f"{self._ios_history_avg_fps[i]:.1f}",
                ])
            saved = self._preview_csv(self._tr("preview_ios_fps_csv"), csv_rows, default_path)
            if saved:
                # CSV 导出附带曲线图 JPG
                try:
                    pm = self._render_fps_plots_pixmap("ios")
                    if pm is not None:
                        img_path = os.path.splitext(saved)[0] + "_charts.jpg"
                        if pm.save(img_path, "JPG", 92):
                            self._ios_log(f"📤 曲线图已导出: {img_path}")
                except Exception as _ie:
                    log_exception(_ie, "iOS 帧率 CSV 附带曲线图导出失败")
                self._ios_log(f"✅ iOS 帧率 CSV 已导出: {saved}")
                QMessageBox.information(self, self._tr("msg_export_success"), self._tr("msg_export_success_csv").format(path=saved))
        except Exception as e:
            log_exception(e, "iOS 帧率 CSV 导出失败")
            QMessageBox.critical(self, self._tr("msg_export_failed"), self._tr("msg_export_failed_csv").format(err=e))

    def _export_ios_hw_report(self):
        """导出 iOS 硬件监测 CSV 报告（含预览功能）"""
        if not self._ios_hw_history_times:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_no_hw_data"))
            return
        default_name = f"ios_hw_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        default_path = os.path.expanduser(f"~/Desktop/{default_name}")
        try:
            udid = self._get_ios_hw_selected_device() or ""
            csv_rows: list[list] = []
            csv_rows.append(["# iOS 硬件监测报告"])
            csv_rows.append(["# 导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            csv_rows.append(["# 设备 UDID", udid])
            csv_rows.append(["# 采样数", len(self._ios_hw_history_times)])
            csv_rows.append([])

            # 汇总统计
            def _stats(vals):
                if not vals:
                    return 0, 0, 0, 0
                return (round(sum(vals) / len(vals), 2), round(max(vals), 2),
                        round(min(vals), 2), round(statistics_stdev(vals), 2))

            cpu_avg, cpu_max, cpu_min, cpu_std = _stats(self._ios_hw_history_cpu_usage)
            gpu_avg, gpu_max, gpu_min, gpu_std = _stats(self._ios_hw_history_gpu)
            mem_avg, mem_max, mem_min, mem_std = _stats(self._ios_hw_history_mem)

            csv_rows.append(["# ===== 使用率汇总统计 ====="])
            csv_rows.append(["指标", "平均值", "最大值", "最小值", "标准差"])
            csv_rows.append(["CPU 使用率(%)", cpu_avg, cpu_max, cpu_min, cpu_std])
            csv_rows.append(["GPU 利用率(%)", gpu_avg, gpu_max, gpu_min, gpu_std])
            csv_rows.append(["内存使用率(%)", mem_avg, mem_max, mem_min, mem_std])
            csv_rows.append([])

            csv_rows.append(["# ===== 时间序列数据 ====="])
            csv_rows.append(["时间(秒)", "CPU使用率(%)", "GPU利用率(%)", "内存使用率(%)"])
            for i in range(len(self._ios_hw_history_times)):
                csv_rows.append([
                    f"{self._ios_hw_history_times[i]:.2f}",
                    f"{self._ios_hw_history_cpu_usage[i]:.1f}",
                    f"{self._ios_hw_history_gpu[i]:.1f}",
                    f"{self._ios_hw_history_mem[i]:.1f}",
                ])
            saved = self._preview_csv(self._tr("preview_ios_hw_csv"), csv_rows, default_path)
            if saved:
                # CSV 导出附带曲线图 JPG
                try:
                    pm = self._render_hw_plots_pixmap("ios")
                    if pm is not None:
                        img_path = os.path.splitext(saved)[0] + "_charts.jpg"
                        if pm.save(img_path, "JPG", 92):
                            self._ios_log(f"📤 曲线图已导出: {img_path}")
                except Exception as _ie:
                    log_exception(_ie, "iOS 硬件 CSV 附带曲线图导出失败")
                self._ios_log(f"✅ iOS 硬件监测 CSV 已导出: {saved}")
                QMessageBox.information(self, self._tr("msg_export_success"), self._tr("msg_export_success_csv").format(path=saved))
        except Exception as e:
            log_exception(e, "iOS 硬件 CSV 导出失败")
            QMessageBox.critical(self, self._tr("msg_export_failed"), self._tr("msg_export_failed_csv").format(err=e))

    # ==================== iOS 历史记录 ====================

    def _ios_history_refresh_lists(self):
        """刷新 iOS 历史记录列表（与 Tab 3 安卓历史列表一致：最新在前，#5-#1 编号）"""
        try:
            self.ios_hist_fps_list.clear()
            for i, rpt in enumerate(reversed(self._ios_fps_reports)):
                dt = rpt.get("start_time") or rpt.get("start_dt")
                dt_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "未知时间"
                app = rpt.get("package") or rpt.get("app_name", "?")
                s = rpt.get("summary", {})
                avg = s.get("avg_fps", 0)
                dur = rpt.get("duration_sec", 0)
                dur_str = f"{dur//60}分{dur%60}秒" if dur >= 60 else f"{dur}秒"
                text = f"#{5-i}  {dt_str}\n   🎮 {app}  |  平均 {avg} FPS  |  {dur_str}"
                item = QListWidgetItem(text)
                item.setFont(QFont("Menlo", 12))
                item.setForeground(QColor("#1565C0"))
                item.setData(Qt.UserRole, rpt)
                self.ios_hist_fps_list.addItem(item)
        except Exception:
            pass
        try:
            self.ios_hist_hw_list.clear()
            for i, rpt in enumerate(reversed(self._ios_hw_reports)):
                dt = rpt.get("start_time") or rpt.get("start_dt")
                dt_str = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "未知时间"
                dur = rpt.get("duration_sec", 0)
                dur_str = f"{dur//60}分{dur%60}秒" if dur >= 60 else f"{dur}秒"
                n = len(rpt.get("times", []))
                gpu_avg = "--"
                fs = rpt.get("freq_summary", {})
                if fs and "GPU 利用率(%)" in fs:
                    gpu_avg = f"{fs['GPU 利用率(%)']['avg']:.1f}%"
                elif not fs and rpt.get("gpu_usage"):
                    gpu_vals = rpt.get("gpu_usage", [])
                    gpu_avg = f"{sum(gpu_vals)/len(gpu_vals):.1f}%" if gpu_vals else "--"
                cpu_count = "CPU/GPU/内存"
                text = f"#{5-i}  {dt_str}\n   🔧 {cpu_count} 监测  |  GPU 均用 {gpu_avg}  |  {dur_str}"
                item = QListWidgetItem(text)
                item.setFont(QFont("Menlo", 12))
                item.setForeground(QColor("#7B1FA2"))
                item.setData(Qt.UserRole, rpt)
                self.ios_hist_hw_list.addItem(item)
        except Exception:
            pass

    def _ios_history_clear_details(self):
        """清空 iOS 历史详情区"""
        try:
            # 清空摘要
            while self.ios_hist_summary_layout.count():
                item = self.ios_hist_summary_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.ios_hist_table.setRowCount(0)
            self.ios_hist_plot.clear()
            self.ios_hist_plot.addLegend()
        except Exception:
            pass

    def _ios_history_on_fps_clicked(self, item):
        """点击 iOS 帧率历史记录（与 Tab 3 安卓 FPS 详情页结构一致）"""
        rpt = item.data(Qt.UserRole)
        if not rpt:
            return
        self._ios_history_clear_details()
        dt = rpt.get("start_time") or rpt.get("start_dt")
        end_dt = rpt.get("end_time")
        dur = rpt.get("duration_sec", 0)
        dur_str = f"{dur//60:02d}:{dur%60:02d}" if dur < 3600 else f"{dur//3600:02d}:{(dur%3600)//60:02d}:{dur%60:02d}"
        app = rpt.get("package") or rpt.get("app_name", "--")
        device = rpt.get("device_id", "--")
        device_show = device[:18] if len(device) <= 18 else device[:15] + "..."
        s = rpt.get("summary", {})
        fps_avg = s.get("avg_fps", "--")
        low_1 = s.get("low_1_fps", "--")
        low_01 = s.get("low_01_fps", "--")
        jank_rate = s.get("jank_rate", "--")
        tstr = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "--"
        test_app_show = app[:20] if len(app) <= 20 else app[:17] + "..."
        jr_color = "#D32F2F" if isinstance(jank_rate, (int, float)) and jank_rate >= 5 else "#2E7D32"
        summary_rows = [
            ("记录类型", "🎮 帧率测试", "#1565C0"),
            ("开始时间", tstr, "#475569"),
            ("设备", device_show, "#475569"),
            ("测试时长", dur_str, "#0277BD"),
            ("测试应用", test_app_show, "#6A1B9A"),
            ("平均FPS", str(fps_avg), "#2E7D32"),
            ("1% Low", str(low_1), "#E65100"),
            ("0.1% Low", str(low_01), "#BF360C"),
            ("卡顿率", str(jank_rate) + "%" if isinstance(jank_rate, (int, float)) else str(jank_rate), jr_color),
        ]
        self._ios_history_set_summary(summary_rows)
        # 统计表
        table_rows = [
            ("平均 FPS", s.get("avg_fps", "--")),
            ("最低 FPS", s.get("min_fps", "--")),
            ("最高 FPS", s.get("max_fps", "--")),
            ("1% Low FPS", s.get("low_1_fps", "--")),
            ("0.1% Low FPS", s.get("low_01_fps", "--")),
            ("FPS 标准差", s.get("std_fps", "--")),
            ("卡顿帧数", s.get("jank_count", "--")),
            ("卡顿率 (%)", s.get("jank_rate", "--")),
            ("P95 帧时 (ms)", s.get("p95_frame_ms", "--")),
            ("P99 帧时 (ms)", s.get("p99_frame_ms", "--")),
            ("FPS 跌落次数", s.get("fps_drop_count", "--")),
            ("测试时长 (秒)", dur if dur else s.get("duration_sec", "--")),
            ("采样点数量", len(rpt.get("times", []))),
            ("开始时间", tstr),
            ("结束时间", end_dt.strftime("%H:%M:%S") if end_dt else "--"),
        ]
        self._ios_history_set_table(table_rows)
        # 曲线（使用相对时间）
        times = rpt.get("times", [])
        fps_vals = rpt.get("fps", [])
        avg_vals = rpt.get("avg_fps", [])
        if times:
            t0 = times[0]
            xs = [t - t0 for t in times]
            self.ios_hist_plot.plot(xs, fps_vals, pen=mkPen('#2196F3', width=2), name=self._tr("legend_instant_fps"))
            self.ios_hist_plot.plot(xs, avg_vals, pen=mkPen('#FF9800', width=2, style=Qt.DashLine), name=self._tr("legend_avg_fps"))
            self.ios_hist_plot.addLegend()
            self.ios_hist_plot.setTitle(self._tr("chart_ios_fps_series").format(time=tstr[:16]))
            self.ios_hist_plot.setLabel('left', 'FPS')
            self.ios_hist_plot.setLabel('bottom', self._tr("lbl_axis_time"))

    def _ios_history_on_hw_clicked(self, item):
        """点击 iOS 硬件历史记录（与 Tab 3 安卓 HW 详情页结构对齐）"""
        rpt = item.data(Qt.UserRole)
        if not rpt:
            return
        self._ios_history_clear_details()
        dt = rpt.get("start_time") or rpt.get("start_dt")
        end_dt = rpt.get("end_time")
        dur = rpt.get("duration_sec", 0)
        dur_str = f"{dur//60:02d}:{dur%60:02d}" if dur < 3600 else f"{dur//3600:02d}:{(dur%3600)//60:02d}:{dur%60:02d}"
        tstr = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "--"
        device = rpt.get("device_id", "--")
        device_show = device[:18] if len(device) <= 18 else device[:15] + "..."
        cpu_vals = rpt.get("cpu_usage", [])
        gpu_vals = rpt.get("gpu_usage", [])
        mem_vals = rpt.get("mem_pct", [])
        n = len(rpt.get("times", []))
        n_cluster_label = f"{len(cpu_vals and [1])}" if cpu_vals else "0"
        n_gpu_label = len(gpu_vals) if gpu_vals else 0
        summary_rows = [
            ("记录类型", "🔧 CPU/GPU 监测", "#7B1FA2"),
            ("开始时间", tstr, "#475569"),
            ("设备", device_show, "#475569"),
            ("监测时长", dur_str, "#6A1B9A"),
            ("CPU 集群数", "使用率", "#1565C0"),
            ("GPU 采样点", str(n_gpu_label), "#00838F"),
            ("总采样点", str(n), "#37474F"),
            ("结束时间", end_dt.strftime("%H:%M:%S") if end_dt else "--", "#475569"),
        ]
        self._ios_history_set_summary(summary_rows)
        # 频率统计摘要 + 统计表
        fs = rpt.get("freq_summary", {})
        table_rows = [
            ("开始时间", tstr),
            ("结束时间", end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "--"),
            ("监测时长 (秒)", str(dur)),
            ("采样点数", str(n)),
            ("— CPU/GPU/内存 使用率统计 (%) —", ""),
        ]
        for key, short in [("CPU 使用率(%)", "CPU"), ("GPU 利用率(%)", "GPU"), ("内存 使用率(%)", "内存")]:
            if key in fs:
                st = fs[key]
                table_rows.append((f"{short} 平均(%)", f"{st['avg']:.1f}"))
                table_rows.append((f"{short} 最大/最小(%)", f"{st['max']:.1f} / {st['min']:.1f}"))
                table_rows.append((f"{short} 标准差(%)", f"{st['std']:.1f}"))
            else:
                arr = {"CPU": cpu_vals, "GPU": gpu_vals, "内存": mem_vals}.get(short, [])
                if arr:
                    avg = sum(arr) / len(arr)
                    mx = max(arr)
                    mn = min(arr)
                    sd = (sum((x - avg) ** 2 for x in arr) / len(arr)) ** 0.5
                    table_rows.append((f"{short} 平均(%)", f"{avg:.1f}"))
                    table_rows.append((f"{short} 最大/最小(%)", f"{mx:.1f} / {mn:.1f}"))
                    table_rows.append((f"{short} 标准差(%)", f"{sd:.1f}"))
        self._ios_history_set_table(table_rows)
        # 曲线
        times = rpt.get("times", [])
        if times:
            self.ios_hist_plot.plot(times, cpu_vals, pen=mkPen('#2196F3', width=2), name=self._tr("legend_cpu_usage_pct"))
            self.ios_hist_plot.plot(times, gpu_vals, pen=mkPen('#00838F', width=2, style=Qt.DashLine), name=self._tr("legend_gpu_usage_pct"))
            self.ios_hist_plot.plot(times, mem_vals, pen=mkPen('#4CAF50', width=2), name=self._tr("legend_mem_usage_pct"))
            self.ios_hist_plot.addLegend()
            self.ios_hist_plot.setTitle(self._tr("chart_ios_hw_series").format(time=tstr[:16]))
            self.ios_hist_plot.setLabel('left', self._tr("lbl_axis_usage"))
            self.ios_hist_plot.setLabel('bottom', self._tr("lbl_axis_time"))

    def _ios_history_set_summary(self, rows):
        """设置 iOS 历史摘要区（与 Tab3 结构一致）"""
        while self.ios_hist_summary_layout.count():
            item = self.ios_hist_summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, (label, value, color) in enumerate(rows):
            row = i // 2
            col_pair = (i % 2) * 2
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"font-size: 13px; color: {self._fg_muted()}; font-weight: bold;")
            val = QLabel(str(value))
            val.setFont(QFont("Menlo", 15, QFont.Bold))
            val.setStyleSheet(f"color: {color};")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.ios_hist_summary_layout.addWidget(lbl, row, col_pair)
            self.ios_hist_summary_layout.addWidget(val, row, col_pair + 1)

    def _ios_history_set_table(self, rows):
        """设置 iOS 历史统计表（与 Tab3 风格一致）"""
        self.ios_hist_table.setRowCount(len(rows))
        for i, (m, v) in enumerate(rows):
            item_m = QTableWidgetItem(str(m))
            item_v = QTableWidgetItem(str(v))
            item_m.setFont(QFont("Menlo", 12))
            item_v.setFont(QFont("Menlo", 12, QFont.Bold))
            item_v.setForeground(QColor("#0277BD"))
            self.ios_hist_table.setItem(i, 0, item_m)
            self.ios_hist_table.setItem(i, 1, item_v)

    def _ios_history_add_summary(self, key: str, value):
        """兼容旧方法，转发到 _ios_history_set_summary 单条版本（保留防止外部调用）"""
        self._ios_history_set_summary([(key, value, self._fg())])

    def _history_export_selected(self):
        """导出选中的安卓历史记录为 CSV"""
        items = []
        if self.hist_fps_list.currentItem():
            items.append(("fps", self.hist_fps_list.currentItem().data(Qt.UserRole)))
        if self.hist_hw_list.currentItem():
            items.append(("hw", self.hist_hw_list.currentItem().data(Qt.UserRole)))
        if not items:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_history"))
            return
        default_path = os.path.expanduser(
            f"~/Desktop/history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self, self._tr("dlg_export_history"), default_path, "CSV (*.csv)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                for typ, rpt in items:
                    if typ == "fps":
                        w.writerow(["=== 安卓帧率测试历史报告 ==="])
                        start_dt = rpt.get("start_time") or rpt.get("start_dt")
                        end_dt = rpt.get("end_time")
                        w.writerow(["开始时间", start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else "--"])
                        w.writerow(["结束时间", end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "--"])
                        w.writerow(["测试时长(秒)", rpt.get("duration_sec", "--")])
                        w.writerow(["设备", rpt.get("device_id", "--")])
                        w.writerow(["测试应用", rpt.get("package", "--")])
                        w.writerow([])
                        w.writerow(["=== 汇总统计 ==="])
                        s = rpt.get("summary", {})
                        for k, v in s.items():
                            w.writerow([k, v])
                        w.writerow([])
                        w.writerow(["=== 时间序列 ==="])
                        w.writerow(["时间戳(秒)", "瞬时FPS", "平均FPS"])
                        times = rpt.get("times", [])
                        fps_vals = rpt.get("fps", [])
                        avg_vals = rpt.get("avg_fps", [])
                        t0 = times[0] if times else 0
                        for i in range(len(times)):
                            fps_v = fps_vals[i] if i < len(fps_vals) else ""
                            avg_v = avg_vals[i] if i < len(avg_vals) else ""
                            w.writerow([f"{times[i]-t0:.1f}", fps_v, avg_v])
                    else:
                        w.writerow(["=== 安卓 CPU/GPU 监测历史报告 ==="])
                        start_dt = rpt.get("start_time") or rpt.get("start_dt")
                        end_dt = rpt.get("end_time")
                        w.writerow(["开始时间", start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else "--"])
                        w.writerow(["结束时间", end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "--"])
                        w.writerow(["监测时长(秒)", rpt.get("duration_sec", "--")])
                        w.writerow(["设备", rpt.get("device_id", "--")])
                        w.writerow([])
                        w.writerow(["=== 频率统计 (MHz) ==="])
                        w.writerow(["指标", "平均", "最大", "最小", "标准差"])
                        fs = rpt.get("freq_summary", {})
                        for k, v in fs.items():
                            if isinstance(v, dict):
                                w.writerow([k, f"{v.get('avg',0):.1f}", f"{v.get('max',0):.0f}", f"{v.get('min',0):.0f}", f"{v.get('std',0):.1f}"])
                        w.writerow([])
                        w.writerow(["=== 时间序列 ==="])
                        times = rpt.get("times", [])
                        cpu_usage = rpt.get("cpu_usage", [])
                        gpu_usage = rpt.get("gpu_usage", [])
                        mem_pct = rpt.get("mem_pct", [])
                        cpu_freqs = rpt.get("cpu_freqs", [])
                        gpu_freqs = rpt.get("gpu_freqs", [])
                        temps = rpt.get("temps", [])
                        # 构建表头
                        header = ["时间(秒)"]
                        cluster_labels = []
                        if cpu_freqs:
                            first = cpu_freqs[0] if cpu_freqs else []
                            for ci, cf in enumerate(first):
                                lbl = f"CPU{ci}(MHz)"
                                cluster_labels.append(lbl)
                                header.append(lbl)
                        header.append("GPU频率(MHz)")
                        if cpu_usage:
                            header.append("CPU使用率(%)")
                        if mem_pct:
                            header.append("内存使用率(%)")
                        if temps:
                            header.append("CPU温度(°C)")
                        w.writerow(header)
                        for i in range(len(times)):
                            row = [f"{times[i]:.1f}"]
                            for ci, _ in enumerate(cluster_labels):
                                cf_list = cpu_freqs[i] if i < len(cpu_freqs) else []
                                row.append(f"{cf_list[ci]:.0f}" if ci < len(cf_list) else "")
                            row.append(f"{gpu_freqs[i]:.0f}" if i < len(gpu_freqs) else "")
                            if cpu_usage:
                                row.append(f"{cpu_usage[i]:.1f}" if i < len(cpu_usage) else "")
                            if mem_pct:
                                row.append(f"{mem_pct[i]:.1f}" if i < len(mem_pct) else "")
                            if temps:
                                row.append(f"{temps[i]:.1f}" if i < len(temps) else "")
                            w.writerow(row)
                    w.writerow([])
            self._log(f"📤 历史 CSV 已导出: {file_path}")
            QMessageBox.information(self, self._tr("msg_export_success"), self._tr("msg_export_success_csv").format(path=file_path))
        except Exception as e:
            log_exception(e, "安卓历史 CSV 导出失败")
            QMessageBox.critical(self, self._tr("msg_export_failed"), self._tr("msg_export_failed_csv").format(err=e))

    def _ios_history_export_selected(self):
        """导出选中的 iOS 历史记录为 CSV（与 Tab3 安卓导出格式对齐）"""
        items = []
        if self.ios_hist_fps_list.currentItem():
            items.append(("fps", self.ios_hist_fps_list.currentItem().data(Qt.UserRole)))
        if self.ios_hist_hw_list.currentItem():
            items.append(("hw", self.ios_hist_hw_list.currentItem().data(Qt.UserRole)))
        if not items:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_history"))
            return
        default_path = os.path.expanduser(
            f"~/Desktop/ios_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出 iOS 历史 CSV", default_path, "CSV 文件 (*.csv)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                for typ, rpt in items:
                    if typ == "fps":
                        w.writerow(["=== iOS 帧率测试历史报告 ==="])
                        start_dt = rpt.get("start_time") or rpt.get("start_dt")
                        end_dt = rpt.get("end_time")
                        w.writerow(["开始时间", start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else "--"])
                        w.writerow(["结束时间", end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "--"])
                        w.writerow(["测试时长(秒)", rpt.get("duration_sec", "--")])
                        w.writerow(["设备", rpt.get("device_id", "--")])
                        w.writerow(["测试应用", rpt.get("package") or rpt.get("app_name", "--")])
                        w.writerow([])
                        w.writerow(["=== 汇总统计 ==="])
                        s = rpt.get("summary", {})
                        for k, v in s.items():
                            w.writerow([k, v])
                        w.writerow([])
                        w.writerow(["=== 时间序列 ==="])
                        w.writerow(["时间戳(秒)", "瞬时FPS", "平均FPS"])
                        times = rpt.get("times", [])
                        fps_vals = rpt.get("fps", [])
                        avg_vals = rpt.get("avg_fps", [])
                        t0 = times[0] if times else 0
                        for i in range(len(times)):
                            fps_v = fps_vals[i] if i < len(fps_vals) else ""
                            avg_v = avg_vals[i] if i < len(avg_vals) else ""
                            w.writerow([f"{times[i]-t0:.1f}", fps_v, avg_v])
                    else:
                        w.writerow(["=== iOS CPU/GPU 监测历史报告 ==="])
                        start_dt = rpt.get("start_time") or rpt.get("start_dt")
                        end_dt = rpt.get("end_time")
                        w.writerow(["开始时间", start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else "--"])
                        w.writerow(["结束时间", end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "--"])
                        w.writerow(["监测时长(秒)", rpt.get("duration_sec", "--")])
                        w.writerow(["设备", rpt.get("device_id", "--")])
                        w.writerow([])
                        w.writerow(["=== 使用率统计 (%) ==="])
                        w.writerow(["指标", "平均", "最大", "最小", "标准差"])
                        fs = rpt.get("freq_summary", {})
                        cpu_vals = rpt.get("cpu_usage", [])
                        gpu_vals = rpt.get("gpu_usage", [])
                        mem_vals = rpt.get("mem_pct", [])
                        def _fallback_stat(arr):
                            if not arr:
                                return {"avg": 0, "max": 0, "min": 0, "std": 0}
                            a = sum(arr)/len(arr)
                            mx = max(arr); mn = min(arr)
                            sd = (sum((x-a)**2 for x in arr)/len(arr))**0.5
                            return {"avg": a, "max": mx, "min": mn, "std": sd}
                        labels = [("CPU 使用率(%)", "CPU 使用率(%)", cpu_vals),
                                  ("GPU 利用率(%)", "GPU 利用率(%)", gpu_vals),
                                  ("内存 使用率(%)", "内存 使用率(%)", mem_vals)]
                        for csv_key, rpt_key, arr in labels:
                            st = fs.get(rpt_key) or _fallback_stat(arr)
                            w.writerow([csv_key, f"{st['avg']:.1f}", f"{st['max']:.1f}", f"{st['min']:.1f}", f"{st['std']:.1f}"])
                        w.writerow([])
                        w.writerow(["=== 时间序列 ==="])
                        header = ["时间(秒)", "CPU使用率(%)", "GPU利用率(%)", "内存使用率(%)"]
                        w.writerow(header)
                        times = rpt.get("times", [])
                        for i in range(len(times)):
                            row = [f"{times[i]:.1f}"]
                            row.append(f"{cpu_vals[i]:.1f}" if i < len(cpu_vals) else "")
                            row.append(f"{gpu_vals[i]:.1f}" if i < len(gpu_vals) else "")
                            row.append(f"{mem_vals[i]:.1f}" if i < len(mem_vals) else "")
                            w.writerow(row)
                    w.writerow([])
            self._ios_log(f"✅ iOS 历史 CSV 已导出: {file_path}")
            QMessageBox.information(self, self._tr("msg_export_success"), self._tr("msg_export_success_csv").format(path=file_path))
        except Exception as e:
            log_exception(e, "iOS 历史 CSV 导出失败")
            QMessageBox.critical(self, self._tr("msg_export_failed"), self._tr("msg_export_failed_csv").format(err=e))

    # ==================== iOS 设备管理 ====================

    def _ios_log(self, message: str):
        """iOS 日志输出：UI 文本框 + 文件"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.ios_log_text.append(f"[{timestamp}] {message}")
            self.ios_log_text.verticalScrollBar().setValue(
                self.ios_log_text.verticalScrollBar().maximum()
            )
        except Exception:
            pass
        try:
            if message.startswith("❌") or "失败" in message or "错误" in message or "异常" in message:
                _logger.error(f"[iOS] {message}")
            elif message.startswith("⚠️"):
                _logger.warning(f"[iOS] {message}")
            else:
                _logger.info(f"[iOS] {message}")
        except Exception:
            pass

    def _refresh_ios_devices(self):
        """刷新 iOS 设备列表"""
        self._ios_log("🔄 正在扫描 iOS 设备...")
        devices = self.ios_client.get_devices()

        _ios_combos = [self.ios_device_combo, self.ios_hw_device_combo, self.ios_info_device_combo]
        _ios_load_combo = getattr(self, "ios_load_device_combo", None)
        if _ios_load_combo is not None:
            _ios_combos.append(_ios_load_combo)
        for combo in _ios_combos:
            combo.clear()

        if not devices:
            for combo in _ios_combos:
                combo.addItem(self._tr("combo_no_ios_device"))
            self.ios_device_info_label.setText(self._tr("stat_device_disconnected"))
            self._ios_log("⚠️ 未检测到 iOS 设备")
            return

        for udid, status in devices:
            label = f"{udid[:16]}... ({status})"
            for combo in _ios_combos:
                combo.addItem(label, udid)

        # 获取设备信息显示在标签上
        try:
            info = self.ios_client.get_device_info(devices[0][0])
            if "error" not in info:
                self.ios_device_info_label.setText(
                    f"设备信息: {info.get('display_name', '未知')} | "
                    f"iOS {info.get('ios_version', '?')} | "
                    f"{info.get('chip_name', '?')}"
                )
        except Exception:
            pass
        self._ios_log(f"✅ 检测到 {len(devices)} 台 iOS 设备")

    def _refresh_ios_apps(self):
        """列出 iOS 已安装应用"""
        udid = self._get_ios_selected_device()
        if not udid:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_ios_device"))
            return
        self._ios_log("📋 正在获取已安装应用列表...")
        self.ios_list_apps_btn.setEnabled(False)
        try:
            apps = self.ios_client.get_installed_apps(udid)
            self.ios_app_combo.clear()
            if apps:
                for app in apps:
                    self.ios_app_combo.addItem(app)
                self._ios_log(f"✅ 获取到 {len(apps)} 个应用")
            else:
                self.ios_app_combo.addItem(self._tr("combo_no_app_list"))
                self._ios_log("⚠️ 未获取到应用列表")
        except Exception as e:
            self._ios_log(f"❌ 获取应用列表失败: {e}")
        finally:
            self.ios_list_apps_btn.setEnabled(True)

    def _detect_ios_foreground_app(self):
        """自动识别 iOS 设备当前前台运行的应用"""
        udid = self._get_ios_selected_device()
        if not udid:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_ios_device"))
            return
        self._ios_log("📱 正在识别前台应用...")
        self.ios_foreground_btn.setEnabled(False)
        try:
            result = self.ios_client.get_foreground_app(udid)
            if result and "error" not in result:
                app_name = result.get("name", "")
                bundle_id = result.get("bundle_id", "")
                pid = result.get("pid", 0)
                self._ios_log(f"✅ 前台应用: {app_name} (PID: {pid}, Bundle: {bundle_id})")
                # 自动填入应用选择框
                self.ios_app_combo.setEditText(app_name)
            elif result and "error" in result:
                err = result["error"]
                if "tunneld" in err.lower() or "sudo" in err.lower():
                    QMessageBox.warning(
                        self, "需要启动 tunneld",
                        f"iOS 17+ 识别前台应用需要 RSD 隧道。\n\n"
                        f"请在终端执行:\n  sudo pymobiledevice3 remote tunneld\n\n"
                        f"详细错误:\n{err}"
                    )
                else:
                    QMessageBox.warning(self, self._tr("msg_ios_foreground_failed"), self._tr("msg_ios_foreground_failed_body").format(err=err))
                self._ios_log(f"❌ 识别前台应用失败: {err}")
            else:
                self._ios_log("⚠️ 未识别到前台应用（可能设备在主屏幕）")
                QMessageBox.information(self, self._tr("msg_ios_foreground_title"), self._tr("msg_ios_foreground_none"))
        except Exception as e:
            log_exception(e, "识别前台应用异常")
            self._ios_log(f"❌ 识别前台应用异常: {e}")
        finally:
            self.ios_foreground_btn.setEnabled(True)

    def _get_ios_selected_device(self) -> Optional[str]:
        idx = self.ios_device_combo.currentIndex()
        if idx < 0:
            return None
        return self.ios_device_combo.itemData(idx)

    def _get_ios_hw_selected_device(self) -> Optional[str]:
        idx = self.ios_hw_device_combo.currentIndex()
        if idx < 0:
            return None
        return self.ios_hw_device_combo.itemData(idx)

    # ==================== iOS 测试控制 ====================

    def _start_ios_test(self):
        """开始 iOS 帧率测试"""
        try:
            self._start_ios_test_inner()
        except Exception as e:
            log_exception(e, "iOS 帧率测试启动异常")
            try:
                self.ios_start_btn.setEnabled(True)
                self.ios_stop_btn.setEnabled(False)
                self.ios_clear_btn.setEnabled(True)
                self.ios_device_combo.setEnabled(True)
            except Exception:
                pass
            self._ios_log(f"❌ 开始 iOS 帧率测试失败: {e}")
            QMessageBox.critical(self, self._tr("msg_error"),self._tr("msg_start_ios_fps_failed").format(err=e))

    def _start_ios_test_inner(self):
        udid = self._get_ios_selected_device()
        if not udid:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_ios_device"))
            return

        # 优先使用下拉框选择的刷新率，否则从设备信息获取
        refresh_rate = self.ios_refresh_rate_combo.currentData() or 60
        poll_interval = self.ios_interval_combo.currentData() or 1.0
        try:
            info = self.ios_client.get_device_info(udid)
            if "refresh_rate" in info and info["refresh_rate"] > refresh_rate:
                # 如果设备支持更高刷新率，自动切换下拉框
                dev_rate = info["refresh_rate"]
                for i in range(self.ios_refresh_rate_combo.count()):
                    if self.ios_refresh_rate_combo.itemData(i) == dev_rate:
                        self.ios_refresh_rate_combo.setCurrentIndex(i)
                        refresh_rate = dev_rate
                        break
        except Exception:
            pass

        self.ios_analyzer.refresh_rate = refresh_rate
        self.ios_analyzer.frame_threshold_ms = 1000.0 / refresh_rate * 1.2
        # 更新卡顿阈值线
        self.ios_threshold_line.setPos(1000.0 / refresh_rate)

        self._ios_history_times.clear()
        self._ios_history_fps.clear()
        self._ios_history_avg_fps.clear()
        self._ios_history_stats.clear()
        self.ios_fps_curve.setData([], [])
        self.ios_avg_curve.setData([], [])
        self.ios_frame_bar.setOpts(x=[], height=[], width=0.8)
        self.ios_analyzer.reset()

        self._ios_log(f"🚀 开始 iOS 帧率测试 (刷新率: {refresh_rate}Hz, 间隔: {poll_interval}s)")

        self.ios_fps_thread = IOSFPSCollectorThread(
            self.ios_client, udid, self.ios_analyzer, refresh_rate,
            poll_interval=poll_interval
        )
        self.ios_fps_thread.stats_ready.connect(self._on_ios_fps_stats)
        self.ios_fps_thread.log_message.connect(self._ios_log)
        self.ios_fps_thread.error_occurred.connect(
            lambda e: self._ios_log(f"❌ {e}")
        )
        self.ios_fps_thread.finished_signal.connect(self._on_ios_fps_finished)
        self.ios_fps_thread.start()

        self.ios_start_btn.setEnabled(False)
        self.ios_stop_btn.setEnabled(True)
        self.ios_clear_btn.setEnabled(False)
        self.ios_export_btn.setEnabled(False)
        self.ios_device_combo.setEnabled(False)
        self._ios_test_start_time = time.time()
        self._ios_fps_test_start_dt = datetime.now()
        self.ios_test_timer.start(1000)

        # 联动启动 CPU/GPU 监测
        if not self._ios_linking_start:
            self._ios_linking_start = True
            try:
                if not (self.ios_hw_thread and self.ios_hw_thread.isRunning()):
                    for i in range(self.ios_hw_device_combo.count()):
                        if self.ios_hw_device_combo.itemData(i) == udid:
                            self.ios_hw_device_combo.setCurrentIndex(i)
                            break
                    self._start_ios_hw_monitor()
                    self._ios_log("🔗 已联动启动 CPU/GPU 监测")
            finally:
                self._ios_linking_start = False

    def _stop_ios_test(self):
        """停止 iOS 帧率测试（联动停止 CPU/GPU 监测）"""
        # 立即更新按钮状态，防止重复点击
        try:
            self.ios_start_btn.setEnabled(False)
            self.ios_stop_btn.setEnabled(False)
            self.ios_clear_btn.setEnabled(False)
            self.ios_export_btn.setEnabled(False)
            self.ios_device_combo.setEnabled(False)
        except Exception:
            pass
        if self.ios_fps_thread and self.ios_fps_thread.isRunning():
            self.ios_fps_thread.stop()
            self._ios_log("⏹ 正在停止 iOS 帧率采集...")
            self.ios_fps_thread.wait(3000)
        # 联动停止 CPU/GPU 监测
        if not self._ios_linking_stop:
            self._ios_linking_stop = True
            try:
                if self.ios_hw_thread and self.ios_hw_thread.isRunning():
                    self._stop_ios_hw_monitor()
                    self._ios_log("🔗 已联动停止 CPU/GPU 监测")
            finally:
                self._ios_linking_stop = False

    def _on_ios_fps_stats(self, stats):
        """iOS FPS 统计数据到达"""
        self._ios_history_times.append(stats.timestamp)
        self._ios_history_fps.append(stats.fps)
        self._ios_history_avg_fps.append(stats.avg_fps)
        self._ios_history_stats.append(stats)
        # 防止长时间测试导致历史列表无限增长（保留最近 7200 点 ≈ 2 小时）
        _max_hist = 7200
        if len(self._ios_history_times) > _max_hist:
            overflow = len(self._ios_history_times) - _max_hist
            del self._ios_history_times[:overflow]
            del self._ios_history_fps[:overflow]
            del self._ios_history_avg_fps[:overflow]
            del self._ios_history_stats[:overflow]

        # 更新 FPS 曲线（限制显示点数，避免长时间测试后性能下降）
        max_points = 300
        times = self._ios_history_times[-max_points:]
        t0 = times[0] if times else 0
        xs = [t - t0 for t in times]
        self.ios_fps_curve.setData(xs, self._ios_history_fps[-max_points:])
        self.ios_avg_curve.setData(xs, self._ios_history_avg_fps[-max_points:])

        # 自适应 Y 轴范围（与 Android 侧一致）
        all_fps = self._ios_history_fps[-max_points:] + self._ios_history_avg_fps[-max_points:]
        if all_fps:
            raw_max = max(all_fps) if all_fps else 0
            raw_min = min(all_fps) if all_fps else 0
            ymax = max(raw_max * 1.1, 10.0)
            ymin = min(0, raw_min - 5)
            self.ios_fps_plot.setYRange(ymin, ymax)

        # 更新帧时间分布柱状图（最近 50 帧）
        recent_ft = stats.frame_times[-50:] if stats.frame_times else []
        if recent_ft:
            self.ios_frame_bar.setOpts(
                x=list(range(len(recent_ft))),
                height=recent_ft,
                width=0.8,
            )
            self.ios_frame_plot.setXRange(0, len(recent_ft))
            # 动态调整 Y 轴范围
            max_ft = max(recent_ft) if recent_ft else 33
            self.ios_frame_plot.setYRange(0, max(max_ft * 1.2, 33))

        # 更新统计标签（含 P95/P99）
        label_map = {
            "fps": f"{stats.fps:.1f}", "avg_fps": f"{stats.avg_fps:.1f}",
            "min_fps": f"{stats.min_fps:.1f}", "max_fps": f"{stats.max_fps:.1f}",
            "low_1": f"{stats.low_1_fps:.1f}", "low_01": f"{stats.low_01_fps:.1f}",
            "std_fps": f"{stats.std_fps:.2f}", "jank_count": str(stats.jank_count),
            "total_frames": str(stats.total_frames),
            "jank_rate": f"{stats.jank_rate:.2f}%",
            "p95": f"{stats.percentile_95:.2f}",
            "p99": f"{stats.percentile_99:.2f}",
        }
        for key, text in label_map.items():
            if key in self._ios_stat_labels:
                self._ios_stat_labels[key].setText(text)

        # 更新卡顿率进度条
        jank_pct = min(stats.jank_rate, 100.0)
        self.ios_jank_bar.setValue(int(jank_pct))
        self.ios_jank_bar.setFormat(self._tr("fmt_jank_rate").format(val=f"{stats.jank_rate:.2f}"))
        # 根据卡顿率改变颜色
        if jank_pct < 2:
            chunk_color = "#4CAF50"
        elif jank_pct < 5:
            chunk_color = "#FFC107"
        else:
            chunk_color = "#F44336"
        self.ios_jank_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {self._fg_muted()};
                border-radius: 6px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                color: {self._fg()};
                height: 28px;
            }}
            QProgressBar::chunk {{
                background-color: {chunk_color};
                border-radius: 4px;
            }}
        """)

    def _on_ios_fps_finished(self):
        """iOS 帧率测试结束"""
        # 断开旧线程信号并清理引用
        try:
            if self.ios_fps_thread:
                self.ios_fps_thread.disconnect()
                self.ios_fps_thread.deleteLater()
        except Exception:
            pass
        self.ios_test_timer.stop()
        self.ios_start_btn.setEnabled(True)
        self.ios_stop_btn.setEnabled(False)
        self.ios_clear_btn.setEnabled(True)
        self.ios_export_btn.setEnabled(True)
        self.ios_device_combo.setEnabled(True)
        self._ios_log("✅ iOS 帧率测试已停止")

        summary = self.ios_analyzer.get_summary()
        self._ios_log("=" * 50)
        self._ios_log("📋 iOS 测试摘要:")
        for k, v in summary.items():
            self._ios_log(f"  {k}: {v}")
        self._ios_log("=" * 50)

        # 保存到历史记录
        if self._ios_history_stats:
            device_id = self._get_ios_selected_device() or ""
            app_name = self.ios_app_combo.currentText().strip() or "未知应用"
            start_dt = self._ios_fps_test_start_dt or datetime.now()
            end_dt = datetime.now()
            duration_sec = int((end_dt - start_dt).total_seconds())
            # 深拷贝 stats
            stats_snapshot = []
            for s in self._ios_history_stats:
                stats_snapshot.append({
                    "fps": s.fps, "avg_fps": s.avg_fps, "min_fps": s.min_fps, "max_fps": s.max_fps,
                    "std_fps": s.std_fps, "jank_count": s.jank_count, "total_frames": s.total_frames,
                    "jank_rate": s.jank_rate, "percentile_95": s.percentile_95, "percentile_99": s.percentile_99,
                    "timestamp": s.timestamp
                })
            report = {
                "id": f"fps_{int(start_dt.timestamp())}",
                "type": "fps",
                "start_time": start_dt,
                "end_time": end_dt,
                "duration_sec": duration_sec,
                "device_id": device_id,
                "package": app_name,
                "summary": dict(summary),
                "times": list(self._ios_history_times),
                "fps": list(self._ios_history_fps),
                "avg_fps": list(self._ios_history_avg_fps),
                "stats": stats_snapshot,
            }
            self._ios_fps_reports.append(report)
            self._ios_history_refresh_lists()

        # 综合性能评价（iOS 端）— 用 QTimer.singleShot 延迟弹窗
        def _deferred_ios_eval():
            try:
                device_id = self._get_ios_selected_device() or ""
                device_info = {}
                if device_id and self.ios_client:
                    try:
                        info = self.ios_client.get_device_info(device_id) or {}
                        if "error" not in info:
                            device_info = info
                    except Exception:
                        pass
                refresh_rate = getattr(self.ios_analyzer, "refresh_rate", 60) or 60
                eval_result = self._evaluate_fps_performance(summary, device_info, refresh_rate)
                if eval_result:
                    eval_result["platform"] = "ios"
                    eval_result["device_serial"] = device_id
                    # iOS 选择的应用保存在 ios_app_combo
                    eval_result["app_package"] = self.ios_app_combo.currentData() or self.ios_app_combo.currentText() or ""
                    eval_result["duration_sec"] = int(summary.get("duration_sec", 0))
                    eval_result["start_time"] = datetime.now()
                    eval_result["session_id"] = None
                    self._show_fps_evaluation_dialog(eval_result)
            except Exception as e:
                log_exception(e, "iOS 综合性能评价失败")
        QTimer.singleShot(100, _deferred_ios_eval)

    def _update_ios_duration(self):
        """更新 iOS 测试时长"""
        if self._ios_test_start_time > 0:
            elapsed = int(time.time() - self._ios_test_start_time)
            mins, secs = divmod(elapsed, 60)
            hrs, mins = divmod(mins, 60)
            if hrs > 0:
                self.ios_duration_label.setText(self._tr("fmt_duration_hms").format(h=hrs, m=mins, s=secs))
            else:
                self.ios_duration_label.setText(self._tr("fmt_duration_ms").format(m=mins, s=secs))

    def _clear_ios_fps_data(self):
        """清空 iOS 帧率数据"""
        if self.ios_fps_thread and self.ios_fps_thread.isRunning():
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_test_running"))
            return
        # 联动清空时跳过确认（由联动停止调用）
        if not self._ios_linking_stop and self._ios_history_times:
            reply = QMessageBox.question(
                self, self._tr("msg_confirm_clear"),
                self._tr("msg_confirm_clear_body"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        self._ios_history_times.clear()
        self._ios_history_fps.clear()
        self._ios_history_avg_fps.clear()
        self._ios_history_stats.clear()
        self.ios_fps_curve.setData([], [])
        self.ios_avg_curve.setData([], [])
        self.ios_frame_bar.setOpts(x=[], height=[], width=0.8)
        self.ios_analyzer.reset()
        self.ios_fps_plot.setYRange(0, 60)
        self.ios_frame_plot.setYRange(0, 50)
        for key in self._ios_stat_labels:
            self._ios_stat_labels[key].setText("--")
        self.ios_jank_bar.setValue(0)
        self.ios_jank_bar.setFormat(self._tr("fmt_jank_rate_zero"))
        self.ios_duration_label.setText(self._tr("stat_duration_zero"))
        self._ios_test_start_time = 0
        self._ios_fps_test_start_dt = None
        self._ios_log("🗑 iOS 帧率数据已清空")

    def _on_ios_refresh_rate_changed(self):
        """iOS 屏幕刷新率变更"""
        rate = self.ios_refresh_rate_combo.currentData()
        if rate:
            self.ios_analyzer.refresh_rate = rate
            self.ios_analyzer.frame_threshold_ms = 1000.0 / rate * 1.2
            # 更新卡顿阈值线
            self.ios_threshold_line.setPos(1000.0 / rate)
            self._ios_log(f"📐 屏幕刷新率设为 {rate}Hz, 卡顿阈值 {1000.0/rate:.2f}ms")

    # ==================== iOS CPU/GPU 监测控制 ====================

    def _start_ios_hw_monitor(self):
        """开始 iOS 硬件监测"""
        try:
            self._start_ios_hw_monitor_inner()
        except Exception as e:
            log_exception(e, "iOS 硬件监测启动异常")
            try:
                self.ios_hw_start_btn.setEnabled(True)
                self.ios_hw_stop_btn.setEnabled(False)
                self.ios_hw_status_label.setText(self._tr("stat_start_failed"))
                self.ios_hw_status_label.setStyleSheet("color: #F44336; font-size: 13px;")
            except Exception:
                pass
            self._ios_log(f"❌ iOS 硬件监测启动失败: {e}")
            QMessageBox.critical(self, self._tr("msg_error"),self._tr("msg_start_ios_hw_failed").format(err=e))

    def _start_ios_hw_monitor_inner(self):
        udid = self._get_ios_hw_selected_device()
        if not udid:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_ios_device_monitor"))
            return

        self._ios_hw_history_times.clear()
        self._ios_hw_history_cpu_usage.clear()
        self._ios_hw_history_mem.clear()
        self._ios_hw_history_gpu.clear()
        self._ios_hw_curves.clear()
        self.ios_hw_plot.clear()
        self.ios_hw_plot.addLegend()
        self._ios_hw_plot_start_time = time.time()
        self._ios_hw_start_dt = datetime.now()
        self._ios_hw_monitor_start_dt = datetime.now()

        # 采集间隔（读取硬件监测页下拉框，默认 1.0s）
        poll_interval = 1.0
        if hasattr(self, "ios_hw_interval_combo") and self.ios_hw_interval_combo.currentData():
            poll_interval = float(self.ios_hw_interval_combo.currentData())
        self._ios_log(f"🚀 正在启动 iOS 硬件监测 (需挂载 DDI, 间隔={poll_interval}s)...")

        # 清理旧线程（避免信号累积与内存泄漏）
        if self.ios_hw_thread:
            try:
                if self.ios_hw_thread.isRunning():
                    self.ios_hw_thread.stop()
                    self.ios_hw_thread.wait(2000)
                self.ios_hw_thread.disconnect()
                self.ios_hw_thread.deleteLater()
            except Exception:
                pass
        self.ios_hw_thread = IOSHWMonitorThread(self.ios_client, udid, poll_interval=poll_interval)
        self.ios_hw_thread.hw_data_ready.connect(self._on_ios_hw_data)
        self.ios_hw_thread.error_occurred.connect(lambda e: self._ios_log(f"❌ {e}"))
        self.ios_hw_thread.start_failed.connect(self._on_ios_hw_start_failed)
        self.ios_hw_thread.started_ok.connect(self._on_ios_hw_started)
        self.ios_hw_thread.start()

        self.ios_hw_start_btn.setEnabled(False)
        self.ios_hw_status_label.setText(self._tr("stat_connecting"))
        self.ios_hw_status_label.setStyleSheet("color: #FF9800; font-size: 13px; font-weight: bold;")

    def _on_ios_hw_started(self):
        """iOS 监测会话启动成功"""
        self.ios_hw_stop_btn.setEnabled(True)
        self.ios_hw_status_label.setText(self._tr("stat_monitoring"))
        self.ios_hw_status_label.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")
        self._ios_log("✅ iOS 硬件监测已启动")

    def _on_ios_hw_start_failed(self, error: str):
        """iOS 监测会话启动失败"""
        self.ios_hw_start_btn.setEnabled(True)
        self.ios_hw_status_label.setText(self._tr("stat_start_failed"))
        self.ios_hw_status_label.setStyleSheet("color: #F44336; font-size: 13px;")
        self._ios_log(f"❌ iOS 监测启动失败: {error}")
        log_exception(RuntimeError(error), "iOS DVT 监测启动失败")
        # 用更宽的对话框显示完整错误(含解决方案)
        dlg = QMessageBox(self)
        dlg.setWindowTitle(self._tr("msg_ios_monitor_start_failed_title"))
        dlg.setIcon(QMessageBox.Critical)
        dlg.setText(self._tr("msg_ios_monitor_start_failed_text"))
        dlg.setInformativeText(
            f"\n{error}\n\n"
            f"快速排查:\n"
            f"• 设备已开启开发者模式 + 信任此电脑\n"
            f"• iOS 17+ 需在终端运行: sudo pymobiledevice3 tunnel start\n"
            f"• DDI 文件缓存目录:\n  {self.ios_client.get_ddi_cache_dir()}\n"
            f"  (需要 Image.dmg / BuildManifest.plist / Image.trustcache)"
        )
        dlg.setStandardButtons(QMessageBox.Ok)
        dlg.exec_()

    def _check_ios_ddi_status(self):
        """检查 iOS 设备 DDI 挂载状态 + 本地缓存"""
        udid = self._get_ios_hw_selected_device()
        if not udid:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_ios_device"))
            return
        self._ios_log("🔍 正在检查 DDI 挂载状态...")
        self.ios_ddi_check_btn.setEnabled(False)
        try:
            status = self.ios_client.check_ddi_status(udid)
            cache_dir = status.get("cache_dir", "")
            cache_ok = status.get("cache_files_exist", False)
            mounted = status.get("mounted", False)
            mount_type = status.get("mount_type", "")
            err = status.get("error", "")

            cache_status = self._tr("lbl_cache_ok") if cache_ok else self._tr("lbl_cache_missing")
            if mounted:
                msg = self._tr("ddi_mounted").format(mount_type=mount_type, cache_dir=cache_dir, cache_status=cache_status)
                self._ios_log(f"✅ DDI 已挂载 ({mount_type})")
            elif err:
                msg = self._tr("ddi_not_mounted_err").format(err=err, cache_dir=cache_dir, cache_status=cache_status)
                self._ios_log(f"⚠️ DDI 未挂载 (连接错误)")
            else:
                msg = self._tr("ddi_not_mounted").format(cache_dir=cache_dir, cache_status=cache_status)
                self._ios_log(f"⚠️ DDI 未挂载, 缓存文件: {'齐全' if cache_ok else '缺失'}")
            QMessageBox.information(self, self._tr("msg_ddi_title"), msg)
        except Exception as e:
            log_exception(e, "检查 DDI 状态失败")
            QMessageBox.critical(self, self._tr("msg_error"), self._tr("msg_ddi_check_failed").format(err=e))
        finally:
            self.ios_ddi_check_btn.setEnabled(True)

    def _on_ios_hw_data(self, data: dict):
        """iOS 硬件监测数据到达"""
        elapsed = time.time() - self._ios_hw_plot_start_time
        self._ios_hw_history_times.append(elapsed)
        cpu_usage = max(0.0, min(100.0, float(data.get("cpu_usage", 0.0) or 0.0)))
        self._ios_hw_history_cpu_usage.append(cpu_usage)
        mem_pct = max(0.0, min(100.0, float(data.get("mem_used_pct", 0.0) or 0.0)))
        self._ios_hw_history_mem.append(mem_pct)
        gpu_usage = max(0.0, min(100.0, float(data.get("gpu_usage", 0.0) or 0.0)))
        self._ios_hw_history_gpu.append(gpu_usage)

        # 更新曲线（iOS：红实线CPU + 品红虚线GPU + 绿色点线内存，保证不重合）
        if "cpu" not in self._ios_hw_curves:
            self._ios_hw_curves["cpu"] = self.ios_hw_plot.plot(
                pen=mkPen('#ef4444', width=3), name=self._tr("legend_cpu_usage"))
        if "gpu" not in self._ios_hw_curves:
            self._ios_hw_curves["gpu"] = self.ios_hw_plot.plot(
                pen=mkPen('#ec4899', width=2.8, style=Qt.DashLine), name=self._tr("legend_gpu_usage"))
        if "mem" not in self._ios_hw_curves:
            self._ios_hw_curves["mem"] = self.ios_hw_plot.plot(
                pen=mkPen('#22c55e', width=2.6, style=Qt.DotLine), name=self._tr("legend_mem_usage"))

        self._ios_hw_curves["cpu"].setData(self._ios_hw_history_times, self._ios_hw_history_cpu_usage)
        self._ios_hw_curves["gpu"].setData(self._ios_hw_history_times, self._ios_hw_history_gpu)
        self._ios_hw_curves["mem"].setData(self._ios_hw_history_times, self._ios_hw_history_mem)

        # 更新 CPU 数值面板
        self.ios_cpu_usage_label.setText(f"{cpu_usage:.1f} %")
        self.ios_cpu_usage_bar.setValue(int(max(0, min(100, cpu_usage))))
        self.ios_cpu_usage_bar.setFormat(f"{cpu_usage:.1f}%")
        cpu_count = data.get("cpu_count", 0)
        if cpu_count > 0:
            self.ios_cpu_cores_label.setText(self._tr("fmt_cpu_cores").format(n=cpu_count))

        # 更新内存数值面板
        mem_total = data.get("mem_total_mb", 0)
        mem_used = data.get("mem_used_mb", 0)
        self.ios_mem_label.setText(f"{mem_used} MB / {mem_total} MB")
        self.ios_mem_bar.setValue(int(max(0, min(100, mem_pct))))
        self.ios_mem_bar.setFormat(f"{mem_pct:.1f}%")

        # 更新 GPU 数值面板（钳制 0-100，避免一直 100% 的夹取错觉；<=0 显示 N/A）
        if gpu_usage >= 0.1:
            display_gpu = max(0.0, min(100.0, gpu_usage))
            self.ios_gpu_label.setText(f"{display_gpu:.1f} %")
            self.ios_gpu_bar.setValue(int(max(0, min(100, display_gpu))))
            self.ios_gpu_bar.setFormat(f"{display_gpu:.1f}%")
        else:
            self.ios_gpu_label.setText("N/A")
            self.ios_gpu_bar.setValue(0)
            self.ios_gpu_bar.setFormat("N/A")

        # GPU 子项（渲染器/平铺器，从 FPS 采集器获取；同样钳制范围）
        if self.ios_fps_thread and self.ios_fps_thread._collector:
            ren_raw = self.ios_fps_thread._collector.get_gpu_renderer_usage()
            til_raw = self.ios_fps_thread._collector.get_gpu_tiler_usage()
            ren = max(0.0, min(100.0, float(ren_raw or 0.0)))
            til = max(0.0, min(100.0, float(til_raw or 0.0)))
            self.ios_gpu_renderer_label.setText(f"{ren:.1f} %" if ren > 0 else "-- %")
            self.ios_gpu_tiler_label.setText(f"{til:.1f} %" if til > 0 else "-- %")

    def _stop_ios_hw_monitor(self):
        """停止 iOS 硬件监测（联动停止帧率测试）"""
        if self.ios_hw_thread and self.ios_hw_thread.isRunning():
            self.ios_hw_thread.stop()
            self.ios_hw_thread.wait(5000)
        self.ios_hw_start_btn.setEnabled(True)
        self.ios_hw_stop_btn.setEnabled(False)
        self.ios_hw_status_label.setText(self._tr("stat_stopped"))
        self.ios_hw_status_label.setStyleSheet(f"color: {self._fg_muted()}; font-size: 13px;")
        self._ios_log("⏹ iOS 硬件监测已停止")

        # 保存到历史记录
        if self._ios_hw_history_times:
            device_id = self._get_ios_hw_selected_device() or ""
            start_dt = self._ios_hw_monitor_start_dt or datetime.now()
            end_dt = datetime.now()
            duration_sec = int((end_dt - start_dt).total_seconds())
            times_snapshot = list(self._ios_hw_history_times)
            cpu_snapshot = list(self._ios_hw_history_cpu_usage)
            gpu_snapshot = list(self._ios_hw_history_gpu)
            mem_snapshot = list(self._ios_hw_history_mem)
            def _stat(arr):
                if not arr:
                    return {"avg": 0, "max": 0, "min": 0, "std": 0}
                a = sum(arr) / len(arr)
                mx = max(arr)
                mn = min(arr)
                sd = (sum((x - a) ** 2 for x in arr) / len(arr)) ** 0.5
                return {"avg": a, "max": mx, "min": mn, "std": sd}
            freq_summary = {
                "CPU 使用率(%)": _stat(cpu_snapshot),
                "GPU 利用率(%)": _stat(gpu_snapshot),
                "内存 使用率(%)": _stat(mem_snapshot),
            }
            report = {
                "id": f"hw_{int(start_dt.timestamp())}",
                "type": "hw",
                "start_time": start_dt,
                "end_time": end_dt,
                "duration_sec": duration_sec,
                "device_id": device_id,
                "freq_summary": freq_summary,
                "times": times_snapshot,
                "cpu_usage": cpu_snapshot,
                "gpu_usage": gpu_snapshot,
                "mem_pct": mem_snapshot,
            }
            self._ios_hw_reports.append(report)
            self._ios_history_refresh_lists()

        # 联动停止帧率测试
        if not self._ios_linking_stop:
            self._ios_linking_stop = True
            try:
                if self.ios_fps_thread and self.ios_fps_thread.isRunning():
                    self._stop_ios_test()
                    self._ios_log("🔗 已联动停止帧率测试")
            finally:
                self._ios_linking_stop = False

    def _clear_ios_hw_data(self):
        """清空 iOS 硬件监测数据"""
        if self.ios_hw_thread and self.ios_hw_thread.isRunning():
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_monitor_running"))
            return

        if not self._ios_hw_history_times:
            self._ios_hw_plot_start_time = time.time()
            return

        reply = QMessageBox.question(
            self, self._tr("msg_confirm_clear"),
            self._tr("msg_confirm_clear_body"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._ios_hw_history_times.clear()
        self._ios_hw_history_cpu_usage.clear()
        self._ios_hw_history_mem.clear()
        self._ios_hw_history_gpu.clear()
        self._ios_hw_curves.clear()
        self.ios_hw_plot.clear()
        self.ios_hw_plot.addLegend()
        self._ios_hw_plot_start_time = time.time()

        self.ios_cpu_usage_label.setText("-- %")
        self.ios_cpu_usage_bar.setValue(0)
        self.ios_cpu_usage_bar.setFormat("0.0%")
        self.ios_cpu_cores_label.setText(self._tr("stat_cpu_cores_na"))
        self.ios_mem_label.setText("-- MB / -- MB")
        self.ios_mem_bar.setValue(0)
        self.ios_mem_bar.setFormat("0.0%")
        self.ios_gpu_label.setText("-- %")
        self.ios_gpu_bar.setValue(0)
        self.ios_gpu_bar.setFormat("0.0%")
        self.ios_gpu_renderer_label.setText("-- %")
        self.ios_gpu_tiler_label.setText("-- %")

        self.ios_hw_status_label.setText(self._tr("stat_cleared"))
        self.ios_hw_status_label.setStyleSheet("color: #FF9800; font-size: 13px;")
        self._ios_log("🗑 iOS 监测数据已清空")

    # ==================== iOS 设备信息 ====================

    def _load_ios_device_info(self):
        """加载 iOS 设备信息"""
        idx = self.ios_info_device_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_ios_device"))
            return
        udid = self.ios_info_device_combo.itemData(idx)
        if not udid:
            return

        self._ios_log("📡 正在获取 iOS 设备信息...")
        self.ios_info_load_btn.setEnabled(False)
        try:
            info = self.ios_client.get_device_info(udid)
            if "error" in info:
                QMessageBox.critical(self, self._tr("msg_error"),self._tr("msg_get_info_failed_ios").format(info_err=info['error']))
                return

            rows = [
                ("品牌", info.get("brand", "Apple")),
                ("设备名称", info.get("device_name", "--")),
                ("营销名称", info.get("display_name", "--")),
                ("型号 (ProductType)", info.get("model", "--")),
                ("芯片", info.get("chip_name", "--")),
                ("iOS 版本", info.get("ios_version", "--")),
                ("Build 版本", info.get("build_number", "--")),
                ("设备类型", info.get("device_class", "--")),
                ("硬件型号", info.get("hardware_model", "--")),
                ("CPU 核心数", str(info.get("cpu_cores", "--"))),
                ("CPU 架构", info.get("cpu_abi", "arm64e")),
                ("屏幕刷新率", f"{info.get('refresh_rate', 60)} Hz"),
                ("平台", info.get("platform", "iOS")),
                ("UDID", info.get("udid", "--")),
                ("ECID", info.get("ecid", "--")),
            ]
            self.ios_info_table.setRowCount(len(rows))
            for i, (key, val) in enumerate(rows):
                item_k = QTableWidgetItem(key)
                item_k.setFont(QFont("Menlo", 13, QFont.Bold))
                item_k.setForeground(QColor("#00838F"))
                item_v = QTableWidgetItem(str(val))
                item_v.setFont(QFont("Menlo", 13))
                item_v.setForeground(QColor("#1e293b"))
                self.ios_info_table.setItem(i, 0, item_k)
                self.ios_info_table.setItem(i, 1, item_v)
            self._ios_log("✅ iOS 设备信息获取成功")
        except Exception as e:
            QMessageBox.critical(self, self._tr("msg_error"),self._tr("msg_get_info_failed").format(err=e))
        finally:
            self.ios_info_load_btn.setEnabled(True)

    def _init_device_info_tab(self):
        """构建手机信息页面 (Tab 4)"""
        tab4 = QWidget()
        tab4.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(tab4)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.tab_widget.addTab(tab4, self._tr("tab_device_info"))

        # 顶部控制栏
        ctrl = QHBoxLayout()
        _lbl = QLabel(self._tr("lbl_select_device"))
        self._i18n_refs["lbl_info_select_device"] = _lbl
        ctrl.addWidget(_lbl)
        self.info_device_combo = QComboBox()
        self.info_device_combo.setMinimumWidth(300)
        ctrl.addWidget(self.info_device_combo)

        self.info_refresh_btn = QPushButton(self._tr("btn_refresh_device"))
        self._i18n_refs["info_btn_refresh_device"] = self.info_refresh_btn
        self.info_refresh_btn.clicked.connect(self._refresh_info_devices)
        ctrl.addWidget(self.info_refresh_btn)

        self.info_load_btn = QPushButton(self._tr("btn_get_info"))
        self._i18n_refs["info_btn_get_info"] = self.info_load_btn
        self.info_load_btn.setMinimumHeight(40)
        self.info_load_btn.setStyleSheet("""
            QPushButton { background-color: #00838F; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #006064; }
        """)
        self.info_load_btn.clicked.connect(self._load_device_info)
        ctrl.addWidget(self.info_load_btn)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        # 设备信息表格
        info_group = QGroupBox(self._tr("grp_device_info"))
        self._i18n_refs["grp_info_device_info"] = info_group
        info_group.setStyleSheet(f"""
            QGroupBox {{ font-size: 14px; font-weight: bold; color: #0277BD;
                        border: 2px solid #0288D1; border-radius: 8px; margin-top: 16px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        info_layout = QVBoxLayout(info_group)

        self.device_info_table = QTableWidget()
        self.device_info_table.setColumnCount(2)
        self.device_info_table.setHorizontalHeaderLabels([self._tr("header_item"), self._tr("header_detail")])
        self.device_info_table.horizontalHeader().setStretchLastSection(True)
        self.device_info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.device_info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.device_info_table.setFont(QFont("Menlo", 13))
        self.device_info_table.setAlternatingRowColors(True)
        self.device_info_table.verticalHeader().setVisible(False)
        self.device_info_table.setEditTriggers(QTableWidget.NoEditTriggers)
        info_layout.addWidget(self.device_info_table)

        layout.addWidget(info_group, stretch=1)

        # 初始化空表
        self._device_info_data = None

    def _refresh_info_devices(self):
        """刷新手机信息页的设备下拉框"""
        self.info_device_combo.clear()
        try:
            devices = self.adb_client.get_devices()
            for device_id, status in devices:
                if status == "device":
                    model = self.adb_client.get_device_model(device_id)
                    self.info_device_combo.addItem(f"{model} ({device_id})", device_id)
            if self.info_device_combo.count() == 0:
                self.info_device_combo.addItem(self._tr("combo_no_device"), "")
        except Exception as e:
            self.info_device_combo.addItem(self._tr("fmt_error_prefix").format(err=e), "")

    def _load_device_info(self):
        """加载并显示设备信息"""
        # 优先从帧率测试页的设备下拉框获取设备ID
        device_id = self.device_combo.currentData()
        if not device_id and self.info_device_combo.count() > 0:
            device_id = self.info_device_combo.currentData()
        if not device_id:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_device_connect"))
            return

        self._log(f"📡 正在获取设备 {device_id} 的信息...")

        try:
            info = self.adb_client.get_device_info(device_id)
            self._device_info_data = info

            # 组合芯片名称
            chip_name = info.get("soc_model", "") or info.get("hardware", "") or info.get("platform", "")
            if info.get("soc_manufacturer"):
                chip_name = f"{info['soc_manufacturer']} {chip_name}".strip()

            # 组合手机名称
            phone_name = f"{info.get('brand', '')} {info.get('model', '')}".strip()
            if not phone_name:
                phone_name = info.get("device_name", "未知设备")

            rows = [
                ("📱 手机名称", phone_name),
                ("🔧 芯片名称", chip_name or "未知"),
                ("厂商", info.get("manufacturer", "") or "未知"),
                ("设备型号", info.get("model", "") or "未知"),
                ("设备代号", info.get("device_name", "") or "未知"),
                ("品牌", info.get("brand", "") or "未知"),
                ("Android 版本", info.get("android_version", "") or "未知"),
                ("SDK 版本", info.get("sdk_version", "") or "未知"),
                ("固件版本号", info.get("build_number", "") or "未知"),
                ("硬件平台", info.get("hardware", "") or "未知"),
                ("SoC 型号", info.get("soc_model", "") or "未知"),
                ("SoC 厂商", info.get("soc_manufacturer", "") or "未知"),
                ("主板平台", info.get("platform", "") or "未知"),
                ("CPU 架构", info.get("cpu_abi", "") or "未知"),
                ("CPU 核心数", f"{info.get('cpu_cores', 0)} 核"),
                ("GPU 信息", info.get("gpu_info", "") or "未知"),
                ("屏幕分辨率", info.get("screen_resolution", "") or "未知"),
                ("屏幕密度 (DPI)", info.get("screen_density", "") or "未知"),
                ("内存总量", f"{info.get('ram_total_mb', 0)} MB ({info.get('ram_total_mb', 0)/1024:.1f} GB)" if info.get('ram_total_mb') else "未知"),
                ("内核版本", info.get("kernel_version", "") or "未知"),
            ]

            self.device_info_table.setRowCount(len(rows))
            for i, (key, val) in enumerate(rows):
                item_k = QTableWidgetItem(key)
                item_k.setFont(QFont("Menlo", 13, QFont.Bold))
                item_k.setForeground(QColor("#00838F"))
                item_v = QTableWidgetItem(str(val))
                item_v.setFont(QFont("Menlo", 13))
                item_v.setForeground(QColor("#1e293b"))
                self.device_info_table.setItem(i, 0, item_k)
                self.device_info_table.setItem(i, 1, item_v)

            # 同步到 info_device_combo
            if self.info_device_combo.findData(device_id) < 0:
                self._refresh_info_devices()

            self._log(f"✅ 设备信息获取完成: {phone_name} / {chip_name}")

        except Exception as e:
            self._log(f"❌ 获取设备信息失败: {e}")
            QMessageBox.critical(self, self._tr("msg_error"),self._tr("msg_get_info_failed").format(err=e))

    def _init_history_tab(self):
        """构建 CSV 历史记录页面"""
        tab3 = QWidget()
        tab3.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(tab3)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.tab_widget.addTab(tab3, self._tr("tab_history"))

        # 顶部提示条
        tip_bar = QHBoxLayout()
        tip = QLabel(self._tr("lbl_history_tip"))
        self._i18n_refs["hist_lbl_tip"] = tip
        tip.setStyleSheet(f"color: {self._fg()}; font-size: 13px; font-weight: bold;")
        tip_bar.addWidget(tip)
        tip_bar.addStretch()

        self.hist_export_all_btn = QPushButton(self._tr("btn_export_csv"))
        self._i18n_refs["hist_btn_export_csv"] = self.hist_export_all_btn
        self.hist_export_all_btn.setMinimumHeight(36)
        self.hist_export_all_btn.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; font-size: 13px;
                          font-weight: bold; border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.hist_export_all_btn.clicked.connect(self._history_export_selected)
        tip_bar.addWidget(self.hist_export_all_btn)

        # 联系作者按钮
        self.hist_contact_btn = QPushButton(self._tr("btn_contact_report"))
        self._i18n_refs["hist_btn_contact"] = self.hist_contact_btn
        self.hist_contact_btn.setMinimumHeight(36)
        self.hist_contact_btn.setStyleSheet("""
            QPushButton { background-color: #0f172a; color: white; font-size: 13px;
                          font-weight: bold; border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background-color: #1e293b; }
        """)
        self.hist_contact_btn.clicked.connect(self._navigate_to_contact)
        tip_bar.addWidget(self.hist_contact_btn)

        layout.addLayout(tip_bar)

        # 主区域：左右分栏
        body = QSplitter(Qt.Horizontal)

        # 左侧：历史记录列表（4 组：FPS / 负载 / HW / 评价，使用 2x2 网格布局）
        left = QWidget()
        left_lay_wrapper = QHBoxLayout(left)
        left_lay_wrapper.setContentsMargins(0, 0, 0, 0)
        left_lay_wrapper.setSpacing(6)
        # 左列：FPS + 负载
        col_left = QVBoxLayout()
        col_left.setSpacing(6)

        fps_gb = QGroupBox(self._tr("grp_fps_history"))
        self._i18n_refs["grp_hist_fps_history"] = fps_gb
        fps_gb.setStyleSheet(f"""
            QGroupBox {{ font-size: 13px; font-weight: bold; color: #0277BD;
                        border: 2px solid #0288D1; border-radius: 8px; margin-top: 14px; padding-top: 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        fps_lay = QVBoxLayout(fps_gb)
        fps_lay.setContentsMargins(8, 10, 8, 8)
        self.hist_fps_list = QListWidget()
        self.hist_fps_list.itemClicked.connect(self._history_on_fps_clicked)
        self.hist_fps_list.setStyleSheet("QListWidget { font-size: 12px; border: none; background: #fafbfc; }")
        fps_lay.addWidget(self.hist_fps_list)
        col_left.addWidget(fps_gb, stretch=1)

        load_gb = QGroupBox(self._tr("grp_load_history"))
        self._i18n_refs["grp_hist_load_history"] = load_gb
        load_gb.setStyleSheet(f"""
            QGroupBox {{ font-size: 13px; font-weight: bold; color: #B71C1C;
                        border: 2px solid #C62828; border-radius: 8px; margin-top: 14px; padding-top: 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        load_lay = QVBoxLayout(load_gb)
        load_lay.setContentsMargins(8, 10, 8, 8)
        self.hist_load_list = QListWidget()
        self.hist_load_list.itemClicked.connect(self._history_on_load_clicked)
        self.hist_load_list.setStyleSheet("QListWidget { font-size: 12px; border: none; background: #fafbfc; }")
        load_lay.addWidget(self.hist_load_list)
        col_left.addWidget(load_gb, stretch=1)
        left_lay_wrapper.addLayout(col_left, stretch=1)

        # 右列：CPU/GPU监测 + 性能评价
        col_right = QVBoxLayout()
        col_right.setSpacing(6)

        hw_gb = QGroupBox(self._tr("grp_hw_history"))
        self._i18n_refs["grp_hist_hw_history"] = hw_gb
        hw_gb.setStyleSheet(f"""
            QGroupBox {{ font-size: 13px; font-weight: bold; color: #7B1FA2;
                        border: 2px solid #7B1FA2; border-radius: 8px; margin-top: 14px; padding-top: 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        hw_lay = QVBoxLayout(hw_gb)
        hw_lay.setContentsMargins(8, 10, 8, 8)
        self.hist_hw_list = QListWidget()
        self.hist_hw_list.itemClicked.connect(self._history_on_hw_clicked)
        self.hist_hw_list.setStyleSheet("QListWidget { font-size: 12px; border: none; background: #fafbfc; }")
        hw_lay.addWidget(self.hist_hw_list)
        col_right.addWidget(hw_gb, stretch=1)

        eval_gb = QGroupBox(self._tr("grp_eval_history"))
        self._i18n_refs["grp_hist_eval_history"] = eval_gb
        eval_gb.setStyleSheet(f"""
            QGroupBox {{ font-size: 13px; font-weight: bold; color: #E65100;
                        border: 2px solid #EF6C00; border-radius: 8px; margin-top: 14px; padding-top: 8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        eval_lay = QVBoxLayout(eval_gb)
        eval_lay.setContentsMargins(8, 10, 8, 8)
        self.hist_eval_list = QListWidget()
        self.hist_eval_list.itemClicked.connect(self._history_on_eval_clicked)
        self.hist_eval_list.setStyleSheet("QListWidget { font-size: 12px; border: none; background: #fafbfc; }")
        eval_lay.addWidget(self.hist_eval_list)
        col_right.addWidget(eval_gb, stretch=1)
        left_lay_wrapper.addLayout(col_right, stretch=1)

        body.addWidget(left)

        # 右侧：详情 + 图表
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)

        # 详情摘要
        self.hist_summary_gb = QGroupBox(self._tr("grp_detail_summary"))
        self._i18n_refs["grp_hist_detail_summary"] = self.hist_summary_gb
        self.hist_summary_gb.setStyleSheet(f"""
            QGroupBox {{ font-size: 14px; font-weight: bold; color: {self._fg()};
                        border: 2px solid #607D8B; border-radius: 8px; margin-top: 16px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }}
        """)
        self.hist_summary_layout = QGridLayout(self.hist_summary_gb)
        right_lay.addWidget(self.hist_summary_gb)

        # 统计数值表格
        table_gb = QGroupBox(self._tr("grp_stats_data"))
        self._i18n_refs["grp_hist_stats_data"] = table_gb
        table_lay = QVBoxLayout(table_gb)
        self.hist_table = QTableWidget()
        self.hist_table.setColumnCount(2)
        self.hist_table.setHorizontalHeaderLabels([self._tr("header_metric"), self._tr("header_value")])
        self.hist_table.horizontalHeader().setStretchLastSection(True)
        self.hist_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.hist_table.setFont(QFont("Menlo", 12))
        self.hist_table.setAlternatingRowColors(True)
        self.hist_table.verticalHeader().setVisible(False)
        self.hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        table_lay.addWidget(self.hist_table)
        right_lay.addWidget(table_gb, stretch=1)

        # 图表
        chart_gb = QGroupBox(self._tr("grp_time_series"))
        self._i18n_refs["grp_hist_time_series"] = chart_gb
        chart_lay = QVBoxLayout(chart_gb)
        self.hist_plot = PlotWidget()
        self.hist_plot.addLegend()
        self.hist_plot.showGrid(x=True, y=True, alpha=0.3)
        chart_lay.addWidget(self.hist_plot)
        right_lay.addWidget(chart_gb, stretch=1)

        # 温度右轴 ViewBox（用于 HW 历史温度曲线，双 Y 轴）
        self._hist_temp_vb = pg.ViewBox()
        self.hist_plot.showAxis('right')
        self.hist_plot.scene().addItem(self._hist_temp_vb)
        self.hist_plot.getAxis('right').linkToView(self._hist_temp_vb)
        self._hist_temp_vb.setXLink(self.hist_plot)
        self.hist_plot.getAxis('right').setLabel(self._tr("lbl_temp_axis"), color='#D32F2F')
        self.hist_plot.getAxis('right').setPen('#D32F2F')
        def _sync_hist_temp_view():
            self._hist_temp_vb.setGeometry(self.hist_plot.getViewBox().sceneBoundingRect())
            self._hist_temp_vb.linkedViewChanged(self.hist_plot.getViewBox(), self._hist_temp_vb.XAxis)
        _sync_hist_temp_view()
        self.hist_plot.getViewBox().sigResized.connect(_sync_hist_temp_view)
        self.hist_plot.hideAxis('right')  # 默认隐藏，仅 HW 有温度时显示

        body.addWidget(right)
        body.setStretchFactor(0, 2)
        body.setStretchFactor(1, 3)
        body.setSizes([520, 880])

        layout.addWidget(body, stretch=1)

        # 初始化右侧空状态
        self._history_clear_details()
        # 刷新列表
        self._history_refresh_lists()

    def _init_hw_monitor_tab(self):
        """构建 CPU/GPU 监测页面"""
        tab2 = QWidget()
        tab2.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(tab2)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ===== 顶部控制栏 =====
        ctrl = QHBoxLayout()
        _lbl = QLabel(self._tr("lbl_monitor_device"))
        self._i18n_refs["hw_lbl_monitor_device"] = _lbl
        ctrl.addWidget(_lbl)
        self.hw_device_combo = QComboBox()
        self.hw_device_combo.setMinimumWidth(280)
        ctrl.addWidget(self.hw_device_combo)

        # 采集间隔（与 FPS 测试页保持一致的选项）
        _lbl = QLabel(self._tr("lbl_interval_short"))
        self._i18n_refs["hw_lbl_interval_short"] = _lbl
        ctrl.addWidget(_lbl)
        self.hw_interval_combo = QComboBox()
        for iv in [0.1, 0.3, 0.5, 1.0, 2.0]:
            self.hw_interval_combo.addItem(f"{iv}s", iv)
        self.hw_interval_combo.setCurrentIndex(3)  # 默认 1.0s
        self.hw_interval_combo.setToolTip(self._tr("tip_hw_interval"))
        ctrl.addWidget(self.hw_interval_combo)

        self.hw_refresh_btn = QPushButton(self._tr("btn_refresh_device"))
        self._i18n_refs["hw_btn_refresh_device"] = self.hw_refresh_btn
        self.hw_refresh_btn.clicked.connect(self._refresh_devices)
        ctrl.addWidget(self.hw_refresh_btn)

        self.hw_start_btn = QPushButton(self._tr("btn_start_monitor"))
        self._i18n_refs["hw_btn_start_monitor"] = self.hw_start_btn
        self.hw_start_btn.setMinimumHeight(40)
        self.hw_start_btn.setStyleSheet("""
            QPushButton { background-color: #7B1FA2; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #6A1B9A; }
            QPushButton:disabled { background-color: rgba(123,31,162,80); color: rgba(226,232,240,120); }
        """)
        self.hw_start_btn.clicked.connect(self._start_hw_monitor)
        ctrl.addWidget(self.hw_start_btn)

        self.hw_stop_btn = QPushButton(self._tr("btn_stop_monitor"))
        self._i18n_refs["hw_btn_stop_monitor"] = self.hw_stop_btn
        self.hw_stop_btn.setMinimumHeight(40)
        self.hw_stop_btn.setEnabled(False)
        self.hw_stop_btn.setStyleSheet("""
            QPushButton { background-color: #F44336; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #D32F2F; }
            QPushButton:disabled { background-color: rgba(244,67,54,80); color: rgba(226,232,240,120); }
        """)
        self.hw_stop_btn.clicked.connect(self._stop_hw_monitor)
        ctrl.addWidget(self.hw_stop_btn)

        self.hw_clear_btn = QPushButton(self._tr("btn_clear"))
        self._i18n_refs["hw_btn_clear"] = self.hw_clear_btn
        self.hw_clear_btn.setMinimumHeight(40)
        self.hw_clear_btn.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: rgba(255,152,0,80); color: rgba(226,232,240,120); }
        """)
        self.hw_clear_btn.clicked.connect(self._clear_hw_monitor_data)
        ctrl.addWidget(self.hw_clear_btn)

        self.hw_export_btn = QPushButton(self._tr("btn_export"))
        self._i18n_refs["hw_btn_export"] = self.hw_export_btn
        self.hw_export_btn.setMinimumHeight(40)
        self.hw_export_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-size: 14px;
                          font-weight: bold; border-radius: 6px; padding: 6px 20px; }
            QPushButton:hover { background-color: #388E3C; }
            QPushButton:disabled { background-color: rgba(76,175,80,80); color: rgba(226,232,240,120); }
        """)
        self.hw_export_btn.clicked.connect(self._show_hw_export_menu)
        ctrl.addWidget(self.hw_export_btn)

        self.hw_status_label = QLabel(self._tr("lbl_status"))
        self._i18n_refs["hw_lbl_status"] = self.hw_status_label
        self.hw_status_label.setStyleSheet(f"color: {self._fg_muted()}; font-size: 13px;")
        ctrl.addWidget(self.hw_status_label)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # ===== 主区域：左右分栏 =====
        hw_splitter = QSplitter(Qt.Horizontal)

        # --- 左侧：CPU 区域 ---
        cpu_widget = QWidget()
        cpu_layout = QVBoxLayout(cpu_widget)
        cpu_layout.setContentsMargins(0, 0, 0, 0)

        # CPU 超大核突出卡片
        prime_group = QGroupBox(self._tr("grp_prime"))
        self._i18n_refs["hw_grp_prime"] = prime_group
        prime_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #7B1FA2;
                        border: 2px solid #7B1FA2; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        prime_layout = QVBoxLayout(prime_group)

        # 超大核大号频率显示
        prime_top = QHBoxLayout()
        self.prime_freq_label = QLabel("-- MHz")
        self.prime_freq_label.setFont(QFont("Menlo", 28, QFont.Bold))
        self.prime_freq_label.setStyleSheet("color: #7B1FA2;")
        self.prime_freq_label.setAlignment(Qt.AlignCenter)
        prime_top.addWidget(self.prime_freq_label)
        prime_top.addStretch()

        self.prime_max_label = QLabel(self._tr("lbl_prime_max"))
        self._i18n_refs["hw_lbl_prime_max"] = self.prime_max_label
        self.prime_max_label.setStyleSheet(f"font-size: 13px; color: {self._fg_muted()};")
        prime_top.addWidget(self.prime_max_label)
        prime_layout.addLayout(prime_top)

        self.prime_bar = QProgressBar()
        self.prime_bar.setRange(0, 100)
        self.prime_bar.setValue(0)
        self.prime_bar.setFixedHeight(24)
        self.prime_bar.setTextVisible(True)
        self.prime_bar.setFormat("0%")
        self.prime_bar.setStyleSheet("""
            QProgressBar { border: 1px solid rgba(100,116,139,80); border-radius: 6px; text-align: center;
                           font-size: 13px; font-weight: bold; background-color: rgba(226,232,240,200); }
            QProgressBar::chunk { background-color: #7B1FA2; border-radius: 5px; }
        """)
        prime_layout.addWidget(self.prime_bar)

        self.prime_cores_label = QLabel(self._tr("lbl_prime_cores"))
        self._i18n_refs["hw_lbl_prime_cores"] = self.prime_cores_label
        self.prime_cores_label.setStyleSheet(f"font-size: 12px; color: {self._fg_muted()};")
        prime_layout.addWidget(self.prime_cores_label)
        cpu_layout.addWidget(prime_group)

        # CPU 全部集群频率
        cpu_clusters_group = QGroupBox(self._tr("grp_cpu_clusters"))
        self._i18n_refs["hw_grp_cpu_clusters"] = cpu_clusters_group
        cpu_clusters_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #1565C0;
                        border: 2px solid #2196F3; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        self._hw_cpu_clusters_layout = QVBoxLayout(cpu_clusters_group)
        self._hw_cpu_cluster_bars = []  # 动态创建的 (bar, label) 列表
        cpu_layout.addWidget(cpu_clusters_group)

        # CPU 利用率 + 温度
        cpu_stats_group = QGroupBox(self._tr("grp_cpu_temp_usage"))
        self._i18n_refs["hw_grp_cpu_stats"] = cpu_stats_group
        cpu_stats_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #E65100;
                        border: 2px solid #FF9800; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        cpu_stats_layout = QVBoxLayout(cpu_stats_group)

        self.hw_cpu_usage_bar = QProgressBar()
        self.hw_cpu_usage_bar.setRange(0, 100)
        self.hw_cpu_usage_bar.setValue(0)
        self.hw_cpu_usage_bar.setFixedHeight(20)
        self.hw_cpu_usage_bar.setFormat("0.0%")
        self.hw_cpu_usage_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid #ccc; border-radius: 4px; text-align: center;
                           font-size: 12px; background-color: {self._note_bg()}; }}
            QProgressBar::chunk {{ background-color: #FF9800; border-radius: 3px; }}
        """)
        cpu_stats_layout.addWidget(self.hw_cpu_usage_bar)

        temp_row = QHBoxLayout()
        _lbl = QLabel(self._tr("lbl_cpu_temp"))
        self._i18n_refs["hw_lbl_cpu_temp"] = _lbl
        temp_row.addWidget(_lbl)
        self.hw_cpu_temp_label = QLabel("-- °C")
        self.hw_cpu_temp_label.setFont(QFont("Menlo", 16, QFont.Bold))
        self.hw_cpu_temp_label.setStyleSheet("color: #4CAF50;")
        temp_row.addWidget(self.hw_cpu_temp_label)
        temp_row.addStretch()
        cpu_stats_layout.addLayout(temp_row)
        cpu_layout.addWidget(cpu_stats_group)

        # 电池/功率卡片
        battery_group = QGroupBox(self._tr("grp_battery_power"))
        self._i18n_refs["hw_grp_battery_power"] = battery_group
        battery_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #7C3AED;
                        border: 2px solid #7C3AED; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        battery_layout = QVBoxLayout(battery_group)

        # 功率大字
        self.hw_power_label = QLabel("-- mW")
        self.hw_power_label.setFont(QFont("Menlo", 26, QFont.Bold))
        self.hw_power_label.setStyleSheet("color: #7C3AED;")
        self.hw_power_label.setAlignment(Qt.AlignCenter)
        battery_layout.addWidget(self.hw_power_label)

        # 电压 / 电流 / 电量 / 温度
        info_grid = QGridLayout()
        def _make_info_pair(row, title_key, attr_name, unit="", val_color="#64748b"):
            t = QLabel(self._tr(title_key))
            self._i18n_refs[f"hw_lbl_{attr_name}"] = t
            t.setStyleSheet(f"font-size: 12px; color: {self._fg_muted()};")
            info_grid.addWidget(t, row, 0)
            lbl = QLabel(f"-- {unit}")
            lbl.setStyleSheet(f"font-size: 13px; color: {val_color}; font-family: 'Menlo', monospace;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            setattr(self, attr_name, lbl)
            info_grid.addWidget(lbl, row, 1)

        _make_info_pair(0, "lbl_voltage",    "hw_voltage_label",  unit="mV",  val_color="#0891b2")
        _make_info_pair(1, "lbl_current",    "hw_current_label",  unit="mA",  val_color="#0ea5e9")
        _make_info_pair(2, "lbl_capacity",   "hw_capacity_label", unit="%",   val_color="#22c55e")
        _make_info_pair(3, "lbl_battery_temp","hw_bat_temp_label", unit="°C",  val_color="#f97316")
        self.hw_battery_status_label = QLabel("")
        self.hw_battery_status_label.setStyleSheet(f"font-size: 11px; color: {self._fg_muted()};")
        self.hw_battery_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        info_grid.addWidget(self.hw_battery_status_label, 4, 0, 1, 2)
        battery_layout.addLayout(info_grid)
        cpu_layout.addWidget(battery_group)

        cpu_layout.addStretch()

        hw_splitter.addWidget(cpu_widget)

        # --- 右侧：GPU 区域 ---
        gpu_widget = QWidget()
        gpu_layout = QVBoxLayout(gpu_widget)
        gpu_layout.setContentsMargins(0, 0, 0, 0)

        # GPU 频率卡片
        gpu_freq_group = QGroupBox(self._tr("grp_gpu_freq"))
        self._i18n_refs["hw_grp_gpu_freq"] = gpu_freq_group
        gpu_freq_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #00838F;
                        border: 2px solid #00838F; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        gpu_freq_layout = QVBoxLayout(gpu_freq_group)

        gpu_freq_top = QHBoxLayout()
        self.gpu_freq_label = QLabel("-- MHz")
        self.gpu_freq_label.setFont(QFont("Menlo", 28, QFont.Bold))
        self.gpu_freq_label.setStyleSheet("color: #00838F;")
        self.gpu_freq_label.setAlignment(Qt.AlignCenter)
        gpu_freq_top.addWidget(self.gpu_freq_label)
        gpu_freq_top.addStretch()

        self.gpu_max_label = QLabel(self._tr("lbl_gpu_max"))
        self._i18n_refs["hw_lbl_gpu_max"] = self.gpu_max_label
        self.gpu_max_label.setStyleSheet(f"font-size: 13px; color: {self._fg_muted()};")
        gpu_freq_top.addWidget(self.gpu_max_label)
        gpu_freq_layout.addLayout(gpu_freq_top)

        self.gpu_freq_bar = QProgressBar()
        self.gpu_freq_bar.setRange(0, 100)
        self.gpu_freq_bar.setValue(0)
        self.gpu_freq_bar.setFixedHeight(24)
        self.gpu_freq_bar.setTextVisible(True)
        self.gpu_freq_bar.setFormat("0%")
        self.gpu_freq_bar.setStyleSheet("""
            QProgressBar { border: 1px solid rgba(100,116,139,80); border-radius: 6px; text-align: center;
                           font-size: 13px; font-weight: bold; background-color: rgba(226,232,240,200); }
            QProgressBar::chunk { background-color: #00838F; border-radius: 5px; }
        """)
        gpu_freq_layout.addWidget(self.gpu_freq_bar)

        self.gpu_freq_note = QLabel("")
        self.gpu_freq_note.setWordWrap(True)
        self.gpu_freq_note.setStyleSheet(f"font-size: 11px; color: {self._fg_muted()};")
        gpu_freq_layout.addWidget(self.gpu_freq_note)
        gpu_layout.addWidget(gpu_freq_group)

        # GPU 渲染负载
        gpu_load_group = QGroupBox(self._tr("grp_gpu_load"))
        self._i18n_refs["hw_grp_gpu_load"] = gpu_load_group
        gpu_load_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #455A64;
                        border: 2px solid #607D8B; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        gpu_load_grid = QGridLayout(gpu_load_group)
        self._hw_gpu_load_labels = {}
        gpu_items = [
            ("P50", "gpu_p50", "#00695C"),
            ("P90", "gpu_p90", "#F57C00"),
            ("P95", "gpu_p95", "#D32F2F"),
            ("P99", "gpu_p99", "#D32F2F"),
        ]
        for i, (label_text, key, color) in enumerate(gpu_items):
            row = i // 2
            col = (i % 2) * 2
            gpu_load_grid.addWidget(QLabel(f"{label_text}:"), row, col)
            lbl = QLabel("-- ms")
            lbl.setFont(QFont("Menlo", 14, QFont.Bold))
            lbl.setStyleSheet(f"color: {color};")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            gpu_load_grid.addWidget(lbl, row, col + 1)
            self._hw_gpu_load_labels[key] = lbl
        gpu_layout.addWidget(gpu_load_group)

        # GPU 显存 + 内存
        mem_group = QGroupBox(self._tr("grp_mem_gpu"))
        self._i18n_refs["hw_grp_mem_gpu"] = mem_group
        mem_group.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; color: #2E7D32;
                        border: 2px solid #00695C; border-radius: 8px; margin-top: 16px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 0 6px; }
        """)
        mem_layout = QVBoxLayout(mem_group)
        self.hw_mem_bar = QProgressBar()
        self.hw_mem_bar.setRange(0, 100)
        self.hw_mem_bar.setValue(0)
        self.hw_mem_bar.setFixedHeight(20)
        self.hw_mem_bar.setFormat("0.0%")
        self.hw_mem_bar.setStyleSheet("""
            QProgressBar { border: 1px solid rgba(100,116,139,80); border-radius: 4px; text-align: center;
                           font-size: 12px; background-color: rgba(226,232,240,200); }
            QProgressBar::chunk { background-color: #00695C; border-radius: 3px; }
        """)
        mem_layout.addWidget(self.hw_mem_bar)
        self.hw_mem_detail_label = QLabel("--")
        self.hw_mem_detail_label.setStyleSheet("font-size: 12px; color: #00695C; font-weight: bold;")
        mem_layout.addWidget(self.hw_mem_detail_label)
        self.hw_gpu_mem_label = QLabel(self._tr("lbl_gpu_mem"))
        self._i18n_refs["hw_lbl_gpu_mem"] = self.hw_gpu_mem_label
        self.hw_gpu_mem_label.setStyleSheet("font-size: 12px; color: #6A1B9A; font-weight: bold;")
        mem_layout.addWidget(self.hw_gpu_mem_label)
        gpu_layout.addWidget(mem_group)
        gpu_layout.addStretch()

        hw_splitter.addWidget(gpu_widget)

        # ===== 底部：实时频率曲线图 =====
        self.hw_plot = PlotWidget(title=self._tr("chart_hw_freq_title"))
        self._i18n_refs["hw_plot"] = self.hw_plot
        self._apply_realtime_plot_styling(self.hw_plot, y_left=self._tr("chart_hw_freq_left"),
                                          y_left_color="#60a5fa", x_label=self._tr("chart_fps_bottom"))
        self.hw_plot.setTitle(self._tr("chart_hw_freq_title"), color="#f8fafc", size="12pt")
        self.hw_plot.addLegend()
        self._hw_curves = {}  # {label: curve}
        self._hw_plot_start_time = 0

        # ===== 温度曲线图 =====
        self.hw_temp_plot = PlotWidget(title=self._tr("chart_temp_title"))
        self._i18n_refs["hw_temp_plot"] = self.hw_temp_plot
        self._apply_realtime_plot_styling(self.hw_temp_plot, y_left=self._tr("chart_temp_left"),
                                          y_left_color="#fb923c", x_label=self._tr("chart_fps_bottom"))
        self.hw_temp_plot.setTitle(self._tr("chart_temp_title"), color="#f8fafc", size="12pt")
        self.hw_temp_plot.addLegend()
        self._hw_temp_curve = None
        self._hw_history_temp = []

        # ===== CPU 使用率 / 内存使用率曲线图 =====
        self.hw_usage_plot = PlotWidget(title=self._tr("chart_usage_title"))
        self._i18n_refs["hw_usage_plot"] = self.hw_usage_plot
        self._apply_realtime_plot_styling(self.hw_usage_plot, y_left=self._tr("chart_usage_left"),
                                          y_left_color="#f87171", x_label=self._tr("chart_fps_bottom"))
        self.hw_usage_plot.setTitle(self._tr("chart_usage_title"), color="#f8fafc", size="12pt")
        self.hw_usage_plot.addLegend()
        self._hw_usage_curves = {}  # {"CPU 使用率": curve, "内存使用率": curve}

        # ===== 设备功率曲线图 =====
        self.hw_power_plot = PlotWidget(title=self._tr("chart_power_title"))
        self._i18n_refs["hw_power_plot"] = self.hw_power_plot
        self._apply_realtime_plot_styling(self.hw_power_plot, y_left=self._tr("chart_power_left"),
                                          y_left_color="#a78bfa", x_label=self._tr("chart_fps_bottom"))
        self.hw_power_plot.setTitle(self._tr("chart_power_title"), color="#f8fafc", size="12pt")
        self.hw_power_plot.addLegend()
        self._hw_power_curve = None
        self._hw_history_power = []

        hw_splitter.setStretchFactor(0, 1)
        hw_splitter.setStretchFactor(1, 1)
        hw_splitter.setSizes([500, 500])

        layout.addWidget(hw_splitter, stretch=1)
        layout.addWidget(self.hw_plot, stretch=1)
        layout.addWidget(self.hw_usage_plot, stretch=1)
        layout.addWidget(self.hw_temp_plot, stretch=1)
        layout.addWidget(self.hw_power_plot, stretch=1)

        self.tab_widget.addTab(tab2, self._tr("tab_hw"))

    def _rating_to_label(self, rating_key: str) -> str:
        """将 rating key (good/warn/bad) 翻译为当前语言的评级文字"""
        mapping = {"good": "rating_good", "warn": "rating_warn", "bad": "rating_bad"}
        return self._tr(mapping.get(rating_key, "rating_good"))

    def _build_load_conclusion(self, summary: dict) -> list:
        """根据 summary 原始数据生成当前语言的结论文本行列表"""
        st = summary.get("stats", {}) or {}
        c = st.get("cpu") or {}
        g = st.get("gpu") or {}
        m = st.get("mem") or {}
        t = st.get("cpu_temp") or st.get("temp") or {}
        rating_key = summary.get("rating_key") or summary.get("rating") or "good"
        rating_label = self._rating_to_label(rating_key)
        issues = summary.get("issues", []) or []
        actual_dur = int(summary.get("duration_sec") or 0)

        lines = []
        dur_min = actual_dur // 60
        dur_sec = actual_dur % 60
        lines.append(self._tr("load_con_duration").format(min=dur_min, sec=dur_sec, total=actual_dur))
        lines.append(self._tr("load_con_samples").format(
            cpu=c.get("n") or 0, gpu=g.get("n") or 0, mem=m.get("n") or 0, temp=t.get("n") or 0))
        lines.append("")
        # CPU
        if c.get("avg") is not None:
            lines.append(self._tr("load_con_cpu").format(avg=c["avg"], max=c.get("max", 0), min=c.get("min", 0)))
        else:
            lines.append(self._tr("load_con_cpu_na"))
        # GPU
        if g.get("avg") is not None:
            lines.append(self._tr("load_con_gpu").format(avg=g["avg"], max=g.get("max", 0), min=g.get("min", 0)))
        else:
            lines.append(self._tr("load_con_gpu_na"))
        # 内存
        if m.get("avg") is not None:
            lines.append(self._tr("load_con_mem").format(avg=m["avg"], max=m.get("max", 0)))
        else:
            lines.append(self._tr("load_con_mem_na"))
        # 温度
        if t.get("avg") is not None:
            lines.append(self._tr("load_con_temp").format(avg=t["avg"], max=t.get("max", 0), min=t.get("min", 0)))
        else:
            lines.append(self._tr("load_con_temp_na"))
        lines.append("")
        lines.append(self._tr("load_con_errors").format(count=summary.get("errors", 0)))
        if issues:
            lines.append(self._tr("load_con_issues_found").format(count=len(issues)))
            for ikey, iparams in issues:
                lines.append("  · " + self._tr(ikey).format(**iparams))
        else:
            lines.append(self._tr("load_con_no_issues"))
        lines.append("")
        lines.append(self._tr("load_con_rating").format(rating=rating_label))
        con_key = {"good": "load_con_good", "warn": "load_con_warn", "bad": "load_con_bad"}.get(rating_key, "load_con_good")
        lines.append(self._tr(con_key))
        return lines

    def _init_load_test_tab(self, platform: str):
        """构建负载测试 Tab（安卓 / iOS 通用）— 三页式：原理页 → 运行页 → 结果页

        - Page 0 原理页：负载测试原理 + 风险提示，确认后跳转运行页
        - Page 1 运行页：仅计时数字 + 仪表盘环形动画 + 停止按钮（不展示实时数据）
        - Page 2 结果页：稳定性结论 + CPU使用率表格 + CPU/内存/温度曲线 + 导出报告
        """
        is_android = platform.lower() == "android"
        prefix = "android_" if is_android else "ios_"
        target_tab = self.tab_widget if is_android else self.ios_tab_widget
        # 负载测试 Tab 使用独立的设备下拉框，避免复用帧率测试 Tab 的 combo 导致控件被 reparent
        device_combo = QComboBox()
        device_combo.setMinimumWidth(280)
        if is_android:
            self.android_load_device_combo = device_combo
        else:
            self.ios_load_device_combo = device_combo
        title = self._tr("tab_load_test")

        tab = QWidget()
        tab.setStyleSheet("background-color: #f8fafc;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 顶部：设备选择 + 控制按钮
        top_card = QFrame()
        top_card.setStyleSheet("""
            QFrame { background-color: white; border: 1px solid #e2e8f0; border-radius: 14px; }
        """)
        top_lay = QHBoxLayout(top_card)
        top_lay.setContentsMargins(24, 20, 24, 20)
        top_lay.setSpacing(18)

        _lbl = QLabel(self._tr("lbl_load_device"))
        self._i18n_refs[f"{prefix}load_lbl_device"] = _lbl
        top_lay.addWidget(_lbl)
        top_lay.addWidget(device_combo, 1)

        refresh_btn = QPushButton(self._tr("btn_refresh_device"))
        self._i18n_refs[f"{prefix}load_btn_refresh"] = refresh_btn
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton { background-color: #e2e8f0; color: #334155; border-radius: 8px;
                          padding: 8px 18px; border: none; font-size: 14px; }
            QPushButton:hover { background-color: #cbd5e1; }
        """)

        def _do_refresh_load_devices():
            """负载测试 Tab 专用刷新：直接检测设备并填充独立 combo"""
            combo = device_combo
            combo.clear()
            if is_android:
                try:
                    devices = self.adb_client.get_devices()
                    if devices:
                        for device_id, status in devices:
                            try:
                                model = self.adb_client.get_device_model(device_id)
                                label = f"{model} ({device_id})"
                            except Exception:
                                label = f"{device_id}"
                            combo.addItem(label, device_id)
                    else:
                        combo.addItem(self._tr("combo_no_device_tip"), "")
                except Exception as e:
                    combo.addItem(self._tr("combo_error_prefix") + str(e), "")
            else:
                try:
                    devices = self.ios_client.get_devices()
                    if devices:
                        for udid, status in devices:
                            combo.addItem(f"{udid[:16]}... ({status})", udid)
                    else:
                        combo.addItem(self._tr("combo_no_ios_device_tip"), "")
                except Exception as e:
                    combo.addItem(self._tr("combo_error_prefix") + str(e), "")

        refresh_btn.clicked.connect(_do_refresh_load_devices)
        top_lay.addWidget(refresh_btn)

        layout.addWidget(top_card)

        # ===== 三页式 QStackedWidget =====
        stack = QStackedWidget()

        # --- Page 0: 原理与风险提示 ---
        page0 = QWidget()
        p0_lay = QVBoxLayout(page0)
        p0_lay.setContentsMargins(0, 0, 0, 0)
        p0_lay.setSpacing(16)

        principle_card = QFrame()
        principle_card.setStyleSheet("QFrame { background-color: white; border: 1px solid #e2e8f0; border-radius: 14px; }")
        pc_lay = QVBoxLayout(principle_card)
        pc_lay.setContentsMargins(28, 24, 28, 24)
        pc_lay.setSpacing(12)
        pc_title = QLabel(self._tr("load_principle_title"))
        self._i18n_refs[f"{prefix}load_principle_title"] = pc_title
        pc_title.setFont(QFont("PingFang SC", 18, QFont.Bold))
        pc_title.setStyleSheet("color: #0f172a;")
        pc_lay.addWidget(pc_title)
        pc_body = QLabel(self._tr("load_principle_body"))
        self._i18n_refs[f"{prefix}load_principle_body"] = pc_body
        pc_body.setWordWrap(True)
        pc_body.setFont(QFont("PingFang SC", 13))
        pc_body.setStyleSheet("color: #334155;")
        pc_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        pc_lay.addWidget(pc_body)
        p0_lay.addWidget(principle_card)

        risk_card = QFrame()
        risk_card.setStyleSheet("QFrame { background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 14px; }")
        rc_lay = QVBoxLayout(risk_card)
        rc_lay.setContentsMargins(28, 24, 28, 24)
        rc_lay.setSpacing(12)
        rc_title = QLabel(self._tr("load_risk_title"))
        self._i18n_refs[f"{prefix}load_risk_title"] = rc_title
        rc_title.setFont(QFont("PingFang SC", 18, QFont.Bold))
        rc_title.setStyleSheet("color: #dc2626;")
        rc_lay.addWidget(rc_title)
        rc_body = QLabel(self._tr("load_risk_body"))
        self._i18n_refs[f"{prefix}load_risk_body"] = rc_body
        rc_body.setWordWrap(True)
        rc_body.setFont(QFont("PingFang SC", 13))
        rc_body.setStyleSheet("color: #991b1b;")
        rc_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rc_lay.addWidget(rc_body)
        p0_lay.addWidget(risk_card)

        p0_lay.addStretch()

        confirm_start_btn = QPushButton(self._tr("btn_load_confirm_start"))
        self._i18n_refs[f"{prefix}load_btn_confirm"] = confirm_start_btn
        confirm_start_btn.setCursor(Qt.PointingHandCursor)
        confirm_start_btn.setMinimumHeight(48)
        confirm_start_btn.setMinimumWidth(280)
        confirm_start_btn.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #ef4444, stop:1 #dc2626); color: white; border-radius: 10px;
                        padding: 10px 32px; font-size: 16px; font-weight: bold; border: none; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #dc2626, stop:1 #b91c1c); }
        """)
        p0_lay.addWidget(confirm_start_btn, alignment=Qt.AlignCenter)

        stack.addWidget(page0)

        # --- Page 1: 运行页（计时 + 仪表盘动画 + 停止）---
        page1 = QWidget()
        p1_lay = QVBoxLayout(page1)
        p1_lay.setContentsMargins(0, 10, 0, 10)
        p1_lay.setSpacing(16)

        running_title = QLabel(self._tr("load_running_title"))
        self._i18n_refs[f"{prefix}load_running_title"] = running_title
        running_title.setAlignment(Qt.AlignCenter)
        running_title.setFont(QFont("PingFang SC", 22, QFont.Bold))
        running_title.setStyleSheet("color: #0f172a;")
        p1_lay.addWidget(running_title)

        time_value_label = QLabel("01:00:00")
        self._i18n_refs[f"{prefix}load_time_value"] = time_value_label
        time_value_label.setFont(QFont("Menlo", 64, QFont.Bold))
        time_value_label.setStyleSheet("color: #1e3a5f;")
        time_value_label.setAlignment(Qt.AlignCenter)
        p1_lay.addWidget(time_value_label)

        dashboard = DashboardAnimation()
        p1_lay.addWidget(dashboard, alignment=Qt.AlignCenter)

        running_hint = QLabel(self._tr("load_running_hint_anim"))
        self._i18n_refs[f"{prefix}load_running_hint"] = running_hint
        running_hint.setAlignment(Qt.AlignCenter)
        running_hint.setFont(QFont("PingFang SC", 13))
        running_hint.setStyleSheet("color: #64748b;")
        running_hint.setWordWrap(True)
        p1_lay.addWidget(running_hint)

        p1_lay.addStretch()

        stop_btn = QPushButton(self._tr("btn_stop_load"))
        self._i18n_refs[f"{prefix}load_btn_stop"] = stop_btn
        stop_btn.setCursor(Qt.PointingHandCursor)
        stop_btn.setMinimumHeight(44)
        stop_btn.setMinimumWidth(200)
        stop_btn.setStyleSheet("""
            QPushButton { background-color: #475569; color: white; border-radius: 10px;
                          padding: 10px 32px; font-size: 16px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #334155; }
        """)
        p1_lay.addWidget(stop_btn, alignment=Qt.AlignCenter)

        stack.addWidget(page1)

        # --- Page 2: 结果页（紧凑布局，一页内展示表格 + 3 条折线 + 顶部摘要）---
        page2 = QWidget()
        p2_lay = QVBoxLayout(page2)
        p2_lay.setContentsMargins(14, 10, 14, 10)
        p2_lay.setSpacing(6)

        # 2.1 顶部栏：标题 + 实际时长标签 + 操作按钮（预览 / 导出菜单含 JPG / 重新测试）
        result_top = QFrame()
        result_top.setStyleSheet("QFrame { background-color: white; border: 1px solid #e2e8f0; border-radius: 10px; }")
        rt_lay = QHBoxLayout(result_top)
        rt_lay.setContentsMargins(16, 10, 16, 10)
        rt_lay.setSpacing(10)
        result_title_lbl = QLabel(self._tr("load_result_title"))
        self._i18n_refs[f"{prefix}load_result_title"] = result_title_lbl
        result_title_lbl.setFont(QFont("PingFang SC", 16, QFont.Bold))
        result_title_lbl.setStyleSheet("color: #0f172a;")
        rt_lay.addWidget(result_title_lbl)
        rt_lay.addStretch()

        result_elapsed_lbl = QLabel(f"⏱ {self._tr('lbl_duration_short')} 00:00:00")
        self._i18n_refs[f"{prefix}load_elapsed_lbl"] = result_elapsed_lbl
        result_elapsed_lbl.setFont(QFont("Menlo", 13, QFont.Bold))
        result_elapsed_lbl.setStyleSheet("color: #0369a1;")
        rt_lay.addWidget(result_elapsed_lbl)

        btn_load_retest = QPushButton(self._tr("btn_retest_load"))
        self._i18n_refs[f"{prefix}load_btn_retest"] = btn_load_retest
        btn_load_retest.setCursor(Qt.PointingHandCursor)
        btn_load_retest.setMinimumHeight(34)
        btn_load_retest.setEnabled(False)
        btn_load_retest.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2563eb, stop:1 #1d4ed8); color:white;
                          border-radius: 8px; padding: 6px 16px; font-size: 13px; font-weight: bold; border: none; }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1d4ed8, stop:1 #1e40af); }
            QPushButton:disabled { background: #94a3b8; }
        """)
        rt_lay.addWidget(btn_load_retest)

        btn_load_preview = QPushButton(self._tr("btn_preview_report"))
        self._i18n_refs[f"{prefix}load_btn_preview"] = btn_load_preview
        btn_load_preview.setCursor(Qt.PointingHandCursor)
        btn_load_preview.setMinimumHeight(34)
        btn_load_preview.setEnabled(False)
        btn_load_preview.setStyleSheet("""
            QPushButton { background-color: #0ea5e9; color: white; border-radius: 8px;
                          padding: 6px 16px; font-size: 13px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #0284c7; }
            QPushButton:disabled { background: #94a3b8; }
        """)
        rt_lay.addWidget(btn_load_preview)

        # 导出菜单：CSV / HTML / JPG
        btn_load_export_menu = QPushButton(self._tr("btn_export_report"))
        self._i18n_refs[f"{prefix}load_btn_export_menu"] = btn_load_export_menu
        btn_load_export_menu.setCursor(Qt.PointingHandCursor)
        btn_load_export_menu.setMinimumHeight(34)
        btn_load_export_menu.setEnabled(False)
        btn_load_export_menu.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; border-radius: 8px;
                          padding: 6px 16px; font-size: 13px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background: #94a3b8; }
        """)
        export_menu = QMenu(btn_load_export_menu)
        act_load_export_csv = QAction("📄 " + self._tr("btn_export_csv"), self)
        act_load_export_html = QAction("🌐 " + self._tr("menu_html_export"), self)
        act_load_export_jpg = QAction("🖼 " + self._tr("menu_jpg_export"), self)
        # 注意：不在此处直接绑定导出动作（方法尚未定义，会触发 AttributeError）
        # 稍后在同作用域尾部，通过 disconnect/connect 绑定到本地闭包 _export_csv/_export_html/_export_jpg
        export_menu.addAction(act_load_export_csv)
        export_menu.addAction(act_load_export_html)
        export_menu.addAction(act_load_export_jpg)
        btn_load_export_menu.setMenu(export_menu)
        rt_lay.addWidget(btn_load_export_menu)
        p2_lay.addWidget(result_top)

        # 2.2 摘要卡片（一行 9 个紧凑卡片：评级/时长/异常  +  CPU/内存/温度 各均+峰）
        summary_row = QFrame()
        summary_row.setStyleSheet("QFrame { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }")
        s_lay = QHBoxLayout(summary_row)
        s_lay.setContentsMargins(10, 8, 10, 8)
        s_lay.setSpacing(6)

        def _tiny_card(title, val, color):
            w = QFrame()
            w.setStyleSheet(f"QFrame {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }}")
            lv = QVBoxLayout(w)
            lv.setContentsMargins(8, 5, 8, 5)
            lv.setSpacing(1)
            t = QLabel(title)
            t.setStyleSheet("color: #64748b; font-size: 11px;")
            v = QLabel(str(val))
            v.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 700;")
            lv.addWidget(t)
            lv.addWidget(v, alignment=Qt.AlignCenter)
            w.setFixedHeight(58)
            return w, v

        c1, rating_value = _tiny_card(self._tr("lbl_rating"), "-", "#0277BD")
        c2, elapsed_value = _tiny_card(self._tr("lbl_duration_short"), "00:00", "#0288D1")
        c3, errors_value = _tiny_card(self._tr("lbl_errors"), "0", "#546E7A")
        c4, card_cpu_avg_value = _tiny_card(self._tr("lbl_cpu_avg_pct"), "-", "#dc2626")
        c5, card_cpu_max_value = _tiny_card(self._tr("lbl_cpu_peak_pct"), "-", "#991b1b")
        c6, card_mem_avg_value = _tiny_card(self._tr("lbl_mem_avg_mb"), "-", "#7c3aed")
        c7, card_mem_max_value = _tiny_card(self._tr("lbl_mem_peak_mb"), "-", "#5b21b6")
        c8, card_temp_avg_value = _tiny_card(self._tr("lbl_temp_avg_c"), "-", "#ea580c")
        c9, card_temp_max_value = _tiny_card(self._tr("lbl_temp_peak_c"), "-", "#c2410c")
        for w in [c1, c2, c3, c4, c5, c6, c7, c8, c9]:
            s_lay.addWidget(w, 1)
        p2_lay.addWidget(summary_row)

        # 2.3 主区：左 = 详细统计表；右 = 3 条折线图（堆叠，每条约 100px 高）
        main_grid = QFrame()
        main_grid.setStyleSheet("QFrame { background: transparent; }")
        mg_lay = QGridLayout(main_grid)
        mg_lay.setContentsMargins(0, 0, 0, 0)
        mg_lay.setSpacing(8)

        # 左：详细统计表（高度限制为 ~310，一页内）
        left_wrap = QFrame()
        left_wrap.setStyleSheet("QFrame { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }")
        lw_lay = QVBoxLayout(left_wrap)
        lw_lay.setContentsMargins(8, 6, 8, 6)
        lh = QLabel(self._tr("grp_load_detail_table"))
        lh.setFont(QFont("PingFang SC", 12, QFont.Bold))
        lh.setStyleSheet("color: #0f172a;")
        lw_lay.addWidget(lh)
        cpu_table = QTableWidget()
        cpu_table.setColumnCount(5)
        cpu_table.setHorizontalHeaderLabels([self._tr("tbl_load_cpu_stats"), self._tr("tbl_load_col_samples"), self._tr("tbl_load_col_avg"), self._tr("tbl_load_col_max"), self._tr("tbl_load_col_min")])
        cpu_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        cpu_table.horizontalHeader().setMinimumSectionSize(50)
        cpu_table.setAlternatingRowColors(True)
        cpu_table.setStyleSheet("QTableWidget { background: white; gridline-color: #e2e8f0; border: none; font-size: 12px; }"
                                 "QHeaderView::section { background: #f1f5f9; font-weight: bold; font-size: 12px; padding: 2px; }"
                                 "QTableWidget::item { padding: 1px 4px; }")
        cpu_table.setFixedHeight(290)
        cpu_table.verticalHeader().setDefaultSectionSize(19)
        cpu_table.setEditTriggers(QTableWidget.NoEditTriggers)
        cpu_table.setSelectionBehavior(QTableWidget.SelectRows)
        cpu_table.verticalHeader().setVisible(False)
        lw_lay.addWidget(cpu_table, 1)

        # 右：3 条折线（堆叠）
        right_wrap = QFrame()
        right_wrap.setStyleSheet("QFrame { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }")
        rw_lay = QVBoxLayout(right_wrap)
        rw_lay.setContentsMargins(8, 6, 8, 6)
        rw_lay.setSpacing(5)
        rh = QLabel(self._tr("grp_load_result_charts"))
        rh.setFont(QFont("PingFang SC", 12, QFont.Bold))
        rh.setStyleSheet("color: #0f172a;")
        rw_lay.addWidget(rh)

        result_cpu_plot = pg.PlotWidget()
        result_cpu_plot.setBackground("#2b2f36")
        result_cpu_plot.showGrid(x=True, y=True, alpha=0.25)
        result_cpu_plot.setLabel("left", self._tr("chart_load_cpu_usage"), color="#ff6b6b")
        result_cpu_plot.setLabel("bottom", self._tr("chart_load_temp_bottom"))
        result_cpu_plot.setMouseEnabled(x=True, y=False)
        result_cpu_plot.setMenuEnabled(False)
        result_cpu_plot.setMinimumHeight(95)
        result_cpu_plot.setMaximumHeight(105)
        result_cpu_plot.getAxis('left').setPen(pg.mkPen("#ff6b6b", width=2))
        result_cpu_plot.getAxis('bottom').setPen(pg.mkPen("#cbd5e1"))
        result_cpu_plot.getAxis('left').setTextPen(pg.mkPen("#ff6b6b"))
        result_cpu_plot.getAxis('bottom').setTextPen(pg.mkPen("#e2e8f0"))
        rw_lay.addWidget(result_cpu_plot, 1)

        result_mem_plot = pg.PlotWidget()
        result_mem_plot.setBackground("#2b2f36")
        result_mem_plot.showGrid(x=True, y=True, alpha=0.25)
        result_mem_plot.setLabel("left", self._tr("chart_load_mem_usage"), color="#a78bfa")
        result_mem_plot.setLabel("bottom", self._tr("chart_load_temp_bottom"))
        result_mem_plot.setMouseEnabled(x=True, y=False)
        result_mem_plot.setMenuEnabled(False)
        result_mem_plot.setMinimumHeight(95)
        result_mem_plot.setMaximumHeight(105)
        result_mem_plot.getAxis('left').setPen(pg.mkPen("#a78bfa", width=2))
        result_mem_plot.getAxis('bottom').setPen(pg.mkPen("#cbd5e1"))
        result_mem_plot.getAxis('left').setTextPen(pg.mkPen("#a78bfa"))
        result_mem_plot.getAxis('bottom').setTextPen(pg.mkPen("#e2e8f0"))
        rw_lay.addWidget(result_mem_plot, 1)

        result_temp_plot = pg.PlotWidget()
        result_temp_plot.setBackground("#2b2f36")
        result_temp_plot.showGrid(x=True, y=True, alpha=0.25)
        result_temp_plot.setLabel("left", self._tr("chart_load_temp_result"), color="#fb923c")
        result_temp_plot.setLabel("bottom", self._tr("chart_load_temp_bottom"))
        result_temp_plot.setMouseEnabled(x=True, y=False)
        result_temp_plot.setMenuEnabled(False)
        result_temp_plot.setMinimumHeight(95)
        result_temp_plot.setMaximumHeight(105)
        result_temp_plot.getAxis('left').setPen(pg.mkPen("#fb923c", width=2))
        result_temp_plot.getAxis('bottom').setPen(pg.mkPen("#cbd5e1"))
        result_temp_plot.getAxis('left').setTextPen(pg.mkPen("#fb923c"))
        result_temp_plot.getAxis('bottom').setTextPen(pg.mkPen("#e2e8f0"))
        rw_lay.addWidget(result_temp_plot, 1)

        mg_lay.addWidget(left_wrap, 0, 0)
        mg_lay.addWidget(right_wrap, 0, 1)
        mg_lay.setColumnStretch(0, 10)
        mg_lay.setColumnStretch(1, 12)
        p2_lay.addWidget(main_grid, 1)

        # 结论卡片（放在最底部，高度紧凑）
        conclusion_card = QFrame()
        conclusion_card.setStyleSheet("QFrame { background: white; border: 1px solid #e2e8f0; border-radius: 10px; }")
        conclusion_card.setMaximumHeight(90)
        cc_lay = QVBoxLayout(conclusion_card)
        cc_lay.setContentsMargins(14, 8, 14, 8)
        cc_lay.setSpacing(4)
        cc_title = QLabel(self._tr("lbl_conclusion"))
        self._i18n_refs[f"{prefix}load_lbl_conclusion"] = cc_title
        cc_title.setFont(QFont("PingFang SC", 13, QFont.Bold))
        cc_title.setStyleSheet("color: #0f172a;")
        cc_lay.addWidget(cc_title)
        cc_text = QLabel(self._tr("lbl_waiting"))
        self._i18n_refs[f"{prefix}load_lbl_waiting"] = cc_text
        cc_text.setWordWrap(True)
        cc_text.setFont(QFont("PingFang SC", 11))
        cc_text.setStyleSheet("color: #64748b;")
        cc_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cc_lay.addWidget(cc_text, 1)
        p2_lay.addWidget(conclusion_card)

        stack.addWidget(page2)

        layout.addWidget(stack, stretch=1)

        # 加入 Tab 栏
        target_tab.addTab(tab, title)

        # 创建后立即刷新一次设备列表
        _do_refresh_load_devices()

        # 状态存成员变量
        state = {
            "stack": stack,
            "thread": None,
            "confirm_start_btn": confirm_start_btn,
            "stop_btn": stop_btn,
            "export_btn": btn_load_export_menu,  # 负载测试 Tab：导出=菜单按钮（分 CSV/HTML/JPG）
            "btn_retest": btn_load_retest,
            "btn_preview": btn_load_preview,
            "btn_export_menu": btn_load_export_menu,
            "act_export_csv": act_load_export_csv,
            "act_export_html": act_load_export_html,
            "act_export_jpg": act_load_export_jpg,
            "time_value": time_value_label,
            "dashboard": dashboard,
            "cc_text": cc_text,
            "cpu_table": cpu_table,
            "result_cpu_plot": result_cpu_plot,
            "result_mem_plot": result_mem_plot,
            "result_temp_plot": result_temp_plot,
            "result_elapsed_lbl": result_elapsed_lbl,
            "rating_value": rating_value,
            "elapsed_value": elapsed_value,
            "errors_value": errors_value,
            "card_cpu_avg_value": card_cpu_avg_value,
            "card_cpu_max_value": card_cpu_max_value,
            "card_mem_avg_value": card_mem_avg_value,
            "card_mem_max_value": card_mem_max_value,
            "card_temp_avg_value": card_temp_avg_value,
            "card_temp_max_value": card_temp_max_value,
            "is_android": is_android,
            "last_summary": None,
        }
        setattr(self, f"_{prefix}load_state", state)

        def fmt_hms(sec: int) -> str:
            h = sec // 3600
            m = (sec % 3600) // 60
            s = sec % 60
            return f"{h:02d}:{m:02d}:{s:02d}"

        def _on_tick(elapsed: int, remaining: int, snap: dict):
            # 运行页：倒计时显示（从 01:00:00 倒数到 00:00:00）
            remaining_v = max(0, int(remaining))
            elapsed_v = max(0, int(elapsed))
            state["elapsed_sec"] = elapsed_v
            state["remaining_sec"] = remaining_v
            time_value_label.setText(fmt_hms(remaining_v))
            # 数据库：写入负载测试采样
            try:
                if self._db_load_session_id:
                    self._db.insert_load_test_sample(self._db_load_session_id, float(elapsed), snap)
            except Exception:
                pass

        def _on_finished_summary(summary: dict):
            stop_btn.setEnabled(False)
            confirm_start_btn.setEnabled(True)
            # 停止仪表盘动画
            dashboard.stop_anim() if hasattr(dashboard, "stop_anim") else dashboard.stop()
            # 播放"叮"提示音
            try:
                _play_ding()
            except Exception:
                pass
            # 弹窗大字显示"测试已完成"
            QMessageBox.information(self, self._tr("load_test_complete_title"),
                                    self._tr("load_test_complete_msg"))
            # 自动跳转结果页
            stack.setCurrentIndex(2)
            # 存储结论标签供填充函数复用
            state["conclusion_label"] = cc_text
            state["last_summary"] = summary
            # 生成翻译后的结论文本行（中英文适配）
            summary["lines"] = self._build_load_conclusion(summary)
            # 调用统一填充函数：卡片/表/曲线/按钮状态
            _fill_result_page(summary)
            # 数据库：写入负载测试汇总并结束会话
            try:
                if self._db_load_session_id:
                    self._db.insert_load_test_summary(self._db_load_session_id, summary)
                    actual_dur = summary.get("duration_sec") or state.get("elapsed_sec", 3600)
                    self._db.finish_session(self._db_load_session_id, actual_dur)
                    self._db_load_session_id = None
            except Exception as e:
                log_exception(e, "数据库: 写入负载测试汇总失败")

            # 保存到 UI 缓存 + 历史记录（左Tab列表）
            try:
                dur_final = summary.get("duration_sec") or state.get("elapsed_sec", 0)
                start_dt = state.get("start_dt") or datetime.now()
                end_dt = start_dt + timedelta(seconds=int(dur_final))
                report_id = f"load_{start_dt.strftime('%Y%m%d%H%M%S')}"
                rep = {
                    "id": report_id,
                    "start_time": start_dt,
                    "end_time": end_dt,
                    "duration_sec": int(dur_final),
                    "device_id": device_combo.currentData() or "",
                    "platform": "android" if is_android else "ios",
                    "rating": summary.get("rating_key") or summary.get("rating") or "good",
                    "rating_key": summary.get("rating_key") or summary.get("rating") or "good",
                    "issues": summary.get("issues", []) or [],
                    "errors": summary.get("errors", 0),
                    "stats": summary.get("stats", {}) or {},
                    "time_series": summary.get("time_series", {}) or {},
                    "lines": summary.get("lines", []) or [],
                }
                target_deque = self._load_reports if is_android else self._ios_load_reports
                if len(target_deque) >= 5:
                    target_deque.popleft()
                target_deque.append(rep)
                # 刷新历史列表
                try:
                    self._history_refresh_lists()
                except Exception:
                    pass
            except Exception as e:
                log_exception(e, "负载测试结果追加到历史失败")

        def _on_error(msg: str):
            _logger.warning(f"负载测试错误: {msg}")

        def _fill_result_page(summary: dict):
            """填充结果页所有控件 + 使能按钮"""
            # 时长（以实际为准：优先 state 里的 elapsed_sec，其次 summary）
            elapsed = int(state.get("elapsed_sec") or summary.get("duration_sec") or 0)
            state["elapsed_sec"] = elapsed
            summary["duration_sec"] = elapsed
            hrs, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            hhmmss = f"{hrs:02d}:{mins:02d}:{secs:02d}"
            hhmm = f"{mins + hrs * 60:02d}:{secs:02d}"
            # 顶部栏：实际时长
            rel = state.get("result_elapsed_lbl")
            if rel is not None:
                rel.setText(f"⏱ {self._tr('lbl_duration_short')} {hhmmss}")
            # 摘要卡片
            rv = state.get("rating_value")
            if rv is not None:
                rating_key = summary.get("rating_key") or summary.get("rating") or "good"
                rating_label = self._rating_to_label(rating_key)
                rv.setText(rating_label)
                rating_color = {"good": "#16a34a", "warn": "#f59e0b", "bad": "#dc2626"}.get(rating_key, "#0277BD")
                rv.setStyleSheet(f"color: {rating_color}; font-size: 15px; font-weight: 700;")
            ev = state.get("elapsed_value")
            if ev is not None:
                ev.setText(hhmm if hrs == 0 else hhmmss)
            errv = state.get("errors_value")
            if errv is not None:
                errv.setText(str(summary.get("errors", 0)))
            st = summary.get("stats", {}) or {}
            c = (st.get("cpu") or {})
            cv = state.get("card_cpu_avg_value")
            if cv is not None:
                cv.setText(f"{c.get('avg', '-')}" if isinstance(c.get('avg'), (int, float)) else "-")
            cmv = state.get("card_cpu_max_value")
            if cmv is not None:
                cmv.setText(f"{c.get('max', '-')}" if isinstance(c.get('max'), (int, float)) else "-")
            m = (st.get("mem") or {})
            mv = state.get("card_mem_avg_value")
            if mv is not None:
                mv.setText(f"{m.get('avg', '-')}" if isinstance(m.get('avg'), (int, float)) else "-")
            mmv = state.get("card_mem_max_value")
            if mmv is not None:
                mmv.setText(f"{m.get('max', '-')}" if isinstance(m.get('max'), (int, float)) else "-")
            t = (st.get("cpu_temp") or {})
            tv = state.get("card_temp_avg_value")
            if tv is not None:
                tv.setText(f"{t.get('avg', '-')}" if isinstance(t.get('avg'), (int, float)) else "-")
            tmv = state.get("card_temp_max_value")
            if tmv is not None:
                tmv.setText(f"{t.get('max', '-')}" if isinstance(t.get('max'), (int, float)) else "-")

            # 统计表
            tbl = state.get("cpu_table")
            if tbl is not None:
                tbl.setRowCount(0)
                rows_to_set: list[tuple] = []
                _metric_keys = [
                    ("cpu", "load_metric_cpu"),
                    ("gpu", "load_metric_gpu"),
                    ("mem", "load_metric_mem"),
                    ("cpu_temp", "load_metric_cpu_temp"),
                ]
                for mkey, tr_key in _metric_keys:
                    s = st.get(mkey) or {}
                    if not s:
                        continue
                    mname = self._tr(tr_key)
                    rows_to_set.append((
                        mname,
                        str(s.get("n", "-")),
                        f"{s['avg']:.1f}" if isinstance(s.get("avg"), (int, float)) else "-",
                        f"{s['max']:.1f}" if isinstance(s.get("max"), (int, float)) else "-",
                        f"{s['min']:.1f}" if isinstance(s.get("min"), (int, float)) else "-",
                    ))
                tbl.setRowCount(len(rows_to_set))
                for r, row in enumerate(rows_to_set):
                    for cidx, v in enumerate(row):
                        it = QTableWidgetItem(str(v))
                        it.setTextAlignment(Qt.AlignCenter)
                        tbl.setItem(r, cidx, it)

            # 3 条折线 — 必须过滤 None，且强制 float（pyqtgraph np.isfinite 不支持 object/None）
            ts = summary.get("time_series") or {}
            raw_times = ts.get("time", []) or []
            raw_cpus = ts.get("cpu", []) or []
            raw_mems = ts.get("mem", []) or []
            raw_temps = ts.get("cpu_temp", []) or []

            def _clean(xx, yy):
                xs, ys = [], []
                m = min(len(xx), len(yy))
                for i in range(m):
                    try:
                        xv = float(xx[i])
                        yv = float(yy[i])
                        if not (np.isnan(xv) or np.isnan(yv) or np.isinf(xv) or np.isinf(yv)):
                            xs.append(xv)
                            ys.append(yv)
                    except (TypeError, ValueError):
                        continue
                return np.array(xs, dtype=np.float64), np.array(ys, dtype=np.float64)

            if raw_times:
                pl_cpu = state.get("result_cpu_plot")
                if pl_cpu is not None:
                    pl_cpu.clear()
                    xs, ys = _clean(raw_times, raw_cpus)
                    if len(xs) > 0:
                        pl_cpu.plot(xs, ys, pen=mkPen("#ff6b6b", width=2.4), name="CPU(%)")
                        pl_cpu.addLegend(offset=(4, 4))
                pl_mem = state.get("result_mem_plot")
                if pl_mem is not None:
                    pl_mem.clear()
                    xs, ys = _clean(raw_times, raw_mems)
                    if len(xs) > 0:
                        pl_mem.plot(xs, ys, pen=mkPen("#a78bfa", width=2.4), name="MEM(MB)")
                        pl_mem.addLegend(offset=(4, 4))
                pl_temp = state.get("result_temp_plot")
                if pl_temp is not None:
                    pl_temp.clear()
                    xs, ys = _clean(raw_times, raw_temps)
                    if len(xs) > 0:
                        pl_temp.plot(xs, ys, pen=mkPen("#fb923c", width=2.4), name="TEMP(°C)")
                        pl_temp.addLegend(offset=(4, 4))

            # 结论正文
            cc_text = state.get("conclusion_label") or state.get("cc_text")
            if cc_text is not None:
                lines = summary.get("lines", []) or []
                cc_text.setText("\n".join(lines) if lines else "-")

            # 启用导出 / 预览 / 重新测试按钮
            bem = state.get("btn_export_menu")
            if bem is not None:
                bem.setEnabled(True)
            bp = state.get("btn_preview")
            if bp is not None:
                bp.setEnabled(True)
            br = state.get("btn_retest")
            if br is not None:
                br.setEnabled(True)
            stop_btn.setEnabled(False)
            confirm_start_btn.setEnabled(True)

        def _start():
            device_id = device_combo.currentData()
            if not device_id:
                QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_device"))
                return
            # 切换到运行页
            stack.setCurrentIndex(1)
            # 重置状态
            state["last_summary"] = None
            state["elapsed_sec"] = 0
            state["start_dt"] = datetime.now()
            confirm_start_btn.setEnabled(False)
            stop_btn.setEnabled(True)
            # 倒计时：从 01:00:00 开始倒数到 00:00:00
            time_value_label.setText("01:00:00")
            # 启动仪表盘动画
            dashboard.start()

            # 负载测试固定 1 小时倒计时
            max_duration = 3600
            if is_android:
                thread = LoadTestThread(
                    "android",
                    adb_client=self.adb_client,
                    device_id=device_id,
                    duration_sec=max_duration,
                )
            else:
                thread = LoadTestThread(
                    "ios",
                    ios_client=self.ios_client,
                    udid=device_id,
                    duration_sec=max_duration,
                )
            thread.tick.connect(_on_tick)
            thread.finished_summary.connect(_on_finished_summary)
            thread.error_occurred.connect(_on_error)
            state["thread"] = thread
            thread.start()
            _logger.info(f"{'安卓' if is_android else 'iOS'} 负载测试已启动（无固定时长，以实际停止为准）")

            # 创建数据库会话
            try:
                plat = "android" if is_android else "ios"
                dev_pk = self._db_get_or_create_device(device_id, plat)
                self._db_load_session_id = self._db.create_session(
                    device_id=dev_pk, platform=plat, test_type="load_test",
                    app_package="", refresh_rate=0, poll_interval=1.0
                )
            except Exception as e:
                log_exception(e, "数据库: 创建负载测试会话失败")

        def _stop():
            thr = state["thread"]
            if thr and thr.isRunning():
                thr.stop()
                thr.wait(5000)
                # 断开信号并清理引用
                try:
                    thr.disconnect()
                    thr.deleteLater()
                except Exception:
                    pass
                _logger.info("负载测试已手动停止")
                # 手动停止也要生成结论
                if thr.isFinished() and state["last_summary"] is None:
                    summary = thr._build_summary()
                    _on_finished_summary(summary)
                else:
                    stop_btn.setEnabled(False)
                    confirm_start_btn.setEnabled(True)
            else:
                stop_btn.setEnabled(False)
                confirm_start_btn.setEnabled(True)

        def _retest():
            """重新测试：回到开始页"""
            try:
                # 停掉当前线程（如有）
                thr = state.get("thread")
                if thr and thr.isRunning():
                    thr.stop()
                    thr.wait(4000)
                    try:
                        thr.disconnect()
                        thr.deleteLater()
                    except Exception:
                        pass
                # 清空结果控件状态
                bem = state.get("btn_export_menu")
                if bem is not None:
                    bem.setEnabled(False)
                bp = state.get("btn_preview")
                if bp is not None:
                    bp.setEnabled(False)
                br = state.get("btn_retest")
                if br is not None:
                    br.setEnabled(False)
                rel = state.get("result_elapsed_lbl")
                if rel is not None:
                    rel.setText(f"⏱ {self._tr('lbl_duration_short')} 00:00:00")
                # 回到开始页
                stack.setCurrentIndex(0)
                confirm_start_btn.setEnabled(True)
                stop_btn.setEnabled(False)
                # 停止仪表盘动画（DashboardAnimation 只有 stop_anim，无 stop）
                if hasattr(dashboard, "stop_anim"):
                    dashboard.stop_anim()
                elif hasattr(dashboard, "stop"):
                    dashboard.stop()
                time_value_label.setText("01:00:00")
                # 清除上次结果缓存，避免下次启动误用旧数据
                state["last_summary"] = None
                state["elapsed_sec"] = 0
                state["thread"] = None
            except Exception as _e:
                log_exception(_e, "负载测试: 重新测试失败")
                # 即使异常也确保回到开始页
                try:
                    stack.setCurrentIndex(0)
                    confirm_start_btn.setEnabled(True)
                    stop_btn.setEnabled(False)
                except Exception:
                    pass

        def _summary_or_warn():
            sm = state.get("last_summary")
            if not sm:
                QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_load_finish_first"))
            return sm

        def _export_csv():
            summary = _summary_or_warn()
            if not summary:
                return
            did = device_combo.currentData() or ""
            platform_name = self._tr("platform_android") if is_android else self._tr("platform_ios")
            desktop = os.path.expanduser("~/Desktop")
            fname_suffix = f"load_{'android' if is_android else 'ios'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ts = summary.get("time_series") or {}
            rating_key = summary.get("rating_key") or summary.get("rating") or "good"
            rating_label = self._rating_to_label(rating_key)
            csv_rows: list[list] = []
            csv_rows.append([self._tr("load_csv_report_title").format(platform=platform_name)])
            csv_rows.append([self._tr("lbl_stability_rating"), rating_label])
            csv_rows.append([self._tr("load_csv_export_time"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            csv_rows.append([self._tr("load_csv_device_id"), did if did else "-"])
            dur = int(state.get("elapsed_sec") or summary.get("duration_sec") or 0)
            csv_rows.append([self._tr("load_csv_duration_sec"), str(dur)])
            csv_rows.append([])
            csv_rows.append([self._tr("load_csv_conclusion")])
            for ln in summary.get("lines", []):
                csv_rows.append([ln])
            csv_rows.append([])
            st = summary.get("stats", {})
            csv_rows.append([self._tr("load_csv_stats")])
            csv_rows.append([self._tr("load_csv_metric"),
                             self._tr("tbl_load_col_samples"),
                             self._tr("tbl_load_col_avg"),
                             self._tr("tbl_load_col_max"),
                             self._tr("tbl_load_col_min")])
            _metric_keys = [
                ("cpu", self._tr("load_metric_cpu")),
                ("gpu", self._tr("load_metric_gpu")),
                ("mem", self._tr("load_metric_mem")),
                ("cpu_temp", self._tr("load_metric_cpu_temp")),
            ]
            for mkey, mname in _metric_keys:
                s = st.get(mkey) or {}
                csv_rows.append([mname, s.get("n"), s.get("avg"), s.get("max"), s.get("min")])
            if ts:
                csv_rows.append([])
                csv_rows.append([self._tr("load_csv_trend")])
                csv_rows.append([self._tr("load_csv_seconds"),
                                 self._tr("load_metric_cpu"),
                                 self._tr("load_metric_gpu"),
                                 self._tr("load_metric_mem"),
                                 self._tr("load_metric_cpu_temp")])
                times = ts.get("time", [])
                cpus = ts.get("cpu", [])
                gpus = ts.get("gpu", [])
                mems = ts.get("mem", [])
                temps = ts.get("cpu_temp", [])
                for i, t in enumerate(times):
                    csv_rows.append([
                        t,
                        cpus[i] if i < len(cpus) else "",
                        gpus[i] if i < len(gpus) else "",
                        mems[i] if i < len(mems) else "",
                        temps[i] if i < len(temps) else "",
                    ])
            default_path = os.path.join(desktop, f"{fname_suffix}.csv")
            try:
                saved = self._preview_csv(self._tr("preview_load_csv").format(platform=platform_name), csv_rows, default_path)
                if saved:
                    QMessageBox.information(self, self._tr("msg_success"), self._tr("msg_export_success_csv").format(path=saved))
                    _logger.info(f"CSV 报告已导出: {saved}")
            except Exception as e:
                log_exception(e, f"{platform_name} load CSV export failed")
                QMessageBox.critical(self, self._tr("msg_failed"), self._tr("msg_export_failed_simple").format(err=e))

        def _export_html():
            summary = _summary_or_warn()
            if not summary:
                return
            did = device_combo.currentData() or ""
            platform_name = self._tr("platform_android") if is_android else self._tr("platform_ios")
            desktop = os.path.expanduser("~/Desktop")
            fname_suffix = f"load_{'android' if is_android else 'ios'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            dur = int(state.get("elapsed_sec") or summary.get("duration_sec") or 0)
            hrs, rem = divmod(dur, 3600)
            mins, secs = divmod(rem, 60)
            dur_show = f"{dur}s ({hrs:02d}:{mins:02d}:{secs:02d})"
            rating_key = summary.get("rating_key") or summary.get("rating") or "good"
            rating_label = self._rating_to_label(rating_key)
            try:
                info_items = [
                    (self._tr("load_html_device_platform"), "Android" if is_android else "iOS"),
                    (self._tr("load_csv_device_id"), did if did else "-"),
                    (self._tr("lbl_stability_rating"), rating_label),
                    (self._tr("load_html_test_duration"), dur_show),
                    (self._tr("load_html_error_count"), str(summary.get("errors", 0))),
                    (self._tr("load_csv_export_time"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                ]
                info_html = self._html_info_section(info_items)
                st = summary.get("stats", {})
                card_items = []
                rating_color_cls = {"good": "good", "warn": "warn", "bad": "bad"}.get(rating_key, "")
                card_items.append((self._tr("lbl_stability_rating"), rating_label, rating_color_cls))
                for mkey, mname_avg, mname_peak, unit in [
                    ("cpu", self._tr("load_html_cpu_avg"), self._tr("load_html_cpu_peak"), "%"),
                    ("gpu", self._tr("load_html_gpu_avg"), self._tr("load_html_gpu_peak"), "%"),
                    ("cpu_temp", self._tr("load_html_temp_avg"), self._tr("load_html_temp_peak"), "°C"),
                ]:
                    s = st.get(mkey) or {}
                    v = s.get("avg")
                    if v is None:
                        continue
                    cls = "bad" if (mkey == "cpu_temp" and isinstance(v, (int, float)) and v > 65) else (
                        "warn" if (mkey == "cpu_temp" and isinstance(v, (int, float)) and v > 60) else "")
                    card_items.append((f"{mname_avg} ({unit})", f"{v:.1f}", cls))
                    mx = s.get("max")
                    if mx is not None:
                        card_items.append((f"{mname_peak} ({unit})", f"{mx:.1f}", ""))
                cards_html = self._html_summary_cards(card_items) if card_items else ""
                lines_html = "".join(f"<p style='margin:6px 0;'>{l or '&nbsp;'}</p>" for l in summary.get("lines", []))
                conclusion_html = (
                    f'<div class="card"><h2>{self._tr("load_html_stability_conclusion")}</h2>'
                    f'<div style="line-height:1.8;font-size:14px;color:#334155;">{lines_html}</div></div>'
                )
                charts_html = ""
                ts = summary.get("time_series") or {}
                if ts:
                    times = ts.get("time", []) or []
                    cpus = ts.get("cpu", []) or []
                    gpus = ts.get("gpu", []) or []
                    mems = ts.get("mem", []) or []
                    temps = ts.get("cpu_temp", []) or []
                    charts_html += self._html_chart_section(
                        self._tr("load_html_resource_trend"),
                        x_data=times, x_label=self._tr("load_html_sample_sec"), y_unit="%",
                        extra_chips=[self._tr("load_html_per_sec"), self._tr("load_html_draggable")],
                        series_list=[
                            {"name": self._tr("load_metric_cpu"), "data": cpus, "color": "#dc2626", "areaStyle": True, "width": 2.6},
                            {"name": self._tr("load_metric_gpu"), "data": gpus, "color": "#0891b2", "width": 2.6},
                            {"name": self._tr("load_html_mem_div100"), "data": [round(m / 100, 2) if isinstance(m, (int, float)) else None for m in mems], "color": "#7c3aed", "width": 2.6},
                        ],
                    )
                    charts_html += self._html_chart_section(
                        self._tr("load_html_temp_curve"),
                        x_data=times, x_label=self._tr("load_html_sample_sec"), y_unit="°C",
                        extra_chips=[self._tr("load_html_cpu_core_temp"), self._tr("load_html_threshold_bad")],
                        series_list=[
                            {"name": self._tr("load_metric_cpu_temp"), "data": temps, "color": "#ea580c", "width": 2.8, "areaStyle": True},
                        ],
                    )
                # 内嵌曲线图截图（保证任何时候都有曲线图）
                plots_html = ""
                try:
                    plot_widgets = [
                        (state.get("result_cpu_plot"), 1700, 520,
                         self._tr("chart_load_cpu_trend") or "CPU 使用率趋势"),
                        (state.get("result_mem_plot"), 1700, 520,
                         self._tr("chart_load_mem_trend") or "内存占用趋势"),
                        (state.get("result_temp_plot"), 1700, 460,
                         self._tr("chart_load_temp_trend") or "CPU 温度趋势"),
                    ]
                    pms = []
                    for w, wid, hei, title in plot_widgets:
                        if w is None:
                            continue
                        p = self._plot_to_pixmap(w, wid, hei, title=title)
                        if p is not None:
                            pms.append(p)
                    pm_all = self._stack_pixmaps_vertically(
                        pms,
                        title_text=(self._tr("load_html_chart_snapshot") or "负载测试曲线图"),
                        subtitle_text=(dur_show + "  ·  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        footer_text="星穹视界 · Stellar Vision FPS Tester  ·  负载稳定性测试",
                    ) if pms else None
                    b64 = self._pixmap_to_base64(pm_all) if pm_all is not None else ""
                    if b64:
                        plots_html = f"""
                        <section class="charts-images-section" style="margin-top:32px;">
                          <h2 style="font-size:18px;margin-bottom:12px;color:#0f172a;border-left:4px solid #0ea5e9;padding-left:10px;">{self._tr("load_html_chart_snapshot")}</h2>
                          <div style="background:white;border-radius:12px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
                            <img src="data:image/png;base64,{b64}" style="width:100%;height:auto;display:block;border-radius:8px;" />
                          </div>
                        </section>"""
                except Exception as _ie:
                    log_exception(_ie, f"{platform_name} load HTML chart snapshot failed")

                body_all = info_html + cards_html + conclusion_html + charts_html + plots_html
                default_path = os.path.join(desktop, f"{fname_suffix}.html")
                rtitle = self._tr("report_title_load").format(platform=platform_name)
                rsub = self._tr("lbl_stability_rating") + f": [{rating_label}] · " + dur_show
                saved = self._preview_html(
                    self._tr("preview_load_html").format(platform=platform_name), body_all, default_path, rtitle, rsub,
                )
                if saved:
                    QMessageBox.information(self, self._tr("msg_success"), self._tr("msg_export_success_html").format(path=saved))
                    _logger.info(f"HTML 报告已导出: {saved}")
            except Exception as e:
                log_exception(e, f"{platform_name} load HTML export failed")
                QMessageBox.critical(self, self._tr("msg_failed"), self._tr("msg_export_failed_simple").format(err=e))

        def _export_jpg():
            summary = _summary_or_warn()
            if not summary:
                return
            platform_name = self._tr("platform_android") if is_android else self._tr("platform_ios")
            desktop = os.path.expanduser("~/Desktop")
            default_path = os.path.join(desktop, f"load_{'android' if is_android else 'ios'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
            # 抓取 page2 整个结果页
            target = stack.widget(2) if stack.count() > 2 else None
            if target is None:
                QMessageBox.warning(self, self._tr("msg_warn"), self._tr("load_jpg_no_screenshot"))
                return
            try:
                pixmap = target.grab()
                # 预览（使用简单的 QLabel 对话框，含保存按钮）
                dlg = QDialog(self)
                dlg.setWindowTitle(self._tr("msg_save_jpg_title"))
                dlg.resize(960, 600)
                lv = QVBoxLayout(dlg)
                sc = QScrollArea()
                sc.setWidgetResizable(True)
                sc_lbl = QLabel()
                sc_lbl.setPixmap(pixmap.scaledToWidth(900, Qt.SmoothTransformation))
                sc_lbl.setAlignment(Qt.AlignCenter)
                sc.setWidget(sc_lbl)
                lv.addWidget(sc, 1)
                btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
                lv.addWidget(btns)

                def _save():
                    path, _ = QFileDialog.getSaveFileName(
                        self, self._tr("msg_save_jpg_title"), default_path,
                        self._tr("fmt_jpg_filter") + ";;JPEG (*.jpg *.jpeg);;All Files (*)"
                    )
                    if not path:
                        return
                    if not path.lower().endswith(('.jpg', '.jpeg')):
                        path += ".jpg"
                    if pixmap.save(path, "JPG", quality=92):
                        QMessageBox.information(self, self._tr("msg_success"),
                                                self._tr("msg_export_success_jpg").format(path=path))
                        _logger.info(f"JPG 报告已导出: {path}")
                        dlg.accept()
                    else:
                        QMessageBox.critical(self, self._tr("msg_failed"), self._tr("msg_export_failed_jpg").format(err=""))

                btns.accepted.connect(_save)
                btns.rejected.connect(dlg.reject)
                dlg.exec_()
            except Exception as e:
                log_exception(e, f"{platform_name} load JPG export failed")
                QMessageBox.critical(self, self._tr("msg_failed"), self._tr("msg_export_failed_simple").format(err=e))

        def _preview_report():
            """预览：生成 HTML 并预览（不强制保存）"""
            summary = _summary_or_warn()
            if not summary:
                return
            # 临时保存到 /tmp 并用浏览器打开预览
            platform_name = self._tr("platform_android") if is_android else self._tr("platform_ios")
            tmp_dir = tempfile.gettempdir()
            default_path = os.path.join(tmp_dir, f"load_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            did = device_combo.currentData() or ""
            dur = int(state.get("elapsed_sec") or summary.get("duration_sec") or 0)
            hrs, rem = divmod(dur, 3600)
            mins, secs = divmod(rem, 60)
            dur_show = f"{dur}s ({hrs:02d}:{mins:02d}:{secs:02d})"
            rating_key = summary.get("rating_key") or summary.get("rating") or "good"
            rating_label = self._rating_to_label(rating_key)
            try:
                info_items = [
                    (self._tr("load_html_device_platform"), "Android" if is_android else "iOS"),
                    (self._tr("load_csv_device_id"), did if did else "-"),
                    (self._tr("lbl_stability_rating"), rating_label),
                    (self._tr("load_html_test_duration"), dur_show),
                    (self._tr("load_html_error_count"), str(summary.get("errors", 0))),
                    (self._tr("load_csv_export_time"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                ]
                info_html = self._html_info_section(info_items)
                st = summary.get("stats", {})
                card_items = []
                rating_color_cls = {"good": "good", "warn": "warn", "bad": "bad"}.get(rating_key, "")
                card_items.append((self._tr("lbl_stability_rating"), rating_label, rating_color_cls))
                for mkey, mname_avg, mname_peak, unit in [
                    ("cpu", self._tr("load_html_cpu_avg"), self._tr("load_html_cpu_peak"), "%"),
                    ("gpu", self._tr("load_html_gpu_avg"), self._tr("load_html_gpu_peak"), "%"),
                    ("cpu_temp", self._tr("load_html_temp_avg"), self._tr("load_html_temp_peak"), "°C"),
                ]:
                    s = st.get(mkey) or {}
                    v = s.get("avg")
                    if v is None:
                        continue
                    cls = "bad" if (mkey == "cpu_temp" and isinstance(v, (int, float)) and v > 65) else (
                        "warn" if (mkey == "cpu_temp" and isinstance(v, (int, float)) and v > 60) else "")
                    card_items.append((f"{mname_avg} ({unit})", f"{v:.1f}", cls))
                    mx = s.get("max")
                    if mx is not None:
                        card_items.append((f"{mname_peak} ({unit})", f"{mx:.1f}", ""))
                cards_html = self._html_summary_cards(card_items) if card_items else ""
                lines_html = "".join(f"<p style='margin:6px 0;'>{l or '&nbsp;'}</p>" for l in summary.get("lines", []))
                conclusion_html = (
                    f'<div class="card"><h2>{self._tr("load_html_stability_conclusion")}</h2>'
                    f'<div style="line-height:1.8;font-size:14px;color:#334155;">{lines_html}</div></div>'
                )
                charts_html = ""
                ts = summary.get("time_series") or {}
                if ts:
                    times = ts.get("time", []) or []
                    cpus = ts.get("cpu", []) or []
                    gpus = ts.get("gpu", []) or []
                    mems = ts.get("mem", []) or []
                    temps = ts.get("cpu_temp", []) or []
                    charts_html += self._html_chart_section(
                        self._tr("load_html_resource_trend"),
                        x_data=times, x_label=self._tr("load_html_sample_sec"), y_unit="%",
                        series_list=[
                            {"name": self._tr("load_metric_cpu"), "data": cpus, "color": "#dc2626", "areaStyle": True, "width": 2.6},
                            {"name": self._tr("load_metric_gpu"), "data": gpus, "color": "#0891b2", "width": 2.6},
                            {"name": self._tr("load_html_mem_div100"), "data": [round(m / 100, 2) if isinstance(m, (int, float)) else None for m in mems], "color": "#7c3aed", "width": 2.6},
                        ],
                    )
                    charts_html += self._html_chart_section(
                        self._tr("load_html_temp_curve"),
                        x_data=times, x_label=self._tr("load_html_sample_sec"), y_unit="°C",
                        series_list=[
                            {"name": self._tr("load_metric_cpu_temp"), "data": temps, "color": "#ea580c", "width": 2.8, "areaStyle": True},
                        ],
                    )
                # 内嵌曲线图截图（保证任何时候都有曲线图）
                plots_html = ""
                try:
                    plot_widgets = [
                        (state.get("result_cpu_plot"), 1700, 520,
                         self._tr("chart_load_cpu_trend") or "CPU 使用率趋势"),
                        (state.get("result_mem_plot"), 1700, 520,
                         self._tr("chart_load_mem_trend") or "内存占用趋势"),
                        (state.get("result_temp_plot"), 1700, 460,
                         self._tr("chart_load_temp_trend") or "CPU 温度趋势"),
                    ]
                    pms = []
                    for w, wid, hei, title in plot_widgets:
                        if w is None:
                            continue
                        p = self._plot_to_pixmap(w, wid, hei, title=title)
                        if p is not None:
                            pms.append(p)
                    pm_all = self._stack_pixmaps_vertically(
                        pms,
                        title_text=(self._tr("load_html_chart_snapshot") or "负载测试曲线图"),
                        subtitle_text=(dur_show + "  ·  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        footer_text="星穹视界 · Stellar Vision FPS Tester  ·  负载稳定性测试",
                    ) if pms else None
                    b64 = self._pixmap_to_base64(pm_all) if pm_all is not None else ""
                    if b64:
                        plots_html = f"""
                        <section class="charts-images-section" style="margin-top:32px;">
                          <h2 style="font-size:18px;margin-bottom:12px;color:#0f172a;border-left:4px solid #0ea5e9;padding-left:10px;">{self._tr("load_html_chart_snapshot")}</h2>
                          <div style="background:white;border-radius:12px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
                            <img src="data:image/png;base64,{b64}" style="width:100%;height:auto;display:block;border-radius:8px;" />
                          </div>
                        </section>"""
                except Exception as _ie:
                    log_exception(_ie, f"{platform_name} load HTML chart snapshot failed")

                body_all = info_html + cards_html + conclusion_html + charts_html + plots_html
                rtitle = self._tr("report_title_load").format(platform=platform_name)
                rsub = self._tr("lbl_stability_rating") + f": [{rating_label}] · " + dur_show
                # 渲染 HTML 并保存到 /tmp 后用系统浏览器预览
                full_html = MainWindow._HTML_TEMPLATE.format(
                    title=rtitle, subtitle=rsub, body=body_all,
                    gen_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
                with open(default_path, "w", encoding="utf-8") as fp:
                    fp.write(full_html)
                # 在预览对话框中展示
                dlg = QDialog(self)
                dlg.setWindowTitle(self._tr("preview_load_html").format(platform=platform_name))
                dlg.resize(1100, 720)
                from PyQt5.QtWebEngineWidgets import QWebEngineView
                layout_v = QVBoxLayout(dlg)
                view = QWebEngineView()
                view.setHtml(full_html, QUrl.fromLocalFile(default_path))
                layout_v.addWidget(view, 1)
                # 保存按钮
                save_bar = QHBoxLayout()
                save_bar.addStretch(1)
                save_btn = QPushButton(self._tr("menu_html_export"))
                save_btn.setFixedHeight(32)
                save_btn.setStyleSheet("""
                    QPushButton { background-color: #3b82f6; color: white; border-radius: 8px;
                                  padding: 6px 20px; font-size: 13px; font-weight: bold; border: none; }
                    QPushButton:hover { background-color: #2563eb; }
                """)

                def _save_html():
                    sp, _ = QFileDialog.getSaveFileName(
                        self, self._tr("msg_success"),
                        os.path.join(os.path.expanduser("~/Desktop"), os.path.basename(default_path)),
                        "HTML (*.html)"
                    )
                    if sp:
                        try:
                            import shutil
                            shutil.copyfile(default_path, sp)
                            QMessageBox.information(self, self._tr("msg_success"),
                                                    self._tr("msg_export_success_html").format(path=sp))
                        except Exception as ex:
                            QMessageBox.critical(self, self._tr("msg_failed"), str(ex))
                save_btn.clicked.connect(_save_html)
                close_btn = QPushButton(self._tr("btn_close") or "关闭")
                close_btn.setFixedHeight(32)
                close_btn.clicked.connect(dlg.accept)
                save_bar.addWidget(save_btn)
                save_bar.addWidget(close_btn)
                layout_v.addLayout(save_bar)
                dlg.exec_()
            except ImportError:
                # 无 QWebEngine：系统浏览器打开
                try:
                    info_items = [
                        (self._tr("load_html_device_platform"), "Android" if is_android else "iOS"),
                        (self._tr("load_csv_device_id"), did if did else "-"),
                        (self._tr("lbl_stability_rating"), rating_label),
                        (self._tr("load_html_test_duration"), dur_show),
                    ]
                    info_html = self._html_info_section(info_items)
                    full_html = MainWindow._HTML_TEMPLATE.format(
                        title=rtitle, subtitle=rsub, body=(info_html + conclusion_html + charts_html),
                        gen_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )
                    with open(default_path, "w", encoding="utf-8") as fp:
                        fp.write(full_html)
                    import webbrowser
                    webbrowser.open("file://" + default_path)
                except Exception as e2:
                    log_exception(e2, "预览失败")
                    QMessageBox.critical(self, self._tr("msg_failed"), str(e2))
            except Exception as e:
                log_exception(e, "负载预览失败")
                QMessageBox.critical(self, self._tr("msg_failed"), self._tr("msg_export_failed_simple").format(err=e))

        # ====== 按钮连接 ======
        confirm_start_btn.clicked.connect(_start)
        stop_btn.clicked.connect(_stop)
        # 新按钮（retest/preview/export-menu 子项）连接到本地闭包
        try:
            btn_load_retest.clicked.connect(_retest)
        except Exception:
            pass
        try:
            btn_load_preview.clicked.connect(_preview_report)
        except Exception:
            pass
        # CSV / HTML / JPG 导出动作连接到本地闭包
        try:
            try:
                act_load_export_csv.triggered.disconnect()
            except Exception:
                pass
            act_load_export_csv.triggered.connect(_export_csv)
            try:
                act_load_export_html.triggered.disconnect()
            except Exception:
                pass
            act_load_export_html.triggered.connect(_export_html)
            try:
                act_load_export_jpg.triggered.disconnect()
            except Exception:
                pass
            act_load_export_jpg.triggered.connect(_export_jpg)
        except Exception:
            pass


    # ---------- 负载测试导出 / 预览：安全兜底 stub ----------
    # 真实绑定发生在 _init_load_test_tab(...) 尾部，通过 disconnect() + connect()
    # 挂接到本地闭包函数 _export_csv / _export_html / _export_jpg。
    # 这里仅提供防 AttributeError 的兜底（理论上不会触发）。
    def _on_load_export_csv_clicked(self):
        try:
            QMessageBox.information(self, self._tr("msg_tip"),
                                    self._tr("msg_not_ready_yet") or "测试尚未结束，暂无数据可导出。")
        except Exception as _e:
            log_exception(_e, "_on_load_export_csv_clicked stub")

    def _on_load_export_html_clicked(self):
        try:
            QMessageBox.information(self, self._tr("msg_tip"),
                                    self._tr("msg_not_ready_yet") or "测试尚未结束，暂无数据可导出。")
        except Exception as _e:
            log_exception(_e, "_on_load_export_html_clicked stub")

    def _on_load_export_jpg_clicked(self):
        try:
            QMessageBox.information(self, self._tr("msg_tip"),
                                    self._tr("msg_not_ready_yet") or "测试尚未结束，暂无数据可导出。")
        except Exception as _e:
            log_exception(_e, "_on_load_export_jpg_clicked stub")

    def _setup_plot_style(self):
        """全局设置图表样式 — 灰色主题：灰色底+浅色高亮文字曲线"""
        pg.setConfigOptions(antialias=True, background='#2b2f36', foreground='#f1f5f9')

    def _apply_realtime_plot_styling(self, pw, title: str = "", y_left: str = "", y_left_color: str = "#e2e8f0",
                                     x_label: str = "") -> None:
        """为实时曲线 PlotWidget 统一应用：灰底、高对比、白字加粗坐标轴。

        目的：在保证布局合理、颜色合理的前提下，用户在任何光照下都能清晰看清曲线与刻度，
        曲线绝不重叠或重合（不同色 + 实线虚线组合）。
        """
        if pw is None:
            return
        pw.setBackground("#2b2f36")
        pw.showGrid(x=True, y=True, alpha=0.18)
        if title:
            pw.setTitle(title, color="#f8fafc", size="11pt")
        if y_left:
            pw.setLabel("left", y_left, **{"color": y_left_color})
        if x_label:
            pw.setLabel("bottom", x_label, **{"color": "#cbd5e1"})
        # 坐标轴笔
        leftAxis = pw.getAxis("left")
        if leftAxis is not None:
            leftAxis.setPen(pg.mkPen(y_left_color, width=2))
            leftAxis.setTextPen(pg.mkPen(y_left_color))
        bottomAxis = pw.getAxis("bottom")
        if bottomAxis is not None:
            bottomAxis.setPen(pg.mkPen("#cbd5e1", width=2))
            bottomAxis.setTextPen(pg.mkPen("#e2e8f0"))
        pw.setMouseEnabled(x=True, y=False)
        pw.setMenuEnabled(False)

    # ---- 统一白色主题 ----
    def _apply_light_theme(self):
        """为整个应用设置统一的白色主题 (#f8fafc 浅色风格)"""
        self.setStyleSheet("""
            /* 主窗口与所有页面 */
            QMainWindow, QWidget {
                background-color: #f8fafc;
                color: #1e293b;
                font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
            }

            /* 标签 */
            QLabel {
                color: #1e293b;
                background: transparent;
            }

            /* Tab 栏 */
            QTabWidget::pane {
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 8px;
                background-color: #f8fafc;
                top: -1px;
            }
            QTabBar::tab {
                background-color: rgba(226, 232, 240, 200);
                color: #64748b;
                border: 1px solid rgba(100, 116, 139, 80);
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 10px 16px;
                margin-right: 2px;
                font-size: 13px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #0284c7;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background-color: rgba(203, 213, 225, 200);
                color: #1e293b;
            }

            /* 分组框 */
            QGroupBox {
                background-color: rgba(241, 245, 249, 200);
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 16px;
                color: #0f172a;
                font-size: 14px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 8px;
                color: #0f172a;
                background-color: transparent;
            }

            /* 下拉框 */
            QComboBox {
                background-color: rgba(226, 232, 240, 220);
                color: #1e293b;
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 6px;
                padding: 5px 12px;
                min-height: 24px;
            }
            QComboBox:hover {
                border-color: #0284c7;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid rgba(100, 116, 139, 80);
                selection-background-color: #0284c7;
                selection-color: #ffffff;
                outline: none;
            }

            /* 按钮通用（未被自定义样式覆盖的） */
            QPushButton {
                background-color: rgba(226, 232, 240, 220);
                color: #1e293b;
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 6px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: rgba(203, 213, 225, 220);
                border-color: rgba(100, 116, 139, 120);
            }
            QPushButton:pressed {
                background-color: rgba(241, 245, 249, 220);
            }
            QPushButton:disabled {
                background-color: rgba(203, 213, 225, 150);
                color: rgba(148, 163, 184, 120);
            }

            /* 进度条 */
            QProgressBar {
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 6px;
                text-align: center;
                color: #1e293b;
                background-color: rgba(226, 232, 240, 200);
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #0284c7;
                border-radius: 4px;
            }

            /* 文本编辑框（日志） */
            QTextEdit {
                background-color: #f8fafc;
                color: #1e293b;
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 6px;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
            }

            /* 滚动条 */
            QScrollBar:vertical {
                background-color: rgba(241, 245, 249, 200);
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(148, 163, 184, 180);
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(100, 116, 139, 180);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: rgba(241, 245, 249, 200);
                height: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background-color: rgba(148, 163, 184, 180);
                border-radius: 5px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: rgba(100, 116, 139, 180);
            }

            /* 分割器 */
            QSplitter::handle {
                background-color: rgba(100, 116, 139, 100);
            }
            QSplitter::handle:hover {
                background-color: #0284c7;
            }

            /* 列表控件 */
            QListWidget, QTableWidget {
                background-color: #f8fafc;
                alternate-background-color: #f1f5f9;
                color: #1e293b;
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 6px;
                gridline-color: rgba(100, 116, 139, 40);
                selection-background-color: rgba(2, 132, 199, 100);
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid rgba(2, 132, 199, 80);
                padding: 8px 6px;
                font-weight: bold;
                font-size: 13px;
            }

            /* 滚动区域 */
            QScrollArea {
                background-color: transparent;
                border: none;
            }

            /* 工具提示 */
            QToolTip {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid rgba(100, 116, 139, 100);
                padding: 4px 8px;
                border-radius: 4px;
            }

            /* 复选框 */
            QCheckBox {
                color: #1e293b;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid rgba(100, 116, 139, 120);
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #0284c7;
            }

            /* 菜单项 */
            QMenu {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid rgba(100, 116, 139, 80);
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }

            /* 状态栏 */
            QStatusBar {
                background-color: #f8fafc;
                color: #64748b;
                border-top: 1px solid rgba(100, 116, 139, 80);
            }

            /* 进度条（卡顿率专用大条） */
            QProgressBar#jankBar {
                height: 28px;
                font-size: 14px;
                font-weight: bold;
                color: #1e293b;
            }
        """)

    # ---- 主题颜色工具（白色主题固定值） ----
    def _fg(self) -> str:
        """主文字颜色 — 深色文字，白色主题下清晰可见"""
        return '#1e293b'

    def _fg_muted(self) -> str:
        """次要/弱化文字颜色"""
        return '#64748b'

    def _bg_light(self) -> str:
        """卡片/高亮背景的浅色底色"""
        return '#f1f5f9'

    def _bg_base(self) -> str:
        """控件底背景（白色）"""
        return '#ffffff'

    def _note_bg(self) -> str:
        """注释/说明条背景（浅橙色）"""
        return '#FFF3E0'

    # ==================== 设备与应用管理 ====================
    def _log(self, message: str):
        """写日志：UI 文本框 + 文件"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text.append(f"[{timestamp}] {message}")
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
        except Exception:
            pass
        # 文件日志
        try:
            if message.startswith("❌") or "失败" in message or "错误" in message or "异常" in message:
                _logger.error(f"[Android] {message}")
            elif message.startswith("⚠️"):
                _logger.warning(f"[Android] {message}")
            elif message.startswith("✅") or message.startswith("🚀"):
                _logger.info(f"[Android] {message}")
            else:
                _logger.info(f"[Android] {message}")
        except Exception:
            pass

    def _refresh_devices(self):
        """刷新设备列表"""
        try:
            devices = self.adb_client.get_devices()
            self.device_combo.clear()
            self.hw_device_combo.clear()
            if not devices:
                self.device_combo.addItem(self._tr("combo_no_device_usb"))
                self.hw_device_combo.addItem(self._tr("combo_no_device"))
                self.device_info_label.setText(self._tr("stat_device_disconnected"))
                self._log("⚠️ 未检测到安卓设备")
                self._log("💡 请确保：1. 手机已通过USB连接电脑；2. 已开启『开发者选项』和『USB调试』；3. 手机上允许USB调试授权")
            else:
                for device_id, status in devices:
                    try:
                        model = self.adb_client.get_device_model(device_id)
                        version = self.adb_client.get_android_version(device_id)
                        label = f"{device_id} - {model} (Android {version}) [{status}]"
                    except Exception:
                        label = f"{device_id} [{status}]"
                    self.device_combo.addItem(label, device_id)
                    self.hw_device_combo.addItem(label, device_id)

                if devices:
                    first_id = devices[0][0]
                    try:
                        model = self.adb_client.get_device_model(first_id)
                        version = self.adb_client.get_android_version(first_id)
                        self.device_info_label.setText(self._tr("fmt_device_info_full").format(model=model, version=version, id=first_id))
                    except Exception:
                        self.device_info_label.setText(self._tr("fmt_device_info_id").format(id=first_id))
                self._log(f"✅ 检测到 {len(devices)} 个设备")
            # 同步填充负载测试 Tab 的独立设备下拉框
            load_combo = getattr(self, "android_load_device_combo", None)
            if load_combo:
                load_combo.clear()
                for i in range(self.device_combo.count()):
                    load_combo.addItem(self.device_combo.itemText(i), self.device_combo.itemData(i))
        except Exception as e:
            QMessageBox.critical(self, self._tr("msg_adb_error"), str(e))
            self._log(f"❌ ADB错误: {e}")

    def _refresh_packages(self):
        """刷新应用包列表"""
        device_id = self._get_selected_device_id()
        if not device_id:
            return
        try:
            self._log("正在获取已安装应用列表（可能需要几秒）...")
            packages = self.adb_client.get_installed_packages(device_id)
            self.package_combo.clear()
            self.package_combo.addItems(packages)
            self._log(f"✅ 已加载 {len(packages)} 个第三方应用")
        except Exception as e:
            self._log(f"❌ 获取应用列表失败: {e}")

    def _get_current_app(self):
        """获取当前前台应用"""
        device_id = self._get_selected_device_id()
        if not device_id:
            return
        try:
            package = self.adb_client.get_current_package(device_id)
            if package:
                # 在combo中查找或添加
                index = self.package_combo.findText(package)
                if index >= 0:
                    self.package_combo.setCurrentIndex(index)
                else:
                    self.package_combo.insertItem(0, package)
                    self.package_combo.setCurrentIndex(0)
                self._log(f"📱 当前前台应用: {package}")
            else:
                self._log("⚠️ 无法获取当前应用，请手动输入包名")
        except Exception as e:
            self._log(f"❌ 获取当前应用失败: {e}")

    def _get_selected_device_id(self) -> Optional[str]:
        """获取当前选择的设备ID"""
        device_id = self.device_combo.currentData()
        if not device_id:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_android_device"))
            self._log("⚠️ 未选择设备")
            return None
        return device_id

    def _on_refresh_rate_changed(self):
        """刷新率变化时更新阈值"""
        rate = self.refresh_rate_combo.currentData()
        self.analyzer.refresh_rate = rate
        self.analyzer.frame_threshold_ms = 1000.0 / rate * 1.2
        threshold = 1000.0 / rate
        if hasattr(self, 'threshold_line') and self.threshold_line:
            self.threshold_line.setPos(threshold)
            self.threshold_line.label = f"卡顿阈值 ({threshold:.2f}ms)"
        self._log(f"🔄 刷新率已设置为 {rate}Hz，卡顿阈值: {threshold:.2f}ms")

    # ==================== 测试控制 ====================
    def _start_test(self):
        """开始测试"""
        try:
            self._start_test_inner()
        except Exception as e:
            log_exception(e, "Android 开始测试异常")
            self._log(f"❌ 开始测试失败: {e}")
            QMessageBox.critical(self, self._tr("msg_error"), self._tr("msg_start_test_failed").format(err=e))
            # 恢复按钮可用性
            try:
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)
                self.device_combo.setEnabled(True)
            except Exception:
                pass

    def _start_test_inner(self):
        device_id = self._get_selected_device_id()
        if not device_id:
            return

        package_name = self.package_combo.currentText().strip()
        if not package_name:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_app"))
            return

        # 更新刷新率
        self._on_refresh_rate_changed()

        # 清空历史数据（但询问用户）—— 联动启动时跳过询问，保留数据继续追加
        if not self._linking_start and self.history_stats:
            reply = QMessageBox.question(
                self, "确认",
                "存在上次的测试数据，是否清空后开始新测试？\n（选择「否」将保留数据并继续追加）",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Yes:
                self._clear_plot_data()

        # 获取采集间隔
        poll_interval = self.interval_combo.currentData()

        self._log(f"🚀 开始测试: 应用={package_name}, 设备={device_id}, 间隔={poll_interval}s")

        # 启动采集线程
        self.collector_thread = FPSCollectorThread(
            self.adb_client, device_id, package_name, self.analyzer, poll_interval
        )
        self.collector_thread.stats_ready.connect(self._on_stats_ready)
        # 帧率测试页不再显示硬件监控（已移至独立的 CPU/GPU 监测页面）
        self.collector_thread.log_message.connect(self._log)
        self.collector_thread.error_occurred.connect(self._on_collector_error)
        self.collector_thread.finished_signal.connect(self._on_collector_finished)
        self.collector_thread.start()

        # 记录开始时间
        self._fps_test_start_dt = datetime.now()

        # 创建数据库会话
        try:
            dev_pk = self._db_get_or_create_device(device_id, "android")
            refresh_rate = self.refresh_rate_combo.currentData() or 60
            self._db_session_id = self._db.create_session(
                device_id=dev_pk, platform="android", test_type="fps",
                app_package=package_name, refresh_rate=refresh_rate,
                poll_interval=poll_interval
            )
        except Exception as e:
            log_exception(e, "数据库: 创建FPS会话失败")

        # 更新UI状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.refresh_btn.setEnabled(False)
        self.current_app_btn.setEnabled(False)
        self.refresh_pkg_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.package_combo.setEnabled(False)

        # 启动计时器
        self.test_start_time = time.time()
        self.test_timer.start(1000)

        # 联动启动 CPU/GPU 监测（避免递归调用）
        if not self._linking_start:
            self._linking_start = True
            try:
                if not (self.hw_monitor_thread and self.hw_monitor_thread.isRunning()):
                    # 同步设备到 HW 监测页的下拉框
                    for i in range(self.hw_device_combo.count()):
                        if self.hw_device_combo.itemData(i) == device_id:
                            self.hw_device_combo.setCurrentIndex(i)
                            break
                    self._start_hw_monitor()
                    self._log("🔗 已联动启动 CPU/GPU 监测")
            finally:
                self._linking_start = False

    def _stop_test(self):
        """停止测试（联动停止 CPU/GPU 监测）"""
        # 立即更新按钮状态：开始禁用期间保持停止不可点，结束后再恢复
        try:
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            self.current_app_btn.setEnabled(False)
            self.refresh_pkg_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            self.device_combo.setEnabled(False)
            self.package_combo.setEnabled(False)
        except Exception:
            pass
        if self.collector_thread and self.collector_thread.isRunning():
            self.collector_thread.stop()
            self._log("⏹ 正在停止采集...")
            # 等待线程退出（最多 3 秒），避免快速重启时旧线程仍在运行导致数据混乱
            self.collector_thread.wait(3000)
        # 联动停止 CPU/GPU 监测
        if not self._linking_stop:
            self._linking_stop = True
            try:
                if self.hw_monitor_thread and self.hw_monitor_thread.isRunning():
                    self._stop_hw_monitor()
                    self._log("🔗 已联动停止 CPU/GPU 监测")
            finally:
                self._linking_stop = False

    def _on_collector_error(self, error_msg: str):
        """采集线程错误"""
        self._log(f"❌ {error_msg}")
        QMessageBox.critical(self, self._tr("msg_error"),error_msg)

    def _on_collector_finished(self):
        """采集线程结束"""
        # 断开旧线程信号并清理引用，避免多次启停后信号累积与内存泄漏
        try:
            if self.collector_thread:
                self.collector_thread.disconnect()
                self.collector_thread.deleteLater()
        except Exception:
            pass
        self.test_timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        self.current_app_btn.setEnabled(True)
        self.refresh_pkg_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.device_combo.setEnabled(True)
        self.package_combo.setEnabled(True)
        self._log("✅ 测试已停止")

        # 输出摘要
        summary = self.analyzer.get_summary()
        self._log("=" * 50)
        self._log("📋 测试摘要:")
        for k, v in summary.items():
            self._log(f"  {k}: {v}")
        self._log("=" * 50)

        # 用最终汇总数据刷新统计面板（含 1% Low / 0.1% Low）
        self._update_final_stats(summary)

        # 保存到 CSV 历史记录
        if self.history_stats and len(self.history_stats) > 0:
            self._history_save_fps_report(summary)

        # 数据库：写入汇总并结束会话（先保存 session_id 供评价弹窗使用）
        _finished_session_id = getattr(self, "_db_session_id", None)
        try:
            if self._db_session_id:
                self._db.insert_fps_summary(self._db_session_id, summary)
                duration = summary.get("duration_sec", 0)
                self._db.finish_session(self._db_session_id, duration)
                self._db_session_id = None
        except Exception as e:
            log_exception(e, "数据库: 写入FPS汇总失败")

        # 综合性能评价 — 用 QTimer.singleShot 延迟弹窗，避免被前面代码异常阻断
        def _deferred_eval():
            try:
                device_id = self.device_combo.currentData() or ""
                device_info = {}
                if device_id and self.adb_client:
                    try:
                        device_info = self.adb_client.get_device_info(device_id) or {}
                    except Exception:
                        pass
                refresh_rate = getattr(self.analyzer, "refresh_rate", 60)
                eval_result = self._evaluate_fps_performance(summary, device_info, refresh_rate)
                if eval_result:
                    eval_result["platform"] = "android"
                    eval_result["device_serial"] = device_id
                    # 注意：安卓目标应用保存在 package_combo
                    eval_result["app_package"] = self.package_combo.currentData() or self.package_combo.currentText() or ""
                    eval_result["duration_sec"] = int(summary.get("duration_sec", 0))
                    eval_result["start_time"] = datetime.now()
                    eval_result["session_id"] = _finished_session_id
                    self._show_fps_evaluation_dialog(eval_result)
            except Exception as e:
                log_exception(e, "综合性能评价失败")
        QTimer.singleShot(100, _deferred_eval)

    def _identify_chipset_tier(self, device_info: dict) -> tuple:
        """识别芯片等级，返回 (tier_key, tier_name, detail)
        兼容 Android(soc_model/hardware/soc_manufacturer) 与 iOS(chip_name)"""
        soc = (device_info.get("soc_model") or "").lower()
        hardware = (device_info.get("hardware") or "").lower()
        manufacturer = (device_info.get("soc_manufacturer") or "").lower()
        chip_name = (device_info.get("chip_name") or "").lower()
        combined = f"{soc} {hardware} {manufacturer} {chip_name}"
        # 详情显示用：优先 soc_model，其次 chip_name(iOS)，再次 hardware
        detail_name = (device_info.get("soc_model") or
                       device_info.get("chip_name") or
                       device_info.get("hardware") or
                       device_info.get("soc_manufacturer") or
                       "--")

        # 旗舰级
        flagship_patterns = [
            "sm8", "snapdragon 8 gen", "snapdragon 8 elite", "sd8",
            "a17", "a18", "a16",
            "dimensity 9", "mt6989", "mt6991",
            "kirin 9000", "kirin 9020", "kirin 9010",
            "tensor g3", "tensor g4",
        ]
        # 高端
        highend_patterns = [
            "sm8350", "sm8450", "sm8550", "snapdragon 8", "sd888", "sd870", "sd865",
            "dimensity 8", "dimensity 7",
            "kirin 990",
            "a15", "a14",
        ]
        # 中端
        midrange_patterns = [
            "snapdragon 7", "snapdragon 6", "sd7", "sd6",
            "dimensity 6", "dimensity 5",
            "kirin 8", "kirin 7",
            "a13", "a12",
        ]
        # 入门
        budget_patterns = [
            "snapdragon 4", "sd4", "helio", "unisoc", "kirin 710", "kirin 712",
        ]

        for p in flagship_patterns:
            if p in combined:
                return ("flagship", self._tr("fps_eval_chipset_flagship"), detail_name)
        for p in highend_patterns:
            if p in combined:
                return ("highend", self._tr("fps_eval_chipset_highend"), detail_name)
        for p in midrange_patterns:
            if p in combined:
                return ("midrange", self._tr("fps_eval_chipset_midrange"), detail_name)
        for p in budget_patterns:
            if p in combined:
                return ("budget", self._tr("fps_eval_chipset_budget"), detail_name)
        return ("unknown", self._tr("fps_eval_chipset_unknown"), detail_name)

    def _evaluate_fps_performance(self, summary: dict, device_info: dict, refresh_rate: int) -> Optional[dict]:
        """根据帧率数据 + 芯片信息综合评价手机性能，返回评价结果 dict"""
        if not summary:
            return None

        def _f(v, default=0.0):
            """安全浮点转换：None / NaN / 非数值都回落到 default"""
            try:
                if v is None:
                    return float(default)
                x = float(v)
                if np.isnan(x) or np.isinf(x):
                    return float(default)
                return x
            except (TypeError, ValueError):
                return float(default)

        def _i(v, default=0):
            try:
                if v is None:
                    return int(default)
                return int(float(v))
            except (TypeError, ValueError):
                return int(default)

        total_frames = _i(summary.get("total_frames", 0))
        if total_frames < 10:
            return None

        avg_fps = _f(summary.get("avg_fps", 0))
        jank_rate = _f(summary.get("jank_rate", 0))
        std_fps = _f(summary.get("std_fps", 0))
        low_1 = _f(summary.get("low_1_fps", 0))
        low_01 = _f(summary.get("low_01_fps", 0))
        fps_drop_count = _i(summary.get("fps_drop_count", 0))
        rr = max(1.0, _f(refresh_rate, 60))

        # 1. 帧率达标度 (40 分)
        #    达标线 = 目标帧率的 90%（多数游戏会略低于屏幕刷新率，留出 10% 余量更合理）
        #    若平均帧率明显低于屏幕刷新率（<80%），尝试识别游戏限帧上限（30/45/60/90/120/144），
        #    以限帧上限作为目标，避免高刷屏 + 60fps 游戏被误判为不达标。
        effective_cap = rr
        if avg_fps < rr * 0.8:
            for _cap in (30, 45, 60, 90, 120, 144):
                if _cap * 0.9 <= avg_fps <= _cap * 1.08:
                    effective_cap = float(_cap)
                    break
        target_fps = max(30.0, effective_cap * 0.9)
        fps_ratio = min(1.0, avg_fps / target_fps)
        fps_score = round(fps_ratio * 40, 1)

        # 2. 稳定性 (25 分): 卡顿率 15 分 + 标准差 10 分
        if jank_rate < 3:
            jank_score = 15
        elif jank_rate < 8:
            jank_score = 10
        elif jank_rate < 15:
            jank_score = 5
        else:
            jank_score = 0
        if std_fps < 6:
            std_score = 10
        elif std_fps < 12:
            std_score = 5
        else:
            std_score = 0
        stability_score = jank_score + std_score

        # 3. Low FPS 表现 (20 分): 1% Low 12 分 + 0.1% Low 8 分
        if low_1 >= rr * 0.7:
            low1_score = 12
        elif low_1 >= rr * 0.4:
            low1_score = 8
        elif low_1 >= 25:
            low1_score = 4
        else:
            low1_score = 0
        if low_01 >= rr * 0.4:
            low01_score = 8
        elif low_01 >= 25:
            low01_score = 4
        else:
            low01_score = 0
        lowfps_score = low1_score + low01_score

        # 4. 掉帧控制 (15 分)
        drop_rate = fps_drop_count / max(1, total_frames) * 100
        if drop_rate < 2:
            drop_score = 15
        elif drop_rate < 5:
            drop_score = 10
        elif drop_rate < 10:
            drop_score = 5
        else:
            drop_score = 0

        total_score = round(fps_score + stability_score + lowfps_score + drop_score, 1)
        total_score = min(100, max(0, total_score))

        # 等级
        if total_score >= 85:
            rating_key, rating_color = "fps_eval_excellent", "#16a34a"
        elif total_score >= 70:
            rating_key, rating_color = "fps_eval_good", "#2563eb"
        elif total_score >= 55:
            rating_key, rating_color = "fps_eval_fair", "#f59e0b"
        elif total_score >= 35:
            rating_key, rating_color = "fps_eval_poor", "#ea580c"
        else:
            rating_key, rating_color = "fps_eval_bad", "#dc2626"

        # 芯片分析
        tier_key, tier_name, chip_detail = self._identify_chipset_tier(device_info)

        # 详细分析
        analysis_lines = []
        raw_ratio = min(1.0, avg_fps / effective_cap)
        target_label = int(effective_cap) if effective_cap != rr else refresh_rate
        cap_note = f"（检测到限帧 {int(effective_cap)} FPS）" if effective_cap != rr else ""
        analysis_lines.append(f"• 平均帧率 {avg_fps:.1f} FPS（目标 {target_label} FPS{cap_note}），达标率 {raw_ratio*100:.0f}%")
        analysis_lines.append(f"• 卡顿率 {jank_rate:.2f}%，帧率标准差 {std_fps:.2f}")
        analysis_lines.append(f"• 1% Low = {low_1:.1f} FPS，0.1% Low = {low_01:.1f} FPS")
        analysis_lines.append(f"• 掉帧次数 {fps_drop_count}（占总帧数 {drop_rate:.2f}%）")
        analysis_lines.append(f"• 芯片：{chip_detail}（{tier_name}）")

        # 综合评语
        if total_score >= 85:
            analysis_lines.append(f"\n✨ 该设备在当前应用下表现出旗舰级流畅度，帧率稳定、卡顿极少，游戏体验极佳。")
        elif total_score >= 70:
            analysis_lines.append(f"\n✅ 该设备整体流畅，偶有轻微卡顿但不影响核心体验，可胜任绝大多数游戏场景。")
        elif total_score >= 55:
            analysis_lines.append(f"\n🔶 该设备基本可流畅运行，但部分高负载场景存在明显掉帧，建议适当降低画质。")
        elif total_score >= 35:
            analysis_lines.append(f"\n⚠️ 该设备卡顿较为频繁，影响游戏体验，建议降低画质或分辨率以提升流畅度。")
        else:
            analysis_lines.append(f"\n❌ 该设备帧率严重不足，游戏体验较差，建议大幅降低画质或更换更高性能设备。")

        return {
            "total_score": total_score,
            "rating": self._tr(rating_key),
            "rating_color": rating_color,
            "scores": {
                "fps": fps_score,
                "stability": stability_score,
                "lowfps": lowfps_score,
                "drop": drop_score,
            },
            "chipset_tier": tier_name,
            "chip_detail": chip_detail,
            "analysis_lines": analysis_lines,
            "summary": summary,
        }

    def _show_fps_evaluation_dialog(self, eval_result: dict):
        """弹窗显示综合性能评价结果"""
        if not eval_result:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(self._tr("fps_eval_title"))
        dlg.setMinimumWidth(520)
        dlg.setStyleSheet("QDialog { background-color: #f8fafc; }")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        # 标题
        title = QLabel(self._tr("fps_eval_title"))
        title.setFont(QFont("PingFang SC", 20, QFont.Bold))
        title.setStyleSheet("color: #0f172a;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        # 评分大字
        score_card = QFrame()
        score_card.setStyleSheet(f"QFrame {{ background: white; border: 2px solid {eval_result['rating_color']}; border-radius: 16px; }}")
        sc_lay = QVBoxLayout(score_card)
        sc_lay.setContentsMargins(20, 16, 20, 16)
        sc_lay.setSpacing(6)
        score_label = QLabel(self._tr("fps_eval_score"))
        score_label.setAlignment(Qt.AlignCenter)
        score_label.setStyleSheet("color: #64748b; font-size: 14px;")
        sc_lay.addWidget(score_label)
        score_value = QLabel(f"{eval_result['total_score']:.1f}")
        score_value.setAlignment(Qt.AlignCenter)
        score_value.setFont(QFont("Menlo", 56, QFont.Bold))
        score_value.setStyleSheet(f"color: {eval_result['rating_color']};")
        sc_lay.addWidget(score_value)
        rating_value = QLabel(eval_result["rating"])
        rating_value.setAlignment(Qt.AlignCenter)
        rating_value.setFont(QFont("PingFang SC", 18, QFont.Bold))
        rating_value.setStyleSheet(f"color: {eval_result['rating_color']};")
        sc_lay.addWidget(rating_value)
        lay.addWidget(score_card)

        # 分项得分
        scores = eval_result["scores"]
        score_items = [
            (self._tr("fps_eval_fps_score"), scores["fps"], 40, "#3b82f6"),
            (self._tr("fps_eval_stability_score"), scores["stability"], 25, "#16a34a"),
            (self._tr("fps_eval_lowfps_score"), scores["lowfps"], 20, "#f59e0b"),
            (self._tr("fps_eval_drop_score"), scores["drop"], 15, "#ea580c"),
        ]
        for name, val, max_val, color in score_items:
            row = QHBoxLayout()
            lbl = QLabel(f"{name}:  {val:.1f} / {max_val}")
            lbl.setFont(QFont("PingFang SC", 12))
            lbl.setStyleSheet("color: #334155;")
            row.addWidget(lbl)
            row.addStretch()
            bar = QProgressBar()
            bar.setRange(0, max_val)
            bar.setValue(int(val))
            bar.setFixedHeight(10)
            bar.setTextVisible(False)
            bar.setFixedWidth(160)
            bar.setStyleSheet(f"""
                QProgressBar {{ background: #e2e8f0; border: none; border-radius: 5px; }}
                QProgressBar::chunk {{ background-color: {color}; border-radius: 5px; }}
            """)
            row.addWidget(bar)
            lay.addLayout(row)

        # 芯片分析
        chip_lbl = QLabel(f"{self._tr('fps_eval_chipset')}:  {eval_result['chip_detail']}（{eval_result['chipset_tier']}）")
        chip_lbl.setFont(QFont("PingFang SC", 12, QFont.Bold))
        chip_lbl.setStyleSheet("color: #7c3aed; padding: 8px 0;")
        lay.addWidget(chip_lbl)

        # 详细分析
        analysis_title = QLabel(self._tr("fps_eval_analysis"))
        analysis_title.setFont(QFont("PingFang SC", 14, QFont.Bold))
        analysis_title.setStyleSheet("color: #0f172a; padding-top: 8px;")
        lay.addWidget(analysis_title)
        for line in eval_result["analysis_lines"]:
            al = QLabel(line)
            al.setWordWrap(True)
            al.setFont(QFont("PingFang SC", 12))
            al.setStyleSheet("color: #334155; padding: 2px 0;")
            al.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(al)

        lay.addStretch()

        # 关闭按钮
        close_btn = QPushButton(self._tr("fps_eval_close"))
        close_btn.setMinimumHeight(38)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background-color: #3b82f6; color: white; border-radius: 8px;
                          padding: 8px 32px; font-size: 15px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #2563eb; }
        """)

        def _save_and_close():
            """保存到数据库 + 历史记录，再关闭对话框"""
            try:
                # 准备 DB 入参
                summary_meta = eval_result.get("summary") or {}
                analysis_json_obj = {"lines": eval_result.get("analysis_lines", [])}
                import json as _json
                eval_db_dict = {
                    "session_id": eval_result.get("session_id"),
                    "device_serial": eval_result.get("device_serial", ""),
                    "platform": eval_result.get("platform", ""),
                    "app_package": eval_result.get("app_package", ""),
                    "start_time": (eval_result.get("start_time") or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
                                  if hasattr(eval_result.get("start_time"), "strftime") else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_sec": float(eval_result.get("duration_sec", 0) or 0),
                    "total_score": float(eval_result.get("total_score", 0) or 0),
                    "rating": eval_result.get("rating", ""),
                    "rating_color": eval_result.get("rating_color", ""),
                    "fps_score": float(eval_result.get("scores", {}).get("fps", 0) or 0),
                    "stability_score": float(eval_result.get("scores", {}).get("stability", 0) or 0),
                    "lowfps_score": float(eval_result.get("scores", {}).get("lowfps", 0) or 0),
                    "drop_score": float(eval_result.get("scores", {}).get("drop", 0) or 0),
                    "chipset_tier": eval_result.get("chipset_tier", ""),
                    "chip_detail": eval_result.get("chip_detail", ""),
                    "analysis_json": _json.dumps(analysis_json_obj, ensure_ascii=False),
                    "summary_json": _json.dumps(summary_meta if isinstance(summary_meta, dict) else {}, ensure_ascii=False),
                }
                eval_db_id: Optional[int] = None
                try:
                    if hasattr(self, "_db") and self._db is not None:
                        eval_db_id = self._db.insert_evaluation(eval_db_dict)
                except Exception as e2:
                    log_exception(e2, "DB 写入性能评价失败")
                # 入历史记录 deque
                dt = eval_result.get("start_time") or datetime.now()
                if not hasattr(dt, "strftime"):
                    dt = datetime.now()
                rec_id = f"eval_{dt.strftime('%Y%m%d%H%M%S')}"
                rec = {
                    "id": rec_id,
                    "db_id": eval_db_id,
                    "start_time": dt,
                    "duration_sec": int(eval_result.get("duration_sec", 0) or 0),
                    "total_score": float(eval_result.get("total_score", 0) or 0),
                    "rating": eval_result.get("rating", "-"),
                    "rating_color": eval_result.get("rating_color", "#64748b"),
                    "scores": {
                        "fps": float(eval_result.get("scores", {}).get("fps", 0) or 0),
                        "stability": float(eval_result.get("scores", {}).get("stability", 0) or 0),
                        "lowfps": float(eval_result.get("scores", {}).get("lowfps", 0) or 0),
                        "drop": float(eval_result.get("scores", {}).get("drop", 0) or 0),
                    },
                    "chipset_tier": eval_result.get("chipset_tier", ""),
                    "chip_detail": eval_result.get("chip_detail", ""),
                    "platform": eval_result.get("platform", ""),
                    "device_serial": eval_result.get("device_serial", ""),
                    "app_package": eval_result.get("app_package", ""),
                    "analysis_lines": eval_result.get("analysis_lines", []),
                }
                is_android_eval = (eval_result.get("platform") or "android") == "android"
                dq = self._eval_records if is_android_eval else self._ios_eval_records
                if len(dq) >= 5:
                    dq.popleft()
                dq.append(rec)
                if is_android_eval:
                    try:
                        self._history_refresh_lists()
                    except Exception:
                        pass
            except Exception as e:
                log_exception(e, "保存性能评价到历史失败")
            dlg.accept()

        close_btn.clicked.connect(_save_and_close)
        lay.addWidget(close_btn, alignment=Qt.AlignCenter)

        dlg.exec_()

    def _update_duration(self):
        """更新测试时长显示"""
        if self.test_start_time > 0:
            elapsed = int(time.time() - self.test_start_time)
            mins, secs = divmod(elapsed, 60)
            hrs, mins = divmod(mins, 60)
            if hrs > 0:
                self.duration_label.setText(self._tr("fmt_duration_hms").format(h=hrs, m=mins, s=secs))
            else:
                self.duration_label.setText(self._tr("fmt_duration_ms").format(m=mins, s=secs))

    # ==================== 数据更新与绘图 ====================
    def _on_stats_ready(self, stats: FPSStats):
        """收到新的统计数据"""
        # 记录历史
        self.history_times.append(stats.timestamp)
        self.history_fps.append(stats.fps)
        self.history_avg_fps.append(stats.avg_fps)
        self.history_stats.append(stats)
        # 防止长时间测试导致历史列表无限增长（保留最近 7200 点 ≈ 2 小时）
        _max_hist = 7200
        if len(self.history_times) > _max_hist:
            overflow = len(self.history_times) - _max_hist
            del self.history_times[:overflow]
            del self.history_fps[:overflow]
            del self.history_avg_fps[:overflow]
            del self.history_stats[:overflow]

        # 数据库：写入帧率采样
        try:
            if self._db_session_id:
                self._db.insert_fps_sample(self._db_session_id, stats)
        except Exception as e:
            log_exception(e, "数据库: 写入FPS采样失败")

        # 更新FPS曲线（限制历史长度）
        max_points = 300
        times = self.history_times[-max_points:]
        t0 = times[0] if times else 0
        xs = [t - t0 for t in times]
        self.fps_curve.setData(xs, self.history_fps[-max_points:])
        self.avg_curve.setData(xs, self.history_avg_fps[-max_points:])

        # 限制Y轴范围（根据数据自适应）
        all_fps = self.history_fps[-max_points:] + self.history_avg_fps[-max_points:]
        if all_fps:
            raw_max = max(all_fps) if all_fps else 0
            raw_min = min(all_fps) if all_fps else 0
            # 保证 ymax > 0，避免全 0 时范围 [-5,0] 导致曲线不可见
            ymax = max(raw_max * 1.1, 10.0)
            ymin = min(0, raw_min - 5)
            self.fps_plot.setYRange(ymin, ymax)

        # 更新帧时间分布（柱状图，取最近一次采样的帧时间列表）
        if stats.frame_times:
            n = min(len(stats.frame_times), 120)
            recent = stats.frame_times[-n:]
            xs_bar = list(range(len(recent)))
            # 根据卡顿情况着色：超过阈值的用红色，否则绿色
            rate = self.refresh_rate_combo.currentData()
            threshold_ms = 1000.0 / rate
            brushes = []
            for ft in recent:
                if ft > threshold_ms * 1.2:
                    brushes.append(pg.mkBrush(244, 67, 54))  # 红 - 卡顿
                elif ft > threshold_ms:
                    brushes.append(pg.mkBrush(255, 152, 0))  # 橙 - 临界
                else:
                    brushes.append(pg.mkBrush(76, 175, 80))  # 绿 - 正常
            self.frame_bar.setOpts(x=xs_bar, height=recent, width=0.8, brushes=brushes)
            # 自动调整纵轴
            self.frame_plot.setYRange(0, max(max(recent) * 1.1, threshold_ms * 2))

        # 更新统计标签
        self._update_stat_labels(stats)

    def _update_stat_labels(self, stats: FPSStats):
        """更新右侧统计面板"""
        label_map = {
            "fps": f"{stats.fps:.1f}",
            "avg_fps": f"{stats.avg_fps:.1f}",
            "min_fps": f"{stats.min_fps:.1f}",
            "max_fps": f"{stats.max_fps:.1f}",
            "low_1": f"{stats.low_1_fps:.1f}" if stats.low_1_fps > 0 else "--",
            "low_01": f"{stats.low_01_fps:.1f}" if stats.low_01_fps > 0 else "--",
            "std_fps": f"{stats.std_fps:.2f}",
            "jank_count": str(stats.jank_count),
            "total_frames": str(stats.total_frames),
            "jank_rate": f"{stats.jank_rate:.2f}%",
            "p95": f"{stats.percentile_95:.2f}",
            "p99": f"{stats.percentile_99:.2f}",
        }
        for key, text in label_map.items():
            if key in self._stat_labels:
                self._stat_labels[key].setText(text)

        # 更新卡顿率进度条和颜色
        jank_rate = stats.jank_rate
        display_rate = min(jank_rate, 100.0)
        self.jank_bar.setValue(int(display_rate))
        self.jank_bar.setFormat(self._tr("fmt_jank_rate").format(val=f"{jank_rate:.2f}"))
        if jank_rate < 2:
            chunk_color = "#4CAF50"  # 绿
        elif jank_rate < 5:
            chunk_color = "#FFC107"  # 黄
        else:
            chunk_color = "#F44336"  # 红
        self.jank_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {self._fg_muted()};
                border-radius: 6px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                color: {self._fg()};
                height: 28px;
            }}
            QProgressBar::chunk {{
                background-color: {chunk_color};
                border-radius: 4px;
            }}
        """)

    def _update_final_stats(self, summary: dict):
        """停止测试后，用最终汇总数据刷新统计面板"""
        final_map = {
            "avg_fps": f"{summary.get('avg_fps', 0):.1f}",
            "min_fps": f"{summary.get('min_fps', 0):.1f}",
            "max_fps": f"{summary.get('max_fps', 0):.1f}",
            "low_1": f"{summary.get('low_1_fps', 0):.1f}" if summary.get('low_1_fps', 0) > 0 else "--",
            "low_01": f"{summary.get('low_01_fps', 0):.1f}" if summary.get('low_01_fps', 0) > 0 else "--",
            "std_fps": f"{summary.get('std_fps', 0):.2f}",
            "jank_count": str(summary.get('jank_count', 0)),
            "total_frames": str(summary.get('total_frames', 0)),
            "jank_rate": f"{summary.get('jank_rate', 0):.2f}%",
            "p95": f"{summary.get('p95_frame_ms', 0):.2f}",
            "p99": f"{summary.get('p99_frame_ms', 0):.2f}",
        }
        for key, text in final_map.items():
            if key in self._stat_labels:
                self._stat_labels[key].setText(text)

        # 更新卡顿率进度条
        jank_rate = summary.get('jank_rate', 0)
        self.jank_bar.setValue(int(min(jank_rate, 100.0)))
        self.jank_bar.setFormat(self._tr("fmt_jank_rate").format(val=f"{jank_rate:.2f}"))
        if jank_rate < 2:
            chunk_color = "#4CAF50"
        elif jank_rate < 5:
            chunk_color = "#FFC107"
        else:
            chunk_color = "#F44336"
        self.jank_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {self._fg_muted()};
                border-radius: 6px;
                text-align: center;
                font-size: 14px;
                font-weight: bold;
                color: {self._fg()};
                height: 28px;
            }}
            QProgressBar::chunk {{
                background-color: {chunk_color};
                border-radius: 4px;
            }}
        """)

    def _clear_plot_data(self):
        """清空绘图数据"""
        self.history_times.clear()
        self.history_fps.clear()
        self.history_avg_fps.clear()
        self.history_stats.clear()
        self.fps_curve.setData([], [])
        self.avg_curve.setData([], [])
        self.frame_bar.setOpts(x=[], height=[], width=0.8)
        # 重置 Y 轴范围，避免清空后仍保持旧范围
        self.fps_plot.setYRange(0, 60)
        self.frame_plot.setYRange(0, 50)
        self.duration_label.setText(self._tr("stat_duration_zero"))
        self.test_start_time = 0
        for lbl in self._stat_labels.values():
            lbl.setText("--")
        self.jank_bar.setValue(0)
        self.jank_bar.setFormat(self._tr("fmt_jank_rate_zero"))

    def _clear_data(self):
        """清空所有数据（带确认）"""
        if self.collector_thread and self.collector_thread.isRunning():
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_test_running"))
            return

        if not self.history_stats:
            # 没有数据也做重置，清除分析器缓存
            self._clear_plot_data()
            self.analyzer.reset()
            self._log("🗑 已重置分析器")
            return

        reply = QMessageBox.question(
            self, self._tr("msg_confirm_clear"),
            self._tr("msg_confirm_clear_body"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.analyzer.reset()
            self._clear_plot_data()
            self._log("🗑 数据已清空")

    # ==================== 数据管理 ====================

    # ----- 通用 HTML 报告模板 -----
    _HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
         background: #f0f2f5; color: #1e293b; padding: 24px; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  .header {{ background: linear-gradient(135deg, #0f172a, #1e3a5f); color: white;
             border-radius: 16px 16px 0 0; padding: 32px 40px; }}
  .header h1 {{ font-size: 28px; margin-bottom: 6px; }}
  .header .subtitle {{ font-size: 14px; opacity: 0.8; }}
  .card {{ background: white; border-radius: 0 0 16px 16px; padding: 32px 40px;
           box-shadow: 0 4px 24px rgba(0,0,0,0.08); margin-bottom: 24px; }}
  .card h2 {{ font-size: 18px; color: #0f172a; margin-bottom: 16px;
              padding-bottom: 10px; border-bottom: 2px solid #e2e8f0; }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px 32px; margin-bottom: 8px; }}
  .info-item {{ display: flex; align-items: center; }}
  .info-item .label {{ color: #64748b; font-size: 13px; min-width: 100px; }}
  .info-item .value {{ font-weight: 600; font-size: 14px; margin-left: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #f1f5f9; color: #475569; font-weight: 600; padding: 10px 12px;
        text-align: left; border-bottom: 2px solid #e2e8f0; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }}
  tr:hover td {{ background: #f8fafc; }}
  .stat-value {{ font-family: "Menlo", monospace; font-weight: 700; color: #1565C0; }}
  .good {{ color: #16a34a; }} .warn {{ color: #f59e0b; }} .bad {{ color: #dc2626; }}
  .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; }}
  .stat-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
                padding: 16px; text-align: center; }}
  .stat-card .stat-label {{ font-size: 12px; color: #64748b; margin-bottom: 6px; }}
  .stat-card .stat-num {{ font-family: "Menlo", monospace; font-size: 24px; font-weight: 700; }}
  .footer {{ text-align: center; color: #94a3b8; font-size: 12px; margin-top: 24px; }}
  .data-table-wrap {{ max-height: 500px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 8px; }}
  .data-table-wrap table thead th {{ position: sticky; top: 0; z-index: 1; }}
  .chart-card .chart-box {{ width: 100%; height: 380px; background: #e8eaed; border: 1px solid #b7bcc2; border-radius: 10px; overflow: hidden; }}
  .chart-tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
  .chart-tabs span.chip {{ display:inline-block; padding:4px 12px; border-radius:999px;
                            font-size:12px; background:#eef2ff; color:#4338ca; border:1px solid #c7d2fe; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{title}</h1>
    <div class="subtitle">{subtitle}</div>
  </div>
  {body}
  <div class="footer">由 星穹视界帧率测试 生成 · {gen_time}</div>
</div>
</body>
</html>"""

    def _html_info_section(self, items):
        """生成信息网格 HTML"""
        cells = "".join(
            f'<div class="info-item"><span class="label">{k}</span>'
            f'<span class="value">{v}</span></div>'
            for k, v in items
        )
        return f'<div class="card"><h2>📋 基本信息</h2><div class="info-grid">{cells}</div></div>'

    def _html_summary_cards(self, items):
        """生成汇总统计卡片 HTML: [(label, value, color_class), ...]"""
        cards = "".join(
            f'<div class="stat-card"><div class="stat-label">{lbl}</div>'
            f'<div class="stat-num {cls}">{val}</div></div>'
            for lbl, val, cls in items
        )
        return f'<div class="card"><h2>📊 汇总统计</h2><div class="summary-grid">{cards}</div></div>'

    def _html_data_table(self, headers, rows):
        """生成数据表格 HTML"""
        th = "".join(f"<th>{h}</th>" for h in headers)
        trs = ""
        for row in rows:
            tds = "".join(f"<td>{c}</td>" for c in row)
            trs += f"<tr>{tds}</tr>"
        return (
            f'<div class="card"><h2>📈 采样明细</h2>'
            f'<div class="data-table-wrap"><table><thead><tr>{th}</tr></thead>'
            f'<tbody>{trs}</tbody></table></div></div>'
        )

    def _html_chart_section(self, title: str, x_data: list,
                            series_list: list, x_label: str = "时间 (秒)",
                            extra_chips: list | None = None,
                            height: int = 380, y_unit: str = "") -> str:
        """生成一张 ECharts 趋势图卡片 HTML（在 <body> 内自执行初始化）

        series_list: [{"name": str, "data": list, "color": "#hex", "type":"line"(默认),
                       "yAxisIndex":0(默认), "smooth":True(默认)} ...]
        """
        import json, random
        chart_id = f"c_{random.randint(10_000_000, 99_999_999)}"
        chips_html = ""
        if extra_chips:
            chips_html = '<div class="chart-tabs">' + "".join(
                f'<span class="chip">{c}</span>' for c in extra_chips
            ) + "</div>"

        # ---------- 视觉常量：灰色背景 + 高对比度深色文字 + 加粗线条 ----------
        CHART_BG   = "#e8eaed"   # 图表画布：中性中灰（#e8eaed），对深浅色线都有足够对比
        TEXT_DARK  = "#1f2937"   # 主文字：深墨色，在 #e8eaed 上对比度 ≈ 15:1，远超 WCAG AA
        TEXT_MED   = "#374151"   # 次文字：中度墨色（图例、标签），对比度 ≈ 10:1
        GRID_LINE  = "#b7bcc2"   # 网格线：深一度的灰，保证与背景区分但不喧宾
        AXIS_LINE  = "#6b7280"   # 坐标轴：更深的灰
        # 加粗线条：对调用方传入的 width × 放大系数；默认值由 2 → 3.5
        LINE_WIDTH_DEFAULT = 3.8
        def _boost_width(w):
            if w is None:
                return LINE_WIDTH_DEFAULT
            try:
                return max(LINE_WIDTH_DEFAULT, float(w) * 2.0)
            except (TypeError, ValueError):
                return LINE_WIDTH_DEFAULT
        # 面积填充透明度适当降低，灰底上更清晰
        AREA_OPACITY = 0.22

        # 二次处理：防止 JSON 里的 None 影响 ECharts；对每个 series.data 用 JSON dump
        ech_series = []
        for s in series_list:
            color = s.get("color", "#2563eb")
            line_w = _boost_width(s.get("width"))
            sd = {
                "name": s.get("name", "Series"),
                "type": s.get("type", "line"),
                "smooth": s.get("smooth", True),
                "showSymbol": s.get("showSymbol", False),
                "data": s.get("data", []),
                "lineStyle": {"width": line_w, "color": color},
                "itemStyle": {"color": color},
                "yAxisIndex": s.get("yAxisIndex", 0),
                "emphasis": {"focus": "series", "lineStyle": {"width": line_w + 1.2}},
                "z": 5,   # 确保线条在网格之上
            }
            if "areaStyle" in s and s["areaStyle"]:
                sd["areaStyle"] = {"opacity": AREA_OPACITY, "color": color}
            ech_series.append(sd)
        option = {
            "backgroundColor": CHART_BG,   # ★ 灰色画布背景
            "grid": {"left": 56, "right": 56 if any(s.get("yAxisIndex", 0) != 0 for s in series_list) else 28,
                     "top": 56, "bottom": 56},
            "tooltip": {
                "trigger": "axis",
                "backgroundColor": "rgba(17, 24, 39, 0.92)",
                "borderColor": "#111827",
                "borderWidth": 1,
                "textStyle": {"color": "#f9fafb", "fontSize": 13},
                "extraCssText": "box-shadow: 0 6px 20px rgba(0,0,0,0.25); border-radius: 8px; padding: 8px 12px;",
            },
            "legend": {
                "top": 12, "textStyle": {"fontSize": 13, "color": TEXT_DARK, "fontWeight": "bold"},
                "itemGap": 18, "itemWidth": 28, "itemHeight": 14,
            },
            "toolbox": {
                "right": 12, "top": 8,
                "iconStyle": {"borderColor": TEXT_DARK},
                "emphasis": {"iconStyle": {"borderColor": "#111827"}},
                "feature": {
                    "saveAsImage": {"title": "保存PNG", "pixelRatio": 2},
                    "dataZoom": {"title": {"zoom": "缩放", "back": "重置缩放"}},
                    "restore": {"title": "还原"},
                },
            },
            "dataZoom": [
                {"type": "inside"},
                {"type": "slider", "height": 20, "bottom": 8,
                 "textStyle": {"color": TEXT_MED, "fontSize": 11},
                 "borderColor": GRID_LINE,
                 "backgroundColor": "#ffffff",
                 "fillerColor": "rgba(37, 99, 235, 0.15)",
                 "handleStyle": {"color": "#2563eb"}},
            ],
            "xAxis": {
                "type": "category", "data": x_data, "name": x_label,
                "nameLocation": "middle", "nameGap": 30,
                "nameTextStyle": {"color": TEXT_DARK, "fontSize": 12, "fontWeight": "bold"},
                "axisLabel": {"fontSize": 11, "color": TEXT_MED, "fontWeight": 500},
                "axisLine": {"lineStyle": {"color": AXIS_LINE, "width": 1.2}},
                "axisTick": {"lineStyle": {"color": AXIS_LINE}},
            },
            "yAxis": [{
                "type": "value", "name": y_unit, "nameGap": 36,
                "nameTextStyle": {"color": TEXT_DARK, "fontSize": 12, "fontWeight": "bold"},
                "axisLabel": {"fontSize": 11, "color": TEXT_MED, "fontWeight": 500},
                "axisLine": {"lineStyle": {"color": AXIS_LINE, "width": 1.2}, "show": True},
                "axisTick": {"show": True, "lineStyle": {"color": AXIS_LINE}},
                "splitLine": {"lineStyle": {"type": "dashed", "color": GRID_LINE, "width": 1}},
            }],
            "series": ech_series,
        }
        # 如有双 Y 轴：加一条 yAxis（按最大 yAxisIndex 补齐）
        max_yi = max((s.get("yAxisIndex", 0) for s in series_list), default=0)
        if max_yi >= 1:
            while len(option["yAxis"]) <= max_yi:
                option["yAxis"].append({
                    "type": "value",
                    "nameTextStyle": {"color": TEXT_DARK, "fontSize": 12, "fontWeight": "bold"},
                    "axisLabel": {"fontSize": 11, "color": TEXT_MED, "fontWeight": 500},
                    "axisLine": {"lineStyle": {"color": AXIS_LINE, "width": 1.2}, "show": True},
                    "axisTick": {"show": True, "lineStyle": {"color": AXIS_LINE}},
                    "splitLine": {"show": False},
                })
        option_json = json.dumps(option, ensure_ascii=False, allow_nan=False)
        html = (
            f'<div class="card chart-card"><h2>📉 {title}</h2>'
            f'{chips_html}'
            f'<div id="{chart_id}" class="chart-box" style="height:{height}px;"></div>'
            f'<script type="text/javascript">'
            f'(function(){{'
            f'  try {{ '
            f'    var dom = document.getElementById("{chart_id}");'
            f'    var chart = echarts.init(dom, null, {{renderer: "canvas"}});'
            f'    chart.setOption({option_json});'
            f'    window.addEventListener("resize", function(){{chart.resize();}});'
            f'  }} catch(e) {{ document.getElementById("{chart_id}").innerHTML = '
            f'    "<div style=\\"padding:20px;color:#dc2626;text-align:center;\\">图表加载失败：" + e.message + "</div>"; }}'
            f'}})();'
            f'</script></div>'
        )
        return html

    # ============================================================
    # 导出预览：HTML / CSV 在保存前弹窗确认
    # ============================================================
    def _preview_html(self, preview_title: str, html_body: str,
                      default_save_path: str,
                      report_title: str = "报告", report_subtitle: str = "") -> str | None:
        """弹出 HTML 预览对话框，用户确认后返回保存路径，取消返回 None。

        使用 QTextBrowser（setHtml）渲染，顶部「取消/保存」按钮；保存时走 _save_html。
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextBrowser, QLabel, QFileDialog
        # 构造预览用的完整 HTML（与最终导出内容一致）
        preview_full = MainWindow._HTML_TEMPLATE.format(
            title=report_title, subtitle=report_subtitle,
            body=html_body,
            gen_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        dlg = QDialog(self)
        dlg.setWindowTitle(preview_title)
        dlg.resize(960, 720)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        tip = QLabel(self._tr("lbl_html_preview_tip"))
        tip.setStyleSheet("color:#64748b;font-size:12px;")
        v.addWidget(tip)
        br = QTextBrowser()
        br.setOpenExternalLinks(True)
        br.setHtml(preview_full)
        v.addWidget(br, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel_btn = QPushButton(self._tr("btn_cancel"))
        cancel_btn.setStyleSheet("QPushButton{padding:8px 20px;border-radius:8px;background:#e2e8f0;color:#334155;border:none;}QPushButton:hover{background:#cbd5e1;}")
        save_btn = QPushButton(self._tr("btn_save_html"))
        save_btn.setStyleSheet("QPushButton{padding:8px 24px;border-radius:8px;background:#3b82f6;color:white;border:none;font-weight:bold;}QPushButton:hover{background:#2563eb;}")
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        v.addLayout(btns)
        result_path = [None]

        def _do_save():
            fp, _ = QFileDialog.getSaveFileName(self, self._tr("msg_save_html_title"), default_save_path, self._tr("fmt_html_filter"))
            if not fp:
                return
            try:
                self._save_html(fp, report_title, report_subtitle, html_body)
                result_path[0] = fp
                dlg.accept()
            except Exception as e:
                from app_logger import log_exception
                log_exception(e, "保存 HTML 失败")
                QMessageBox.critical(self, self._tr("msg_save_failed"), str(e))

        cancel_btn.clicked.connect(dlg.reject)
        save_btn.clicked.connect(_do_save)
        if dlg.exec_() == QDialog.Accepted:
            return result_path[0]
        return None

    def _preview_csv(self, preview_title: str, csv_rows: list[list],
                     default_save_path: str) -> str | None:
        """弹出 CSV 预览对话框，用户确认后返回保存路径，取消返回 None。"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QLabel, QHeaderView, QFileDialog
        dlg = QDialog(self)
        dlg.setWindowTitle(preview_title)
        dlg.resize(820, 560)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        tip = QLabel(self._tr("lbl_csv_preview_tip"))
        tip.setStyleSheet("color:#64748b;font-size:12px;")
        v.addWidget(tip)
        tw = QTableWidget()
        n_rows = len(csv_rows)
        n_cols = max((len(r) for r in csv_rows), default=1)
        tw.setRowCount(n_rows)
        tw.setColumnCount(n_cols)
        tw.setHorizontalHeaderLabels([f"{self._tr('lbl_column')}{i+1}" for i in range(n_cols)])
        tw.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tw.verticalHeader().setVisible(False)
        for r_idx, row in enumerate(csv_rows):
            for c_idx in range(n_cols):
                val = row[c_idx] if c_idx < len(row) else ""
                item = QTableWidgetItem("" if val is None else str(val))
                tw.setItem(r_idx, c_idx, item)
        v.addWidget(tw, 1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel_btn = QPushButton(self._tr("btn_cancel"))
        cancel_btn.setStyleSheet("QPushButton{padding:8px 20px;border-radius:8px;background:#e2e8f0;color:#334155;border:none;}QPushButton:hover{background:#cbd5e1;}")
        save_btn = QPushButton(self._tr("btn_save_csv"))
        save_btn.setStyleSheet("QPushButton{padding:8px 24px;border-radius:8px;background:#16a34a;color:white;border:none;font-weight:bold;}QPushButton:hover{background:#15803d;}")
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        v.addLayout(btns)
        result_path = [None]

        def _do_save():
            fp, _ = QFileDialog.getSaveFileName(self, self._tr("msg_save_csv_title"), default_save_path, self._tr("fmt_csv_filter"))
            if not fp:
                return
            try:
                with open(fp, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    for r in csv_rows:
                        w.writerow(r)
                result_path[0] = fp
                dlg.accept()
            except Exception as e:
                from app_logger import log_exception
                log_exception(e, "保存 CSV 失败")
                QMessageBox.critical(self, self._tr("msg_save_failed"), str(e))

        cancel_btn.clicked.connect(dlg.reject)
        save_btn.clicked.connect(_do_save)
        if dlg.exec_() == QDialog.Accepted:
            return result_path[0]
        return None

    @staticmethod
    def _fps_color(fps):
        """FPS 着色：绿(>=55) / 橙(40-54) / 红(<40)"""
        try:
            v = float(fps)
        except (ValueError, TypeError):
            return ""
        if v >= 55:
            return "good"
        elif v >= 40:
            return "warn"
        return "bad"

    @staticmethod
    def _save_html(file_path, title, subtitle, body):
        """写入 HTML 文件"""
        html = MainWindow._HTML_TEMPLATE.format(
            title=title, subtitle=subtitle,
            body=body,
            gen_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

    # ----- 曲线图导出工具 -----
    @staticmethod
    def _plot_to_pixmap(plot_widget, width: int = 1600, height: int = 640, title: str = ""):
        """把 PlotWidget 渲染为**超高物理分辨率** QPixmap（4K~级像素数）。

        核心策略：
        - 固定以 scale=4（目标是物理像素 ≥ 4× 逻辑像素）生成位图，
          直接保存为 JPG/PNG 不再缩回去，避免二次重采样导致糊。
        - PlotWidget 的字体 / 轴宽度 / 标题字号 都按 scale 线性放大，
          否则放大 render 后文字会显得太小（这才是「看不清」的主因）。
        - 背景统一浅色白底 + 卡片圆角 + 标题栏，视觉专业且打印清晰。
        """
        from PyQt5.QtGui import QImage, QPainter, QPixmap, QColor, QBrush, QFont, QPen, QLinearGradient, QRadialGradient
        from PyQt5.QtCore import Qt, QRectF, QSize
        if plot_widget is None:
            return None
        try:
            import pyqtgraph as pg

            # 4 倍物理像素（目标：单张图 ≥ 2400px 宽，打印/放大都清楚）
            scale = 4
            inner_w = width * scale
            inner_h = height * scale

            # 外层卡片画布：边距 + 标题栏
            pad_lr = 56 * scale
            pad_tb = 44 * scale
            title_h = (92 * scale) if title else 0
            canvas_w = inner_w + pad_lr * 2
            canvas_h = inner_h + pad_tb * 2 + title_h

            img = QImage(canvas_w, canvas_h, QImage.Format_ARGB32)
            img.setDevicePixelRatio(1.0)  # 始终按真实物理像素输出保存
            img.fill(QColor("#f1f5f9"))
            painter = QPainter(img)
            try:
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                painter.setRenderHint(QPainter.TextAntialiasing, True)
                painter.setRenderHint(QPainter.HighQualityAntialiasing, True)

                # 1. 主卡片（圆角白底 + 双阴影）
                card_x = 12 * scale
                card_y = 12 * scale
                card_w = canvas_w - 24 * scale
                card_h = canvas_h - 24 * scale
                radius = 28 * scale

                # 外阴影 1（大淡）
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(15, 23, 42, 18)))
                painter.drawRoundedRect(QRectF(card_x + 6, card_y + 12, card_w, card_h), radius, radius)
                # 外阴影 2（小深）
                painter.setBrush(QBrush(QColor(15, 23, 42, 28)))
                painter.drawRoundedRect(QRectF(card_x + 2, card_y + 4, card_w, card_h), radius, radius)
                # 白底卡片
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.drawRoundedRect(QRectF(card_x, card_y, card_w, card_h), radius, radius)
                # 卡片描边
                painter.setPen(QPen(QColor(226, 232, 240, 255), max(1, 2 * scale)))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(QRectF(card_x, card_y, card_w, card_h), radius, radius)

                # 2. 顶部标题栏（渐变条 + 标题文字，字号 × scale）
                if title:
                    tb_y = card_y + 28 * scale
                    tb_x = card_x + 40 * scale
                    tb_w = card_w - 80 * scale
                    tb_h = title_h - 44 * scale
                    # 渐变背景
                    painter.setPen(Qt.NoPen)
                    g = QLinearGradient(tb_x, tb_y, tb_x + tb_w, tb_y)
                    g.setColorAt(0.0, QColor("#0284c7"))
                    g.setColorAt(0.5, QColor("#2563eb"))
                    g.setColorAt(1.0, QColor("#4f46e5"))
                    painter.setBrush(QBrush(g))
                    painter.drawRoundedRect(QRectF(tb_x, tb_y, tb_w, tb_h), 12 * scale, 12 * scale)
                    # 标题文字：字号用 22pt × scale，保证 4K 下仍然是大标题
                    title_fsize = max(18, 22 * scale)
                    painter.setPen(QPen(QColor(255, 255, 255, 255), 1))
                    f = QFont("PingFang SC", title_fsize, QFont.Bold)
                    painter.setFont(f)
                    painter.drawText(QRectF(tb_x + 36 * scale, tb_y, tb_w - 72 * scale, tb_h),
                                     Qt.AlignLeft | Qt.AlignVCenter, title)

                # 3. 暂存 PlotWidget 样式，并在高分辨率下设置放大字体/轴
                orig_bg = plot_widget.backgroundBrush() if hasattr(plot_widget, "backgroundBrush") else None
                axes_info = []  # (ax, old_pen, old_text_pen, old_style)
                orig_label_styles = {}  # side -> old style dict

                # 先把 PlotWidget 几何放大，再做 render
                orig_geom = plot_widget.geometry()
                # 临时应用：背景 + 网格 + 轴粗细/颜色 + 轴标签字体放大
                try:
                    plot_widget.setBackground("#ffffff")
                    for axkey in ("left", "bottom", "right", "top"):
                        try:
                            ax = plot_widget.getAxis(axkey)
                        except Exception:
                            ax = None
                        if ax is None:
                            continue
                        old_pen = ax.pen() if hasattr(ax, "pen") else None
                        old_text_pen = ax.textPen() if hasattr(ax, "textPen") else None
                        # 轴宽度 × scale，深色
                        dk_pen = pg.mkPen("#0f172a", width=max(2, 3 * scale))
                        ax.setPen(dk_pen)
                        # 刻度文字：直接用 QFont 放大
                        try:
                            old_tick_font = ax.tickFont if hasattr(ax, "tickFont") and ax.tickFont is not None else None
                        except Exception:
                            old_tick_font = None
                        tf = QFont("PingFang SC", max(12, 14 * scale))
                        try:
                            ax.setTickFont(tf)
                        except Exception:
                            pass
                        # 标签字体（labelStyle 里会带大小/颜色/字重）
                        old_style = None
                        try:
                            if hasattr(ax, "_style") and ax._style is not None:
                                old_style = dict(ax._style)
                            elif hasattr(ax, "labelStyle"):
                                try:
                                    old_style = dict(ax.labelStyle) if ax.labelStyle else None
                                except Exception:
                                    old_style = None
                        except Exception:
                            old_style = None
                        new_style = {
                            "color": "#0f172a",
                            "font-size": f"{max(16, 20 * scale)}pt",
                            "font-family": "PingFang SC, Microsoft YaHei, sans-serif",
                            "font-weight": "bold",
                        }
                        try:
                            ax.setLabel(**new_style) if False else ax.setLabel(
                                ax.labelText, units=ax.units, **new_style
                            ) if hasattr(ax, "labelText") else None
                        except Exception:
                            pass
                        # 更安全的方法：直接调用 setStyle 或重写 labelStyle
                        try:
                            if hasattr(ax, "setStyle"):
                                ax.setStyle(None)  # 先清
                            ax.labelStyle = new_style
                            if hasattr(ax, "setLabel"):
                                # 重新刷新 label
                                txt = ""
                                try:
                                    txt = getattr(ax, "_labelText", "") or (
                                        ax.label.toPlainText() if hasattr(ax, "label") and hasattr(ax.label, "toPlainText") else ""
                                    )
                                except Exception:
                                    pass
                                if txt:
                                    ax.setLabel(txt, **new_style)
                        except Exception:
                            pass
                        # 刻度文字颜色（深黑）
                        ax.setTextPen(pg.mkPen(QColor("#0f172a")))
                        axes_info.append((ax, old_pen, old_text_pen, old_style, old_tick_font))

                    # 网格：半透明黑，35% 显示
                    try:
                        plot_widget.showGrid(x=True, y=True, alpha=0.35)
                    except Exception:
                        pass

                    # 把 plot 的所有已绘制曲线「笔宽再粗一点」：让导出后线条不那么细
                    curve_backup = []
                    try:
                        plot_item = plot_widget.getPlotItem() if hasattr(plot_widget, "getPlotItem") else None
                        if plot_item is not None:
                            for it in plot_item.items:
                                try:
                                    pen = getattr(it, "opts", {}).get("pen") if hasattr(it, "opts") else None
                                    if pen is None:
                                        try:
                                            pen = it.opts["pen"] if hasattr(it, "opts") and "pen" in it.opts else None
                                        except Exception:
                                            pen = None
                                    if pen is None:
                                        continue
                                    w0 = 1.5
                                    try:
                                        if hasattr(pen, "width"):
                                            w0 = pen.width() or 1.5
                                        elif hasattr(pen, "widthF"):
                                            w0 = pen.widthF() or 1.5
                                    except Exception:
                                        w0 = 1.5
                                    w1 = max(2, w0 * scale)
                                    # 复制一支更粗的笔
                                    from PyQt5.QtGui import QColor as _QC
                                    try:
                                        c = pen.color()
                                        cap = pen.capStyle()
                                        dash = pen.style()
                                        dash_pattern = None
                                        if dash == Qt.CustomDashLine:
                                            try:
                                                dash_pattern = pen.dashPattern()
                                            except Exception:
                                                dash_pattern = None
                                        new_pen = QPen(c, w1, dash)
                                        new_pen.setCapStyle(cap)
                                        if dash_pattern is not None:
                                            try:
                                                new_pen.setDashPattern(dash_pattern)
                                            except Exception:
                                                pass
                                        old_pen_saved = pen
                                        it.setPen(new_pen)
                                        curve_backup.append((it, old_pen_saved))
                                    except Exception:
                                        pass
                                except Exception:
                                    continue
                    except Exception:
                        pass

                    # 4. 真实按 4× 尺寸渲染到 plot_img
                    plot_img = QImage(inner_w, inner_h, QImage.Format_ARGB32)
                    plot_img.fill(QColor("#ffffff"))
                    pw_painter = QPainter(plot_img)
                    try:
                        pw_painter.setRenderHint(QPainter.Antialiasing, True)
                        pw_painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                        pw_painter.setRenderHint(QPainter.TextAntialiasing, True)
                        pw_painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
                        plot_widget.setGeometry(0, 0, inner_w, inner_h)
                        # 强制一次 layout/polish，保证放大后的字体生效
                        try:
                            plot_widget.ensurePolished()
                            plot_widget.layout().activate() if plot_widget.layout() else None
                        except Exception:
                            pass
                        plot_widget.render(pw_painter)
                    finally:
                        pw_painter.end()
                        try:
                            plot_widget.setGeometry(orig_geom)
                        except Exception:
                            pass

                    # 5. 曲线笔还原
                    for it, old_pen in curve_backup:
                        try:
                            it.setPen(old_pen)
                        except Exception:
                            pass

                    # 拷贝到卡片画布 + 画图外框
                    plot_x = card_x + pad_lr
                    plot_y = card_y + pad_tb + title_h
                    painter.setPen(QPen(QColor(203, 213, 225, 255), max(1, 2 * scale)))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRoundedRect(QRectF(plot_x - 4, plot_y - 4, inner_w + 8, inner_h + 8),
                                            12 * scale, 12 * scale)
                    painter.drawImage(QRectF(plot_x, plot_y, inner_w, inner_h),
                                      plot_img, QRectF(0, 0, inner_w, inner_h))
                finally:
                    # 还原背景 / 轴
                    try:
                        if orig_bg is not None and hasattr(plot_widget, "setBackground"):
                            try:
                                plot_widget.setBackground(orig_bg)
                            except Exception:
                                plot_widget.setBackground("#2b2f36")
                    except Exception:
                        pass
                    for ax, old_pen, old_text_pen, old_style, old_tick_font in axes_info:
                        try:
                            if old_pen is not None:
                                try:
                                    ax.setPen(old_pen)
                                except Exception:
                                    pass
                            if old_text_pen is not None:
                                try:
                                    ax.setTextPen(old_text_pen)
                                except Exception:
                                    pass
                            if old_tick_font is not None and hasattr(ax, "setTickFont"):
                                try:
                                    ax.setTickFont(old_tick_font)
                                except Exception:
                                    pass
                            if old_style and hasattr(ax, "labelStyle"):
                                try:
                                    txt = getattr(ax, "_labelText", "") or ""
                                    if hasattr(ax, "label") and hasattr(ax.label, "toPlainText"):
                                        txt = ax.label.toPlainText() or txt
                                    units = getattr(ax, "units", "") or ""
                                    try:
                                        ax.setLabel(txt, units=units, **old_style)
                                    except Exception:
                                        ax.labelStyle = old_style
                                except Exception:
                                    try:
                                        ax.labelStyle = old_style
                                    except Exception:
                                        pass
                        except Exception:
                            pass
            finally:
                painter.end()

            # 不再做任何 scaled！直接输出 4× 物理像素图，保证保存后清晰。
            pm = QPixmap.fromImage(img)
            return pm
        except Exception as _e:
            try:
                from app_logger import log_exception
                log_exception(_e, "_plot_to_pixmap 超高分辨率导出失败")
            except Exception:
                pass
            return None

    @staticmethod
    def _pixmap_to_base64(pm) -> str:
        """QPixmap 转 PNG base64 字符串（用于 HTML 内嵌）"""
        from PyQt5.QtCore import QByteArray, QBuffer
        if pm is None:
            return ""
        try:
            barray = QByteArray()
            buf = QBuffer(barray)
            buf.open(QBuffer.WriteOnly)
            pm.save(buf, "PNG")
            buf.close()
            import base64
            return base64.b64encode(bytes(barray)).decode("ascii")
        except Exception:
            return ""

    @staticmethod
    def _stack_pixmaps_vertically(pixmaps: list, bg_color=(241, 245, 249),
                                  title_text: str = "", subtitle_text: str = "",
                                  footer_text: str = ""):
        """多个 QPixmap 纵向拼接为大图（高物理像素也能自适应）。

        根据首图宽度估算一个缩放因子，使页眉/页脚字体、间距在 1x/2x/4x 下都协调。
        """
        from PyQt5.QtGui import QImage, QPainter, QPixmap, QColor, QFont, QPen, QBrush, QLinearGradient
        from PyQt5.QtCore import Qt, QRectF, QPointF
        valid = [p for p in pixmaps if p is not None and not p.isNull()]
        if not valid:
            return None
        w = max(p.width() for p in valid)
        # 参考宽度（1600 为设计稿的 1x），由此算出整体缩放系数
        ref_w = 1700
        u = max(1.0, w / ref_w)
        gap = int(40 * u)
        header_h = 0
        if title_text:
            header_h = int((260 if subtitle_text else 180) * u)
        footer_h = int(120 * u) if footer_text else 0
        margin = int(32 * u)
        h = sum(p.height() for p in valid) + (len(valid) - 1) * gap + header_h + footer_h + margin * 2
        img = QImage(w, h, QImage.Format_ARGB32)
        img.fill(QColor(bg_color[0], bg_color[1], bg_color[2]))
        painter = QPainter(img)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

            y = margin

            # 封面头（横幅 + 大标题 + 副标题）
            if header_h > 0:
                pad_x = int(40 * u)
                radius = int(28 * u)
                bar = QLinearGradient(0, y, w, y)
                bar.setColorAt(0.0, QColor("#0ea5e9"))
                bar.setColorAt(0.35, QColor("#2563eb"))
                bar.setColorAt(1.0, QColor("#6366f1"))
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(bar))
                painter.drawRoundedRect(QRectF(pad_x, y, w - pad_x * 2, header_h - int(12 * u)), radius, radius)
                # 装饰小圆点
                for i, c in enumerate([(255, 255, 255, 62), (255, 255, 255, 36), (255, 255, 255, 22)]):
                    painter.setBrush(QBrush(QColor(*c)))
                    cx = w - pad_x - int(120 * u) - i * int(52 * u)
                    cy = y + int(58 * u) + i * int(32 * u)
                    rr = int((28 - i * 6) * u)
                    painter.drawEllipse(QPointF(cx, cy), rr, rr)
                # 主标题（按 u 缩放）
                title_fsize = int(48 * u)
                sub_fsize = int(20 * u)
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.setFont(QFont("PingFang SC", title_fsize, QFont.Bold))
                top_y = y + int(28 * u)
                painter.drawText(QRectF(pad_x + int(60 * u), top_y,
                                        w - (pad_x + int(60 * u)) - int(400 * u), int(78 * u)),
                                 Qt.AlignLeft | Qt.AlignVCenter, title_text)
                if subtitle_text:
                    painter.setFont(QFont("PingFang SC", sub_fsize))
                    painter.setPen(QPen(QColor(224, 242, 254), 1))
                    painter.drawText(QRectF(pad_x + int(60 * u), top_y + int(90 * u),
                                            w - (pad_x + int(60 * u)) * 2, int(48 * u)),
                                     Qt.AlignLeft | Qt.AlignVCenter, subtitle_text)
                y += header_h

            # 子图逐一绘制
            for p in valid:
                painter.drawPixmap((w - p.width()) // 2, y, p)
                y += p.height() + gap

            # 页脚
            if footer_h > 0:
                fy = h - footer_h - int(8 * u)
                painter.setPen(QPen(QColor(148, 163, 184), 1))
                painter.setFont(QFont("PingFang SC", max(12, int(18 * u))))
                painter.drawText(QRectF(int(32 * u), fy, w - int(64 * u), footer_h),
                                 Qt.AlignCenter | Qt.AlignVCenter, footer_text)
        finally:
            painter.end()
        return QPixmap.fromImage(img)

    def _render_fps_plots_pixmap(self, platform: str = "android"):
        """安卓或 iOS FPS 页所有曲线图纵向拼接成大图（带封面头与单图标题）"""
        plots = []
        if platform == "ios":
            plots.append((getattr(self, "ios_fps_plot", None), 1700, 640,
                          self._tr("chart_fps_trend_title") or "帧率趋势（瞬时 / 平均 / 1% Low / 0.1% Low）"))
            plots.append((getattr(self, "ios_frame_plot", None), 1700, 480,
                          self._tr("chart_frame_time_title") or "帧时分布（P95 / P99）"))
            plots.append((getattr(self, "ios_hist_plot", None), 1700, 500,
                          self._tr("chart_fps_hist_title") or "FPS 分布直方图"))
            plots.append((getattr(self, "ios_dist_plot", None), 1700, 480,
                          self._tr("chart_jitter_dist_title") or "卡顿抖动分布"))
            header_title = self._tr("report_title_ios_fps") or "iOS 帧率测试报告"
            subtitle_extra = self.ios_app_combo.currentText().strip() if getattr(self, "ios_app_combo", None) else ""
        else:
            plots.append((getattr(self, "fps_plot", None), 1700, 640,
                          self._tr("chart_fps_trend_title") or "帧率趋势（瞬时 / 平均 / 1% Low / 0.1% Low）"))
            plots.append((getattr(self, "frame_dist_plot", None), 1700, 480,
                          self._tr("chart_frame_time_title") or "帧时分布（P95 / P99）"))
            plots.append((getattr(self, "hist_plot", None), 1700, 500,
                          self._tr("chart_fps_hist_title") or "FPS 分布直方图"))
            plots.append((getattr(self, "frame_plot", None), 1700, 480,
                          self._tr("chart_jitter_dist_title") or "卡顿抖动分布"))
            header_title = self._tr("report_title_fps") or "安卓帧率测试报告"
            subtitle_extra = self.package_combo.currentText().strip() if getattr(self, "package_combo", None) else ""

        pms = []
        for w, wid, hei, title in plots:
            pm = self._plot_to_pixmap(w, wid, hei, title=title)
            if pm is not None:
                pms.append(pm)
        try:
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            now_str = ""
        sub = subtitle_extra + ("  ·  " + now_str if now_str else "") if subtitle_extra else (now_str or "")
        footer = "星穹视界 · Stellar Vision FPS Tester  ·  仅用于性能测试场景"
        return self._stack_pixmaps_vertically(pms, title_text=header_title,
                                              subtitle_text=sub, footer_text=footer)

    def _render_hw_plots_pixmap(self, platform: str = "android"):
        """安卓或 iOS HW 页所有曲线图纵向拼接成大图（带封面头与单图标题）"""
        plots = []
        if platform == "ios":
            plots.append((getattr(self, "ios_hw_plot", None), 1700, 640,
                          self._tr("chart_hw_resource_title") or "资源占用趋势（CPU / GPU / 内存）"))
            plots.append((getattr(self, "ios_hw_usage_plot", None), 1700, 520,
                          self._tr("chart_hw_usage_breakdown") or "CPU/GPU/内存使用明细"))
            plots.append((getattr(self, "ios_hw_temp_plot", None), 1700, 440,
                          self._tr("chart_hw_temp_title") or "温度变化趋势"))
            header_title = self._tr("report_title_ios_hw") or "iOS 硬件监测报告"
            subtitle_extra = ""
        else:
            plots.append((getattr(self, "hw_plot", None), 1700, 640,
                          self._tr("chart_hw_resource_title") or "资源占用趋势（CPU / GPU / 内存）"))
            plots.append((getattr(self, "hw_usage_plot", None), 1700, 520,
                          self._tr("chart_hw_usage_breakdown") or "CPU/GPU/内存使用明细"))
            plots.append((getattr(self, "hw_temp_plot", None), 1700, 440,
                          self._tr("chart_hw_temp_title") or "温度变化趋势"))
            plots.append((getattr(self, "hw_power_plot", None), 1700, 440,
                          self._tr("chart_hw_power_title") or "电池功率 / 电流趋势"))
            header_title = self._tr("report_title_hw") or "安卓硬件监测报告"
            subtitle_extra = ""

        pms = []
        for w, wid, hei, title in plots:
            pm = self._plot_to_pixmap(w, wid, hei, title=title)
            if pm is not None:
                pms.append(pm)
        try:
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            now_str = ""
        sub = (subtitle_extra + "  ·  " + now_str) if (subtitle_extra and now_str) else (subtitle_extra or now_str or "")
        footer = "星穹视界 · Stellar Vision FPS Tester  ·  仅用于性能测试场景"
        return self._stack_pixmaps_vertically(pms, title_text=header_title,
                                              subtitle_text=sub, footer_text=footer)

    def _save_pixmap_dialog(self, default_path: str, pixmap) -> Optional[str]:
        """弹出 JPG 保存对话框，保存 pixmap 为图片。返回保存的路径，失败返回 None"""
        if pixmap is None or pixmap.isNull():
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_no_hw_export_data"))
            return None
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, self._tr("msg_save_jpg_title"), default_path,
            self._tr("fmt_jpg_filter") + ";;PNG (*.png)"
        )
        if not path:
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            path += ".jpg"
            ext = ".jpg"
        fmt = "PNG" if ext == ".png" else "JPG"
        # JPG 质量 100：追求最佳清晰度；PNG 本身无损用默认 -1
        quality = -1 if fmt == "PNG" else 100
        ok = pixmap.save(path, fmt, quality)
        if not ok:
            QMessageBox.critical(self, self._tr("msg_error"), self._tr("msg_save_failed"))
            return None
        return path

    # ----- 导出菜单（CSV / HTML / JPG 三选一）-----
    def _show_fps_export_menu(self):
        """安卓帧率：导出菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 8px 32px; border-radius: 4px; font-size: 14px; }
            QMenu::item:selected { background-color: #e0f2fe; }
        """)
        act_csv = menu.addAction(self._tr("menu_csv_export"))
        act_html = menu.addAction(self._tr("menu_html_export"))
        act_jpg = menu.addAction(self._tr("menu_jpg_export"))
        action = menu.exec_(self.export_btn.mapToGlobal(self.export_btn.rect().bottomLeft()))
        if action == act_csv:
            self._export_csv()
        elif action == act_html:
            self._export_fps_html()
        elif action == act_jpg:
            self._export_fps_jpg()

    def _show_hw_export_menu(self):
        """安卓 CPU/GPU 监测：导出菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 8px 32px; border-radius: 4px; font-size: 14px; }
            QMenu::item:selected { background-color: #e0f2fe; }
        """)
        act_csv = menu.addAction(self._tr("menu_csv_export"))
        act_html = menu.addAction(self._tr("menu_html_export"))
        act_jpg = menu.addAction(self._tr("menu_jpg_export"))
        action = menu.exec_(self.hw_export_btn.mapToGlobal(self.hw_export_btn.rect().bottomLeft()))
        if action == act_csv:
            self._export_hw_report()
        elif action == act_html:
            self._export_hw_html()
        elif action == act_jpg:
            self._export_hw_jpg()

    def _show_ios_fps_export_menu(self):
        """iOS 帧率：导出菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 8px 32px; border-radius: 4px; font-size: 14px; }
            QMenu::item:selected { background-color: #e0f2fe; }
        """)
        act_csv = menu.addAction(self._tr("menu_csv_export"))
        act_html = menu.addAction(self._tr("menu_html_export"))
        act_jpg = menu.addAction(self._tr("menu_jpg_export"))
        action = menu.exec_(self.ios_export_btn.mapToGlobal(self.ios_export_btn.rect().bottomLeft()))
        if action == act_csv:
            self._export_ios_csv()
        elif action == act_html:
            self._export_ios_fps_html()
        elif action == act_jpg:
            self._export_ios_fps_jpg()

    # ----- JPG 图片导出 -----
    def _export_fps_jpg(self):
        """导出安卓帧率曲线图为 JPG"""
        if not self.history_stats:
            QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_no_export_data"))
            return
        desktop = os.path.expanduser("~/Desktop")
        default_path = os.path.join(desktop, f"fps_charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        pm = self._render_fps_plots_pixmap("android")
        saved = self._save_pixmap_dialog(default_path, pm)
        if saved:
            self._log(f"📷 曲线图图片已导出: {saved}")
            QMessageBox.information(self, self._tr("msg_success"), self._tr("msg_export_success_report").format(path=saved))

    def _export_hw_jpg(self):
        """导出安卓CPU/GPU监测曲线图为 JPG"""
        if not self._hw_history_times:
            QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_no_hw_export_data"))
            return
        desktop = os.path.expanduser("~/Desktop")
        default_path = os.path.join(desktop, f"hw_charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        pm = self._render_hw_plots_pixmap("android")
        saved = self._save_pixmap_dialog(default_path, pm)
        if saved:
            self._log(f"📷 曲线图图片已导出: {saved}")
            QMessageBox.information(self, self._tr("msg_success"), self._tr("msg_export_success_report").format(path=saved))

    def _export_ios_fps_jpg(self):
        """导出 iOS 帧率曲线图为 JPG"""
        if not self._ios_history_stats:
            QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_no_fps_data"))
            return
        desktop = os.path.expanduser("~/Desktop")
        default_path = os.path.join(desktop, f"ios_fps_charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        pm = self._render_fps_plots_pixmap("ios")
        saved = self._save_pixmap_dialog(default_path, pm)
        if saved:
            self._ios_log(f"📷 曲线图图片已导出: {saved}")
            QMessageBox.information(self, self._tr("msg_success"), self._tr("msg_export_success_report").format(path=saved))

    def _export_ios_hw_jpg(self):
        """导出 iOS 硬件监测曲线图为 JPG"""
        if not self._ios_hw_history_times:
            QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_no_hw_data"))
            return
        desktop = os.path.expanduser("~/Desktop")
        default_path = os.path.join(desktop, f"ios_hw_charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        pm = self._render_hw_plots_pixmap("ios")
        saved = self._save_pixmap_dialog(default_path, pm)
        if saved:
            self._ios_log(f"📷 曲线图图片已导出: {saved}")
            QMessageBox.information(self, self._tr("msg_success"), self._tr("msg_export_success_report").format(path=saved))

    def _show_ios_hw_export_menu(self):
        """iOS 硬件监测：导出菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px; }
            QMenu::item { padding: 8px 32px; border-radius: 4px; font-size: 14px; }
            QMenu::item:selected { background-color: #e0f2fe; }
        """)
        act_csv = menu.addAction(self._tr("menu_csv_export"))
        act_html = menu.addAction(self._tr("menu_html_export"))
        act_jpg = menu.addAction(self._tr("menu_jpg_export"))
        action = menu.exec_(self.ios_hw_export_btn.mapToGlobal(self.ios_hw_export_btn.rect().bottomLeft()))
        if action == act_csv:
            self._export_ios_hw_report()
        elif action == act_html:
            self._export_ios_hw_html()
        elif action == act_jpg:
            self._export_ios_hw_jpg()

    # ----- HTML 报告导出 -----
    def _export_fps_html(self):
        """导出安卓帧率 HTML 报告（含 ECharts 趋势图 + 导出预览）"""
        if not self.history_stats:
            QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_no_export_data"))
            return
        desktop = os.path.expanduser("~/Desktop")
        default_name = os.path.join(desktop, f"fps_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        try:
            device_id = self.device_combo.currentData() or "未知"
            app_name = self.package_combo.currentText() or "未知"
            summary = self.analyzer.get_summary()
            refresh_rate = self.refresh_rate_combo.currentData()

            info = self._html_info_section([
                ("设备 ID", device_id),
                ("测试应用", app_name),
                ("屏幕刷新率", f"{refresh_rate}Hz"),
                ("导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ])

            cards = self._html_summary_cards([
                ("平均 FPS", summary.get("avg_fps", "-"), self._fps_color(summary.get("avg_fps", 0))),
                ("最低 FPS", summary.get("min_fps", "-"), self._fps_color(summary.get("min_fps", 0))),
                ("最高 FPS", summary.get("max_fps", "-"), ""),
                ("1% Low", summary.get("low_1_fps", "-"), self._fps_color(summary.get("low_1_fps", 0))),
                ("0.1% Low", summary.get("low_01_fps", "-"), self._fps_color(summary.get("low_01_fps", 0))),
                ("FPS 标准差", summary.get("std_fps", "-"), ""),
                ("卡顿率(%)", summary.get("jank_rate", "-"), ""),
                ("P95 帧时(ms)", summary.get("p95_frame_ms", "-"), ""),
                ("P99 帧时(ms)", summary.get("p99_frame_ms", "-"), ""),
            ])

            # ECharts 趋势图：瞬时FPS / 平均FPS / 1%Low 三线 + 帧时 P95/P99
            times = [round(s.timestamp, 1) for s in self.history_stats]
            fps_inst = [float(s.fps) for s in self.history_stats]
            fps_avg = [float(s.avg_fps) for s in self.history_stats]
            fps_low1 = [float(s.low_1_fps) for s in self.history_stats]
            fps_low01 = [float(s.low_01_fps) for s in self.history_stats]
            charts_html = ""
            charts_html += self._html_chart_section(
                "帧率趋势（瞬时 / 平均 / 1%Low / 0.1%Low）",
                x_data=times, x_label="采样秒数", y_unit="FPS",
                extra_chips=[f"目标刷新率 {refresh_rate}Hz", "无平滑瞬时 FPS", "可拖拽缩放"],
                series_list=[
                    {"name": "瞬时 FPS", "data": fps_inst, "color": "#1d4ed8", "width": 1.4},
                    {"name": "平均 FPS", "data": fps_avg, "color": "#16a34a", "areaStyle": True},
                    {"name": "1% Low FPS", "data": fps_low1, "color": "#f59e0b"},
                    {"name": "0.1% Low FPS", "data": fps_low01, "color": "#dc2626", "width": 1.8},
                ],
            )
            p95 = [float(s.percentile_95) for s in self.history_stats]
            p99 = [float(s.percentile_99) for s in self.history_stats]
            if any(p95) or any(p99):
                charts_html += self._html_chart_section(
                    "帧时分布（P95 / P99）",
                    x_data=times, x_label="采样秒数", y_unit="ms",
                    extra_chips=["数值越低越流畅", "P99 > 50ms 可感知卡顿"],
                    series_list=[
                        {"name": "P95 帧时(ms)", "data": p95, "color": "#7c3aed", "areaStyle": True},
                        {"name": "P99 帧时(ms)", "data": p99, "color": "#be123c"},
                    ],
                )

            headers = ["时间(秒)", "瞬时FPS", "平均FPS", "最低FPS", "最高FPS",
                       "1%Low", "0.1%Low", "标准差", "卡顿帧", "卡顿率(%)",
                       "P95(ms)", "P99(ms)"]
            rows = []
            for s in self.history_stats:
                fps_cls = self._fps_color(s.fps)
                rows.append([
                    f"{s.timestamp:.1f}",
                    f'<span class="{fps_cls} stat-value">{s.fps}</span>',
                    f"{s.avg_fps}", f"{s.min_fps}", f"{s.max_fps}",
                    f"{s.low_1_fps}", f"{s.low_01_fps}",
                    f"{s.std_fps}", f"{s.jank_count}",
                    f"{s.jank_rate}", f"{s.percentile_95}", f"{s.percentile_99}",
                ])
            data_tbl = self._html_data_table(headers, rows)

            # 内嵌曲线图截图（保证任何时候都有曲线图）
            plots_html = ""
            try:
                pm = self._render_fps_plots_pixmap("android")
                b64 = self._pixmap_to_base64(pm) if pm is not None else ""
                if b64:
                    plots_html = f"""
                    <section class="charts-images-section" style="margin-top:32px;">
                      <h2 style="font-size:18px;margin-bottom:12px;color:#0f172a;border-left:4px solid #0288D1;padding-left:10px;">📊 曲线图快照</h2>
                      <div style="background:white;border-radius:12px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
                        <img src="data:image/png;base64,{b64}" style="width:100%;height:auto;display:block;border-radius:8px;" />
                      </div>
                    </section>"""
            except Exception as _ie:
                log_exception(_ie, "安卓帧率 HTML 内嵌曲线图失败")

            body_all = info + cards + charts_html + plots_html + data_tbl
            rtitle = self._tr("report_title_android_fps")
            rsub = f"{app_name} · {device_id}"
            saved = self._preview_html(self._tr("preview_android_fps_html"), body_all, default_name, rtitle, rsub)
            if saved:
                self._log(f"📤 HTML 报告已导出: {saved}")
                QMessageBox.information(self, self._tr("msg_success"), self._tr("msg_export_success_html").format(path=saved))
        except Exception as e:
            log_exception(e, "FPS HTML 导出失败")
            QMessageBox.critical(self, self._tr("msg_error"),self._tr("msg_export_failed_simple").format(err=e))

    def _export_hw_html(self):
        """导出安卓 CPU/GPU 监测 HTML 报告（含 ECharts 趋势图 + 导出预览）"""
        if not self._hw_history_times:
            QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_no_hw_export_data"))
            return
        desktop = os.path.expanduser("~/Desktop")
        default_name = os.path.join(desktop, f"hw_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        try:
            device_id = self.hw_device_combo.currentData() or "未知"
            cpu_labels = list(self._hw_history_cpu.keys())
            gpu_data = self._hw_history_gpu
            n = len(self._hw_history_times)

            info = self._html_info_section([
                ("监测设备", device_id),
                ("采样点数", str(n)),
                ("导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ])

            # 汇总卡片
            cards_data = []
            for label in cpu_labels:
                vals = self._hw_history_cpu[label]
                if vals:
                    avg = sum(vals) / len(vals)
                    cards_data.append((f"{label} 均(MHz)", f"{avg:.0f}", ""))
                    cards_data.append((f"{label} 最大(MHz)", f"{max(vals):.0f}", ""))
            if gpu_data:
                cards_data.append(("GPU 均(MHz)", f"{sum(gpu_data)/len(gpu_data):.0f}", ""))
                cards_data.append(("GPU 最大(MHz)", f"{max(gpu_data):.0f}", ""))
            if self._hw_history_temp:
                avg_t = sum(self._hw_history_temp) / len(self._hw_history_temp)
                max_t = max(self._hw_history_temp)
                cls_t = "bad" if max_t > 65 else ("warn" if max_t > 60 else "")
                cards_data.append(("CPU 均温(°C)", f"{avg_t:.1f}", cls_t))
                cards_data.append(("CPU 最高温(°C)", f"{max_t:.1f}", cls_t))
            cards = self._html_summary_cards(cards_data) if cards_data else ""

            # ECharts 趋势图
            times = [round(t, 1) for t in self._hw_history_times]
            charts_html = ""
            # CPU 集群频率趋势（HPS 实际曲线）
            cpu_colors = ["#2196F3", "#7B1FA2", "#4CAF50", "#FF9800", "#F44336", "#00838F"]
            cpu_series = []
            for i, label in enumerate(cpu_labels):
                vals = self._hw_history_cpu[label]
                cpu_series.append({
                    "name": label,
                    "data": [round(v, 0) if v is not None else None for v in vals],
                    "color": cpu_colors[i % len(cpu_colors)],
                })
            if cpu_series:
                charts_html += self._html_chart_section(
                    "HPS 实际曲线：CPU 集群频率 (MHz)",
                    x_data=times, x_label="采样秒数", y_unit="MHz",
                    extra_chips=["每 1 秒采样", "超大核/大核/小核 分离展示", "可拖拽缩放"],
                    series_list=cpu_series,
                )
            # GPU 真实频率曲线
            if gpu_data:
                charts_html += self._html_chart_section(
                    "GPU 真实频率曲线 (MHz)",
                    x_data=times, x_label="采样秒数", y_unit="MHz",
                    extra_chips=["实际运行频率", "受 SElinux 限制时可能为空"],
                    series_list=[
                        {"name": "GPU 频率(MHz)", "data": [round(v, 0) for v in gpu_data],
                         "color": "#00838F", "width": 2.4, "areaStyle": True},
                    ],
                )
            # CPU 实时温度曲线
            if self._hw_history_temp:
                charts_html += self._html_chart_section(
                    "CPU 实时温度曲线 (°C)",
                    x_data=times, x_label="采样秒数", y_unit="°C",
                    extra_chips=["CPU thermal_zone 最高温", ">60°C 标橙 >65°C 标红"],
                    series_list=[
                        {"name": "CPU 温度(°C)", "data": [round(v, 1) for v in self._hw_history_temp],
                         "color": "#ea580c", "width": 2.4, "areaStyle": True},
                    ],
                )

            # 数据表
            headers = ["时间(秒)"] + cpu_labels
            if gpu_data:
                headers.append("GPU 频率(MHz)")
            if self._hw_history_temp:
                headers.append("CPU 温度(°C)")
            rows = []
            for i, t in enumerate(self._hw_history_times):
                row = [f"{t:.1f}"]
                for label in cpu_labels:
                    vals = self._hw_history_cpu[label]
                    row.append(f"{vals[i]:.0f}" if i < len(vals) else "-")
                if gpu_data:
                    row.append(f"{gpu_data[i]:.0f}" if i < len(gpu_data) else "-")
                if self._hw_history_temp:
                    row.append(f"{self._hw_history_temp[i]:.1f}" if i < len(self._hw_history_temp) else "-")
                rows.append(row)
            data_tbl = self._html_data_table(headers, rows)

            # 内嵌曲线图截图（保证任何时候都有曲线图）
            plots_html = ""
            try:
                pm = self._render_hw_plots_pixmap("android")
                b64 = self._pixmap_to_base64(pm) if pm is not None else ""
                if b64:
                    plots_html = f"""
                    <section class="charts-images-section" style="margin-top:32px;">
                      <h2 style="font-size:18px;margin-bottom:12px;color:#0f172a;border-left:4px solid #7C3AED;padding-left:10px;">📊 曲线图快照</h2>
                      <div style="background:white;border-radius:12px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
                        <img src="data:image/png;base64,{b64}" style="width:100%;height:auto;display:block;border-radius:8px;" />
                      </div>
                    </section>"""
            except Exception as _ie:
                log_exception(_ie, "安卓CPU/GPU HTML 内嵌曲线图失败")

            body_all = info + cards + charts_html + plots_html + data_tbl
            rtitle = self._tr("report_title_hw")
            rsub = f"{device_id} · {n} " + self._tr("lbl_samples")
            saved = self._preview_html(self._tr("preview_android_hw_html"), body_all, default_name, rtitle, rsub)
            if saved:
                self.hw_status_label.setText(self._tr("stat_html_exported"))
                self.hw_status_label.setStyleSheet("color: #4CAF50; font-size: 13px;")
                QMessageBox.information(self, self._tr("msg_export_success"), self._tr("msg_export_success_hw_html").format(path=saved))
        except Exception as e:
            log_exception(e, "HW HTML 导出失败")
            self.hw_status_label.setText(self._tr("stat_export_failed"))
            self.hw_status_label.setStyleSheet("color: #F44336; font-size: 13px;")
            QMessageBox.critical(self, self._tr("msg_export_failed"), str(e))

    def _export_ios_fps_html(self):
        """导出 iOS 帧率 HTML 报告（含 ECharts 趋势图 + 导出预览）"""
        if not self._ios_history_stats:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_no_fps_data"))
            return
        desktop = os.path.expanduser("~/Desktop")
        default_name = os.path.join(desktop, f"ios_fps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        try:
            udid = self._get_ios_selected_device() or "未知"
            app_name = self.ios_app_combo.currentText().strip() or "未知应用"
            summary = self.ios_analyzer.get_summary()

            info = self._html_info_section([
                ("设备 UDID", udid),
                ("测试应用", app_name),
                ("导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ])

            cards = self._html_summary_cards([
                ("平均 FPS", summary.get("avg_fps", "-"), self._fps_color(summary.get("avg_fps", 0))),
                ("最低 FPS", summary.get("min_fps", "-"), self._fps_color(summary.get("min_fps", 0))),
                ("最高 FPS", summary.get("max_fps", "-"), ""),
                ("1% Low", summary.get("low_1_fps", "-"), self._fps_color(summary.get("low_1_fps", 0))),
                ("0.1% Low", summary.get("low_01_fps", "-"), self._fps_color(summary.get("low_01_fps", 0))),
                ("FPS 标准差", summary.get("std_fps", "-"), ""),
                ("卡顿率(%)", summary.get("jank_rate", "-"), ""),
            ])

            # ECharts 趋势图：瞬时 FPS + 平均 FPS
            times = [round(t, 2) for t in self._ios_history_times]
            fps_inst = [round(float(v), 1) for v in self._ios_history_fps]
            fps_avg = [round(float(v), 1) for v in self._ios_history_avg_fps]
            charts_html = self._html_chart_section(
                "iOS 帧率趋势（瞬时 / 平均）",
                x_data=times, x_label="采样秒数", y_unit="FPS",
                extra_chips=["iOS GraphKit 采集", "无平滑显示", "支持缩放平移"],
                series_list=[
                    {"name": "瞬时 FPS", "data": fps_inst, "color": "#1d4ed8", "width": 1.4},
                    {"name": "平均 FPS", "data": fps_avg, "color": "#16a34a", "areaStyle": True},
                ],
            )

            headers = ["时间(秒)", "瞬时FPS", "平均FPS"]
            rows = []
            for i in range(len(self._ios_history_times)):
                fps = self._ios_history_fps[i]
                cls = self._fps_color(fps)
                rows.append([
                    f"{self._ios_history_times[i]:.2f}",
                    f'<span class="{cls} stat-value">{fps:.1f}</span>',
                    f"{self._ios_history_avg_fps[i]:.1f}",
                ])
            data_tbl = self._html_data_table(headers, rows)

            # 内嵌曲线图截图（保证任何时候都有曲线图）
            plots_html = ""
            try:
                pm = self._render_fps_plots_pixmap("ios")
                b64 = self._pixmap_to_base64(pm) if pm is not None else ""
                if b64:
                    plots_html = f"""
                    <section class="charts-images-section" style="margin-top:32px;">
                      <h2 style="font-size:18px;margin-bottom:12px;color:#0f172a;border-left:4px solid #0288D1;padding-left:10px;">📊 曲线图快照</h2>
                      <div style="background:white;border-radius:12px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
                        <img src="data:image/png;base64,{b64}" style="width:100%;height:auto;display:block;border-radius:8px;" />
                      </div>
                    </section>"""
            except Exception as _ie:
                log_exception(_ie, "iOS 帧率 HTML 内嵌曲线图失败")

            body_all = info + cards + charts_html + plots_html + data_tbl
            rtitle = self._tr("report_title_ios_fps")
            rsub = f"{app_name} · {udid}"
            saved = self._preview_html(self._tr("preview_ios_fps_html"), body_all, default_name, rtitle, rsub)
            if saved:
                self._ios_log(f"✅ iOS 帧率 HTML 已导出: {saved}")
                QMessageBox.information(self, self._tr("msg_export_success"), self._tr("msg_export_success_html_report").format(path=saved))
        except Exception as e:
            log_exception(e, "iOS FPS HTML 导出失败")
            QMessageBox.critical(self, self._tr("msg_export_failed"), self._tr("msg_export_failed_html").format(err=e))

    def _export_ios_hw_html(self):
        """导出 iOS 硬件监测 HTML 报告（含 ECharts 趋势图 + 导出预览）"""
        if not self._ios_hw_history_times:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_no_hw_data"))
            return
        desktop = os.path.expanduser("~/Desktop")
        default_name = os.path.join(desktop, f"ios_hw_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        try:
            udid = self._get_ios_hw_selected_device() or "未知"
            n = len(self._ios_hw_history_times)

            def _stats(vals):
                if not vals:
                    return 0, 0, 0, 0
                return (round(sum(vals) / len(vals), 2), round(max(vals), 2),
                        round(min(vals), 2), round(statistics_stdev(vals), 2))

            cpu_avg, cpu_max, _, _ = _stats(self._ios_hw_history_cpu_usage)
            gpu_avg, gpu_max, _, _ = _stats(self._ios_hw_history_gpu)
            mem_avg, mem_max, _, _ = _stats(self._ios_hw_history_mem)

            info = self._html_info_section([
                ("设备 UDID", udid),
                ("采样数", str(n)),
                ("导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ])

            cards = self._html_summary_cards([
                ("CPU 均值(%)", cpu_avg, ""),
                ("CPU 峰值(%)", cpu_max, "bad" if cpu_max > 90 else ""),
                ("GPU 均值(%)", gpu_avg, ""),
                ("GPU 峰值(%)", gpu_max, "bad" if gpu_max > 90 else ""),
                ("内存 均值(%)", mem_avg, ""),
                ("内存 峰值(%)", mem_max, ""),
            ])

            # ECharts 趋势图：CPU/GPU/内存
            times = [round(t, 2) for t in self._ios_hw_history_times]
            charts_html = ""
            charts_html += self._html_chart_section(
                "资源占用趋势（CPU / GPU / 内存）",
                x_data=times, x_label="采样秒数", y_unit="%",
                extra_chips=["iOS 性能控制接口", "每 1 秒采样", "可拖拽缩放"],
                series_list=[
                    {"name": "CPU使用率(%)", "data": [round(v, 1) for v in self._ios_hw_history_cpu_usage],
                     "color": "#dc2626", "areaStyle": True},
                    {"name": "GPU利用率(%)", "data": [round(v, 1) for v in self._ios_hw_history_gpu],
                     "color": "#0891b2"},
                    {"name": "内存使用率(%)", "data": [round(v, 1) for v in self._ios_hw_history_mem],
                     "color": "#7c3aed"},
                ],
            )

            headers = ["时间(秒)", "CPU使用率(%)", "GPU利用率(%)", "内存使用率(%)"]
            rows = []
            for i in range(n):
                rows.append([
                    f"{self._ios_hw_history_times[i]:.2f}",
                    f"{self._ios_hw_history_cpu_usage[i]:.1f}",
                    f"{self._ios_hw_history_gpu[i]:.1f}",
                    f"{self._ios_hw_history_mem[i]:.1f}",
                ])
            data_tbl = self._html_data_table(headers, rows)

            # 内嵌曲线图截图（保证任何时候都有曲线图）
            plots_html = ""
            try:
                pm = self._render_hw_plots_pixmap("ios")
                b64 = self._pixmap_to_base64(pm) if pm is not None else ""
                if b64:
                    plots_html = f"""
                    <section class="charts-images-section" style="margin-top:32px;">
                      <h2 style="font-size:18px;margin-bottom:12px;color:#0f172a;border-left:4px solid #7C3AED;padding-left:10px;">📊 曲线图快照</h2>
                      <div style="background:white;border-radius:12px;padding:16px;box-shadow:0 2px 12px rgba(0,0,0,0.06);">
                        <img src="data:image/png;base64,{b64}" style="width:100%;height:auto;display:block;border-radius:8px;" />
                      </div>
                    </section>"""
            except Exception as _ie:
                log_exception(_ie, "iOS 硬件 HTML 内嵌曲线图失败")

            body_all = info + cards + charts_html + plots_html + data_tbl
            rtitle = self._tr("report_title_ios_hw")
            rsub = f"{udid} · {n} " + self._tr("lbl_samples")
            saved = self._preview_html(self._tr("preview_ios_hw_html"), body_all, default_name, rtitle, rsub)
            if saved:
                self._ios_log(f"✅ iOS 硬件 HTML 已导出: {saved}")
                QMessageBox.information(self, self._tr("msg_export_success"), self._tr("msg_export_success_html_report").format(path=saved))
        except Exception as e:
            log_exception(e, "iOS HW HTML 导出失败")
            QMessageBox.critical(self, self._tr("msg_export_failed"), self._tr("msg_export_failed_html").format(err=e))

    def _export_csv(self):
        """导出CSV报告（含预览功能）"""
        if not self.history_stats:
            QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_no_export_data"))
            return

        # 使用桌面作为默认目录，避免在 .app 包内（只读）导致 errno 30
        desktop = os.path.expanduser("~/Desktop")
        default_name = os.path.join(desktop, f"fps_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        try:
            # 先构造 csv_rows
            csv_rows: list[list] = []
            # 1. 测试基本信息
            csv_rows.append(["=== 安卓帧率测试报告 ==="])
            csv_rows.append(["导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            device_id = self.device_combo.currentData() or "未知"
            csv_rows.append(["设备ID", device_id])
            csv_rows.append(["测试应用", self.package_combo.currentText()])
            csv_rows.append(["屏幕刷新率", f"{self.refresh_rate_combo.currentData()}Hz"])
            csv_rows.append([])

            # 2. 汇总统计
            summary = self.analyzer.get_summary()
            csv_rows.append(["=== 测试汇总 ==="])
            csv_rows.append(["指标", "数值"])
            summary_cn = {
                "duration_sec": "测试时长(秒)",
                "avg_fps": "平均FPS",
                "min_fps": "最低FPS",
                "max_fps": "最高FPS",
                "low_1_fps": "1% Low FPS",
                "low_01_fps": "0.1% Low FPS",
                "std_fps": "FPS标准差",
                "jank_count": "卡顿帧数",
                "jank_rate": "卡顿率(%)",
                "p95_frame_ms": "P95帧时间(ms)",
                "p99_frame_ms": "P99帧时间(ms)",
                "fps_drop_count": "FPS跌落次数",
            }
            for k, cn in summary_cn.items():
                csv_rows.append([cn, summary.get(k, "-")])
            csv_rows.append([])

            # 3. 逐秒明细
            csv_rows.append(["=== 逐秒采样明细 ==="])
            csv_rows.append([
                "时间(秒)", "瞬时FPS", "平均FPS", "最低FPS", "最高FPS",
                "1%Low", "0.1%Low", "FPS标准差", "卡顿帧数", "卡顿率(%)",
                "P95帧时(ms)", "P99帧时(ms)"
            ])
            for s in self.history_stats:
                csv_rows.append([
                    f"{s.timestamp:.1f}", s.fps, s.avg_fps, s.min_fps, s.max_fps,
                    s.low_1_fps, s.low_01_fps,
                    s.std_fps, s.jank_count, s.jank_rate,
                    s.percentile_95, s.percentile_99
                ])

            saved = self._preview_csv(self._tr("preview_android_fps_csv"), csv_rows, default_name)
            if saved:
                # CSV 导出附带曲线图 JPG
                try:
                    pm = self._render_fps_plots_pixmap("android")
                    if pm is not None:
                        img_path = os.path.splitext(saved)[0] + "_charts.jpg"
                        if pm.save(img_path, "JPG", 92):
                            self._log(f"📤 曲线图已导出: {img_path}")
                except Exception as _ie:
                    from app_logger import log_exception
                    log_exception(_ie, "安卓帧率CSV附带曲线图导出失败")
                self._log(f"📤 报告已导出: {saved}")
                QMessageBox.information(self, self._tr("msg_success"), self._tr("msg_export_success_report").format(path=saved))
        except Exception as e:
            self._log(f"❌ 导出失败: {e}")
            QMessageBox.critical(self, self._tr("msg_error"),self._tr("msg_export_failed_simple").format(err=e))

    # ==================== CPU/GPU 监测页面控制 ====================

    def _get_hw_selected_device_id(self) -> Optional[str]:
        """获取监测页面选中的设备ID"""
        idx = self.hw_device_combo.currentIndex()
        if idx < 0:
            return None
        data = self.hw_device_combo.itemData(idx)
        return data if data else None

    def _start_hw_monitor(self):
        """开始硬件监测"""
        try:
            self._start_hw_monitor_inner()
        except Exception as e:
            log_exception(e, "Android CPU/GPU 监测启动异常")
            try:
                self.hw_start_btn.setEnabled(True)
                self.hw_stop_btn.setEnabled(False)
                self.hw_status_label.setText(self._tr("stat_start_failed"))
                self.hw_status_label.setStyleSheet("color: #F44336; font-size: 13px;")
            except Exception:
                pass
            self._log(f"❌ CPU/GPU 监测启动失败: {e}")
            QMessageBox.critical(self, self._tr("msg_error"),self._tr("msg_start_hw_failed").format(err=e))

    def _start_hw_monitor_inner(self):
        device_id = self._get_hw_selected_device_id()
        if not device_id:
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_select_device_monitor"))
            return

        # 采集间隔（读取硬件监测页下拉框，默认 1.0s）
        poll_interval = 1.0
        if hasattr(self, "hw_interval_combo") and self.hw_interval_combo.currentData():
            poll_interval = float(self.hw_interval_combo.currentData())

        # 清空历史
        self._hw_history_times.clear()
        self._hw_history_cpu.clear()
        self._hw_history_gpu.clear()
        self._hw_history_cpu_usage.clear()
        self._hw_history_mem_usage.clear()
        self._hw_history_temp.clear()
        self._hw_history_power.clear()
        self._hw_plot_start_time = time.time()
        self._hw_monitor_start_dt = datetime.now()
        for curve in self._hw_curves.values():
            curve.setData([], [])
        self._hw_curves.clear()
        if self._hw_temp_curve is not None:
            self._hw_temp_curve.setData([], [])
        self._hw_temp_curve = None
        if self._hw_power_curve is not None:
            self._hw_power_curve.setData([], [])
        self._hw_power_curve = None
        for curve in self._hw_usage_curves.values():
            curve.setData([], [])
        self._hw_usage_curves.clear()

        # 清空旧的集群条
        for bar, name_lbl, val_lbl in self._hw_cpu_cluster_bars:
            row_widget = bar.parentWidget()
            if row_widget is not None:
                row_widget.setParent(None)
                row_widget.deleteLater()
        self._hw_cpu_cluster_bars.clear()

        # 清理旧线程（避免信号累积与内存泄漏）
        if self.hw_monitor_thread:
            try:
                if self.hw_monitor_thread.isRunning():
                    self.hw_monitor_thread.stop()
                    self.hw_monitor_thread.wait(2000)
                self.hw_monitor_thread.disconnect()
                self.hw_monitor_thread.deleteLater()
            except Exception:
                pass
        self.hw_monitor_thread = HWMonitorThread(self.adb_client, device_id, poll_interval=poll_interval)
        self.hw_monitor_thread.hw_data_ready.connect(self._on_hw_monitor_data)
        self.hw_monitor_thread.error_occurred.connect(self._on_hw_monitor_error)
        self.hw_monitor_thread.start()

        # 创建数据库会话
        try:
            dev_pk = self._db_get_or_create_device(device_id, "android")
            self._db_hw_session_id = self._db.create_session(
                device_id=dev_pk, platform="android", test_type="hw_monitor",
                app_package="", refresh_rate=0, poll_interval=poll_interval
            )
        except Exception as e:
            log_exception(e, "数据库: 创建硬件监测会话失败")

        self.hw_start_btn.setEnabled(False)
        self.hw_stop_btn.setEnabled(True)
        self.hw_status_label.setText(self._tr("stat_monitoring"))
        self.hw_status_label.setStyleSheet("color: #4CAF50; font-size: 13px; font-weight: bold;")

        # 联动启动帧率测试（避免递归调用）
        if not self._linking_start:
            self._linking_start = True
            try:
                if not (self.collector_thread and self.collector_thread.isRunning()):
                    package_name = self.package_combo.currentText().strip()
                    if package_name:
                        # 同步设备到帧率测试页的下拉框
                        for i in range(self.device_combo.count()):
                            if self.device_combo.itemData(i) == device_id:
                                self.device_combo.setCurrentIndex(i)
                                break
                        self._start_test()
                        self._log("🔗 已联动启动帧率测试")
                    else:
                        self._log("ℹ️ 未选择应用包名，跳过帧率测试联动启动")
            finally:
                self._linking_start = False

    def _stop_hw_monitor(self):
        """停止硬件监测（联动停止帧率测试）"""
        if self.hw_monitor_thread and self.hw_monitor_thread.isRunning():
            self.hw_monitor_thread.stop()
            self.hw_monitor_thread.wait(2000)
        self.hw_start_btn.setEnabled(True)
        self.hw_stop_btn.setEnabled(False)
        self.hw_status_label.setText(self._tr("stat_stopped"))
        self.hw_status_label.setStyleSheet(f"color: {self._fg_muted()}; font-size: 13px;")

        # 保存到 CSV 历史记录
        if self._hw_history_times and len(self._hw_history_times) > 0:
            self._history_save_hw_report()

        # 数据库：结束硬件监测会话
        try:
            if self._db_hw_session_id:
                duration = (datetime.now() - self._hw_monitor_start_dt).total_seconds() if self._hw_monitor_start_dt else 0
                self._db.finish_session(self._db_hw_session_id, duration)
                self._db_hw_session_id = None
        except Exception as e:
            log_exception(e, "数据库: 结束硬件监测会话失败")

        # 联动停止帧率测试
        if not self._linking_stop:
            self._linking_stop = True
            try:
                if self.collector_thread and self.collector_thread.isRunning():
                    self._stop_test()
                    self._log("🔗 已联动停止帧率测试")
            finally:
                self._linking_stop = False

    def _clear_hw_monitor_data(self):
        """清空监测页面的历史数据和曲线"""
        # 监测进行中禁止清空
        if self.hw_monitor_thread and self.hw_monitor_thread.isRunning():
            QMessageBox.warning(self, self._tr("msg_no_data"), self._tr("msg_monitor_running"))
            return

        # 无数据时直接静默重置，避免无意义弹窗
        if not self._hw_history_times:
            self._hw_plot_start_time = time.time()
            return

        # 确认对话框（Yes/No），默认聚焦 No 防止误操作
        reply = QMessageBox.question(
            self, self._tr("msg_confirm_clear"),
            self._tr("msg_confirm_clear_body"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # 清空历史
        self._hw_history_times.clear()
        self._hw_history_cpu.clear()
        self._hw_history_gpu.clear()
        self._hw_history_cpu_usage.clear()
        self._hw_history_mem_usage.clear()
        self._hw_history_temp.clear()
        self._hw_history_power.clear()
        self._hw_plot_start_time = time.time()

        # 清空曲线
        for curve in self._hw_curves.values():
            curve.setData([], [])
        self._hw_curves.clear()
        if self._hw_temp_curve is not None:
            self._hw_temp_curve.setData([], [])
        self._hw_temp_curve = None
        if self._hw_power_curve is not None:
            self._hw_power_curve.setData([], [])
        self._hw_power_curve = None
        for curve in self._hw_usage_curves.values():
            curve.setData([], [])
        self._hw_usage_curves.clear()

        # 重置数值显示
        self.prime_freq_label.setText("-- MHz")
        self.prime_max_label.setText(self._tr("stat_max_na"))
        self.prime_bar.setValue(0)
        self.prime_bar.setFormat("0%")
        self.prime_cores_label.setText(self._tr("stat_cores_na"))

        for bar, name_lbl, val_lbl in self._hw_cpu_cluster_bars:
            bar.setValue(0)
            bar.setFormat("--")
            name_lbl.setText("--")
            val_lbl.setText("--")

        self.hw_cpu_usage_bar.setValue(0)
        self.hw_cpu_usage_bar.setFormat("0.0%")
        self.hw_cpu_temp_label.setText("-- °C")
        self.hw_cpu_temp_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #4CAF50;")

        self.hw_power_label.setText("-- mW")
        self.hw_power_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #7C3AED; font-family: 'Menlo', monospace;")
        self.hw_voltage_label.setText("-- mV")
        self.hw_current_label.setText("-- mA")
        self.hw_capacity_label.setText("-- %")
        self.hw_bat_temp_label.setText("-- °C")
        self.hw_battery_status_label.setText("")

        self.gpu_freq_label.setText("-- MHz")
        self.gpu_max_label.setText(self._tr("stat_max_na"))
        self.gpu_freq_bar.setValue(0)
        self.gpu_freq_bar.setFormat("0%")
        self.gpu_freq_note.setText("")

        for lbl in self._hw_gpu_load_labels.values():
            lbl.setText("-- ms")

        self.hw_mem_bar.setValue(0)
        self.hw_mem_bar.setFormat("0.0%")
        self.hw_mem_detail_label.setText("--")
        self.hw_gpu_mem_label.setText(self._tr("stat_gpu_mem_na"))

        self.hw_status_label.setText(self._tr("stat_cleared"))
        self.hw_status_label.setStyleSheet("color: #FF9800; font-size: 13px;")
        self._log("🗑 CPU/GPU 监测数据已清空")

    def _export_hw_report(self):
        """导出 CPU/GPU 监测报告 (CSV) - 含预览功能"""
        if not self._hw_history_times:
            QMessageBox.information(self, self._tr("msg_no_data"), self._tr("msg_no_hw_export_data"))
            return

        desktop = os.path.expanduser("~/Desktop")
        default_name = os.path.join(desktop, f"hw_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        try:
            times = self._hw_history_times
            cpu_labels = list(self._hw_history_cpu.keys())
            gpu_data = self._hw_history_gpu
            n = len(times)

            csv_rows: list[list] = []
            # 1. 基本信息
            csv_rows.append(["=== CPU/GPU 监测报告 ==="])
            csv_rows.append(["导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            device_id = self.hw_device_combo.currentData() or "未知"
            csv_rows.append(["监测设备", device_id])
            csv_rows.append(["采样点数", n])
            csv_rows.append([])

            # 2. 频率汇总统计
            csv_rows.append(["=== 频率汇总统计 (MHz) ==="])
            csv_rows.append(["指标", "平均", "最大", "最小", "标准差"])
            for label in cpu_labels:
                vals = self._hw_history_cpu[label]
                if vals:
                    avg = sum(vals) / len(vals)
                    mx = max(vals)
                    mn = min(vals)
                    std = (sum((v - avg) ** 2 for v in vals) / len(vals)) ** 0.5
                    csv_rows.append([label, f"{avg:.1f}", f"{mx:.0f}", f"{mn:.0f}", f"{std:.1f}"])
            if gpu_data:
                avg = sum(gpu_data) / len(gpu_data)
                mx = max(gpu_data)
                mn = min(gpu_data)
                std = (sum((v - avg) ** 2 for v in gpu_data) / len(gpu_data)) ** 0.5
                csv_rows.append(["GPU 频率", f"{avg:.1f}", f"{mx:.0f}", f"{mn:.0f}", f"{std:.1f}"])
            csv_rows.append([])

            # 3. 时间序列数据
            header = ["时间(秒)"] + cpu_labels
            if gpu_data:
                header.append("GPU 频率(MHz)")
            if self._hw_history_temp:
                header.append("CPU 温度(°C)")
            csv_rows.append(["=== 时间序列数据 ==="])
            csv_rows.append(header)
            for i, t in enumerate(times):
                row = [f"{t:.1f}"]
                for label in cpu_labels:
                    vals = self._hw_history_cpu[label]
                    row.append(f"{vals[i]:.0f}" if i < len(vals) else "")
                if gpu_data:
                    row.append(f"{gpu_data[i]:.0f}" if i < len(gpu_data) else "")
                if self._hw_history_temp:
                    row.append(f"{self._hw_history_temp[i]:.1f}" if i < len(self._hw_history_temp) else "")
                csv_rows.append(row)

            saved = self._preview_csv(self._tr("preview_android_hw_csv"), csv_rows, default_name)
            if saved:
                # CSV 导出附带曲线图 JPG
                try:
                    pm = self._render_hw_plots_pixmap("android")
                    if pm is not None:
                        img_path = os.path.splitext(saved)[0] + "_charts.jpg"
                        if pm.save(img_path, "JPG", 92):
                            self._log(f"📤 曲线图已导出: {img_path}")
                except Exception as _ie:
                    from app_logger import log_exception
                    log_exception(_ie, "安卓CPU/GPU CSV附带曲线图导出失败")
                self.hw_status_label.setText(self._tr("stat_report_exported"))
                self.hw_status_label.setStyleSheet("color: #4CAF50; font-size: 13px;")
                QMessageBox.information(self, self._tr("msg_export_success"), self._tr("msg_export_success_monitor").format(path=saved))
        except Exception as e:
            QMessageBox.critical(self, self._tr("msg_export_failed"), str(e))
            self.hw_status_label.setText(self._tr("stat_export_failed"))
            self.hw_status_label.setStyleSheet("color: #F44336; font-size: 13px;")

    def _on_hw_monitor_error(self, msg: str):
        """硬件监测错误"""
        self.hw_status_label.setText(self._tr("fmt_status_error").format(msg=msg))
        self.hw_status_label.setStyleSheet("color: #F44336; font-size: 13px;")
        self._log(f"⚠️ {msg}")

    def _on_hw_monitor_data(self, data: dict):
        """收到硬件监测数据，更新监测页面"""
        cpu_freqs = data.get("cpu_freqs", [])
        gpu_freq = data.get("gpu_freq", {})
        gpu_info = data.get("gpu_info", {})
        cpu_usage = data.get("cpu_usage", 0.0)
        cpu_temp = data.get("cpu_temp", 0.0)
        mem_info = data.get("mem_info", {})
        ts = data.get("timestamp", time.time())
        elapsed = ts - self._hw_plot_start_time if self._hw_plot_start_time > 0 else 0

        # --- CPU 超大核 ---
        prime = None
        for f in cpu_freqs:
            if f.get("is_prime"):
                prime = f
                break
        if prime:
            cur = prime["cur_mhz"]
            mx = prime["max_mhz"]
            pct = int(cur / mx * 100) if mx > 0 else 0
            self.prime_freq_label.setText(f"{cur:.0f} MHz")
            self.prime_max_label.setText(self._tr("fmt_max_mhz").format(val=f"{mx:.0f}"))
            self.prime_bar.setValue(pct)
            self.prime_bar.setFormat(f"{cur:.0f} / {mx:.0f} MHz ({pct}%)")
            prime_color = "#D32F2F" if pct > 80 else ("#F57C00" if pct > 50 else "#7B1FA2")
            self.prime_bar.setStyleSheet(f"""
                QProgressBar {{ border: 1px solid rgba(100,116,139,80); border-radius: 6px; text-align: center;
                               font-size: 13px; font-weight: bold; background-color: rgba(226,232,240,200); }}
                QProgressBar::chunk {{ background-color: {prime_color}; border-radius: 5px; }}
            """)
            cores = prime.get("related_cpus", "")
            self.prime_cores_label.setText(self._tr("fmt_cores_cpu").format(cores=cores) if cores else self._tr("stat_cores_na"))

        # --- CPU 全部集群频率（动态创建条）---
        for i, freq_info in enumerate(cpu_freqs):
            while i >= len(self._hw_cpu_cluster_bars):
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 2, 0, 2)
                name_lbl = QLabel("--")
                name_lbl.setMinimumWidth(100)
                name_lbl.setStyleSheet(f"font-size: 12px; color: {self._fg()};")
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setFixedHeight(16)
                bar.setTextVisible(True)
                _bar_bg = self._bg_light()
                bar.setStyleSheet(f"""
                    QProgressBar {{ border: 1px solid rgba(100,116,139,80); border-radius: 3px; text-align: center;
                                   font-size: 11px; background-color: rgba(226,232,240,200); }}
                    QProgressBar::chunk {{ background-color: #1976D2; border-radius: 2px; }}
                """)
                val_lbl = QLabel("--")
                val_lbl.setMinimumWidth(90)
                val_lbl.setStyleSheet(f"font-size: 11px; color: {self._fg_muted()};")
                row_layout.addWidget(name_lbl)
                row_layout.addWidget(bar, 1)
                row_layout.addWidget(val_lbl)
                self._hw_cpu_clusters_layout.addWidget(row_widget)
                self._hw_cpu_cluster_bars.append((bar, name_lbl, val_lbl))
            if i < len(self._hw_cpu_cluster_bars):
                bar, name_lbl, val_lbl = self._hw_cpu_cluster_bars[i]
                cur = freq_info["cur_mhz"]
                mx = freq_info["max_mhz"]
                pct = int(cur / mx * 100) if mx > 0 else 0
                bar.setValue(pct)
                bar.setFormat(f"{cur:.0f}/{mx:.0f} MHz")
                tag = " (超大核)" if freq_info.get("is_prime") else ""
                cores = freq_info.get("related_cpus", "")
                name_lbl.setText(f"{freq_info['cluster']}{tag}\nCPU {cores}" if cores else f"{freq_info['cluster']}{tag}")
                val_lbl.setText(f"{cur:.0f} / {mx:.0f} MHz")
                chunk_color = "#D32F2F" if pct > 80 else ("#F57C00" if pct > 50 else "#1976D2")
                bar.setStyleSheet(f"""
                    QProgressBar {{ border: 1px solid rgba(100,116,139,80); border-radius: 3px; text-align: center;
                                   font-size: 11px; background-color: rgba(226,232,240,200); }}
                    QProgressBar::chunk {{ background-color: {chunk_color}; border-radius: 2px; }}
                """)

        # --- CPU 利用率 ---
        self.hw_cpu_usage_bar.setValue(int(cpu_usage))
        self.hw_cpu_usage_bar.setFormat(f"{cpu_usage:.1f}%")
        usage_color = "#D32F2F" if cpu_usage > 80 else ("#F57C00" if cpu_usage > 50 else "#388E3C")
        self.hw_cpu_usage_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid rgba(100,116,139,80); border-radius: 4px; text-align: center;
                           font-size: 12px; background-color: rgba(226,232,240,200); }}
            QProgressBar::chunk {{ background-color: {usage_color}; border-radius: 3px; }}
        """)

        # --- CPU 温度 ---
        if cpu_temp > 0:
            temp_color = "#F44336" if cpu_temp >= 60 else ("#FF9800" if cpu_temp >= 45 else "#4CAF50")
            self.hw_cpu_temp_label.setText(f"{cpu_temp:.0f} °C")
            self.hw_cpu_temp_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {temp_color};")

        # --- 电池 / 功率 ---
        battery_power = data.get("battery_power", {}) or {}
        power_mw = float(battery_power.get("power_mw", 0.0) or 0.0)
        voltage_mv = int(battery_power.get("voltage_mv", 0) or 0)
        current_ua = int(battery_power.get("current_ua", 0) or 0)
        current_ma = current_ua / 1000.0 if current_ua != 0 else 0.0
        capacity_pct = int(battery_power.get("capacity_pct", 0) or 0)
        bat_temp = float(battery_power.get("temp", 0.0) or 0.0)
        bat_status = battery_power.get("status", "unknown") or "unknown"

        if power_mw > 0:
            # 颜色：超过 5W 红，3W 橙，其余紫
            pcolor = "#dc2626" if power_mw >= 5000 else ("#f97316" if power_mw >= 3000 else "#7C3AED")
            self.hw_power_label.setText(f"{power_mw:.0f} mW")
            self.hw_power_label.setStyleSheet(f"font-size: 26px; font-weight: bold; color: {pcolor}; font-family: 'Menlo', monospace;")
        else:
            self.hw_power_label.setText("-- mW")
            self.hw_power_label.setStyleSheet("font-size: 26px; font-weight: bold; color: #7C3AED; font-family: 'Menlo', monospace;")

        if voltage_mv > 0:
            self.hw_voltage_label.setText(f"{voltage_mv} mV")
        else:
            self.hw_voltage_label.setText("-- mV")
        if current_ua != 0:
            self.hw_current_label.setText(f"{current_ma:+.1f} mA")
        else:
            self.hw_current_label.setText("-- mA")
        if capacity_pct > 0:
            self.hw_capacity_label.setText(f"{capacity_pct} %")
        else:
            self.hw_capacity_label.setText("-- %")
        if bat_temp > 0:
            self.hw_bat_temp_label.setText(f"{bat_temp:.1f} °C")
        else:
            self.hw_bat_temp_label.setText("-- °C")

        status_map = {
            "discharging": self._tr("bat_discharging"),
            "charging":    self._tr("bat_charging"),
            "not_charging":self._tr("bat_not_charging"),
            "full":        self._tr("bat_full"),
            "unknown":     "",
        }
        self.hw_battery_status_label.setText(status_map.get(bat_status, ""))

        # --- GPU 频率 ---
        if gpu_freq.get("accessible") and gpu_freq.get("cur_mhz", 0) > 0:
            cur = gpu_freq["cur_mhz"]
            mx = gpu_freq.get("max_mhz", 0)
            if mx > 0 and cur > 0:
                ratio = cur / mx
                # 合理性钳制：ratio 超过 1.1 视为读错，不展示进度条 100% 夹取
                if ratio > 1.1:
                    accessible = False
                else:
                    pct = max(0, min(100, int(ratio * 100)))
                    self.gpu_freq_label.setText(f"{cur:.0f} MHz")
                    self.gpu_max_label.setText(self._tr("fmt_max_mhz").format(val=f"{mx:.0f}"))
                    self.gpu_freq_bar.setValue(pct)
                    self.gpu_freq_bar.setFormat(f"{cur:.0f} / {mx:.0f} MHz ({pct}%)")
                    avail = gpu_freq.get("available_mhz", [])
                    if avail:
                        self.gpu_freq_note.setText(self._tr("fmt_gpu_avail").format(avail=avail))
                    else:
                        self.gpu_freq_note.setText("")
                    accessible = True
            else:
                accessible = False
            if not accessible:
                self.gpu_freq_label.setText("-- MHz")
                self.gpu_max_label.setText(self._tr("stat_max_na"))
                self.gpu_freq_bar.setValue(0)
                self.gpu_freq_bar.setFormat("0%")
                self.gpu_freq_note.setText(self._tr("note_gpu_freq_selinux"))
        else:
            self.gpu_freq_label.setText("-- MHz")
            self.gpu_max_label.setText(self._tr("stat_max_na"))
            self.gpu_freq_bar.setValue(0)
            self.gpu_freq_bar.setFormat("0%")
            self.gpu_freq_note.setText(self._tr("note_gpu_freq_selinux"))

        # --- GPU 渲染负载 ---
        gpu_keys = {"gpu_p50": "gpu_p50_ms", "gpu_p90": "gpu_p90_ms",
                    "gpu_p95": "gpu_p95_ms", "gpu_p99": "gpu_p99_ms"}
        for ui_key, data_key in gpu_keys.items():
            val = gpu_info.get(data_key, 0.0)
            if ui_key in self._hw_gpu_load_labels:
                if val > 0:
                    self._hw_gpu_load_labels[ui_key].setText(f"{val:.1f} ms")
                else:
                    self._hw_gpu_load_labels[ui_key].setText("-- ms")

        # --- 内存 ---
        mem_pct = mem_info.get("used_pct", 0.0)
        total_mb = mem_info.get("total_mb", 0)
        avail_mb = mem_info.get("available_mb", 0)
        self.hw_mem_bar.setValue(int(mem_pct))
        self.hw_mem_bar.setFormat(f"{mem_pct:.1f}%")
        mem_color = "#D32F2F" if mem_pct > 85 else ("#F57C00" if mem_pct > 70 else "#00695C")
        self.hw_mem_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid rgba(100,116,139,80); border-radius: 4px; text-align: center;
                           font-size: 12px; background-color: rgba(226,232,240,200); }}
            QProgressBar::chunk {{ background-color: {mem_color}; border-radius: 3px; }}
        """)
        self.hw_mem_detail_label.setText(self._tr("fmt_mem_detail").format(total=total_mb, avail=avail_mb, pct=f"{mem_pct:.1f}"))
        gpu_mem = gpu_info.get("gpu_mem_total_mb", 0)
        if gpu_mem > 0:
            self.hw_gpu_mem_label.setText(self._tr("fmt_gpu_mem").format(val=gpu_mem))
        else:
            self.hw_gpu_mem_label.setText(self._tr("stat_gpu_mem_na"))

        # --- 实时频率曲线图 ---
        self._hw_history_times.append(elapsed)
        # 限制历史长度
        MAX_HIST = 120
        if len(self._hw_history_times) > MAX_HIST:
            self._hw_history_times.pop(0)

        # 高对比度曲线调色板：CPU 各集群 4 色 + GPU 品红（虚线），保证在灰底上不重叠不混淆
        cpu_colors = ["#38bdf8", "#c084fc", "#4ade80", "#facc15"]
        cpu_styles = [Qt.SolidLine, Qt.SolidLine, Qt.DashLine, Qt.DotLine]
        for i, freq_info in enumerate(cpu_freqs):
            label = f"CPU {freq_info['cluster']}"
            if label not in self._hw_history_cpu:
                self._hw_history_cpu[label] = []
            self._hw_history_cpu[label].append(freq_info["cur_mhz"])
            if len(self._hw_history_cpu[label]) > MAX_HIST:
                self._hw_history_cpu[label].pop(0)
            if label not in self._hw_curves:
                color = cpu_colors[i % len(cpu_colors)]
                ls = cpu_styles[i % len(cpu_styles)]
                self._hw_curves[label] = self.hw_plot.plot(
                    pen=mkPen(color, width=2.8, style=ls), name=label
                )
            self._hw_curves[label].setData(self._hw_history_times, self._hw_history_cpu[label])

        # GPU 频率曲线（品红虚线 + 粗，独特避免与 CPU 重叠）
        if gpu_freq.get("accessible") and gpu_freq.get("cur_mhz", 0) > 0:
            self._hw_history_gpu.append(gpu_freq["cur_mhz"])
            if len(self._hw_history_gpu) > MAX_HIST:
                self._hw_history_gpu.pop(0)
            if "GPU 频率" not in self._hw_curves:
                self._hw_curves["GPU 频率"] = self.hw_plot.plot(
                    pen=mkPen('#ec4899', width=3, style=Qt.DashLine), name=self._tr("legend_gpu_freq")
                )
            self._hw_curves["GPU 频率"].setData(self._hw_history_times, self._hw_history_gpu)

        # --- 温度曲线 ---（暖橙红粗线 + 面积感）
        if cpu_temp > 0:
            self._hw_history_temp.append(cpu_temp)
            if len(self._hw_history_temp) > MAX_HIST:
                self._hw_history_temp.pop(0)
            if self._hw_temp_curve is None:
                self._hw_temp_curve = self.hw_temp_plot.plot(
                    pen=mkPen('#f97316', width=3.2), name=self._tr("legend_cpu_temp")
                )
            self._hw_temp_curve.setData(self._hw_history_times, self._hw_history_temp)

        # --- CPU 使用率 / 内存使用率曲线 ---（红实线 CPU + 紫虚线内存，明显区分）
        cpu_usage_val = max(0.0, min(100.0, float(cpu_usage or 0.0)))
        self._hw_history_cpu_usage.append(cpu_usage_val)
        if len(self._hw_history_cpu_usage) > MAX_HIST:
            self._hw_history_cpu_usage.pop(0)
        if "CPU 使用率" not in self._hw_usage_curves:
            self._hw_usage_curves["CPU 使用率"] = self.hw_usage_plot.plot(
                pen=mkPen('#ef4444', width=3), name=self._tr("legend_cpu_usage")
            )
        self._hw_usage_curves["CPU 使用率"].setData(self._hw_history_times, self._hw_history_cpu_usage)

        mem_pct_val = max(0.0, min(100.0, float(mem_info.get("used_pct", 0.0) or 0.0)))
        self._hw_history_mem_usage.append(mem_pct_val)
        if len(self._hw_history_mem_usage) > MAX_HIST:
            self._hw_history_mem_usage.pop(0)
        if "内存使用率" not in self._hw_usage_curves:
            self._hw_usage_curves["内存使用率"] = self.hw_usage_plot.plot(
                pen=mkPen('#a78bfa', width=2.8, style=Qt.DashLine), name=self._tr("legend_mem_usage")
            )
        self._hw_usage_curves["内存使用率"].setData(self._hw_history_times, self._hw_history_mem_usage)

        # --- 设备功率曲线 ---
        power_mw_val = max(0.0, float(power_mw or 0.0))
        if power_mw_val > 0:
            self._hw_history_power.append(power_mw_val)
            if len(self._hw_history_power) > MAX_HIST:
                self._hw_history_power.pop(0)
            if self._hw_power_curve is None:
                self._hw_power_curve = self.hw_power_plot.plot(
                    pen=mkPen('#8b5cf6', width=3.2), name=self._tr("legend_power_mw")
                )
            self._hw_power_curve.setData(self._hw_history_times, self._hw_history_power)

        # 数据库：写入硬件监测采样
        try:
            if self._db_hw_session_id:
                hw_sample_data = {
                    "timestamp": elapsed,
                    "cpu_freqs": cpu_freqs,
                    "cpu_usage": cpu_usage,
                    "cpu_temp": cpu_temp,
                    "gpu_freq": gpu_freq.get("cur_mhz", 0) if gpu_freq.get("accessible") else 0,
                    "gpu_load_p50": gpu_info.get("p50", 0),
                    "gpu_load_p90": gpu_info.get("p90", 0),
                    "gpu_load_p95": gpu_info.get("p95", 0),
                    "gpu_load_p99": gpu_info.get("p99", 0),
                    "mem_total_mb": mem_info.get("total_mb", 0),
                    "mem_avail_mb": mem_info.get("available_mb", 0),
                    "mem_used_mb": mem_info.get("total_mb", 0) - mem_info.get("available_mb", 0),
                    "mem_pct": mem_info.get("used_pct", 0.0),
                    "gpu_mem": gpu_info.get("gpu_mem_total_mb", 0),
                    "battery_power_mw": power_mw_val,
                    "battery_voltage_mv": voltage_mv,
                    "battery_current_ua": current_ua,
                    "battery_capacity_pct": capacity_pct,
                    "battery_temp": bat_temp,
                    "battery_status": bat_status,
                }
                self._db.insert_hw_sample(self._db_hw_session_id, elapsed, hw_sample_data)
        except Exception as e:
            log_exception(e, "数据库: 写入硬件监测采样失败")

    # ==================== 数据库辅助方法 ====================
    def _db_get_or_create_device(self, device_serial: str, platform: str) -> int:
        """获取或创建设备记录，返回 device_id。有缓存时直接返回。"""
        cache_key = f"{platform}:{device_serial}"
        if cache_key in self._db_device_ids:
            return self._db_device_ids[cache_key]
        # 尝试获取设备信息
        info = {}
        try:
            if platform == "android":
                info = self.adb_client.get_device_info(device_serial)
            else:
                info = {}
        except Exception:
            info = {}
        dev_pk = self._db.get_or_create_device(device_serial, platform, info)
        if dev_pk:
            self._db_device_ids[cache_key] = dev_pk
        return dev_pk

    # ==================== CSV 历史记录 (Tab 3) ====================

    def _history_save_fps_report(self, summary: dict):
        """保存帧率测试快照到最近5次历史"""
        start_dt = self._fps_test_start_dt or datetime.now()
        end_dt = datetime.now()
        duration_sec = int((end_dt - start_dt).total_seconds())
        device_id = self.device_combo.currentData() or "未知"
        package = self.package_combo.currentText() or "未知"
        # 深拷贝列表
        times_snapshot = list(self.history_times)
        fps_snapshot = list(self.history_fps)
        avg_fps_snapshot = list(self.history_avg_fps)
        stats_snapshot = []
        for s in self.history_stats:
            stats_snapshot.append({
                "fps": s.fps, "avg_fps": s.avg_fps, "min_fps": s.min_fps, "max_fps": s.max_fps,
                "std_fps": s.std_fps, "jank_count": s.jank_count, "total_frames": s.total_frames,
                "jank_rate": s.jank_rate, "percentile_95": s.percentile_95, "percentile_99": s.percentile_99,
                "timestamp": s.timestamp
            })

        report = {
            "id": f"fps_{int(start_dt.timestamp())}",
            "type": "fps",
            "start_time": start_dt,
            "end_time": end_dt,
            "duration_sec": duration_sec,
            "device_id": device_id,
            "package": package,
            "summary": dict(summary),
            "times": times_snapshot,
            "fps": fps_snapshot,
            "avg_fps": avg_fps_snapshot,
            "stats": stats_snapshot,
        }
        self._fps_reports.append(report)
        self._history_refresh_lists()

    def _history_save_hw_report(self):
        """保存 CPU/GPU 监测快照到最近5次历史"""
        start_dt = self._hw_monitor_start_dt or datetime.now()
        end_dt = datetime.now()
        duration_sec = int((end_dt - start_dt).total_seconds())
        device_id = self.hw_device_combo.currentData() or "未知"

        times_snapshot = list(self._hw_history_times)
        # 深拷贝 cpu 字典
        cpu_snapshot = {k: list(v) for k, v in self._hw_history_cpu.items()}
        gpu_snapshot = list(self._hw_history_gpu)

        # 计算频率汇总
        def _stat(arr):
            if not arr:
                return {"avg": 0, "max": 0, "min": 0, "std": 0}
            a = sum(arr) / len(arr)
            mx = max(arr)
            mn = min(arr)
            sd = (sum((x - a) ** 2 for x in arr) / len(arr)) ** 0.5
            return {"avg": a, "max": mx, "min": mn, "std": sd}

        freq_summary = {}
        for label, arr in cpu_snapshot.items():
            freq_summary[label] = _stat(arr)
        if gpu_snapshot:
            freq_summary["GPU 频率"] = _stat(gpu_snapshot)

        report = {
            "id": f"hw_{int(start_dt.timestamp())}",
            "type": "hw",
            "start_time": start_dt,
            "end_time": end_dt,
            "duration_sec": duration_sec,
            "device_id": device_id,
            "freq_summary": freq_summary,
            "times": times_snapshot,
            "cpu": cpu_snapshot,
            "gpu": gpu_snapshot,
            "temp": list(self._hw_history_temp),
            "cpu_usage": list(self._hw_history_cpu_usage),
            "mem_usage": list(self._hw_history_mem_usage),
        }
        self._hw_reports.append(report)
        self._history_refresh_lists()

    def _history_refresh_lists(self):
        """刷新 Tab 3 左侧列表"""
        # FPS 列表：按时间新→旧
        self.hist_fps_list.clear()
        for i, rep in enumerate(reversed(self._fps_reports)):
            tstr = rep["start_time"].strftime("%Y-%m-%d %H:%M:%S")
            dur = rep["duration_sec"]
            dur_str = f"{dur//60}分{dur%60}秒" if dur >= 60 else f"{dur}秒"
            fps_avg = rep["summary"].get("avg_fps", "--")
            pkg = rep["package"][:20] if len(rep["package"]) <= 20 else rep["package"][:17] + "..."
            text = f"#{5-i}  {tstr}\n   🎮 {pkg}  |  平均 {fps_avg} FPS  |  {dur_str}"
            item = QListWidgetItem(text)
            item.setFont(QFont("Menlo", 12))
            item.setForeground(QColor("#1565C0"))
            item.setData(Qt.UserRole, rep["id"])
            self.hist_fps_list.addItem(item)

        # HW 列表
        self.hist_hw_list.clear()
        for i, rep in enumerate(reversed(self._hw_reports)):
            tstr = rep["start_time"].strftime("%Y-%m-%d %H:%M:%S")
            dur = rep["duration_sec"]
            dur_str = f"{dur//60}分{dur%60}秒" if dur >= 60 else f"{dur}秒"
            n_cluster = len(rep["cpu"])
            gpu_avg = "--"
            if "GPU 频率" in rep["freq_summary"]:
                gpu_avg = f"{rep['freq_summary']['GPU 频率']['avg']:.0f}"
            temp_data = rep.get("temp", []) or []
            temp_avg = f"{sum(temp_data)/len(temp_data):.0f}°C" if temp_data else "--"
            text = f"#{5-i}  {tstr}\n   🔧 {n_cluster} 个CPU集群  |  GPU 均频 {gpu_avg} MHz  |  温度 {temp_avg}  |  {dur_str}"
            item = QListWidgetItem(text)
            item.setFont(QFont("Menlo", 12))
            item.setForeground(QColor("#7B1FA2"))
            item.setData(Qt.UserRole, rep["id"])
            self.hist_hw_list.addItem(item)

        # 负载测试列表
        self.hist_load_list.clear()
        for i, rep in enumerate(reversed(self._load_reports)):
            tstr = rep["start_time"].strftime("%Y-%m-%d %H:%M:%S")
            dur = rep["duration_sec"]
            dur_str = f"{dur//60}分{dur%60}秒" if dur >= 60 else f"{dur}秒"
            rating = rep.get("rating", "-")
            stats = rep.get("stats", {}) or {}
            temp_st = stats.get("cpu_temp", {}) or {}
            temp_max = f"{temp_st.get('max','--')}°C" if isinstance(temp_st.get('max'), (int, float)) else "--"
            text = f"#{5-i}  {tstr}\n   🔥 评级 {rating}  |  峰值温 {temp_max}  |  {dur_str}"
            item = QListWidgetItem(text)
            item.setFont(QFont("Menlo", 12))
            item.setForeground(QColor("#B71C1C"))
            item.setData(Qt.UserRole, rep["id"])
            self.hist_load_list.addItem(item)

        # 性能评价列表
        self.hist_eval_list.clear()
        for i, rec in enumerate(reversed(self._eval_records)):
            tstr = rec["start_time"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(rec["start_time"], "strftime") else str(rec["start_time"])
            score = rec.get("total_score", 0)
            rating = rec.get("rating", "-")
            chip = (rec.get("chip_detail") or "--")
            chip_show = chip[:14] if len(chip) <= 14 else chip[:11] + "..."
            text = f"#{5-i}  {tstr}\n   🏆 {score:.1f}分 / {rating}  |  {chip_show}"
            item = QListWidgetItem(text)
            item.setFont(QFont("Menlo", 12))
            item.setForeground(QColor("#E65100"))
            item.setData(Qt.UserRole, rec["id"])
            self.hist_eval_list.addItem(item)

    def _history_find_report(self, report_id: str):
        for rep in self._fps_reports:
            if rep["id"] == report_id:
                return ("fps", rep)
        for rep in self._hw_reports:
            if rep["id"] == report_id:
                return ("hw", rep)
        for rep in self._load_reports:
            if rep["id"] == report_id:
                return ("load", rep)
        for rec in self._eval_records:
            if rec["id"] == report_id:
                return ("eval", rec)
        return None

    def _history_on_load_clicked(self, item: QListWidgetItem):
        rid = item.data(Qt.UserRole)
        found = self._history_find_report(rid)
        if found and found[0] == "load":
            self._history_show_load(found[1])

    def _history_on_eval_clicked(self, item: QListWidgetItem):
        rid = item.data(Qt.UserRole)
        found = self._history_find_report(rid)
        if found and found[0] == "eval":
            self._history_show_eval(found[1])

    def _history_on_fps_clicked(self, item: QListWidgetItem):
        rid = item.data(Qt.UserRole)
        found = self._history_find_report(rid)
        if found and found[0] == "fps":
            self._history_show_fps(found[1])

    def _history_on_hw_clicked(self, item: QListWidgetItem):
        rid = item.data(Qt.UserRole)
        found = self._history_find_report(rid)
        if found and found[0] == "hw":
            self._history_show_hw(found[1])

    def _history_clear_details(self):
        """清空右侧详情"""
        # 清除摘要
        while self.hist_summary_layout.count():
            child = self.hist_summary_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        empty_label = QLabel(self._tr("lbl_empty_history"))
        empty_label.setStyleSheet(f"color: {self._fg_muted()}; font-size: 15px; padding: 20px;")
        empty_label.setAlignment(Qt.AlignCenter)
        self.hist_summary_layout.addWidget(empty_label, 0, 0)

        # 表格清空
        self.hist_table.setRowCount(0)

        # 图表清空
        self.hist_plot.clear()
        self.hist_plot.setTitle("")
        self.hist_plot.setLabel('left', '')
        self.hist_plot.setLabel('bottom', '')
        # 温度右轴清空并隐藏
        if hasattr(self, "_hist_temp_vb") and self._hist_temp_vb is not None:
            self._hist_temp_vb.clear()
            self.hist_plot.hideAxis('right')

    def _history_set_summary(self, rows):
        """设置摘要区：rows = [(label, value, color_str), ...] 2列网格"""
        while self.hist_summary_layout.count():
            child = self.hist_summary_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for i, (label, value, color) in enumerate(rows):
            row = i // 2
            col_pair = (i % 2) * 2
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"font-size: 13px; color: {self._fg_muted()}; font-weight: bold;")
            val = QLabel(str(value))
            val.setFont(QFont("Menlo", 15, QFont.Bold))
            val.setStyleSheet(f"color: {color};")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.hist_summary_layout.addWidget(lbl, row, col_pair)
            self.hist_summary_layout.addWidget(val, row, col_pair + 1)

    def _history_set_table(self, rows):
        """设置统计表：rows = [(metric, value)]"""
        self.hist_table.setRowCount(len(rows))
        for i, (m, v) in enumerate(rows):
            item_m = QTableWidgetItem(str(m))
            item_v = QTableWidgetItem(str(v))
            item_m.setFont(QFont("Menlo", 12))
            item_v.setFont(QFont("Menlo", 12, QFont.Bold))
            item_v.setForeground(QColor("#0277BD"))
            self.hist_table.setItem(i, 0, item_m)
            self.hist_table.setItem(i, 1, item_v)

    def _history_show_fps(self, rep: dict):
        """显示 FPS 历史报告详情"""
        # 摘要
        tstr = rep["start_time"].strftime("%Y-%m-%d %H:%M:%S")
        dur = rep["duration_sec"]
        dur_str = f"{dur//60:02d}:{dur%60:02d}" if dur < 3600 else f"{dur//3600:02d}:{(dur%3600)//60:02d}:{dur%60:02d}"
        s = rep["summary"]
        fps_avg = s.get("avg_fps", "--")
        jank_rate = s.get("jank_rate", "--")
        low_1 = s.get("low_1_fps", "--")
        low_01 = s.get("low_01_fps", "--")
        summary_rows = [
            ("记录类型", "🎮 帧率测试", "#1565C0"),
            ("开始时间", tstr, "#475569"),
            ("设备", rep["device_id"][:18] if len(rep["device_id"]) <= 18 else rep["device_id"][:15] + "...", "#475569"),
            ("测试时长", dur_str, "#0277BD"),
            ("测试应用", rep["package"][:20] if len(rep["package"]) <= 20 else rep["package"][:17] + "...", "#6A1B9A"),
            ("平均FPS", str(fps_avg), "#2E7D32"),
            ("1% Low", str(low_1), "#E65100"),
            ("0.1% Low", str(low_01), "#BF360C"),
            ("卡顿率", str(jank_rate) + "%", "#D32F2F" if isinstance(jank_rate, (int, float)) and jank_rate >= 5 else "#2E7D32"),
        ]
        self._history_set_summary(summary_rows)
        # 统计表
        end_dt = rep.get("end_time")
        table_rows = [
            ("平均 FPS", s.get("avg_fps", "--")),
            ("最低 FPS", s.get("min_fps", "--")),
            ("最高 FPS", s.get("max_fps", "--")),
            ("1% Low FPS", s.get("low_1_fps", "--")),
            ("0.1% Low FPS", s.get("low_01_fps", "--")),
            ("FPS 标准差", s.get("std_fps", "--")),
            ("卡顿帧数", s.get("jank_count", "--")),
            ("卡顿率 (%)", s.get("jank_rate", "--")),
            ("P95 帧时 (ms)", s.get("p95_frame_ms", "--")),
            ("P99 帧时 (ms)", s.get("p99_frame_ms", "--")),
            ("FPS 跌落次数", s.get("fps_drop_count", "--")),
            ("测试时长 (秒)", dur if dur else s.get("duration_sec", "--")),
            ("采样点数量", len(rep.get("times", []))),
            ("开始时间", tstr),
            ("结束时间", end_dt.strftime("%H:%M:%S") if end_dt else "--"),
        ]
        self._history_set_table(table_rows)
        # 曲线（使用相对时间）
        times = rep.get("times", [])
        fps_vals = rep.get("fps", [])
        avg_vals = rep.get("avg_fps", [])
        if times:
            t0 = times[0]
            xs = [t - t0 for t in times]
            self.hist_plot.plot(xs, fps_vals, pen=mkPen('#2196F3', width=2), name=self._tr("legend_instant_fps"))
            self.hist_plot.plot(xs, avg_vals, pen=mkPen('#FF9800', width=2, style=Qt.DashLine), name=self._tr("legend_avg_fps"))
            self.hist_plot.addLegend()
            self.hist_plot.setTitle(self._tr("chart_ios_fps_series").format(time=tstr[:16]))
            self.hist_plot.setLabel('left', 'FPS')
            self.hist_plot.setLabel('bottom', self._tr("lbl_axis_time"))
            self.hist_plot.hideAxis('right')

    def _history_show_hw(self, rep: dict):
        """显示 CPU/GPU 历史报告详情（安卓端：频率 + 使用率 + 温度）"""
        self._history_clear_details()
        dt = rep.get("start_time")
        end_dt = rep.get("end_time")
        dur = rep.get("duration_sec", 0)
        dur_str = f"{dur//60:02d}:{dur%60:02d}" if dur < 3600 else f"{dur//3600:02d}:{(dur%3600)//60:02d}:{dur%60:02d}"
        tstr = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "--"
        device = rep.get("device_id", "--")
        device_show = device[:18] if len(device) <= 18 else device[:15] + "..."
        cpu_freq_dict = rep.get("cpu", {}) or {}
        gpu_freq_vals = rep.get("gpu", []) or []
        temp_vals = rep.get("temp", []) or []
        cpu_usage_vals = rep.get("cpu_usage", []) or []
        mem_usage_vals = rep.get("mem_usage", []) or []
        times = rep.get("times", []) or []
        n = len(times)
        n_cluster = len(cpu_freq_dict)
        summary_rows = [
            ("记录类型", "🔧 CPU/GPU 监测", "#7B1FA2"),
            ("开始时间", tstr, "#475569"),
            ("设备", device_show, "#475569"),
            ("监测时长", dur_str, "#6A1B9A"),
            ("CPU 集群数", str(n_cluster), "#1565C0"),
            ("GPU 采样点", str(len(gpu_freq_vals)), "#00838F"),
            ("温度采样点", str(len(temp_vals)), "#F44336"),
            ("总采样点", str(n), "#37474F"),
            ("结束时间", end_dt.strftime("%H:%M:%S") if end_dt else "--", "#475569"),
        ]
        self._history_set_summary(summary_rows)

        # 统计表
        def _stat(arr):
            if not arr:
                return None
            a = sum(arr) / len(arr)
            mx = max(arr)
            mn = min(arr)
            sd = (sum((x - a) ** 2 for x in arr) / len(arr)) ** 0.5
            return {"avg": a, "max": mx, "min": mn, "std": sd}

        table_rows = [
            ("开始时间", tstr),
            ("结束时间", end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "--"),
            ("监测时长 (秒)", str(dur)),
            ("采样点数", str(n)),
        ]
        # CPU 各集群频率统计
        for label, arr in cpu_freq_dict.items():
            st = _stat(arr)
            if st:
                table_rows.append((f"{label} 均频 (MHz)", f"{st['avg']:.0f}"))
                table_rows.append((f"{label} 最大/最小 (MHz)", f"{st['max']:.0f} / {st['min']:.0f}"))
                table_rows.append((f"{label} 标准差 (MHz)", f"{st['std']:.0f}"))
        # GPU 频率统计
        if gpu_freq_vals:
            st = _stat(gpu_freq_vals)
            if st:
                table_rows.append(("GPU 均频 (MHz)", f"{st['avg']:.0f}"))
                table_rows.append(("GPU 最大/最小 (MHz)", f"{st['max']:.0f} / {st['min']:.0f}"))
                table_rows.append(("GPU 标准差 (MHz)", f"{st['std']:.0f}"))
        # CPU 使用率统计
        if cpu_usage_vals:
            st = _stat(cpu_usage_vals)
            if st:
                table_rows.append(("CPU 平均使用率(%)", f"{st['avg']:.1f}"))
                table_rows.append(("CPU 最大/最小使用率(%)", f"{st['max']:.1f} / {st['min']:.1f}"))
                table_rows.append(("CPU 使用率标准差(%)", f"{st['std']:.1f}"))
        # 内存使用率统计
        if mem_usage_vals:
            st = _stat(mem_usage_vals)
            if st:
                table_rows.append(("内存平均使用率(%)", f"{st['avg']:.1f}"))
                table_rows.append(("内存最大/最小使用率(%)", f"{st['max']:.1f} / {st['min']:.1f}"))
                table_rows.append(("内存使用率标准差(%)", f"{st['std']:.1f}"))
        # CPU 温度统计
        if temp_vals:
            st = _stat(temp_vals)
            if st:
                table_rows.append(("CPU 平均温度(°C)", f"{st['avg']:.1f}"))
                table_rows.append(("CPU 最高/最低温度(°C)", f"{st['max']:.1f} / {st['min']:.1f}"))
                table_rows.append(("CPU 温度标准差(°C)", f"{st['std']:.1f}"))
        self._history_set_table(table_rows)

        # 曲线绘制：CPU 使用率 + 内存使用率（左轴 %），CPU 温度（右轴 °C）
        if times and (cpu_usage_vals or mem_usage_vals or temp_vals):
            self.hist_plot.clear()
            # 对齐长度（取最短）
            min_n = min(len(times), len(cpu_usage_vals), len(mem_usage_vals)) if cpu_usage_vals and mem_usage_vals else len(times)
            xs = times[:min_n]
            if cpu_usage_vals:
                self.hist_plot.plot(xs, cpu_usage_vals[:min_n],
                                    pen=mkPen('#2196F3', width=2), name=self._tr("legend_cpu_usage_pct"))
            if mem_usage_vals:
                self.hist_plot.plot(xs, mem_usage_vals[:min_n],
                                    pen=mkPen('#4CAF50', width=2, style=Qt.DashLine), name=self._tr("legend_mem_usage_pct"))
            # CPU 温度曲线（右侧 Y 轴）
            if temp_vals and hasattr(self, "_hist_temp_vb") and self._hist_temp_vb is not None:
                tn = min(len(times), len(temp_vals))
                self._hist_temp_vb.clear()
                self._hist_temp_vb.addItem(
                    pg.PlotCurveItem(times[:tn], temp_vals[:tn],
                                     pen=mkPen('#F44336', width=2), name=self._tr("legend_cpu_temp"))
                )
                self.hist_plot.showAxis('right')
                self.hist_plot.getAxis('right').setLabel('CPU 温度 (°C)')
            else:
                self.hist_plot.hideAxis('right')
            self.hist_plot.addLegend()
            self.hist_plot.setTitle(self._tr("chart_ios_hw_series").format(time=tstr[:16]))
            self.hist_plot.setLabel('left', self._tr("lbl_axis_usage"))
            self.hist_plot.setLabel('bottom', self._tr("lbl_axis_time"))

    def _history_show_load(self, rep: dict):
        """显示负载测试历史报告详情"""
        self._history_clear_details()
        dt = rep.get("start_time")
        end_dt = rep.get("end_time")
        dur = rep.get("duration_sec", 0)
        dur_str = f"{dur//60:02d}:{dur%60:02d}" if dur < 3600 else f"{dur//3600:02d}:{(dur%3600)//60:02d}:{dur%60:02d}"
        tstr = dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, "strftime") else str(dt)
        device = rep.get("device_id", "--")
        device_show = device[:18] if len(device) <= 18 else device[:15] + "..."
        rating_key = rep.get("rating_key") or rep.get("rating") or "good"
        rating_label = self._rating_to_label(rating_key)
        rating_color = {"good": "#16a34a", "warn": "#f59e0b", "bad": "#dc2626"}.get(rating_key, "#64748b")
        stats = rep.get("stats", {}) or {}
        summary_rows = [
            (self._tr("hist_rec_type"), self._tr("tab_load_test"), "#B71C1C"),
            (self._tr("hist_start_time"), tstr, "#475569"),
            (self._tr("hist_device"), device_show, "#475569"),
            (self._tr("hist_test_duration"), dur_str, "#0277BD"),
            (self._tr("lbl_stability_rating"), rating_label, rating_color),
            (self._tr("load_html_error_count"), str(rep.get("errors", 0)), "#D32F2F" if rep.get("errors", 0) > 0 else "#2E7D32"),
            (self._tr("hist_end_time"), end_dt.strftime("%H:%M:%S") if hasattr(end_dt, "strftime") else "--", "#475569"),
        ]
        self._history_set_summary(summary_rows)
        # 统计表
        st = stats
        table_rows = [
            (self._tr("hist_start_time"), tstr),
            (self._tr("hist_end_time"), end_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(end_dt, "strftime") else "--"),
            (self._tr("load_csv_duration_sec"), str(dur)),
            (self._tr("lbl_stability_rating"), rating_label),
        ]
        _metric_keys2 = [
            ("cpu", "load_metric_cpu"),
            ("gpu", "load_metric_gpu"),
            ("mem", "load_metric_mem"),
            ("cpu_temp", "load_metric_cpu_temp"),
        ]
        for mkey, tr_key in _metric_keys2:
            s = st.get(mkey) or {}
            if not s:
                continue
            mname = self._tr(tr_key)
            n = s.get("n", "-")
            avg_v = s.get("avg")
            mx = s.get("max")
            mn = s.get("min")
            table_rows.append((f"{mname} {self._tr('tbl_load_col_samples')}", str(n)))
            table_rows.append((f"{mname} {self._tr('tbl_load_col_avg')}", f"{avg_v:.1f}" if isinstance(avg_v, (int, float)) else "-"))
            table_rows.append((f"{mname} {self._tr('tbl_load_col_max')}", f"{mx:.1f}" if isinstance(mx, (int, float)) else "-"))
            table_rows.append((f"{mname} {self._tr('tbl_load_col_min')}", f"{mn:.1f}" if isinstance(mn, (int, float)) else "-"))
        self._history_set_table(table_rows)

        # 曲线
        ts = rep.get("time_series") or {}
        times = ts.get("time", []) or []
        cpus = ts.get("cpu", []) or []
        mems = ts.get("mem", []) or []
        temps = ts.get("cpu_temp", []) or []
        if times:
            self.hist_plot.clear()
            if cpus:
                tn = min(len(times), len(cpus))
                self.hist_plot.plot(times[:tn], cpus[:tn],
                                    pen=mkPen('#dc2626', width=2.4), name=self._tr("chart_load_cpu_usage"))
            if mems:
                tn = min(len(times), len(mems))
                # 内存：除以100，映射到%范围便于同图显示
                mem_norm = [round(m / 100.0, 2) if isinstance(m, (int, float)) else None for m in mems[:tn]]
                self.hist_plot.plot(times[:tn], mem_norm,
                                    pen=mkPen('#7c3aed', width=2.4), name=self._tr("chart_load_mem_usage"))
            # 温度（右轴）
            if temps and hasattr(self, "_hist_temp_vb") and self._hist_temp_vb is not None:
                tn = min(len(times), len(temps))
                self._hist_temp_vb.clear()
                self._hist_temp_vb.addItem(
                    pg.PlotCurveItem(times[:tn], temps[:tn],
                                     pen=mkPen('#ea580c', width=2.4), name=self._tr("chart_load_temp_result"))
                )
                self.hist_plot.showAxis('right')
                self.hist_plot.getAxis('right').setLabel(self._tr("chart_load_temp_result"), color='#ea580c')
            else:
                self.hist_plot.hideAxis('right')
            self.hist_plot.addLegend()
            self.hist_plot.setTitle(f"🔥 负载测试趋势 — {tstr[:16]}")
            self.hist_plot.setLabel('left', self._tr("lbl_axis_usage"))
            self.hist_plot.setLabel('bottom', self._tr("lbl_axis_time"))

    def _history_show_eval(self, rec: dict):
        """显示性能评价历史记录详情"""
        self._history_clear_details()
        dt = rec.get("start_time")
        dur = rec.get("duration_sec", 0) or 0
        dur_str = f"{dur//60:02d}:{dur%60:02d}" if dur < 3600 else f"{dur//3600:02d}:{(dur%3600)//60:02d}:{dur%60:02d}"
        tstr = dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(dt, "strftime") else str(dt)
        total_score = rec.get("total_score", 0)
        rating = rec.get("rating", "-")
        rating_color = rec.get("rating_color", "#64748b")
        scores = rec.get("scores", {}) or {}
        summary_rows = [
            ("记录类型", "🏆 性能评价", "#E65100"),
            ("生成时间", tstr, "#475569"),
            ("平台 / 设备", f"{rec.get('platform', '')} / {(rec.get('device_serial') or '--')[:16]}", "#475569"),
            ("测试应用", (rec.get("app_package") or '--')[:18], "#6A1B9A"),
            ("测试时长", dur_str, "#0277BD"),
            ("综合评分", f"{total_score:.1f} / 100", rating_color),
            ("性能等级", rating, rating_color),
            ("芯片", f"{rec.get('chip_detail', '--')}（{rec.get('chipset_tier', '')}）", "#7c3aed"),
        ]
        self._history_set_summary(summary_rows)
        # 统计表：4 个子项得分 + 概要
        table_rows = [
            ("综合评分", f"{total_score:.1f} / 100"),
            ("性能等级", rating),
            ("帧率达标度 / 40", f"{scores.get('fps', 0):.1f}"),
            ("稳定性 / 25", f"{scores.get('stability', 0):.1f}"),
            ("Low FPS 表现 / 20", f"{scores.get('lowfps', 0):.1f}"),
            ("掉帧控制 / 15", f"{scores.get('drop', 0):.1f}"),
            ("芯片等级", f"{rec.get('chipset_tier', '--')}"),
            ("芯片型号", rec.get("chip_detail", "--")),
            ("生成时间", tstr),
        ]
        self._history_set_table(table_rows)
        # 图表：用简单柱状图（BarGraph）展示四维度得分
        self.hist_plot.clear()
        cat_names = [self._tr("fps_eval_fps_score"), self._tr("fps_eval_stability_score"),
                     self._tr("fps_eval_lowfps_score"), self._tr("fps_eval_drop_score")]
        xs = list(range(len(cat_names)))
        ys = [float(scores.get("fps", 0)), float(scores.get("stability", 0)),
              float(scores.get("lowfps", 0)), float(scores.get("drop", 0))]
        maxes = [40.0, 25.0, 20.0, 15.0]
        # 转为百分率便于对比
        ys_pct = [min(100.0, y / m * 100) if m > 0 else 0 for y, m in zip(ys, maxes)]
        colors = ['#3b82f6', '#16a34a', '#f59e0b', '#ea580c']
        bg = pg.BarGraphItem(x=xs, height=ys_pct, width=0.55,
                             brushes=[pg.mkBrush(c) for c in colors],
                             pens=[pg.mkPen(c, width=2) for c in colors])
        self.hist_plot.addItem(bg)
        self.hist_plot.getAxis('bottom').setTicks([list(zip(xs, cat_names))])
        self.hist_plot.setYRange(0, 105)
        self.hist_plot.setLabel('left', '得分率 (%)')
        self.hist_plot.setTitle(f"🏆 四维度得分率 — {tstr[:16]}")
        self.hist_plot.addLegend()
        self.hist_plot.hideAxis('right')