import subprocess
import re
import time
import sys
import os
import shutil
import logging
from typing import List, Optional, Tuple

_logger = logging.getLogger(__name__)


def _chmod_x_if_needed(p: str) -> None:
    """确保 adb 二进制拥有可执行位（某些解压/打包环境会丢失）。"""
    try:
        if os.path.isfile(p) and not os.access(p, os.X_OK):
            st = os.stat(p)
            os.chmod(p, st.st_mode | 0o755)
    except Exception:
        pass


def _find_adb() -> str:
    """
    自动查找 adb 可执行文件路径，按优先级依次搜索：
    1. PyInstaller 打包后内置的 platform-tools/adb
       - onefile 模式：sys._MEIPASS (临时解压目录)
       - onedir macOS .app: Contents/MacOS, Contents/Frameworks, Contents/Resources (均为 PyInstaller 实际放置 datas 的目录)
    2. 脚本同级目录下的 platform-tools/adb（开发模式）
    3. 系统常见安装路径（Android Studio / Homebrew / 手动安装）
    4. PATH 环境变量中的 adb
    """
    def _check(p: str) -> Optional[str]:
        if os.path.isfile(p):
            _chmod_x_if_needed(p)
            if os.access(p, os.X_OK):
                return p
        return None

    # 1. PyInstaller 打包后的资源目录（兼容 onefile 与 onedir）
    frozen = getattr(sys, 'frozen', False)
    meipass = getattr(sys, '_MEIPASS', None)
    candidates: List[str] = []
    if frozen:
        # onefile 模式：MEIPASS 是临时解压根（平台无关）
        if meipass:
            candidates.append(os.path.join(meipass, 'platform-tools', 'adb'))
        # onedir + macOS .app bundle：PyInstaller 的 datas 会落到 Contents/Frameworks/、Contents/MacOS/ 或 Contents/Resources/
        try:
            exe_path = os.path.abspath(sys.executable)
            if '.app' in exe_path:
                contents = None
                for part in exe_path.split(os.sep):
                    if part.endswith('.app'):
                        idx = exe_path.split(os.sep).index(part)
                        contents = os.sep.join(exe_path.split(os.sep)[:idx+1]) + os.sep + 'Contents'
                        break
                if contents:
                    for sub in ('Frameworks', 'MacOS', 'Resources'):
                        candidates.append(os.path.join(contents, sub, 'platform-tools', 'adb'))
        except Exception:
            pass
        # 兜底：相对于 sys.executable 的上两层（onedir 常见形态）
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            candidates.append(os.path.join(exe_dir, 'platform-tools', 'adb'))
            candidates.append(os.path.join(os.path.dirname(exe_dir), 'platform-tools', 'adb'))
        except Exception:
            pass

    for p in candidates:
        hit = _check(p)
        if hit:
            return hit

    # 2. 开发模式：脚本同级目录下的 platform-tools/adb
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_adb = os.path.join(script_dir, 'platform-tools', 'adb')
    if _check(local_adb):
        return local_adb

    # 3. 系统常见路径
    home = os.path.expanduser('~')
    common_paths = [
        os.path.join(home, 'Library', 'Android', 'sdk', 'platform-tools', 'adb'),
        os.path.join(home, 'Android', 'Sdk', 'platform-tools', 'adb'),
        os.path.join(home, '.android-sdk', 'platform-tools', 'adb'),
        '/opt/homebrew/bin/adb',
        '/opt/homebrew/share/android-platform-tools/adb',
        '/usr/local/bin/adb',
        '/usr/local/share/android-platform-tools/adb',
        '/usr/bin/adb',
        '/Applications/Android Studio.app/Contents/android-sdk/platform-tools/adb',
        '/Applications/Android Studio.app/Contents/plugins/android-ndk/resources/platform-tools/adb',
    ]
    for p in common_paths:
        if _check(p):
            return p

    # 4. 从 PATH 中查找
    found = shutil.which('adb')
    if found:
        return found

    return 'adb'  # 回退到默认值，由调用时报错提示


