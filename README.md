# 🎯 FPS\_Test\_Tool · 星穹视界帧率测试

<div align="center">

**Repository:** [`FPS_Test_Tool`](https://github.com/stardomevision/FPS_Test_Tool) · **Homepage:** [stardomevision.github.io/FPS_Test_Tool](https://stardomevision.github.io/FPS_Test_Tool/)

> 🌠 Cross-platform Android & iOS game performance testing tool
> 跨平台安卓 / iOS 游戏性能实测工具
>
> **FPS · 1% / 0.1% Low · CPU · GPU · Memory · Temperature · Power** 全链路监测 · 一键导出 **CSV / HTML / 4× 高清 JPG** 报告

[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-informational.svg?style=flat-square)](#)
[![Android](https://img.shields.io/badge/Android-8+-3DDC84.svg?style=flat-square&logo=android)](#)
[![iOS](https://img.shields.io/badge/iOS-15+-000000.svg?style=flat-square&logo=apple)](#)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](#)
[![Built with](https://img.shields.io/badge/Built%20with-PyQt5%20%2B%20pyqtgraph-41CD52.svg?style=flat-square)](#)
[![License](https://img.shields.io/badge/License-Free%20for%20testing-5B8DEF.svg?style=flat-square)](#)
[![Stars](https://img.shields.io/github/stars/stardomevision/FPS_Test_Tool?style=social)](https://github.com/stardomevision/FPS_Test_Tool/stargazers)
[![Watchers](https://img.shields.io/github/watchers/stardomevision/FPS_Test_Tool?style=social)](https://github.com/stardomevision/FPS_Test_Tool/subscription)
[![Issues](https://img.shields.io/github/issues/stardomevision/FPS_Test_Tool?style=flat-square&color=ea4aaa)](https://github.com/stardomevision/FPS_Test_Tool/issues)

**Repo Name:** `FPS_Test_Tool` &nbsp;·&nbsp; **Alias:** 星穹视界 · Stellar Vision FPS Tester

</div>

---

## ✨ 为什么选它？（Features at a glance）

| 能力 | 说明 |
|------|------|
| 🎬 **实时帧率 FPS** | 瞬时 FPS · 平均 · **1% / 0.1% Low** · 卡顿率 · 标准差 · Jank 分布 |
| 🏅 **智能评级** | 自动识别游戏限帧（30 / 45 / 60 / 90 / 120 / 144），打分不过度严格 |
| ⚡ **安卓功率采集** | sysfs → uevent → batteryproperties → batterystats 多源兼容 |
| 🍎 **iOS 性能采集** | FPS · CPU · GPU · 内存 · 温度 签名式抓取 |
| 💪 **负载稳定性测试** | 可配时长 / 压力等级 · 自动重测 · HTML 报告导出 |
| 📤 **一键导出报告** | CSV · HTML · **4× 超高物理像素 JPG**（字号一并放大，不糊） |
| 🚀 **开屏动画** | 全屏占满 · 星空渐变 · 流星 · 星环 LOGO · 进度百分比 |

---

## 🚀 快速开始

```bash
# 1. 安装依赖
python3 -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt

# 2. 连接手机
#    安卓：开发者选项 → 打开 USB 调试；首次连接在手机点「允许调试」
#    iOS : 设置 → 隐私与安全性 → 开发者模式

# 3. 运行（macOS 也可以直接双击 run.command）
python3 main.py
```

> ⚠️ 首次使用需要把 Android SDK 的 `platform-tools/`（含 `adb`）放到仓库根目录，或在系统 PATH 中能直接调用 `adb`。
> 本仓库**仅源文件**，不包含 Android 官方二进制；下载地址 →
> <https://developer.android.com/studio/releases/platform-tools>

---

## 📸 页面概览

- 🎮 **FPS 页**：实时 FPS 曲线 · P95/P99 帧时分布 · FPS 直方图 · 卡顿抖动分布
- 🧪 **Hardware 页**：CPU / GPU / 内存曲线 · 温度趋势 · 安卓功率/电流趋势
- 📊 **负载稳定性页**：CPU 压力阶梯曲线 · 温度/电压变化 · 稳定性评级 · 重测/导出 HTML
- 📑 **导出报告**：封面头 + 汇总卡片 + 曲线图快照；JPG 为 4× 超采样 + 轴标放大字号

---

## 📁 目录结构

```
FPS_Test_Tool/
├── main.py                        入口
├── main_window.py                 主窗口 UI（开屏动画 / FPS / HW / 负载）
├── adb_client.py                  安卓数据采集（FPS / 硬件 / 电池功率）
├── ios_client.py                  iOS 性能采集
├── fps_analyzer.py                帧率统计 · 评分 · 分级
├── db_manager.py                  SQLite 数据库
├── device_checker.py              设备连通性检测
├── app_logger.py                  日志工具
├── requirements.txt
├── AndroidFPSTester.spec          PyInstaller Windows 打包脚本
├── 星穹视界帧率测试.spec            PyInstaller macOS 打包脚本
├── run.sh / run.command           启动脚本
└── resources/                     LOGO / Icon
```

---

## 🔄 Roadmap & Feedback · 更新计划与问题反馈

> ⚠️ **Notice / 说明**
>
> - **This project will continue to be actively updated.**  **本项目会持续更新。**
> - **iOS side / iOS 端：** Some iOS features may not work correctly on certain iOS versions / devices (e.g. FPS streaming, hardware metrics).
>   **部分功能在特定 iOS 版本或机型上可能失效**（例如实时 FPS 抓取、硬件指标采集等）。
> - **Android side / 安卓端：** Android is the primary supported platform and should be stable.
>   安卓为主要支持平台，功能更稳定；若遇到异常也同样欢迎反馈。

### ✉️ How to report issues · 反馈方式

| Item | 内容 |
|------|------|
| **By Email · 邮件（推荐）** | 📧 **stellar.fps.tool@outlook.com**<br>*(请附上：设备型号 / iOS 或 Android 版本号 / 现象截图或录屏 / 复现步骤，便于快速定位)* |
| **GitHub Issues** | [**github.com/stardomevision/FPS_Test_Tool/issues**](https://github.com/stardomevision/FPS_Test_Tool/issues) |

### 🗓 Release Policy · 版本计划

1. **Bug collection · 收集阶段**  
   Issues / 邮件反馈会集中记录、分类。
2. **Batch fixes · 批量整改**  
   当积累到一定数量后，统一进行一整轮修复 + 回归测试。
3. **Roll out · 发布**
   - **Patch release · 补丁小版本**：针对关键故障，随修随更（如 `v1.x.x` 小版本号）。
   - **Major release · 大版本更新**：一批修复 + 新功能一起推出（如 `v1.x` → `v2.0`），附完整 Release Notes。

> 🌐 This repository will **keep growing** — Star / Watch it to get notified about each patch & major release.
>
> 本仓库**会持续迭代**，点 **Star ⭐ / Watch 👁** 就能第一时间收到每个补丁版本与大版本更新的通知。

---

## ⚠️ 免责声明

本工具仅用于**合法授权的性能测试与优化验收**。
不得用于官方匹配 / 违反用户协议的任何场景；账号、设备、数据风险由使用者自负。
