#!/usr/bin/env bash
# ============================================================================
#  星穹视界帧率测试 - 命令行启动脚本
#  用法:
#      ./run.sh                 # 正常启动 GUI
#      ./run.sh --no-venv       # 跳过 .venv 检测，强制用系统 python
#      ./run.sh --install-deps  # 仅安装依赖后退出
#      ./run.sh --check         # 仅做环境自检，不启动 GUI
# ============================================================================

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# ---------- 参数解析 ----------
NO_VENV=0
INSTALL_DEPS_ONLY=0
CHECK_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --no-venv)       NO_VENV=1 ;;
        --install-deps)  INSTALL_DEPS_ONLY=1 ;;
        --check)         CHECK_ONLY=1 ;;
        -h|--help)
            sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "⚠️  未知参数: $arg  (使用 -h 查看帮助)"
            ;;
    esac
done

# ---------- 颜色 ----------
if [ -t 1 ]; then
    R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' B='\033[1;34m' N='\033[0m'
else
    R=''; G=''; Y=''; B=''; N=''
fi

info()  { printf "${B}[INFO]${N} %s\n" "$*"; }
ok()    { printf "${G}[ OK ]${N} %s\n" "$*"; }
warn()  { printf "${Y}[WARN]${N} %s\n" "$*"; }
err()   { printf "${R}[FAIL]${N} %s\n" "$*" >&2; }

echo "══════════════════════════════════════════════════════"
echo "  星穹视界帧率测试  ·  CLI 启动器"
echo "══════════════════════════════════════════════════════"

# ---------- 1. 选择 Python ----------
PYTHON_BIN=""
if [ "$NO_VENV" -eq 0 ] && [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
    info "使用虚拟环境: .venv"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    err "未找到 python3 / python，请先安装 Python 3.9+。"
    exit 1
fi

PY_VER="$("$PYTHON_BIN" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo 0.0)"
ok "Python 解释器: $PYTHON_BIN  (v$PY_VER)"

# ---------- 2. 依赖检查 / 安装 ----------
DEP_CHECK="$("$PYTHON_BIN" - <<'PY' 2>&1
import sys
missing = []
try:
    import PyQt5          # noqa: F401
except Exception:
    missing.append("PyQt5>=5.15.0")
try:
    import pyqtgraph      # noqa: F401
except Exception:
    missing.append("pyqtgraph>=0.13.0")
if missing:
    print("MISSING:" + " ".join(missing))
    sys.exit(2)
print("OK")
PY
)"
DEP_RC=$?

if [ "$DEP_RC" -eq 0 ]; then
    ok "依赖: PyQt5 / pyqtgraph 已就绪"
else
    MISSING_PKGS="$(echo "$DEP_CHECK" | grep '^MISSING:' | sed 's/^MISSING://')"
    [ -z "$MISSING_PKGS" ] && MISSING_PKGS="-r requirements.txt"
    warn "缺少依赖: $MISSING_PKGS"
    info "正在执行 pip install $MISSING_PKGS ..."
    if ! "$PYTHON_BIN" -m pip install --quiet $MISSING_PKGS; then
        err "依赖安装失败，请手动执行: $PYTHON_BIN -m pip install -r requirements.txt"
        exit 2
    fi
    ok "依赖安装完成"
fi

# ---------- 3. 可选: 仅检查 / 仅安装 ----------
if [ "$INSTALL_DEPS_ONLY" -eq 1 ]; then
    ok "--install-deps 完成"
    exit 0
fi
if [ "$CHECK_ONLY" -eq 1 ]; then
    ok "环境自检通过 ✅"
    echo "  - Python:  $PYTHON_BIN  ($PY_VER)"
    echo "  - 项目:    $SCRIPT_DIR"
    echo "  - ADB:     $SCRIPT_DIR/platform-tools/adb"
    echo "  - 日志:    $HOME/Library/Logs/星穹视界帧率测试"
    echo "  - 数据库:  $HOME/Library/Application Support/StellarVision/fps_tester.db"
    exit 0
fi

# ---------- 4. 启动 GUI ----------
chmod +x "$SCRIPT_DIR/platform-tools/adb" 2>/dev/null
xattr -d com.apple.quarantine "$SCRIPT_DIR/platform-tools/adb" 2>/dev/null

info "启动 main.py ..."
"$PYTHON_BIN" "$SCRIPT_DIR/main.py"
exit $?
