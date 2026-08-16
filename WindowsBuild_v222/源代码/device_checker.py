#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备状态检测工具 - 命令行版
用于在启动GUI前快速检查ADB和设备连接状态
"""

import sys
import shutil
from adb_client import ADBClient


def check_adb_installed() -> bool:
    """检查ADB是否可用"""
    adb_path = shutil.which("adb")
    if adb_path:
        print(f"✅ ADB已安装: {adb_path}")
        return True
    else:
        print("❌ 未找到ADB命令")
        print("   请安装Android SDK Platform-Tools:")
        print("   下载地址: https://developer.android.com/studio/releases/platform-tools")
        print("\n   macOS快速安装(使用Homebrew):")
        print("   brew install android-platform-tools")
        return False


def check_devices():
    """检测并列出所有已连接设备"""
    client = ADBClient()
    try:
        devices = client.get_devices()
        if not devices:
            print("\n⚠️  未检测到任何安卓设备")
            print("   请检查:")
            print("   1. USB数据线是否已连接")
            print("   2. 手机是否开启『开发者选项』->『USB调试』")
            print("   3. 手机上是否已允许本电脑的USB调试授权")
            print("   4. 部分手机需要开启『USB安装』和『USB调试(安全设置)』")
            return False

        print(f"\n✅ 检测到 {len(devices)} 个设备:")
        for i, (device_id, status) in enumerate(devices, 1):
            try:
                model = client.get_device_model(device_id)
                version = client.get_android_version(device_id)
                current_pkg = client.get_current_package(device_id) or "无"
                print(f"\n   [{i}] 设备ID: {device_id}")
                print(f"       状态:   {status}")
                print(f"       型号:   {model}")
                print(f"       版本:   Android {version}")
                print(f"       当前应用: {current_pkg}")
            except Exception as e:
                print(f"\n   [{i}] {device_id} - 状态: {status} (获取详情失败: {e})")

        return True

    except Exception as e:
        print(f"\n❌ 检查设备时出错: {e}")
        return False


def main():
    print("=" * 60)
    print("  安卓帧率测试工具 - 设备状态检查")
    print("=" * 60)

    adb_ok = check_adb_installed()
    if adb_ok:
        check_devices()

    print("\n" + "=" * 60)
    print("  一切就绪后，运行: python main.py 启动图形界面")
    print("=" * 60)


if __name__ == "__main__":
    main()