class ADBClient:
    """ADB客户端封装类，用于与安卓设备通信"""

    def __init__(self, adb_path: Optional[str] = None):
        self.adb_path = adb_path if adb_path else _find_adb()

    def _run_command(self, cmd: List[str], timeout: int = 30) -> str:
        """执行ADB命令并返回输出"""
        try:
            result = subprocess.run(
                [self.adb_path] + cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"ADB命令超时: {' '.join(cmd)}")
        except FileNotFoundError:
            raise RuntimeError(
                f"找不到ADB可执行文件 (尝试路径: {self.adb_path})。\n"
                "请通过以下方式之一解决：\n"
                "1. macOS安装Homebrew后运行: brew install android-platform-tools\n"
                "2. 或从官网下载: https://developer.android.com/studio/releases/platform-tools\n"
                "   解压后将 platform-tools 目录路径配置到本应用的ADB路径设置中"
            )

    def raw_shell(self, device_id: str, script: str, timeout: int = 30) -> str:
        """在指定设备上执行任意 shell 脚本并返回输出"""
        return self._run_command(["-s", device_id, "shell", script], timeout=timeout)

    def get_devices(self) -> List[Tuple[str, str]]:
        """获取已连接的设备列表 [(设备ID, 状态), ...]"""
        output = self._run_command(["devices"])
        devices = []
        for line in output.split("\n")[1:]:
            line = line.strip()
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    devices.append((parts[0], parts[1]))
        return devices

    def get_device_model(self, device_id: str) -> str:
        """获取设备型号"""
        model = self._run_command(["-s", device_id, "shell", "getprop", "ro.product.model"])
        return model if model else "未知设备"

    def get_device_info(self, device_id: str) -> dict:
        """
        获取设备完整基础信息，通过一条 shell 命令批量读取所有 getprop，减少 ADB 往返。
        返回 dict 包含: brand, model, manufacturer, device_name, android_version, sdk_version,
                        build_number, hardware, soc_model, soc_manufacturer, platform,
                        cpu_abi, cpu_cores, screen_density, screen_resolution, ram_total_mb,
                        gpu_info, kernel_version
        """
        info = {
            "brand": "", "model": "", "manufacturer": "", "device_name": "",
            "android_version": "", "sdk_version": "", "build_number": "",
            "hardware": "", "soc_model": "", "soc_manufacturer": "", "platform": "",
            "cpu_abi": "", "cpu_cores": 0, "screen_density": "",
            "screen_resolution": "", "ram_total_mb": 0, "gpu_info": "", "kernel_version": "",
        }
        try:
            # 一次性读取所有 getprop
            prop_cmds = "; ".join([
                f"echo 'BRAND='$(getprop ro.product.brand)",
                f"echo 'MODEL='$(getprop ro.product.model)",
                f"echo 'MANU='$(getprop ro.product.manufacturer)",
                f"echo 'NAME='$(getprop ro.product.name)",
                f"echo 'REL='$(getprop ro.build.version.release)",
                f"echo 'SDK='$(getprop ro.build.version.sdk)",
                f"echo 'BUILD='$(getprop ro.build.display.id)",
                f"echo 'HW='$(getprop ro.hardware)",
                f"echo 'SOC_MODEL='$(getprop ro.soc.model)",
                f"echo 'SOC_MANU='$(getprop ro.soc.manufacturer)",
                f"echo 'PLATFORM='$(getprop ro.board.platform)",
                f"echo 'ABI='$(getprop ro.product.cpu.abi)",
                f"echo 'DENSITY='$(getprop ro.sf.lcd_density)",
            ])
            output = self._run_command(["-s", device_id, "shell", prop_cmds], timeout=10)
            for line in output.splitlines():
                line = line.strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip()
                    if key == "BRAND": info["brand"] = val
                    elif key == "MODEL": info["model"] = val
                    elif key == "MANU": info["manufacturer"] = val
                    elif key == "NAME": info["device_name"] = val
                    elif key == "REL": info["android_version"] = val
                    elif key == "SDK": info["sdk_version"] = val
                    elif key == "BUILD": info["build_number"] = val
                    elif key == "HW": info["hardware"] = val
                    elif key == "SOC_MODEL": info["soc_model"] = val
                    elif key == "SOC_MANU": info["soc_manufacturer"] = val
                    elif key == "PLATFORM": info["platform"] = val
                    elif key == "ABI": info["cpu_abi"] = val
                    elif key == "DENSITY": info["screen_density"] = val

            # CPU 核心数
            cpu_out = self._run_command(["-s", device_id, "shell",
                "cat /proc/cpuinfo | grep -c processor"], timeout=5)
            if cpu_out and cpu_out.strip().isdigit():
                info["cpu_cores"] = int(cpu_out.strip())

            # 屏幕分辨率
            size_out = self._run_command(["-s", device_id, "shell", "wm", "size"], timeout=5)
            if size_out:
                m = re.search(r'(\d+x\d+)', size_out)
                if m:
                    info["screen_resolution"] = m.group(1)

            # 内存总量
            mem_out = self._run_command(["-s", device_id, "shell", "cat", "/proc/meminfo"], timeout=5)
            if mem_out:
                for line in mem_out.splitlines():
                    if "MemTotal:" in line:
                        try:
                            info["ram_total_mb"] = int(line.split()[1]) // 1024
                        except (ValueError, IndexError):
                            pass
                        break

            # GPU 信息（尝试从 dumpsys gpu 获取 GPU 型号）
            try:
                gpu_out = self._run_command(["-s", device_id, "shell", "dumpsys", "gpu"], timeout=10)
                if gpu_out:
                    for line in gpu_out.splitlines():
                        if "GLES:" in line or "glRenderer" in line.lower():
                            info["gpu_info"] = line.strip()
                            break
                    if not info["gpu_info"]:
                        # 尝试从 ro.hardware.egl 推断
                        egl = self._run_command(["-s", device_id, "shell", "getprop", "ro.hardware.egl"], timeout=5)
                        if egl:
                            info["gpu_info"] = egl
            except Exception:
                pass

            # 内核版本
            try:
                kernel = self._run_command(["-s", device_id, "shell", "cat", "/proc/version"], timeout=5)
                if kernel:
                    info["kernel_version"] = kernel.strip()[:120]
            except Exception:
                pass

        except Exception:
            pass
        return info

    def get_android_version(self, device_id: str) -> str:
        """获取安卓版本"""
        version = self._run_command(["-s", device_id, "shell", "getprop", "ro.build.version.release"])
        return version if version else "未知版本"

    def get_current_package(self, device_id: str) -> Optional[str]:
        """
        获取当前前台应用包名，使用多种策略兼容不同安卓版本和厂商ROM：
        1. dumpsys window windows → mCurrentFocus / mFocusedApp
        2. dumpsys activity activities → mResumedActivity / topResumedActivity
        3. dumpsys activity recents → 最近活动
        """
        # 策略1: dumpsys window windows（最常用，但格式因厂商而异）
        try:
            output = self._run_command(
                ["-s", device_id, "shell", "dumpsys", "window", "windows"]
            )
            if output:
                pkg = self._extract_package_from_window(output)
                if pkg:
                    return pkg
        except Exception:
            pass

        # 策略2: dumpsys activity activities（Android 10+ 更可靠）
        try:
            output = self._run_command(
                ["-s", device_id, "shell", "dumpsys", "activity", "activities"]
            )
            if output:
                pkg = self._extract_package_from_activity(output)
                if pkg:
                    return pkg
        except Exception:
            pass

        # 策略3: dumpsys activity recents（兜底）
        try:
            output = self._run_command(
                ["-s", device_id, "shell", "dumpsys", "activity", "recents"]
            )
            if output:
                pkg = self._extract_package_from_recents(output)
                if pkg:
                    return pkg
        except Exception:
            pass

        return None

    @staticmethod
    def _extract_package_from_window(output: str) -> Optional[str]:
        """从 dumpsys window windows 输出中提取包名"""
        # 优先级最高的模式：IME 目标窗口（Android 14+ 高度可靠，输入法只对前台窗口生效）
        ime_patterns = [
            # imeLayeringTarget in display# 0 Window{xxx com.pkg/Activity}
            r'imeLayeringTarget\s+in\s+display#?\s*\d+\s+Window\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # imeInputTarget in display# 0 Window{xxx com.pkg/Activity}
            r'imeInputTarget\s+in\s+display#?\s*\d+\s+Window\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # imeControlTarget in display# 0 Window{xxx com.pkg/Activity}
            r'imeControlTarget\s+in\s+display#?\s*\d+\s+Window\{[^}]*\s+([a-zA-Z0-9_.]+)/',
        ]
        for p in ime_patterns:
            m = re.search(p, output)
            if m:
                pkg = m.group(1)
                if pkg not in ('android', 'com.android.systemui', 'com.android.phone',
                               'com.coloros.assistantscreen', 'com.oplus.games'):
                    return pkg

        # 常见焦点字段模式
        focus_patterns = [
            # mCurrentFocus=Window{abc u0 com.pkg/Activity}
            r'mCurrentFocus=Window\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # mCurrentFocus=Window{abc com.pkg/Activity}
            r'mCurrentFocus=Window\{\S+\s+([a-zA-Z0-9_.]+)/',
            # mFocusedApp=AppWindowToken{... com.pkg/Activity}
            r'mFocusedApp=AppWindowToken\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # mFocusedApp=ActivityRecord{... com.pkg/Activity}
            r'mFocusedApp=ActivityRecord\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # mFocusedApp=com.pkg/Activity (部分ROM简化格式)
            r'mFocusedApp=([a-zA-Z0-9_.]+)/',
            # mObscuringWindow=Window{... com.pkg/...} (Android 12+)
            r'mObscuringWindow=Window\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # 通用：从包含 mCurrentFocus 的行中提取任意包名
            r'mCurrentFocus=.*?\b([a-z]{2,}\.[a-zA-Z0-9_.]+)/',
        ]
        for pattern in focus_patterns:
            match = re.search(pattern, output)
            if match:
                pkg = match.group(1)
                if pkg not in ('android', 'com.android.systemui', 'com.android.phone'):
                    return pkg

        # 最后兜底：从 Window #N 列表中提取 z-order 最靠后的非系统 Window
        # Window 列表一般是按 z-order 排列（系统窗口在前，应用窗口在后），选一个编号较小的应用窗口
        windows = re.findall(
            r'Window\s+#\d+\s+Window\{[^\}]*\s+([a-z]{2,}\.[a-zA-Z0-9_.]+)/[^\s]+\}',
            output
        )
        if windows:
            # 过滤系统应用
            for pkg in reversed(windows):  # 倒序，优先选z-order更高的
                if pkg not in ('android', 'com.android.systemui', 'com.android.phone',
                               'com.android.launcher', 'com.android.launcher3',
                               'com.coloros.assistantscreen', 'com.oplus.games',
                               'com.android.wallpaper.livepicker',
                               'com.android.systemui.wallpapers'):
                    return pkg
            # 所有窗口都是系统的，返回第一个
            return windows[-1]

        # 如果只匹配到系统UI，返回它（总比没有好）
        for pattern in focus_patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _extract_package_from_activity(output: str) -> Optional[str]:
        """从 dumpsys activity activities 输出中提取包名"""
        patterns = [
            # topResumedActivity=ActivityRecord{... com.pkg/Activity}
            r'topResumedActivity=ActivityRecord\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # mResumedActivity: ActivityRecord{... com.pkg/Activity}
            r'mResumedActivity[:\s]+ActivityRecord\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # ResumedActivity: ActivityRecord{... com.pkg/Activity}
            r'ResumedActivity[:\s]+ActivityRecord\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # topActivity=ActivityRecord{... com.pkg/Activity}
            r'topActivity=ActivityRecord\{[^}]*\s+([a-zA-Z0-9_.]+)/',
            # mLastPausedActivity: ActivityRecord{... com.pkg/Activity}
            r'mLastPausedActivity[:\s]+ActivityRecord\{[^}]*\s+([a-zA-Z0-9_.]+)/',
        ]
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                pkg = match.group(1)
                if pkg not in ('android', 'com.android.systemui', 'com.android.phone'):
                    return pkg
        return None

    @staticmethod
    def _extract_package_from_recents(output: str) -> Optional[str]:
        """从 dumpsys activity recents 输出中提取包名"""
        # Recent #0: TaskRecord{... #N com.pkg/Activity ...}
        # 匹配最近一条记录
        matches = re.findall(
            r'Recent\s+#\d+:.*?\b([a-z]{2,}\.[a-zA-Z0-9_.]+)/',
            output
        )
        if matches:
            # 过滤系统应用
            for pkg in matches:
                if pkg not in ('android', 'com.android.systemui', 'com.android.phone',
                               'com.android.launcher', 'com.android.launcher3'):
                    return pkg
            return matches[0]
        return None

    def get_installed_packages(self, device_id: str) -> List[str]:
        """获取已安装的第三方应用包名列表"""
        output = self._run_command(["-s", device_id, "shell", "pm", "list", "packages", "-3"])
        packages = []
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line[len("package:"):])
        return sorted(packages)

    def reset_gfxinfo(self, device_id: str, package_name: str) -> None:
        """重置gfxinfo数据"""
        self._run_command(
            ["-s", device_id, "shell", "dumpsys", "gfxinfo", package_name, "reset"]
        )

    def get_gfxinfo(self, device_id: str, package_name: str) -> str:
        """获取应用的gfxinfo原始数据"""
        return self._run_command(
            ["-s", device_id, "shell", "dumpsys", "gfxinfo", package_name]
        )

    # ===== SurfaceFlinger 帧计数方案（Android 12+ 游戏SurfaceView兼容）=====

    def get_sf_frame_number(self, device_id: str, package_name: str) -> Optional[int]:
        """
        从 SurfaceFlinger 输出中提取指定应用 SurfaceView 的当前帧编号。
        优化版：优先使用设备端 grep 只传输相关行，大幅减少传输量和耗时。
        """
        pkg_pattern = package_name.replace(".", r"\.")

        # 快速路径：用设备端 grep 只提取相关行（从5秒降到<1秒）
        try:
            # grep -A2 找到 SurfaceView 行后2行内的 frame= 字段
            output = self._run_command(
                ["-s", device_id, "shell",
                 "dumpsys SurfaceFlinger | grep -i -A2 'SurfaceView' | grep 'frame='"],
                timeout=10
            )
            if output:
                # 取第一行包含 frame= 的
                for line in output.splitlines():
                    m = re.search(r'frame=(\d+)', line)
                    if m:
                        return int(m.group(1))
        except Exception:
            pass

        # 回退路径：全量 dumpsys SurfaceFlinger + Python 端解析
        try:
            output = self._run_command(
                ["-s", device_id, "shell", "dumpsys", "SurfaceFlinger"],
                timeout=15
            )
            # 先找目标包的 SurfaceView 层，再在其后续行找 frame=
            in_target_layer = False
            for line in output.splitlines():
                if 'SurfaceView' in line and re.search(pkg_pattern, line):
                    in_target_layer = True
                if in_target_layer and 'frame=' in line:
                    m = re.search(r'frame=(\d+)', line)
                    if m:
                        return int(m.group(1))

            # 兜底：任何 SurfaceView 的 frame=
            in_sv = False
            for line in output.splitlines():
                if 'SurfaceView' in line:
                    in_sv = True
                if in_sv and 'frame=' in line:
                    m = re.search(r'frame=(\d+)', line)
                    if m:
                        return int(m.group(1))
        except Exception:
            pass

        return None

    def get_sf_refresh_rate(self, device_id: str) -> Optional[float]:
        """从 SurfaceFlinger 获取当前屏幕刷新率（Hz）"""
        try:
            output = self._run_command(
                ["-s", device_id, "shell", "dumpsys", "SurfaceFlinger"]
            )
            # 查找 vsync_period 行（纳秒）
            for line in output.splitlines():
                if 'vsync_period' in line:
                    m = re.search(r'vsync_period\s+(\d+)', line)
                    if m:
                        ns = int(m.group(1))
                        if ns > 0:
                            return round(1000000000.0 / ns, 1)
            # 兜底：查找 active config 行
            for line in output.splitlines():
                if 'active config' in line.lower():
                    m = re.search(r'(\d+\.?\d*)\s*Hz', line)
                    if m:
                        return float(m.group(1))
            return None
        except Exception:
            return None

    # ==================== CPU / GPU 硬件监控 ====================

    def get_cpu_freqs(self, device_id: str) -> list:
        """
        获取所有 CPU 集群的当前频率和最大频率，并标记超大核（Prime）集群。
        返回: [{"cluster": "policy0", "cur_mhz": 1152.0, "max_mhz": 3532.8,
                "related_cpus": "0-3", "is_prime": False}, ...]
        """
        result = []
        try:
            output = self._run_command(
                ["-s", device_id, "shell", "ls", "/sys/devices/system/cpu/cpufreq/"]
            )
            policies = [l.strip() for l in output.splitlines() if "policy" in l]
            for p in policies:
                # 用一条命令同时读取 cur_freq / max_freq / related_cpus，减少 ADB 往返
                combined = self._run_command(
                    ["-s", device_id, "shell",
                     f"cat /sys/devices/system/cpu/cpufreq/{p}/scaling_cur_freq 2>/dev/null;"
                     f"echo '|';"
                     f"cat /sys/devices/system/cpu/cpufreq/{p}/cpuinfo_max_freq 2>/dev/null;"
                     f"echo '|';"
                     f"cat /sys/devices/system/cpu/cpufreq/{p}/related_cpus 2>/dev/null"]
                )
                parts = combined.split("|") if combined else []
                cur_str = parts[0].strip() if len(parts) > 0 else ""
                max_str = parts[1].strip() if len(parts) > 1 else ""
                related = parts[2].strip() if len(parts) > 2 else ""
                try:
                    cur_mhz = int(cur_str) / 1000.0
                except (ValueError, AttributeError):
                    cur_mhz = 0.0
                try:
                    max_mhz = int(max_str) / 1000.0
                except (ValueError, AttributeError):
                    max_mhz = 0.0
                if max_mhz > 0:
                    result.append({
                        "cluster": p,
                        "cur_mhz": round(cur_mhz, 1),
                        "max_mhz": round(max_mhz, 1),
                        "related_cpus": related,
                        "is_prime": False,
                    })
            # 标记超大核（max_mhz 最大的集群为 Prime）
            if result:
                prime_idx = max(range(len(result)), key=lambda i: result[i]["max_mhz"])
                result[prime_idx]["is_prime"] = True
        except Exception:
            pass
        return result

    def get_gpu_freq(self, device_id: str) -> dict:
        """
        获取 GPU 当前频率和最大频率（MHz）。
        尝试多种 sysfs 路径兼容高通 Adreno (kgsl-3d0) / ARM Mali。
        Android 16+ 可能因 SELinux 限制无法读取，此时 accessible=False。
        返回: {"cur_mhz": 0.0, "max_mhz": 0.0, "available_mhz": [], "accessible": False}
        """
        result = {"cur_mhz": 0.0, "max_mhz": 0.0, "available_mhz": [], "accessible": False}
        try:
            # 当前频率：依次尝试 kgsl gpuclk / devfreq cur_freq / Mali clock
            out = self._run_command(["-s", device_id, "shell",
                "for f in /sys/class/kgsl/kgsl-3d0/gpuclk "
                "/sys/class/kgsl/kgsl-3d0/devfreq/cur_freq "
                "/sys/class/misc/mali0/device/clock; do "
                "v=$(cat $f 2>/dev/null) && [ -n \"$v\" ] && echo $v && break; done"])
            if out:
                try:
                    val = int(out.strip().split()[0])
                    if val > 1000000:
                        result["cur_mhz"] = round(val / 1000000.0, 1)
                    elif val > 1000:
                        result["cur_mhz"] = round(val / 1000.0, 1)
                    else:
                        result["cur_mhz"] = round(val, 1)
                except (ValueError, IndexError, TypeError):
                    pass

            # 最大频率
            out = self._run_command(["-s", device_id, "shell",
                "for f in /sys/class/kgsl/kgsl-3d0/max_gpuclk "
                "/sys/class/kgsl/kgsl-3d0/devfreq/max_freq "
                "/sys/class/misc/mali0/device/max_clock; do "
                "v=$(cat $f 2>/dev/null) && [ -n \"$v\" ] && echo $v && break; done"])
            if out:
                try:
                    val = int(out.strip().split()[0])
                    if val > 1000000:
                        result["max_mhz"] = round(val / 1000000.0, 1)
                    elif val > 1000:
                        result["max_mhz"] = round(val / 1000.0, 1)
                    else:
                        result["max_mhz"] = round(val, 1)
                except (ValueError, IndexError, TypeError):
                    pass

            # 可用频率档位
            out = self._run_command(["-s", device_id, "shell",
                "for f in /sys/class/kgsl/kgsl-3d0/gpu_available_frequencies "
                "/sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies; do "
                "v=$(cat $f 2>/dev/null) && [ -n \"$v\" ] && echo $v && break; done"])
            if out:
                try:
                    freqs = []
                    for token in out.strip().split():
                        val = int(token)
                        if val > 1000000:
                            freqs.append(round(val / 1000000.0, 1))
                        elif val > 1000:
                            freqs.append(round(val / 1000.0, 1))
                        else:
                            freqs.append(round(val, 1))
                    if freqs:
                        result["available_mhz"] = sorted(freqs)
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

        # 关键修复：只有当 cur_mhz>0 AND max_mhz>0 AND cur<=max+合理小误差时才算可读。
        # 否则：
        #   - max=0 会在 UI 侧除以 0 → 进度条 0 或崩溃；
        #   - cur>max（单位读取不一致 / 同一文件 cur=max 只读了一次）会导致 100%。
        cur = result["cur_mhz"]
        mx = result["max_mhz"]
        if cur > 0 and mx > 0 and cur <= mx * 1.1:
            # 如果可用频率档位存在，用档位最大值校准 max，防止 max 路径误读
            avail = result.get("available_mhz") or []
            if avail and max(avail) > 0 and abs(mx - max(avail)) / max(avail) > 0.15:
                result["max_mhz"] = float(max(avail))
            result["accessible"] = True
        else:
            # 任意一项不满足就视为不可读，避免 UI 进度条出现 100% 夹取
            result["accessible"] = False
            # 清零以便后续走警告分支
            if result["max_mhz"] <= 0 or result["cur_mhz"] <= 0:
                pass
        return result

    def get_cpu_usage(self, device_id: str) -> float:
        """
        获取 CPU 总体利用率（百分比）。
        通过两次读取 /proc/stat 计算差值。
        """
        def _read_stat():
            out = self._run_command(["-s", device_id, "shell", "cat", "/proc/stat"])
            if not out:
                return None
            first = out.splitlines()[0]
            parts = first.split()[1:]
            return [int(x) for x in parts[:4]]  # user, nice, system, idle

        s1 = _read_stat()
        if not s1:
            return 0.0
        time.sleep(0.2)
        s2 = _read_stat()
        if not s2:
            return 0.0

        total1 = sum(s1)
        total2 = sum(s2)
        idle1 = s1[3]
        idle2 = s2[3]
        total_delta = total2 - total1
        idle_delta = idle2 - idle1
        if total_delta <= 0:
            return 0.0
        usage = (1.0 - idle_delta / total_delta) * 100.0
        return round(usage, 1)

    def get_cpu_temp(self, device_id: str) -> float:
        """获取 CPU 核心温度（°C），只取 type 含 "cpu" 的 thermal_zone，过滤电池/PMIC 等"""
        try:
            thermal_out = self.raw_shell(device_id,
                'for z in /sys/class/thermal/thermal_zone*; do '
                't=$(cat $z/type 2>/dev/null); v=$(cat $z/temp 2>/dev/null); '
                'echo "$t $v"; done', timeout=3)
            cpu_temps = []
            for line in (thermal_out or "").splitlines():
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                zone_type = parts[0].lower()
                # 只取 CPU 核心温度，过滤掉电池(bcl/vbat/ibat)、PMIC、skin 等
                if "cpu" not in zone_type:
                    continue
                try:
                    raw = int(parts[1])
                    if raw > 1000:
                        cpu_temps.append(raw / 1000.0)
                    elif raw > 20:
                        cpu_temps.append(float(raw))
                except (ValueError, TypeError):
                    continue
            if cpu_temps:
                return round(max(cpu_temps), 1)
        except Exception:
            pass
        # 回退：逐个读取 thermal_zone0-9
        for i in range(10):
            out = self._run_command(
                ["-s", device_id, "shell", "cat", f"/sys/class/thermal/thermal_zone{i}/temp"]
            )
            if not out:
                continue
            out = out.strip()
            if "No such file" in out:
                continue
            try:
                raw = int(out)
                if raw > 0:
                    # 有些设备返回毫度（如 49800 = 49.8°C），有些直接返回度
                    if raw > 1000:
                        return round(raw / 1000.0, 1)
                    elif raw > 20:
                        return float(raw)
            except (ValueError, TypeError):
                continue
        return 0.0

    def get_gpu_info(self, device_id: str, package_name: str = "") -> dict:
        """
        获取 GPU 渲染信息（频率在 Android 16 上被 SELinux 限制，改用 GPU 渲染百分位数据）。
        返回: {"gpu_p50_ms": 1.0, "gpu_p90_ms": 1.0, "gpu_p95_ms": 1.0, "gpu_p99_ms": 1.0,
               "gpu_mem_total_mb": 0, "gpu_mem_proc_mb": 0}
        """
        info = {"gpu_p50_ms": 0.0, "gpu_p90_ms": 0.0, "gpu_p95_ms": 0.0, "gpu_p99_ms": 0.0,
                "gpu_mem_total_mb": 0, "gpu_mem_proc_mb": 0}
        try:
            # 从 gfxinfo 获取 GPU 渲染时间百分位
            target_pkg = package_name or ""
            gfxinfo = self._run_command(
                ["-s", device_id, "shell", "dumpsys", "gfxinfo", target_pkg]
            )
            for line in gfxinfo.splitlines():
                line = line.strip()
                if "50th gpu percentile:" in line:
                    info["gpu_p50_ms"] = float(line.split(":")[-1].replace("ms", "").strip())
                elif "90th gpu percentile:" in line:
                    info["gpu_p90_ms"] = float(line.split(":")[-1].replace("ms", "").strip())
                elif "95th gpu percentile:" in line:
                    info["gpu_p95_ms"] = float(line.split(":")[-1].replace("ms", "").strip())
                elif "99th gpu percentile:" in line:
                    info["gpu_p99_ms"] = float(line.split(":")[-1].replace("ms", "").strip())
        except Exception:
            pass

        # GPU 内存使用（从 dumpsys gpu 获取）
        try:
            gpu_out = self._run_command(["-s", device_id, "shell", "dumpsys", "gpu"])
            for line in gpu_out.splitlines():
                if "Global total:" in line:
                    val = line.split(":")[-1].strip()
                    info["gpu_mem_total_mb"] = int(val) // (1024 * 1024)
                    break
        except Exception:
            pass

        return info

    def get_mem_info(self, device_id: str) -> dict:
        """获取内存使用信息"""
        result = {"total_mb": 0, "available_mb": 0, "used_pct": 0.0}
        try:
            out = self._run_command(["-s", device_id, "shell", "cat", "/proc/meminfo"])
            for line in out.splitlines():
                if "MemTotal:" in line:
                    result["total_mb"] = int(line.split()[1]) // 1024
                elif "MemAvailable:" in line:
                    result["available_mb"] = int(line.split()[1]) // 1024
            if result["total_mb"] > 0:
                used = result["total_mb"] - result["available_mb"]
                result["used_pct"] = round(used / result["total_mb"] * 100, 1)
        except Exception:
            pass
        return result

    def parse_frame_durations(self, gfxinfo_output: str) -> List[float]:
        """
        解析gfxinfo输出，提取帧渲染时间（毫秒）
        支持Android 6.0+的gfxinfo格式
        """
        frame_durations = []
        lines = gfxinfo_output.split("\n")

        # 查找---PROFILEDATA---标记后的数据
        in_profile_data = False
        header_found = False
        column_indices = {}

        for line in lines:
            line = line.strip()
            if "---PROFILEDATA---" in line:
                if not in_profile_data:
                    in_profile_data = True
                    continue
                else:
                    break  # 遇到结束标记

            if not in_profile_data:
                continue

            if not line:
                continue

            # 解析表头
            if not header_found:
                if "Flags" in line or "IntendedVsync" in line:
                    headers = line.split(",")
                    for i, h in enumerate(headers):
                        column_indices[h.strip()] = i
                    header_found = True
                continue

            # 解析帧数据
            values = line.split(",")
            if len(values) < 4:
                continue

            try:
                # 尝试从多个字段计算总帧时间
                total_duration_ms = 0.0

                # 方法1: 使用 FrameCompleted - IntendedVsync
                if "IntendedVsync" in column_indices and "FrameCompleted" in column_indices:
                    intended_idx = column_indices["IntendedVsync"]
                    completed_idx = column_indices["FrameCompleted"]
                    if intended_idx < len(values) and completed_idx < len(values):
                        start = float(values[intended_idx])
                        end = float(values[completed_idx])
                        if end > start > 0:
                            # 纳秒转毫秒
                            total_duration_ms = (end - start) / 1000000.0

                # 方法2: 累加各阶段时间 (旧版格式)
                if total_duration_ms <= 0 or total_duration_ms > 1000:
                    # Draw, Prepare, Process, Execute
                    stages = ["Draw", "Prepare", "Process", "Execute"]
                    stage_sum = 0.0
                    valid = True
                    for stage in stages:
                        if stage in column_indices:
                            idx = column_indices[stage]
                            if idx < len(values):
                                try:
                                    stage_sum += float(values[idx])
                                except (ValueError, IndexError):
                                    valid = False
                                    break
                    if valid and stage_sum > 0:
                        total_duration_ms = stage_sum

                # 过滤异常值
                if 0 < total_duration_ms < 500:
                    frame_durations.append(total_duration_ms)

            except (ValueError, IndexError):
                continue

        # 如果PROFILEDATA解析失败，尝试解析旧格式的帧数统计
        if not frame_durations:
            frame_durations = self._parse_legacy_format(gfxinfo_output)

        return frame_durations

    def _parse_legacy_format(self, gfxinfo_output: str) -> List[float]:
        """解析旧版gfxinfo格式（没有PROFILEDATA标记）"""
        frame_durations = []
        lines = gfxinfo_output.split("\n")

        # 查找 "Total frames rendered:" 获取总帧数
        total_frames = 0
        janky_frames = 0
        frame_time = 16.67  # 默认60fps帧时间

        for line in lines:
            line = line.strip()
            if line.startswith("Total frames rendered:"):
                try:
                    total_frames = int(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("Janky frames:"):
                try:
                    janky_str = line.split(":")[1].strip()
                    janky_frames = int(janky_str.split("(")[0].strip())
                except ValueError:
                    pass

        # 如果只有统计数据，生成近似的帧时间序列
        if total_frames > 0:
            # 假设大部分帧是正常的，部分是卡顿的
            normal_frames = total_frames - janky_frames
            for _ in range(normal_frames):
                frame_durations.append(frame_time)
            for _ in range(janky_frames):
                # 卡顿帧假设为2-5倍正常时间
                frame_durations.append(frame_time * 3)

        return frame_durations

    def get_battery_power(self, device_id: str) -> dict:
        """
        读取安卓设备电池功率相关信息。
        采样优先级：sysfs（battery/bms/main/maxim/...） → uevent → dumpsys batteryproperties
                → dumpsys battery current_now → dumpsys batterystats。
        返回 dict: {
            "voltage_mv": int,       # 电池电压 (毫伏)，失败为 0
            "current_ua": int,       # 瞬时电流 (微安)，放电为负值 / 充电为正值，失败为 0
            "power_mw": float,       # 估算瞬时功率 (毫瓦)
            "temp": float,           # 电池温度 (°C)，失败为 0
            "capacity_pct": int,     # 电池电量百分比，失败为 0
            "status": str,           # discharging/charging/not_charging/full/unknown
            "raw": str,              # dumpsys battery 原始输出（调试用）
            "source": str,           # 电流/电压最终来源（调试用）
        }
        """
        result = {
            "voltage_mv": 0, "current_ua": 0, "power_mw": 0.0,
            "temp": 0.0, "capacity_pct": 0, "status": "unknown", "raw": "",
            "source": "",
        }

        def _conv_current(raw_val, src_name):
            """把任意字符串形式的电流值归一化为 μA（放电负值/充电正值）；失败返回 0"""
            if raw_val is None:
                return 0, ""
            s = str(raw_val).strip()
            if not s:
                return 0, ""
            sign = 1
            low = s.lower()
            # 处理带单位后缀
            for unit in ("microamp", "microamps", "μa", "ua"):
                if low.endswith(unit):
                    s = s[: -len(unit)].strip()
                    break
            else:
                for unit in ("milliamp", "milliamps", "ma"):
                    if low.endswith(unit):
                        s = s[: -len(unit)].strip()
                        sign = 1000  # mA -> μA
                        break
            # 处理符号
            if s.startswith("-"):
                s2 = "-"
                s = s[1:]
            elif s.startswith("+"):
                s2 = ""
                s = s[1:]
            else:
                s2 = ""
            # 去掉非数字
            digits = re.match(r"[0-9]+", s)
            if not digits:
                return 0, ""
            try:
                cv = int(s2 + digits.group(0))
            except ValueError:
                return 0, ""
            # 单位校正：μA 合理区间 |x| ∈ [3_000, 6_000_000]；若太小则认为是 mA 补 1000
            acv = abs(cv)
            if acv == 0:
                return 0, ""
            if acv < 3000:          # 大概率是 mA
                cv *= 1000
            elif acv > 10_000_000:    # 可能是 nA，除 1000
                cv //= 1000
            return cv, src_name

        def _conv_voltage(raw_val, src_name):
            """把任意字符串形式的电压归一化为 mV；失败返回 0"""
            if raw_val is None:
                return 0, ""
            s = str(raw_val).strip()
            if not s:
                return 0, ""
            low = s.lower()
            mul = 1
            for unit in ("microvolt", "microvolts", "μv", "uv"):
                if low.endswith(unit):
                    s = s[: -len(unit)].strip()
                    mul = 0.001  # μV -> mV
                    break
            else:
                for unit in ("millivolt", "millivolts", "mv"):
                    if low.endswith(unit):
                        s = s[: -len(unit)].strip()
                        mul = 1
                        break
                else:
                    for unit in ("volt", "volts", "v"):
                        if low.endswith(unit):
                            s = s[: -len(unit)].strip()
                            mul = 1000
                            break
            digits = re.match(r"-?[0-9]+", s)
            if not digits:
                return 0, ""
            try:
                v = float(digits.group(0))
            except ValueError:
                return 0, ""
            v = v * mul
            # 启发式单位校正（纯数字无单位时）
            if mul == 1 and v > 100:
                if v > 1000000:         # μV
                    v = v / 1000
                elif 1000 < v < 100000:  # mV，无需改
                    pass
                elif 100 < v < 1000:     # 可能是已 mV 或者 100V 异常，取 mV
                    pass
                elif 2 < v < 6:          # V
                    v = v * 1000
                else:
                    return 0, ""
            return int(round(v)), src_name

        try:
            # =========================================================
            # 0. 先探测设备实际存在的 power_supply 节点（避免盲猜路径）
            # =========================================================
            try:
                supply_dirs_raw = self.raw_shell(
                    device_id,
                    "ls -1 /sys/class/power_supply/ 2>/dev/null || true",
                    timeout=5,
                )
                supply_dirs = [x for x in supply_dirs_raw.splitlines() if x.strip()]
            except (TimeoutError, RuntimeError):
                supply_dirs = []
            _logger.debug("get_battery_power: power_supply 节点=%s", supply_dirs)

            # =========================================================
            # 1. dumpsys battery 读取通用属性（电压/温度/电量/充电状态）
            # =========================================================
            try:
                raw = self._run_command(["-s", device_id, "shell", "dumpsys", "battery"], timeout=8)
            except Exception as e:
                _logger.debug("get_battery_power: dumpsys battery 失败: %s", e)
                raw = ""
            result["raw"] = raw
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("level:"):
                    try:
                        result["capacity_pct"] = int(line.split(":", 1)[1].strip())
                    except (TypeError, ValueError):
                        pass
                elif line.startswith("voltage:"):
                    try:
                        val = line.split(":", 1)[1].strip()
                        vv, sn = _conv_voltage(val, "dumpsys_battery_voltage")
                        if vv > 0:
                            result["voltage_mv"] = vv
                            if not result["source"]:
                                result["source"] = sn
                    except Exception:
                        pass
                elif line.startswith("temperature:"):
                    try:
                        t = float(line.split(":", 1)[1].strip())
                        if t > 100 or t < -50:
                            t = t / 10.0
                        result["temp"] = round(t, 1)
                    except (TypeError, ValueError):
                        pass
                elif line.startswith("status:"):
                    try:
                        v = line.split(":", 1)[1].strip().lower()
                        if "discharging" in v or v == "3":
                            result["status"] = "discharging"
                        elif "not charging" in v or v == "4":
                            result["status"] = "not_charging"
                        elif "charging" in v or v == "2":
                            result["status"] = "charging"
                        elif "full" in v or v == "5":
                            result["status"] = "full"
                        else:
                            result["status"] = "unknown"
                    except Exception:
                        pass

            # =========================================================
            # 2. sysfs 批量读取（仅基于实际探测到的节点）+ 通用字段
            #    一条 shell 命令 cat 多个文件，减少 roundtrip
            # =========================================================
            if supply_dirs and (result["current_ua"] == 0 or result["voltage_mv"] <= 0):
                candidates = []
                for d in supply_dirs:
                    for f in ("current_now", "current_avg",
                              "BatteryAverageCurrent", "battery_current"):
                        candidates.append(f"/sys/class/power_supply/{d}/{f}")
                    for f in ("voltage_now", "voltage_avg", "battery_voltage"):
                        candidates.append(f"/sys/class/power_supply/{d}/{f}")
                    candidates.append(f"/sys/class/power_supply/{d}/uevent")
                # 一条命令用 for 循环打印每个文件的 PATH=VALUE 或 PATH= (若读不到)
                shell_script = (
                    "for f in " + " ".join(candidates) + "; do "
                    "v=$(cat \"$f\" 2>/dev/null); echo \"$f=$v\"; done"
                )
                try:
                    batch_raw = self.raw_shell(device_id, shell_script, timeout=8)
                except Exception as e:
                    _logger.debug("get_battery_power: sysfs batch 失败: %s", e)
                    batch_raw = ""
                uev_accum = {}  # path -> {KEY=VAL}
                for line in batch_raw.splitlines():
                    if "=" not in line:
                        continue
                    path, val = line.split("=", 1)
                    path = path.strip()
                    val = val.strip()
                    if path.endswith("/uevent"):
                        if val and "POWER_SUPPLY_" in val:
                            # 单行紧凑 uevent 少见，但做个防护
                            pass
                        continue
                    fname = path.rsplit("/", 1)[-1]
                    fname_low = fname.lower()
                    if fname_low in ("current_now", "current_avg",
                                     "batteryaveragecurrent", "battery_current"):
                        if result["current_ua"] != 0 or not val or not re.search(r"\d", val):
                            continue
                        cv, sn = _conv_current(val, f"sysfs:{path}")
                        if cv != 0:
                            result["current_ua"] = cv
                            result["source"] = sn
                    elif fname_low in ("voltage_now", "voltage_avg", "battery_voltage"):
                        if result["voltage_mv"] > 0 or not val or not re.search(r"\d", val):
                            continue
                        vv, sn = _conv_voltage(val, f"sysfs:{path}")
                        if vv > 0:
                            result["voltage_mv"] = vv
                            if not result["source"]:
                                result["source"] = sn
                # 单独把 uevent 文件读出来解析（上面 for 循环每行一个的模式不适用 uevent 多行内容）
                if result["current_ua"] == 0 or result["voltage_mv"] <= 0:
                    for d in supply_dirs:
                        if result["current_ua"] != 0 and result["voltage_mv"] > 0:
                            break
                        uev_path = f"/sys/class/power_supply/{d}/uevent"
                        try:
                            uev = self.raw_shell(device_id, f"cat {uev_path} 2>/dev/null || true", timeout=5)
                        except Exception:
                            uev = ""
                        if not uev or "POWER_SUPPLY_" not in uev:
                            continue
                        for line in uev.splitlines():
                            line = line.strip()
                            if line.startswith("POWER_SUPPLY_CURRENT_NOW=") and result["current_ua"] == 0:
                                cv, sn = _conv_current(line.split("=", 1)[1].strip(), f"uevent:{uev_path}")
                                if cv != 0:
                                    result["current_ua"] = cv
                                    result["source"] = sn
                            elif line.startswith("POWER_SUPPLY_VOLTAGE_NOW=") and result["voltage_mv"] <= 0:
                                vv, sn = _conv_voltage(line.split("=", 1)[1].strip(), f"uevent:{uev_path}")
                                if vv > 0:
                                    result["voltage_mv"] = vv
                                    if not result["source"]:
                                        result["source"] = sn
                            elif line.startswith("POWER_SUPPLY_TEMP=") and result["temp"] == 0.0:
                                try:
                                    t = float(line.split("=", 1)[1].strip())
                                    if t > 100 or t < -50:
                                        t = t / 10.0
                                    result["temp"] = round(t, 1)
                                except (TypeError, ValueError):
                                    pass

            # =========================================================
            # 3. dumpsys batteryproperties（高通平台）
            # =========================================================
            if result["current_ua"] == 0 or result["voltage_mv"] <= 0:
                try:
                    bp = self._run_command(
                        ["-s", device_id, "shell", "dumpsys", "batteryproperties"], timeout=8
                    )
                except Exception as e:
                    _logger.debug("get_battery_power: dumpsys batteryproperties 失败: %s", e)
                    bp = ""
                if bp:
                    for line in bp.splitlines():
                        ls = line.strip().lower()
                        kv = ls.split(":", 1) if ":" in ls else None
                        if not kv:
                            continue
                        val = kv[1].strip()
                        if (("dc current" in ls or ls.startswith("current now")
                                or ls.startswith("current:")) and result["current_ua"] == 0):
                            cv, sn = _conv_current(val, f"batteryproperties:{kv[0].strip()}")
                            if cv != 0:
                                result["current_ua"] = cv
                                result["source"] = sn
                        elif (("dc voltage" in ls or ls.startswith("voltage:")) and result["voltage_mv"] <= 0):
                            vv, sn = _conv_voltage(val, f"batteryproperties:{kv[0].strip()}")
                            if vv > 0:
                                result["voltage_mv"] = vv
                                if not result["source"]:
                                    result["source"] = sn

            # =========================================================
            # 4. dumpsys battery 内的 "current now:" / "current_avg:" 兜底
            # =========================================================
            if result["current_ua"] == 0 and raw:
                for line in raw.splitlines():
                    line_stripped = line.strip().lower()
                    if line_stripped.startswith("current now:") or line_stripped.startswith("current_avg:"):
                        val = line.split(":", 1)[1].strip()
                        cv, sn = _conv_current(val, f"dumpsys_battery:{line_stripped.split(':')[0]}")
                        if cv != 0:
                            result["current_ua"] = cv
                            result["source"] = sn
                            break

            # =========================================================
            # 5. dumpsys batterystats（Google 官方电流估算，兼容绝大多数未root机型）
            #    读取 "Estimated power use" 下总 mAh，或 "UID  uA" 行作为系统级电流
            # =========================================================
            if result["current_ua"] == 0:
                try:
                    bs = self._run_command(
                        ["-s", device_id, "shell", "dumpsys", "batterystats", "--charged"], timeout=10
                    )
                except Exception as e:
                    _logger.debug("get_battery_power: dumpsys batterystats 失败: %s", e)
                    bs = ""
                if bs:
                    # (a) 找 "UID  uA" 表中的合计（--charged 输出里以 "0:" 或 total 形式出现的系统级近似）
                    #     更简单：找第一行 "UID  uA" 之后所有数字求和
                    in_section = False
                    total_ua_pos = 0
                    total_ua_neg = 0
                    for line in bs.splitlines():
                        s = line.strip()
                        if s.lower().startswith("uid") and "ua" in s.lower():
                            in_section = True
                            continue
                        if in_section:
                            if not s or s.startswith("---") or not s[0].isdigit():
                                # 表结束
                                if total_ua_pos or total_ua_neg:
                                    break
                                continue
                            m = re.findall(r"-?\d+", s)
                            if m:
                                for num_s in m:
                                    try:
                                        n = int(num_s)
                                    except ValueError:
                                        continue
                                    if n > 0:
                                        total_ua_pos += n
                                    else:
                                        total_ua_neg += n
                    if result["current_ua"] == 0:
                        # 取绝对值大的一侧
                        if abs(total_ua_neg) > total_ua_pos and abs(total_ua_neg) > 10_000:
                            result["current_ua"] = total_ua_neg
                            result["source"] = "batterystats:UID_uA_sum"
                        elif total_ua_pos > 10_000:
                            result["current_ua"] = -total_ua_pos  # 放电视为负
                            result["source"] = "batterystats:UID_uA_sum"

            # =========================================================
            # 6. 最终计算功率
            # =========================================================
            current_ma = abs(result["current_ua"]) / 1000.0  # μA -> mA
            voltage_v = result["voltage_mv"] / 1000.0          # mV -> V
            if voltage_v <= 0:
                voltage_v = 3.9
            # 功率合理性范围保护：锂电池瞬时功率一般在 500 mW ~ 20,000 mW (20W) 之间
            power_mw = round(current_ma * voltage_v, 1)
            if 0 < power_mw < 100:
                # 过小，可能是电流单位没校正成功；置 0 避免错误显示
                power_mw = 0.0
                result["current_ua"] = 0
            elif power_mw > 100_000:
                power_mw = 0.0
                result["current_ua"] = 0
            result["power_mw"] = power_mw
            if not result["source"]:
                result["source"] = "none"
            _logger.debug(
                "get_battery_power 结果: current_ua=%d voltage_mv=%d power_mw=%.1f cap=%d%% status=%s temp=%.1f src=%s",
                result["current_ua"], result["voltage_mv"], result["power_mw"],
                result["capacity_pct"], result["status"], result["temp"], result["source"],
            )
        except Exception as e:
            _logger.debug("get_battery_power 异常: %s", e, exc_info=True)
            # 失败：字段保留默认 0
        return result
