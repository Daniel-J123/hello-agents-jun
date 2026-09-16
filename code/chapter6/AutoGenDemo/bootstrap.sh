#!/usr/bin/env bash
# 第 6 章 AutoGenDemo 环境初始化（幂等，可重复执行）
#
# 用法： bash bootstrap.sh            # 默认 Python 3.11
#        bash bootstrap.sh 3.12
#
# 与 local-dev/bootstrap.ps1 同一套路：解释器与下载缓存仍落在 local-dev/ 内，
# 但虚拟环境单独建在本目录 .venv，与主环境 local-dev/.venv 互不影响。
#
# 为什么默认 3.11：与主环境共用 local-dev/python/ 里已下载的那份 CPython，
# 不必再拉一份；教程也是在 3.11 上验证的。autogen 三个包本身是纯 Python 轮子、
# 只声明 >=3.10，换 3.12/3.13 通常也装得上——真正卡解释器版本的是
# pydantic-core、tiktoken、pyarrow 这些带二进制的传递依赖，用 3.11 最省事。

set -euo pipefail

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_ROOT="$(cd "$PROJ_DIR/../../../local-dev" && pwd)"
VENV="$PROJ_DIR/.venv"
PYVER="${1:-3.11}"

# --- 下载与缓存全部锁在项目内部 ---
export UV_PYTHON_INSTALL_DIR="$DEV_ROOT/python"
export UV_CACHE_DIR="$DEV_ROOT/cache/uv"
export PIP_CACHE_DIR="$DEV_ROOT/cache/pip"
# uv 默认会把托管解释器的 shim 装到 ~/.local/bin，这里改指回项目内，
# 免得污染用户目录（本机之前就留过一个 python3.11.exe）
export UV_PYTHON_BIN_DIR="$DEV_ROOT/python/bin"

# 自检脚本输出含中文
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if ! command -v uv >/dev/null 2>&1; then
    echo "未找到 uv，无法初始化项目内环境。" >&2
    exit 1
fi

echo "[1/3] 准备 Python $PYVER （复用 $UV_PYTHON_INSTALL_DIR）..."
uv python install "$PYVER"

if [ -d "$VENV" ]; then
    echo "[2/3] .venv 已存在，跳过创建。"
else
    echo "[2/3] 创建独立虚拟环境 $VENV ..."
    uv venv --seed --python "$PYVER" "$VENV"
fi

# Windows 下 venv 的布局是 Scripts/，Linux/macOS 是 bin/
PY="$VENV/Scripts/python.exe"
[ -f "$PY" ] || PY="$VENV/bin/python"

echo "[3/3] 安装 AutoGen 依赖（uv 解析，冲突立即报错）..."
uv pip install --python "$PY" -r "$PROJ_DIR/requirements.local.txt"

echo
echo "导入自检（把本章案例用到的符号全 import 一遍）："
"$PY" "$PROJ_DIR/check_env.py"

echo
echo "完成。接下来："
echo "  . ./env.sh                          # 载入本章环境"
echo "  python autogen_software_team.py     # 跑团队协作案例"
echo "  streamlit run output.py             # 跑生成的比特币应用"