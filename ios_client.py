"""
iOS 设备客户端 — 封装 pymobiledevice3 异步 API 为同步接口。

能力范围（受 Apple 系统限制）：
- 设备列表 / 设备信息 / 已安装 App：通过 lockdown，全 iOS 版本可用
- CPU 使用率 / 内存：通过 DVT Sysmontap，需挂载 DDI
- GPU 利用率：通过 DVT Graphics 服务，尽力解析
- FPS：通过 Graphics 服务的帧事件计数，不稳定时回退到屏幕刷新率

iOS 17+ 的 DVT 服务必须通过 RSD 隧道访问：
  - 需要用户先启动 tunneld 后台服务：sudo pymobiledevice3 remote tunneld
  - 代码通过 HTTP 127.0.0.1:49151 请求 tunneld 建立隧道，再通过 get_tunneld_device_by_udid
    获取 RemoteServiceDiscoveryService (RSD) 对象作为 LockdownServiceProvider 传入 DvtProvider。
"""

import asyncio
import os
import sys
import threading
import time
import logging
from typing import List, Optional, Tuple, Dict
from concurrent.futures import TimeoutError as FuturesTimeoutError

_logger = logging.getLogger("fps_tester.ios_client")

# Apple Silicon / A/M-series 芯片的页大小固定为 16KB
_APPLE_SILICON_PAGE_SIZE = 16384
# tunneld 后台默认监听地址
_TUNNELD_DEFAULT_ADDR = ("127.0.0.1", 49151)
_TUNNELD_HELLO_URL = f"http://{_TUNNELD_DEFAULT_ADDR[0]}:{_TUNNELD_DEFAULT_ADDR[1]}/hello"
_TUNNELD_START_TUNNEL_URL = f"http://{_TUNNELD_DEFAULT_ADDR[0]}:{_TUNNELD_DEFAULT_ADDR[1]}/start-tunnel"


# ==================== 芯片名称映射 ====================
# ProductType → 芯片名称
_CHIP_MAP = {
    # iPhone
    "iPhone14,2": "A15 Bionic", "iPhone14,3": "A15 Bionic",
    "iPhone14,4": "A15 Bionic", "iPhone14,5": "A15 Bionic",
    "iPhone14,7": "A14 Bionic", "iPhone14,8": "A14 Bionic",
    "iPhone15,2": "A16 Bionic", "iPhone15,3": "A16 Bionic",
    "iPhone15,4": "A14 Bionic", "iPhone15,5": "A14 Bionic",
    "iPhone16,1": "A17 Pro", "iPhone16,2": "A17 Pro",
    "iPhone16,3": "A16 Bionic", "iPhone16,4": "A16 Bionic",
    "iPhone17,1": "A18 Pro", "iPhone17,2": "A18 Pro",
    "iPhone17,3": "A18", "iPhone17,4": "A18",
    "iPhone17,5": "A18",
    # iPad
    "iPad13,1": "A14 Bionic", "iPad13,2": "A14 Bionic",
    "iPad13,4": "M1", "iPad13,5": "M1", "iPad13,6": "M1", "iPad13,7": "M1",
    "iPad13,8": "M1", "iPad13,9": "M1", "iPad13,10": "M1", "iPad13,11": "M1",
    "iPad14,1": "A15 Bionic", "iPad14,2": "A15 Bionic",
    "iPad14,3": "M2", "iPad14,4": "M2", "iPad14,5": "M2", "iPad14,6": "M2",
    "iPad14,8": "A14 Bionic", "iPad14,9": "A14 Bionic",
    "iPad14,10": "A16 Bionic", "iPad14,11": "A16 Bionic",
    "iPad15,3": "M2", "iPad15,4": "M2",
    "iPad15,6": "A16 Bionic", "iPad15,7": "A16 Bionic",
    "iPad16,3": "M3", "iPad16,4": "M3",
}


