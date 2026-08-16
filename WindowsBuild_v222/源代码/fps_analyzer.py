import time
import statistics
from collections import deque
from typing import Optional, Dict, List, Deque
from dataclasses import dataclass, field


@dataclass
class FPSStats:
    """帧率统计数据"""
    timestamp: float = 0.0
    fps: float = 0.0
    avg_fps: float = 0.0
    min_fps: float = 0.0
    max_fps: float = 0.0
    std_fps: float = 0.0
    frame_times: List[float] = field(default_factory=list)
    jank_count: int = 0
    total_frames: int = 0
    jank_rate: float = 0.0
    percentile_95: float = 0.0
    percentile_99: float = 0.0
    low_1_fps: float = 0.0      # 1% Low FPS
    low_01_fps: float = 0.0     # 0.1% Low FPS


class FPSAnalyzer:
    """帧率分析器，实时计算FPS统计数据"""

    # 60fps的阈值：一帧超过16.67ms视为卡顿；对于高刷设备会动态调整
    DEFAULT_FRAME_THRESHOLD_MS = 16.67

    def __init__(self, window_size: int = 120, refresh_rate: int = 60):
        """
        :param window_size: 滑动窗口大小（帧数），用于计算瞬时FPS
        :param refresh_rate: 屏幕刷新率，用于判定卡顿阈值
        """
        self.window_size = window_size
        self.refresh_rate = refresh_rate
        self.frame_threshold_ms = 1000.0 / refresh_rate * 1.2  # 留20%余量

        # 历史帧时间（所有）
        self.all_frame_times: Deque[float] = deque()
        # 滑动窗口内的帧时间
        self.window_frame_times: Deque[float] = deque(maxlen=window_size)

        # 采样历史（每秒一个样本）
        self.fps_history: List[float] = []
        self.time_history: List[float] = []

        self.start_time: Optional[float] = None
        self.last_sample_time: Optional[float] = None

        # 累计统计
        self.total_jank_count = 0
        self.total_frame_count = 0
        # 上次采样时的累计值，用于计算每秒增量
        self._prev_jank_count = 0
        self._prev_frame_count = 0

        # 瞬时 FPS（基于每秒真实帧计数的原始观测 + EMA 平滑，
        # 用于 UI 大数字和曲线，避免"帧时间展开→同秒帧同值→无波动"的跳变问题）
        self._ema_instant_fps: Optional[float] = None
        self._ema_alpha = 0.15  # 平滑系数：越小爬升越慢（0.15=约15%新值+85%历史）
        # 最近一次观测的"原始瞬时 FPS"（未平滑），便于调试
        self._last_raw_instant_fps: Optional[float] = None
        # 最近一次有效观测的时间戳，用于检测应用停止渲染后 FPS 自动归零
        self._last_observe_time: Optional[float] = None

        # 动态卡顿阈值：跟踪实际观测到的最高 FPS，防止用户选 120Hz
        # 但设备只跑 60fps 时导致 100% 卡顿率
        self._max_observed_fps: float = 0.0

    def reset(self) -> None:
        """重置分析器状态"""
        self.all_frame_times.clear()
        self.window_frame_times.clear()
        self.fps_history.clear()
        self.time_history.clear()
        self.start_time = time.time()
        self.last_sample_time = None
        self.total_jank_count = 0
        self.total_frame_count = 0
        self._prev_jank_count = 0
        self._prev_frame_count = 0
        self._ema_instant_fps = None
        self._last_raw_instant_fps = None
        self._last_observe_time = None
        self._max_observed_fps = 0.0

    def observe_instant_fps(self, fps_value: float) -> None:
        """
        注入本次采样周期的真实瞬时 FPS（帧计数法得出：frame_delta / time_delta）。
        直接存储原始值，不做任何平滑 — 真实帧率是多少就显示多少。
        """
        if fps_value is None or fps_value <= 0:
            return
        self._last_raw_instant_fps = float(fps_value)
        self._last_observe_time = time.time()

        # 动态卡顿阈值：跟踪最大观测 FPS
        # 当实际 FPS 持续低于用户选择的刷新率时（如选 120Hz 但实际 60fps），
        # 自动放宽卡顿阈值，避免 100% 卡顿率
        if fps_value > self._max_observed_fps:
            self._max_observed_fps = fps_value
            # 用实际最高 FPS 重新计算阈值（留 50% 余量，比固定 20% 更宽松）
            # 仅当实际 FPS 低于刷新率时才放宽
            if self._max_observed_fps < self.refresh_rate:
                dynamic_threshold = 1000.0 / self._max_observed_fps * 1.5
                # 取较宽松的阈值
                self.frame_threshold_ms = max(self.frame_threshold_ms, dynamic_threshold)

    def add_frames(self, frame_times_ms: List[float]) -> None:
        """
        添加一批帧时间数据
        :param frame_times_ms: 帧渲染时间列表（毫秒）
        """
        if not frame_times_ms:
            return

        current_time = time.time()
        if self.start_time is None:
            self.start_time = current_time

        for ft in frame_times_ms:
            self.all_frame_times.append(ft)
            self.window_frame_times.append(ft)
            self.total_frame_count += 1
            if ft > self.frame_threshold_ms:
                self.total_jank_count += 1

    def _calc_fps_from_window(self, frame_times: List[float]) -> float:
        """根据帧时间列表计算FPS"""
        if not frame_times:
            return 0.0
        avg_frame_time = sum(frame_times) / len(frame_times)
        if avg_frame_time <= 0:
            return 0.0
        return 1000.0 / avg_frame_time

    def _percentile(self, data: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * percentile
        f = int(k)
        c = min(f + 1, len(sorted_data) - 1)
        if f == c:
            return sorted_data[f]
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)

    def _calc_low_fps(self, fps_values: List[float], pct: float) -> float:
        """
        计算 Low FPS（最低 pct% 帧的平均 FPS）
        :param fps_values: 所有帧的 FPS 列表
        :param pct: 百分比，如 0.01 表示 1% Low
        :return: 该百分位段帧的平均 FPS
        """
        if not fps_values:
            return 0.0
        sorted_fps = sorted(fps_values)  # 升序
        n = len(sorted_fps)
        count = max(1, int(n * pct))
        lowest = sorted_fps[:count]
        return sum(lowest) / len(lowest)

    def sample(self) -> Optional[FPSStats]:
        """
        采样当前统计数据。每秒最多采样一次。
        :return: FPSStats对象，如果距离上次采样不足1秒则返回None
        """
        current_time = time.time()

        # 每秒采样一次
        if self.last_sample_time is not None and (current_time - self.last_sample_time) < 0.9:
            return None
        self.last_sample_time = current_time

        if len(self.window_frame_times) == 0 and len(self.all_frame_times) == 0:
            return None

        # 瞬时FPS：直接使用原始观测值，是多少就显示多少，不做平滑
        window_list = list(self.window_frame_times)
        all_list = list(self.all_frame_times)

        window_fps = self._calc_fps_from_window(window_list) if window_list else 0.0
        # 检测应用停止渲染：如果距离上次有效观测超过 2 秒，认为应用已停止渲染，
        # 瞬时 FPS 应归零（而不是保持上次的值）
        if self._last_raw_instant_fps is not None and self._last_raw_instant_fps > 0:
            if self._last_observe_time is not None and (current_time - self._last_observe_time) > 2.0:
                # 超时未收到新帧观测，FPS 归零
                current_fps = 0.0
            else:
                current_fps = self._last_raw_instant_fps
        else:
            current_fps = window_fps
        avg_fps = self._calc_fps_from_window(all_list) if all_list else 0.0

        # 用帧时间直接统计最大最小FPS更准确
        fps_values_window = [1000.0 / ft for ft in window_list if ft > 0]
        fps_values_all = [1000.0 / ft for ft in all_list if ft > 0]

        min_fps = min(fps_values_all) if fps_values_all else 0.0
        max_fps = max(fps_values_all) if fps_values_all else 0.0
        std_fps = statistics.stdev(fps_values_all) if len(fps_values_all) > 1 else 0.0

        # 卡顿率：计算每秒增量（本秒内新增卡顿帧 / 本秒内新增总帧数）
        sec_jank = self.total_jank_count - self._prev_jank_count
        sec_frames = self.total_frame_count - self._prev_frame_count
        jank_rate = (sec_jank / sec_frames * 100) if sec_frames > 0 else 0.0

        # 百分位数
        p95 = self._percentile(all_list, 0.95) if all_list else 0.0
        p99 = self._percentile(all_list, 0.99) if all_list else 0.0

        # 1% Low / 0.1% Low
        low_1 = self._calc_low_fps(fps_values_all, 0.01) if fps_values_all else 0.0
        low_01 = self._calc_low_fps(fps_values_all, 0.001) if fps_values_all else 0.0

        # 记录历史
        elapsed = current_time - self.start_time if self.start_time else 0
        self.fps_history.append(current_fps)
        self.time_history.append(elapsed)

        # 更新上次采样累计值
        self._prev_jank_count = self.total_jank_count
        self._prev_frame_count = self.total_frame_count

        return FPSStats(
            timestamp=elapsed,
            fps=round(current_fps, 1),
            avg_fps=round(avg_fps, 1),
            min_fps=round(min_fps, 1),
            max_fps=round(max_fps, 1),
            std_fps=round(std_fps, 1),
            frame_times=all_list[-100:],  # 只保留最近100帧用于绘图
            jank_count=sec_jank,
            total_frames=sec_frames,
            jank_rate=round(jank_rate, 2),
            percentile_95=round(p95, 2),
            percentile_99=round(p99, 2),
            low_1_fps=round(low_1, 1),
            low_01_fps=round(low_01, 1),
        )

    def get_summary(self) -> Dict:
        """获取完整的测试摘要"""
        all_list = list(self.all_frame_times)
        fps_values = [1000.0 / ft for ft in all_list if ft > 0]

        if not fps_values:
            return {
                "duration_sec": 0,
                "total_frames": 0,
                "avg_fps": 0,
                "min_fps": 0,
                "max_fps": 0,
                "std_fps": 0,
                "jank_count": 0,
                "jank_rate": 0,
                "p95_frame_ms": 0,
                "p99_frame_ms": 0,
                "low_1_fps": 0,
                "low_01_fps": 0,
                "fps_drop_count": 0,
            }

        # 计算掉帧次数（连续3帧低于平均70%）
        avg_fps = statistics.mean(fps_values)
        drop_threshold = avg_fps * 0.7
        fps_drop_count = 0
        consecutive_low = 0
        for f in fps_values:
            if f < drop_threshold:
                consecutive_low += 1
                if consecutive_low >= 3:
                    fps_drop_count += 1
                    consecutive_low = 0
            else:
                consecutive_low = 0

        duration = (time.time() - self.start_time) if self.start_time else 0

        # 1% Low / 0.1% Low
        low_1 = self._calc_low_fps(fps_values, 0.01)
        low_01 = self._calc_low_fps(fps_values, 0.001)

        return {
            "duration_sec": round(duration, 1),
            "total_frames": self.total_frame_count,
            "avg_fps": round(avg_fps, 1),
            "min_fps": round(min(fps_values), 1),
            "max_fps": round(max(fps_values), 1),
            "std_fps": round(statistics.stdev(fps_values) if len(fps_values) > 1 else 0, 1),
            "jank_count": self.total_jank_count,
            "jank_rate": round(self.total_jank_count / self.total_frame_count * 100, 2) if self.total_frame_count else 0,
            "p95_frame_ms": round(self._percentile(all_list, 0.95), 2),
            "p99_frame_ms": round(self._percentile(all_list, 0.99), 2),
            "low_1_fps": round(low_1, 1),
            "low_01_fps": round(low_01, 1),
            "fps_drop_count": fps_drop_count,
        }
