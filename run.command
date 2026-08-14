#!/bin/bash
# ============================================================================
#  星穹视界帧率测试 - macOS 双击启动脚本
#  用法：在访达中双击 run.command，或在终端执行 ./run.command
# ============================================================================

# 切换到脚本所在目录（兼容双击运行时工作目录为 ~）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

clear
echo "════════════════════════════════════════════════════════════"
echo "  星穹视界帧率测试 - Stellar Vision FPS Tester"
echo "  macOS Launcher  ·  双击启动"
echo "════════════════════════════════════════════════════════════"
echo ""

# ------------------------------ 1. Python 检查 ------------------------------
echo "[1/4] 🔍 检查 Python 环境..."
PYTHON_BIN=""

# 优先使用 python3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo ""
    echo "❌ 未找到 Python 3。"
    echo "请通过以下任一方式安装："
    echo "  · 官网下载: https://www.python.org/downloads/"
    echo "  · 使用 Homebrew: brew install python3"
    echo ""
    read -r -p "按回车键退出..." _
    exit 1
fi

PY_VER=$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
PY_MAJOR=${PY_VER%%.*}
PY_MINOR=${PY_VER#*.}
PY_MINOR=${PY_MINOR%%.*}

echo "    ✅ 发现 $PYTHON_BIN  (版本 $PY_VER)"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    echo ""
    echo "⚠️  推荐使用 Python 3.9 或更高版本（当前 $PY_VER）。"
    echo "    继续尝试启动，如遇报错请升级 Python。"
    sleep 1
fi

# ------------------------------ 2. 虚拟环境建议 ------------------------------
echo ""
echo "[2/4] 📦 检查依赖 (PyQt5 / pyqtgraph)..."

# 检查是否存在虚拟环境 .venv
VENV_DIR="$SCRIPT_DIR/.venv"
USE_VENV=0
if [ -d "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/python" ]; then
    echo "    ✅ 检测到虚拟环境 .venv，将使用该环境启动"
    PYTHON_BIN="$VENV_DIR/bin/python"
    USE_VENV=1
fi

# 检查核心依赖是否已安装
$PYTHON_BIN -c "
import sys
missing = []
try:
    import PyQt5
except ImportError:
    missing.append('PyQt5>=5.15.0')
try:
    import pyqtgraph
except ImportError:
    missing.append('pyqtgraph>=0.13.0')
if missing:
    print('MISSING:' + ' '.join(missing))
    sys.exit(2)
print('OK')
" > /tmp/fps_tester_deps.$$ 2>&1
DEPS_RC=$?
DEPS_OUT="$(cat /tmp/fps_tester_deps.$$ 2>/dev/null)"
rm -f /tmp/fps_tester_deps.$$

if [ "$DEPS_RC" -eq 0 ]; then
    echo "    ✅ 所有依赖已就绪"
else
    # 需要安装
    MISSING_PKGS=""
    if echo "$DEPS_OUT" | grep -q "^MISSING:"; then
        MISSING_PKGS="$(echo "$DEPS_OUT" | sed 's/^MISSING://')"
    else
        MISSING_PKGS="-r requirements.txt"
    fi
    echo "    ⚠️  缺少依赖：$MISSING_PKGS"
    echo ""
    echo "    正在尝试自动安装..."

    # 如果尚未创建 venv 且用户有写权限，优先创建本地 .venv 避免污染全局
    if [ "$USE_VENV" -eq 0 ] && [ ! -d "$VENV_DIR" ] && [ -w "$SCRIPT_DIR" ]; then
        echo ""
        echo "    💡 推荐：在项目目录创建隔离的虚拟环境 .venv (y/n)？"
        read -r -p "    推荐选 y（回车默认 y）: " VENV_CHOICE
        if [ -z "$VENV_CHOICE" ] || [[ "$VENV_CHOICE" =~ ^[Yy]$ ]]; then
            echo "    🛠  正在创建虚拟环境 .venv ..."
            if "$PYTHON_BIN" -m venv "$VENV_DIR" 2>/dev/null; then
                echo "    ✅ 虚拟环境创建成功"
                PYTHON_BIN="$VENV_DIR/bin/python"
                USE_VENV=1
            else
                echo "    ⚠️  虚拟环境创建失败，回退到全局 pip 安装"
            fi
        fi
    fi

    echo "    📥 执行: $PYTHON_BIN -m pip install $MISSING_PKGS"
    echo ""
    if $PYTHON_BIN -m pip install $MISSING_PKGS; then
        echo ""
        echo "    ✅ 依赖安装完成"
    else
        echo ""
        echo "❌ 依赖安装失败。"
        echo "请手动执行：  $PYTHON_BIN -m pip install -r requirements.txt"
        echo ""
        read -r -p "按回车键退出..." _
        exit 1
    fi
fi

# ------------------------------ 3. ADB 权限 ------------------------------
echo ""
echo "[3/4] ⚙️  准备环境..."

# 确保本地 platform-tools/adb 可执行
if [ -f "$SCRIPT_DIR/platform-tools/adb" ]; then
    chmod +x "$SCRIPT_DIR/platform-tools/adb" 2>/dev/null
fi

# 确保 macOS 不隔离刚下载的脚本
xattr -d com.apple.quarantine "$SCRIPT_DIR/platform-tools/adb" 2>/dev/null

# 创建日志目录
LOG_DIR="$HOME/Library/Logs/星穹视界帧率测试"
mkdir -p "$LOG_DIR" 2>/dev/null

echo "    📝 日志目录: $LOG_DIR"
DB_PATH="$HOME/Library/Application Support/StellarVision/fps_tester.db"
echo "    💾 数据库路径: $DB_PATH"

# ------------------------------ 4. 启动应用 ------------------------------
echo ""
echo "[4/4] 🚀 启动主程序..."
echo "────────────────────────────────────────────────────────────"
echo ""

"$PYTHON_BIN" "$SCRIPT_DIR/main.py"
EXIT_CODE=$?

echo ""
echo "────────────────────────────────────────────────────────────"
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "✅ 程序正常退出 (exit_code=$EXIT_CODE)"
else
    echo "⚠️  程序异常退出 (exit_code=$EXIT_CODE)"
    echo "    请查看日志目录：$LOG_DIR"
fi
echo ""
read -r -p "按回车键关闭窗口..." _
exit "$EXIT_CODE"