class IOSClient:
    """iOS 设备客户端，封装 pymobiledevice3 的异步 API 为同步接口"""

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def _run(self, coro, timeout: float = 30):
        """在后台事件循环中运行协程，阻塞等待结果"""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # ==================== 设备列表 ====================

    def get_devices(self) -> List[Tuple[str, str]]:
        """获取已连接的 iOS 设备列表 [(UDID, 状态), ...]"""
        try:
            return self._run(self._get_devices_async(), timeout=10)
        except Exception:
            return []

    async def _get_devices_async(self) -> List[Tuple[str, str]]:
        from pymobiledevice3.usbmux import select_devices_by_connection_type
        devices = await select_devices_by_connection_type("USB")
        return [(d.serial, "device") for d in devices]

    # ==================== 设备信息 ====================

    def get_device_info(self, udid: str) -> dict:
        """获取设备基础信息"""
        try:
            return self._run(self._get_device_info_async(udid), timeout=15)
        except Exception as e:
            return {"error": str(e), "udid": udid}

    async def _get_device_info_async(self, udid: str) -> dict:
        from pymobiledevice3.lockdown import create_using_usbmux
        lockdown = await create_using_usbmux(serial=udid, autopair=True)
        try:
            v = lockdown.all_values
            product_type = v.get("ProductType", "")
            chip_name = _CHIP_MAP.get(product_type, f"未知 (chip_id={lockdown.chip_id})")

            # 判断是否 ProMotion (120Hz)
            is_promotion = any(pt in product_type for pt in [
                "iPhone16,", "iPhone17,", "iPad13,4", "iPad13,5", "iPad13,6",
                "iPad13,7", "iPad13,8", "iPad13,9", "iPad13,10", "iPad13,11",
                "iPad14,3", "iPad14,4", "iPad14,5", "iPad14,6",
                "iPad15,3", "iPad15,4", "iPad16,3", "iPad16,4",
            ])
            refresh_rate = 120 if is_promotion else 60

            return {
                "brand": "Apple",
                "model": product_type,
                "display_name": str(lockdown.display_name or product_type),
                "device_name": str(v.get("DeviceName", "") or ""),
                "ios_version": str(lockdown.product_version or ""),
                "build_number": str(v.get("BuildVersion", "") or ""),
                "device_class": str(lockdown.device_class.value if hasattr(lockdown.device_class, "value") else (lockdown.device_class or "")),
                "udid": udid,
                "ecid": str(lockdown.ecid) if lockdown.ecid else "",
                "hardware_model": str(lockdown.hardware_model or ""),
                "chip_name": chip_name,
                "chip_id": int(lockdown.chip_id or 0),
                "cpu_cores": self._get_cpu_count(),
                "refresh_rate": refresh_rate,
                "cpu_abi": "arm64e",
                "platform": "iOS",
            }
        finally:
            await lockdown.close()

    @staticmethod
    def _get_cpu_count() -> int:
        import os
        return os.cpu_count() or 0

    # ==================== 已安装 App ====================

    def get_installed_apps(self, udid: str) -> List[str]:
        """获取已安装的用户 App 的 bundle ID 列表"""
        try:
            return self._run(self._get_apps_async(udid), timeout=20)
        except Exception:
            return []

    async def _get_apps_async(self, udid: str) -> List[str]:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.installation_proxy import InstallationProxyService
        lockdown = await create_using_usbmux(serial=udid, autopair=True)
        try:
            apps = await InstallationProxyService(lockdown=lockdown).get_apps(
                application_type="User", calculate_sizes=False)
            return sorted(apps.keys())
        finally:
            await lockdown.close()

    # ==================== 硬件监测会话 ====================

    def create_monitor(self, udid: str) -> "IOSMonitor":
        """创建持续监测会话（CPU 使用率 / 内存 / GPU）"""
        return IOSMonitor(self, udid)

    def create_fps_collector(self, udid: str, refresh_rate: int = 60) -> "IOSFPSCollector":
        """创建 FPS 采集器"""
        return IOSFPSCollector(self, udid, refresh_rate)

    # ==================== 前台应用识别 ====================

    # 系统守护进程黑名单（不可能是用户应用）
    _SYSTEM_PROCESSES = {
        "backboardd", "SpringBoard", "launchd", "kernel_task", "mediaserverd",
        "audiomxd", "mediaserverd", "DTServiceHub", "remotepairingdeviced",
        "identityservicesd", "wifid", "networkd", "bluetoothd", "configd",
        "locationd", "IMDPersistenceAgent", "thermalmonitord", "cloudd",
        "installd", "tccd", "sibd", "sysmond", "powerd", "logd", "fairplaydeviceidentityd",
        "appprotectiond", "mobiletimerd", "networkserviceproxy", "webbookmarksd",
        "coresymbolicationd", "homed", "gamecontrollerd", "bird", "spotlightknowledged.updater",
        "fmflocatord", "BTLEServer", "MTLCompilerService", "jetpackassetd",
        "generativeexperiencesd", "imagent", "ospredictiond", "axassetsd",
        "AssetCacheLocatorService", "extensionkitservice", "logd_helper",
        "findmybeaconingd", "mobiletimerd", "cfprefsd", "routined", "nanoapperased",
        "searchd", "dprivacyd", "rapportd", "sharingd", "bagmd", "storagekitd",
        "biometrickitd", "coreauthd", "trustd", "securityd", "keychaind",
        "UserManagementDaemon", "appleaccountd", "akd", "apsd", "distnoted",
        "lsd", "FontServicesDaemon", "iconservicesd", "messages-agent",
        "shortcutsd", "carkitd", "cdpd", "continuitycaptured", "deviceaccessd",
        "nanoregistryd", "nfcd", "passd", "partnerd", "phonecallbackd",
        "screentimed", "siri", "siriknowledged", "speechd", "timezoneupdated",
        "uiagentsd", "vmd", "watchdogd", "wirelessproxd", "accessoryupdaterd",
        "appstoreagentd", "itunescloudd", "itunesstored", "musicappd",
        "applefeedbackd", "commcenter", "CommCenter", "carkitservice",
        "diagnosticsd", "diskimagesiod", "fileproviderd", "mDNSResponder",
        "mediaremoted", "MediaRemote", "notifyd", "ptpd", "ptpdriver",
        "usbmuxd", "AppleMobileDeviceHelper",
    }

    def get_foreground_app(self, udid: str) -> Optional[Dict]:
        """获取 iOS 设备当前前台运行的应用信息。
        通过 Sysmontap 获取进程 CPU 使用率，取最高的用户应用。
        返回 {"name": str, "pid": int, "bundle_id": str} 或 None。
        需要 tunneld 已启动（iOS 17+）。
        """
        try:
            return self._run(self._get_foreground_app_async(udid), timeout=30)
        except Exception as e:
            return {"error": str(e)}

    async def _get_foreground_app_async(self, udid: str) -> Optional[Dict]:
        from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
        from pymobiledevice3.services.dvt.instruments.sysmontap import Sysmontap
        from pymobiledevice3.services.dvt.instruments.device_info import DeviceInfo

        rsd = await self._ensure_rsd_service_provider(udid)
        try:
            dvt = DvtProvider(rsd)
            await dvt.__aenter__()
            try:
                # 获取已安装应用 bundle id 集合（用于区分用户应用 vs 系统进程）
                user_app_bundles = set()
                try:
                    di = DeviceInfo(dvt)
                    await di.__aenter__()
                    procs_list = await di.proclist()
                    for p in procs_list:
                        if not isinstance(p, dict):
                            continue
                        bundle = p.get("bundleIdentifier") or ""
                        is_app = p.get("isApplication", False)
                        real_app = p.get("realAppName") or ""
                        # isApplication=True 或 realAppName 包含 /var/containers → 用户应用
                        if is_app or ("/var/containers/Bundle/Application/" in real_app):
                            if bundle:
                                user_app_bundles.add(bundle)
                    await di.__aexit__(None, None, None)
                except Exception:
                    pass

                # 用 Sysmontap 获取 CPU 使用率，取最高的用户应用
                sysmon = await Sysmontap.create(dvt, interval=2000)
                await sysmon.__aenter__()
                best = None
                best_cpu = -1.0
                sample_count = 0
                async for procs in sysmon.iter_processes():
                    sample_count += 1
                    if sample_count > 3:  # 最多读 3 条采样
                        break
                    for p in procs:
                        cpu = p.get("cpuUsage")
                        if cpu is None:
                            continue
                        name = p.get("name") or p.get("comm") or ""
                        pid = p.get("pid", 0)
                        # 排除系统守护进程
                        if name in self._SYSTEM_PROCESSES:
                            continue
                        # 排除明显系统进程（全小写、以 d 结尾的守护进程）
                        if name.endswith("d") and name[0].islower() and name not in (
                            "MobileCal", "MobileSafari", "MobileMail", "MobilePhone",
                        ):
                            continue
                        # 确认是用户应用（有 bundle id 且在用户应用集合中，或名称含中文）
                        # 这里放宽条件：只要不在系统黑名单且 CPU > 0 就算候选
                        if cpu > best_cpu:
                            best_cpu = cpu
                            best = {"name": str(name), "pid": int(pid),
                                    "bundle_id": "", "cpu": float(cpu)}
                    if best and sample_count >= 2:
                        break
                await sysmon.__aexit__(None, None, None)

                if best and best_cpu > 0:
                    # 尝试用 proclist 补全 bundle_id
                    try:
                        di2 = DeviceInfo(dvt)
                        await di2.__aenter__()
                        procs_list = await di2.proclist()
                        for p in procs_list:
                            if not isinstance(p, dict):
                                continue
                            if p.get("pid") == best["pid"]:
                                best["bundle_id"] = str(p.get("bundleIdentifier") or "")
                                display = p.get("displayLocalizedAppName")
                                if display:
                                    best["name"] = str(display)
                                break
                        await di2.__aexit__(None, None, None)
                    except Exception:
                        pass
                    return best
                return None
            finally:
                await dvt.__aexit__(None, None, None)
        finally:
            try:
                await rsd.close()
            except Exception:
                pass

    # ==================== DDI 智能挂载 ====================

    @staticmethod
    def get_ddi_cache_dir() -> str:
        """返回 iOS 17+ Personalized DDI 的本地缓存目录。
        优先使用 APP 内置打包的 DDI（sys._MEIPASS），不存在时回退到用户目录。
        """
        # 1. PyInstaller 打包模式：从 APP 内置资源加载（无需手动下载）
        if getattr(sys, 'frozen', False):
            bundled = os.path.join(sys._MEIPASS, 'Xcode_iOS_DDI_Personalized')
            if os.path.isfile(os.path.join(bundled, 'Image.dmg')):
                return bundled
        # 2. 开发模式 / 回退：pymobiledevice3 用户目录
        from pymobiledevice3.common import get_home_folder
        return str(get_home_folder() / "Xcode_iOS_DDI_Personalized")

    @staticmethod
    def get_xcode_ddi_dir(ios_version: str = "") -> str:
        """返回 iOS <17 经典 DDI 在 Xcode 中的路径"""
        base = "/Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/DeviceSupport"
        if ios_version:
            return f"{base}/{ios_version}"
        return base

    async def ensure_ddi_mounted(self, lockdown) -> Tuple[bool, str]:
        """
        智能挂载 DDI（按优先级走本地路径，避免网络阻塞）:
        1. 检查是否已挂载 (Developer / Personalized)
        2. iOS 17+ 本地缓存存在 → 直接用 PersonalizedImageMounter 挂载本地文件
        3. iOS <17 且 Xcode 本地 DDI 存在 → 直接挂载
        4. 以上都无 → 最后回落 auto_mount(带超时保护)
        5. 全部失败 → 返回详细错误指引
        """
        from pymobiledevice3.services.mobile_image_mounter import (
            DeveloperDiskImageMounter, PersonalizedImageMounter, auto_mount,
        )
        from pymobiledevice3.exceptions import AlreadyMountedError
        from pathlib import Path
        import asyncio

        # 1. 检查是否已挂载
        for img_type, mounter_cls in [("Personalized", PersonalizedImageMounter),
                                       ("Developer", DeveloperDiskImageMounter)]:
            try:
                mounter = mounter_cls(lockdown=lockdown)
                if await mounter.is_image_mounted(img_type):
                    return True, f"{img_type} DDI 已挂载"
            except Exception:
                pass

        cache_dir = Path(self.get_ddi_cache_dir())
        image_path = cache_dir / "Image.dmg"
        manifest_path = cache_dir / "BuildManifest.plist"
        trustcache_path = self._resolve_trustcache(cache_dir)
        errors = []

        # 2. iOS 17+ 本地缓存优先（不走网络）
        if image_path.exists() and manifest_path.exists() and trustcache_path.exists():
            try:
                from pathlib import Path as _P
                await PersonalizedImageMounter(lockdown=lockdown).mount(
                    _P(image_path), _P(manifest_path), _P(trustcache_path))
                return True, f"Personalized DDI 从本地缓存挂载成功 ({trustcache_path.name})"
            except Exception as cache_err:
                errors.append(f"本地缓存挂载失败: {cache_err}")

        # 3. iOS <17 本地 Xcode 路径
        try:
            from packaging.version import Version
            product_version = Version(str(getattr(lockdown, "product_version", "17")))
            if product_version.major < 17:
                version_str = f"{product_version.major}.{product_version.minor}"
                xcode_dir = Path(self.get_xcode_ddi_dir(version_str))
                dmg_path = xcode_dir / "DeveloperDiskImage.dmg"
                sig_path = xcode_dir / "DeveloperDiskImage.dmg.signature"
                if dmg_path.exists() and sig_path.exists():
                    await DeveloperDiskImageMounter(lockdown=lockdown).mount(dmg_path, sig_path)
                    return True, f"Developer DDI 从 Xcode 挂载成功 ({version_str})"
        except Exception as xcode_err:
            errors.append(f"Xcode DDI 挂载失败: {xcode_err}")

        # 4. 最后尝试 auto_mount（带超时，避免网络不好时卡死）
        #    auto_mount 内部会再查 Xcode/缓存，但也会尝试下载
        try:
            mount_task = asyncio.create_task(auto_mount(lockdown))
            await asyncio.wait_for(mount_task, timeout=15)
            return True, "DDI 挂载成功 (auto_mount)"
        except AlreadyMountedError:
            return True, "DDI 已挂载 (auto_mount 报告)"
        except asyncio.TimeoutError:
            errors.append("auto_mount 网络下载超时 (15s)，已跳过")
        except Exception as net_err:
            errors.append(f"auto_mount 失败: {net_err}")

        # 5. 全部失败 → 返回详细错误指引
        err_str = "\n".join(errors) if errors else ""
        return False, (
            f"DDI 挂载失败。\n\n"
            f"失败详情:\n{err_str}\n\n"
            f"本地缓存目录: {cache_dir}\n"
            f"  Image.dmg          : {'✅ 存在' if image_path.exists() else '❌ 不存在'} "
            f"({image_path.stat().st_size/1024/1024:.2f}MB)" if image_path.exists() else f"  Image.dmg          : ❌ 不存在" + "\n"
            f"  BuildManifest.plist: {'✅ 存在' if manifest_path.exists() else '❌ 不存在'} "
            f"({manifest_path.stat().st_size/1024:.2f}KB)" if manifest_path.exists() else f"  BuildManifest.plist: ❌ 不存在" + "\n"
            f"  Trustcache         : {'✅ 存在 ('+trustcache_path.name+')' if trustcache_path.exists() else '❌ 不存在'}\n\n"
            f"解决方案:\n"
            f"1. 从 https://github.com/doronz88/DeveloperDiskImage 下载:\n"
            f"   PersonalizedImages/Xcode_iOS_DDI_Personalized/ 下的三个文件，\n"
            f"   放到上述目录。\n"
            f"2. 或在终端执行 (需代理/VPN):\n"
            f"   pymobiledevice3 mounter auto-mount\n"
            f"3. 设备必须保持解锁、已开启开发者模式、已信任此电脑。\n"
            f"4. iOS 17+ 需先建立 RSD 隧道:\n"
            f"   sudo pymobiledevice3 tunnel start"
        )

    def check_ddi_status(self, udid: str) -> dict:
        """同步检查 DDI 挂载状态 + 本地缓存文件状态"""
        try:
            return self._run(self._check_ddi_status_async(udid), timeout=15)
        except Exception as e:
            return {"mounted": False, "error": str(e),
                    "cache_dir": self.get_ddi_cache_dir(),
                    "cache_files_exist": self._check_cache_files()}

    async def _check_ddi_status_async(self, udid: str) -> dict:
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.mobile_image_mounter import (
            DeveloperDiskImageMounter, PersonalizedImageMounter,
        )
        lockdown = await create_using_usbmux(serial=udid, autopair=True)
        try:
            result = {"mounted": False, "mount_type": "",
                      "cache_dir": self.get_ddi_cache_dir(),
                      "cache_files_exist": self._check_cache_files()}
            for img_type, mounter_cls in [("Developer", DeveloperDiskImageMounter),
                                           ("Personalized", PersonalizedImageMounter)]:
                try:
                    mounter = mounter_cls(lockdown=lockdown)
                    if await mounter.is_image_mounted(img_type):
                        result["mounted"] = True
                        result["mount_type"] = img_type
                        break
                except Exception:
                    pass
            return result
        finally:
            await lockdown.close()

    def _check_cache_files(self) -> bool:
        """检查 iOS 17+ 本地缓存 DDI 文件是否齐全（兼容两种 trustcache 命名）"""
        from pathlib import Path
        cache_dir = Path(self.get_ddi_cache_dir())
        if not (cache_dir / "Image.dmg").exists():
            return False
        if not (cache_dir / "BuildManifest.plist").exists():
            return False
        # 兼容两种 trustcache 文件名:
        #   Image.trustcache          (pymobiledevice3 官方规范 / doronz88 repo)
        #   Image.dmg.trustcache      (其他第三方下载源命名)
        if (cache_dir / "Image.trustcache").exists():
            return True
        if (cache_dir / "Image.dmg.trustcache").exists():
            return True
        return False

    @staticmethod
    def _resolve_trustcache(cache_dir):
        """在缓存目录中定位 trustcache 文件,兼容两种命名。
        参数/返回: pathlib.Path 对象"""
        from pathlib import Path as _Path
        for name in ("Image.trustcache", "Image.dmg.trustcache"):
            p = cache_dir / name
            if p.exists():
                return p
        return cache_dir / "Image.trustcache"

    # ==================== tunneld / RSD 隧道（iOS 17+ DVT 必需） ====================

    def get_tunneld_status(self) -> Dict:
        """检查 tunneld 后台服务是否可访问
        返回: {"running": bool, "url": str, "error": str}
        """
        try:
            import requests
            r = requests.get(_TUNNELD_HELLO_URL, timeout=2)
            if r.status_code == 200:
                return {"running": True, "url": _TUNNELD_HELLO_URL, "error": ""}
            return {"running": False, "url": _TUNNELD_HELLO_URL, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {
                "running": False, "url": _TUNNELD_HELLO_URL,
                "error": (
                    f"tunneld 未启动: {type(e).__name__}. 请先在终端执行:\n"
                    f"  sudo pymobiledevice3 remote tunneld\n"
                    f"启动一次后会持续监听 {_TUNNELD_DEFAULT_ADDR[0]}:{_TUNNELD_DEFAULT_ADDR[1]}"
                ),
            }

    async def _ensure_rsd_service_provider(self, udid: str):
        """iOS 17+ 必须走 RSD 隧道获取 DVT 服务。
        步骤:
          1) HTTP ping tunneld 判定是否启动
          2) HTTP GET /start-tunnel 触发 tunneld 为该设备建 RSD 隧道
          3) 用 get_tunneld_device_by_udid(udid) 拿到 RSD 对象（本身就是 LockdownServiceProvider）
        返回 RSD 可用时返回该对象，否则抛 RuntimeError
        """
        try:
            import requests
        except ImportError as e:
            raise RuntimeError(f"缺少 requests 依赖: {e}") from e

        # 1. tunneld 活着?
        try:
            r = await asyncio.to_thread(requests.get, _TUNNELD_HELLO_URL, timeout=3)
            if r.status_code != 200:
                raise RuntimeError(f"tunneld 返回 HTTP {r.status_code}")
        except Exception as conn_err:
            raise RuntimeError(
                f"无法连接 tunneld ({_TUNNELD_DEFAULT_ADDR[0]}:{_TUNNELD_DEFAULT_ADDR[1]}): "
                f"{type(conn_err).__name__}.\n\n"
                f"iOS 17+ 的 DVT (CPU/内存/GPU/FPS 采集) 需要 RSD 隧道，\n"
                f"请先在终端执行以下命令并保持窗口运行（需要输入 Mac 登录密码）：\n\n"
                f"  sudo pymobiledevice3 remote tunneld\n"
            )

        # 2. 启动隧道（幂等：如果已有会直接返回端口）
        try:
            r = await asyncio.to_thread(
                requests.get, _TUNNELD_START_TUNNEL_URL,
                params={"udid": udid, "connection_type": "usbmux"},
                timeout=20,
            )
        except Exception as req_err:
            raise RuntimeError(f"请求 tunneld 建立隧道失败: {type(req_err).__name__}: {req_err}")

        if r.status_code == 200:
            info = r.json()
            self.logger_info = None  # 占位
        elif r.status_code == 404 or r.status_code == 501:
            try:
                body = r.json()
            except Exception:
                body = {"error": r.text[:300]}
            raise RuntimeError(
                f"tunneld 无法为该设备建立隧道 (HTTP {r.status_code}): "
                f"{body.get('error', body)}. 请确认设备已解锁屏幕、已开启开发者模式、USB 连接正常。"
            )
        else:
            raise RuntimeError(f"启动隧道返回 HTTP {r.status_code}: {r.text[:400]}")

        # 等待隧道生效
        await asyncio.sleep(1.0)

        # 3. 拿到 RSD 对象（它实现了 LockdownServiceProvider 接口，可直接传入 DvtProvider）
        from pymobiledevice3.tunneld.api import get_tunneld_device_by_udid
        rsd = await get_tunneld_device_by_udid(udid)
        if rsd is None:
            raise RuntimeError(
                "tunneld 报告隧道已建立，但 get_tunneld_device_by_udid() 返回 None。"
                " 可能隧道尚未稳定，可稍后重试。"
            )
        return rsd

    def shutdown(self):
        """关闭后台事件循环"""
        self._loop.call_soon_threadsafe(self._loop.stop)


# ==================== 硬件监测会话 ====================

class IOSMonitor:
    """
    iOS 硬件监测会话 — 持续在后台采集 CPU 使用率 / 内存 / GPU 数据。
    使用 DVT Sysmontap 服务，需要 DDI 已挂载。
    """

    def __init__(self, client: IOSClient, udid: str):
        self.client = client
        self.udid = udid
        self._lockdown = None
        self._rsd = None  # iOS 17+ RSD service provider (实现 LockdownServiceProvider 接口)
        self._dvt = None
        self._sysmon = None
        self._graphics = None
        self._latest: Optional[dict] = None
        self._running = False
        self._error: Optional[str] = None
        self._frame_count = 0
        self._frame_start_time = 0.0

    def start(self) -> Tuple[bool, str]:
        """启动监测会话，返回 (是否成功, 错误信息)"""
        try:
            self.client._run(self._start_async(), timeout=30)
            return True, ""
        except Exception as e:
            self._error = str(e)
            return False, self._error

    async def _start_async(self):
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
        from pymobiledevice3.services.dvt.instruments.sysmontap import Sysmontap

        # 1. 先通过 lockdown 挂载 DDI（DDI挂载走传统Lockdown通道，不走RSD）
        self._lockdown = await create_using_usbmux(serial=self.udid, autopair=True)
        ok, msg = await self.client.ensure_ddi_mounted(self._lockdown)
        if not ok:
            try:
                await self._lockdown.close()
            except Exception:
                pass
            self._lockdown = None
            raise RuntimeError(msg)

        # 2. iOS 17+ DVT 必须通过 RSD 隧道拿到 service provider（DvtProvider 只认
        #    LockdownServiceProvider 接口，而 RSD 实现了该接口，可直接传入）
        self._rsd = await self.client._ensure_rsd_service_provider(self.udid)

        # 3. 建立 DVT 通道（传 RSD 而非 Lockdown，解决 InvalidService）
        self._dvt = DvtProvider(self._rsd)
        await self._dvt.__aenter__()

        # 4. 启动 Sysmontap（注意参数叫 interval，单位ms）
        self._sysmon = await Sysmontap.create(self._dvt, interval=1000)
        await self._sysmon.__aenter__()

        self._running = True
        self._frame_start_time = time.time()
        asyncio.ensure_future(self._reader_loop(), loop=self.client._loop)

    async def _reader_loop(self):
        """后台持续读取 Sysmontap 数据。

        注意：DVT/Sysmontap 通道会夹杂巨量心跳字符串 ('k' / 'heart')，
        必须 O(1) 过滤掉否则将严重阻塞有效数据的产出。
        使用 _last_valid（上一次有效值）填充字段缺失的采样行。
        """
        try:
            async for row in self._sysmon:
                if not self._running:
                    break
                # 快速跳过心跳字符串（占比 99%+）
                if isinstance(row, (str, bytes)):
                    continue
                if not isinstance(row, dict):
                    continue
                # 有 SystemCPUUsage 或 System 才认为是一次正规采样
                if "SystemCPUUsage" not in row and "System" not in row:
                    continue
                parsed = self._parse_row(row)
                # 字段回填：保留最后一次有效值，避免心跳/空采样把 UI 数字清零
                if self._latest is not None:
                    for key, val in parsed.items():
                        if val in (0, 0.0) and self._latest.get(key) not in (None, 0, 0.0):
                            parsed[key] = self._latest[key]
                self._latest = parsed
        except Exception as e:
            self._error = str(e)
            self._running = False

    def _parse_row(self, row: dict) -> dict:
        """解析 Sysmontap 行数据（iOS 17+ dataclass 字段 vmXXX，单位：页 × 16KB）"""
        data = {
            "cpu_usage": 0.0,
            "cpu_count": 0,
            "mem_total_mb": 0,
            "mem_used_mb": 0,
            "mem_used_pct": 0.0,
            "gpu_usage": 0.0,
            "timestamp": time.time(),
        }

        # CPU 使用率
        if "SystemCPUUsage" in row:
            cpu = row["SystemCPUUsage"]
            try:
                if isinstance(cpu, dict):
                    vals = [float(v) for v in cpu.values() if isinstance(v, (int, float))]
                    data["cpu_usage"] = round(sum(vals) / max(len(vals), 1), 1) if vals else 0.0
                elif isinstance(cpu, (list, tuple)):
                    vals = [float(v) for v in cpu if isinstance(v, (int, float))]
                    data["cpu_usage"] = round(sum(vals) / max(len(vals), 1), 1) if vals else 0.0
                elif isinstance(cpu, (int, float)):
                    data["cpu_usage"] = round(float(cpu), 1)
            except Exception:
                pass
        # clamp: CPU使用率理论上 [0, N*100]，但实际采样可能有微小负值或过高值
        if data["cpu_usage"] < 0.0:
            data["cpu_usage"] = 0.0
        if data["mem_used_pct"] < 0.0:
            data["mem_used_pct"] = 0.0
        if data["mem_used_pct"] > 100.0:
            data["mem_used_pct"] = 100.0
        if data["gpu_usage"] < 0.0:
            data["gpu_usage"] = 0.0

        if "CPUCount" in row:
            try:
                data["cpu_count"] = int(row["CPUCount"])
            except Exception:
                pass

        # 内存信息：iOS 17+ 的 SysmonSystemAttributes 为 dataclass，页大小 16KB
        if "System" in row and self._sysmon is not None:
            try:
                sys_tup = row["System"]
                if not isinstance(sys_tup, (list, tuple)):
                    sys_tup = (sys_tup,)
                system = self._sysmon.system_attributes_cls(*sys_tup)
                page = _APPLE_SILICON_PAGE_SIZE
                phys_pages = int(getattr(system, "physMemSize", 0) or 0)
                used_pages = int(getattr(system, "vmUsedCount", 0) or 0)
                if phys_pages <= 0:
                    # 回退：vmActive + vmInactive + vmWire
                    used_pages = (
                        int(getattr(system, "vmActiveCount", 0) or 0)
                        + int(getattr(system, "vmInactiveCount", 0) or 0)
                        + int(getattr(system, "vmWireCount", 0) or 0)
                    )
                    free_pages = int(getattr(system, "vmFreeCount", 0) or 0)
                    phys_pages = used_pages + free_pages
                total_bytes = phys_pages * page
                used_bytes = used_pages * page
                if total_bytes > 0:
                    data["mem_total_mb"] = int(total_bytes // (1024 * 1024))
                    data["mem_used_mb"] = int(used_bytes // (1024 * 1024))
                    data["mem_used_pct"] = round(used_bytes / total_bytes * 100, 1)
            except Exception:
                pass

        return data

    def get_latest(self) -> Optional[dict]:
        """获取最新一帧监测数据"""
        return self._latest

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def error(self) -> Optional[str]:
        return self._error

    def stop(self):
        """停止监测"""
        self._running = False
        try:
            self.client._run(self._stop_async(), timeout=10)
        except Exception:
            pass

    async def _stop_async(self):
        try:
            if self._sysmon:
                await self._sysmon.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if self._dvt:
                await self._dvt.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if self._rsd:
                await self._rsd.close()
        except Exception:
            pass
        try:
            if self._lockdown:
                await self._lockdown.close()
        except Exception:
            pass


# ==================== FPS 采集器 ====================

class IOSFPSCollector:
    """
    iOS FPS 采集器 — 通过 Graphics 服务的 CoreAnimationFramesPerSecond 字段获取真实 FPS。
    Graphics 服务每秒返回一个包含 GPU 性能计数器的 dict 事件，其中：
      - CoreAnimationFramesPerSecond: 真实 FPS（Core Animation 渲染帧率）
      - Device Utilization %: GPU 设备利用率
      - Renderer Utilization %: GPU 渲染器利用率
      - Tiler Utilization %: GPU 平铺器利用率
    """

    def __init__(self, client: IOSClient, udid: str, refresh_rate: int = 60):
        self.client = client
        self.udid = udid
        self.refresh_rate = refresh_rate
        self._lockdown = None
        self._rsd = None
        self._dvt = None
        self._graphics = None
        self._running = False
        self._error: Optional[str] = None
        self._fps = 0.0
        self._gpu_usage = 0.0
        self._gpu_renderer_usage = 0.0
        self._gpu_tiler_usage = 0.0
        self._frame_times: List[float] = []
        self._last_fps_time = 0.0
        self._first_event_logged = False
        self._event_count = 0
        # 事件计数法 + 帧间时间差法（核心：interval=0.0 时每个事件=一帧）
        self._event_window_start = 0.0
        self._event_window_count = 0
        self._event_based_fps = 0.0
        self._last_event_time = 0.0  # 用于计算帧间时间差
        # 前 5 个事件全部记录完整字段（用于发现 120fps 相关字段）
        self._debug_log_count = 0

    def start(self) -> Tuple[bool, str]:
        try:
            self.client._run(self._start_async(), timeout=30)
            return True, ""
        except Exception as e:
            self._error = str(e)
            return False, self._error

    async def _start_async(self):
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
        from pymobiledevice3.services.dvt.instruments.graphics import Graphics

        # 1. DDI 挂载
        self._lockdown = await create_using_usbmux(serial=self.udid, autopair=True)
        ok, msg = await self.client.ensure_ddi_mounted(self._lockdown)
        if not ok:
            try:
                await self._lockdown.close()
            except Exception:
                pass
            self._lockdown = None
            raise RuntimeError(msg)

        # 2. iOS 17+ RSD 隧道
        self._rsd = await self.client._ensure_rsd_service_provider(self.udid)

        # 3. 用 RSD 建立DVT通道
        self._dvt = DvtProvider(self._rsd)
        await self._dvt.__aenter__()

        # 4. 创建 Graphics 服务
        # __aenter__ 内部调用 connect() + start_sampling_at_time_interval_(0.0)
        # interval=0.0 = 每帧推送一个事件，事件计数法和帧间时间差法可检测 120fps
        self._graphics = Graphics(self._dvt)
        await self._graphics.__aenter__()
        _logger.info("[iOS Graphics] 服务已启动 (interval=0.0, 事件计数法+帧间时间差法检测120fps)")

        self._running = True
        self._last_fps_time = time.time()
        self._event_window_start = time.time()
        self._event_window_count = 0
        self._event_based_fps = 0.0
        self._last_event_time = 0.0
        asyncio.ensure_future(self._reader_loop(), loop=self.client._loop)

    async def _reader_loop(self):
        """持续读取 Graphics 事件，使用帧间时间差法获取真实 FPS。

        核心原理（interval=0.0 时每个事件 = 一帧渲染完成）：
        1. 帧间时间差 = 当前事件时间 - 上一个事件时间 = 真实帧时间(ms)
        2. 事件计数法：每秒统计事件数 = 真实 FPS
        3. CoreAnimationFramesPerSecond 作为交叉参考（可能被系统截断为 60）
        4. 取 max(事件计数FPS, CA字段FPS) 作为报告 FPS

        这样 120fps 游戏即使 CA 字段报 60，事件计数也能准确报告 120。
        """
        try:
            async for event in self._graphics:
                if not self._running:
                    break
                # Graphics 迭代器产出 dict（通知）或 tuple（dispatch 兜底）
                if not isinstance(event, dict):
                    continue

                self._event_count += 1
                now = time.time()

                # ---- 帧 1: 事件计数法（每秒事件数 = FPS）----
                self._event_window_count += 1
                elapsed = now - self._event_window_start
                if elapsed >= 1.0:
                    self._event_based_fps = self._event_window_count / elapsed
                    self._event_window_count = 0
                    self._event_window_start = now

                # ---- 帧 2: 帧间时间差法（最精确的帧时间）----
                frame_time_ms = 0.0
                if self._last_event_time > 0:
                    dt = now - self._last_event_time
                    frame_time_ms = dt * 1000.0
                    # 合理性过滤：1ms~100ms 之间的帧时间才有效
                    if 1.0 < frame_time_ms < 100.0:
                        self._frame_times.append(frame_time_ms)
                        if len(self._frame_times) > 300:
                            self._frame_times = self._frame_times[-300:]
                self._last_event_time = now

                # ---- 前 5 个事件记录完整字段（调试用）----
                if self._debug_log_count < 5:
                    self._debug_log_count += 1
                    try:
                        _logger.info("[iOS Graphics] 事件 #%d 字段:", self._debug_log_count)
                        for k, v in event.items():
                            _logger.info("[iOS Graphics]   %s = %r (type=%s)",
                                         k, v, type(v).__name__)
                    except Exception:
                        _logger.exception("[iOS Graphics] 记录事件字段失败")

                # ---- FPS 解析：事件计数法(主) + CA字段(交叉参考)，取最大值 ----
                def _try_float(val):
                    if val is None:
                        return None
                    try:
                        f = float(val)
                        return f if f > 0 else None
                    except (TypeError, ValueError):
                        return None

                ca_fps = _try_float(event.get("CoreAnimationFramesPerSecond"))
                if ca_fps is None:
                    ca_fps = _try_float(event.get("coreAnimationFramesPerSecond"))

                # 事件计数法 FPS（主要源，不受 CA 截断限制）
                fps_val = 0.0
                fps_source = ""
                if self._event_based_fps > 0:
                    fps_val = self._event_based_fps
                    fps_source = "event_count"

                # CA 字段作为交叉参考，取较大值
                if ca_fps is not None and ca_fps > fps_val:
                    fps_val = ca_fps
                    fps_source = "CA_FPS"

                if fps_val > 0:
                    self._fps = round(fps_val, 1)
                    # 每 30 个事件记录一次，方便追踪
                    if self._event_count % 30 == 0:
                        _logger.info("[iOS Graphics] FPS=%.1f (src=%s), ca=%s, evt_fps=%.1f, ft=%.2fms, events=%d",
                                     self._fps, fps_source,
                                     f"{ca_fps:.1f}" if ca_fps else "N/A",
                                     self._event_based_fps,
                                     frame_time_ms if frame_time_ms > 0 else -1,
                                     self._event_count)

                # ---- GPU 利用率解析（0 是有效值，需单独处理）----
                def _try_float_any(val):
                    if val is None:
                        return None
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        return None

                dev_util = _try_float_any(event.get("Device Utilization %"))
                if dev_util is not None:
                    self._gpu_usage = dev_util
                ren_util = _try_float_any(event.get("Renderer Utilization %"))
                if ren_util is not None:
                    self._gpu_renderer_usage = ren_util
                til_util = _try_float_any(event.get("Tiler Utilization %"))
                if til_util is not None:
                    self._gpu_tiler_usage = til_util
        except Exception as e:
            self._error = str(e)
            _logger.exception("[iOS Graphics] _reader_loop 异常: %s", e)
            self._running = False

    def get_fps(self) -> float:
        """获取当前 FPS（CoreAnimation 真实帧率）"""
        return self._fps

    def get_gpu_usage(self) -> float:
        """获取 GPU 利用率（Device Utilization %）"""
        return self._gpu_usage

    def get_gpu_renderer_usage(self) -> float:
        """获取 GPU 渲染器利用率（Renderer Utilization %）"""
        return self._gpu_renderer_usage

    def get_gpu_tiler_usage(self) -> float:
        """获取 GPU 平铺器利用率（Tiler Utilization %）"""
        return self._gpu_tiler_usage

    def get_frame_times(self) -> List[float]:
        """获取帧时间列表（毫秒）"""
        return self._frame_times

    def consume_frame_times(self) -> List[float]:
        """取出并清空已累积的帧时间列表（避免重复统计）"""
        times = self._frame_times[:]
        self._frame_times.clear()
        return times

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def error(self) -> Optional[str]:
        return self._error

    def stop(self):
        self._running = False
        try:
            self.client._run(self._stop_async(), timeout=10)
        except Exception:
            pass

    async def _stop_async(self):
        try:
            if self._graphics:
                await self._graphics.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if self._dvt:
                await self._dvt.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            if self._rsd:
                await self._rsd.close()
        except Exception:
            pass
        try:
            if self._lockdown:
                await self._lockdown.close()
        except Exception:
            pass
