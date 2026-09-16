#!/usr/bin/env bash
# 第 6 章 AutoGenDemo 环境载入脚本（Git Bash）
# 用法： . ./env.sh      或  source ./env.sh      —— 必须 source，直接执行无效
#
# 这是 local-dev/env.sh 的"本章替换版"。两套环境的目录名都叫 .venv，在提示符里
# 长得一模一样（activate 用 basename 当标签），所以本脚本会主动把标签改成
# (ch6-autogen)，并在最后核验 python 到底指向谁——不核验就等于没写。

ENV_PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DEV_ROOT="$(cd "$ENV_PROJ_DIR/../../../local-dev" && pwd)"

# --- 缓存与独立解释器仍然锁在项目内部（uv 装东西不会写到 AppData）---
export UV_PYTHON_INSTALL_DIR="$ENV_DEV_ROOT/python"
export UV_CACHE_DIR="$ENV_DEV_ROOT/cache/uv"
export PIP_CACHE_DIR="$ENV_DEV_ROOT/cache/pip"
export NPM_CONFIG_CACHE="$ENV_DEV_ROOT/cache/npm"
export HF_HOME="$ENV_DEV_ROOT/cache/huggingface"

# --- 与系统隔离 ---
export PYTHONNOUSERSITE=1
export PIP_USER=0
export PYTHONUNBUFFERED=1

# --- 中文编码：本章全是中文提示词 ---
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# --- 清掉机器上的 provider 专用 Key（只影响当前 shell 进程）---
# AutoGen 的 OpenAIChatCompletionClient 是显式传 api_key / base_url，不会像
# HelloAgentsLLM 那样自动探测 provider；留这段是为了同一终端里跑其它章节时一致。
unset OPENAI_API_KEY DEEPSEEK_API_KEY DASHSCOPE_API_KEY MODELSCOPE_API_KEY \
      KIMI_API_KEY MOONSHOT_API_KEY ZHIPU_API_KEY GLM_API_KEY \
      OLLAMA_API_KEY OLLAMA_HOST VLLM_API_KEY VLLM_HOST

# --- 刷新网关密钥：FREELLAMA_API_KEY 不能清，反而要重读 ---
if command -v powershell.exe >/dev/null 2>&1; then
    _fresh="$(powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('FREELLAMA_API_KEY','Machine')" 2>/dev/null | tr -d '\r')"
    if [ -z "$_fresh" ]; then
        _fresh="$(powershell.exe -NoProfile -Command "[Environment]::GetEnvironmentVariable('FREELLAMA_API_KEY','User')" 2>/dev/null | tr -d '\r')"
    fi
    if [ -n "$_fresh" ]; then export FREELLAMA_API_KEY="$_fresh"; fi
    unset _fresh
fi

# --- 已经激活了别的环境？先退掉 ---
# 最常见的翻车姿势：先前 source 过 local-dev/env.sh（或 VS Code 自动激活了主环境），
# 然后 cd 进本目录直接跑，提示符还是 (.venv)，于是 python 用的是主环境，
# 报 ModuleNotFoundError: No module named 'autogen_ext'。
if [ -n "${VIRTUAL_ENV:-}" ]; then
    case "$VIRTUAL_ENV" in
        *AutoGenDemo/.venv*) : ;;
        *)
            echo "[ch6/AutoGen] 检测到已激活别的环境： $VIRTUAL_ENV"
            echo "[ch6/AutoGen]        先 deactivate，再切到本章环境"
            if type deactivate >/dev/null 2>&1; then deactivate; fi
            ;;
    esac
fi

# --- 激活本章独立虚拟环境 ---
ACT=""
if [ -f "$ENV_PROJ_DIR/.venv/Scripts/activate" ]; then
    ACT="$ENV_PROJ_DIR/.venv/Scripts/activate"
elif [ -f "$ENV_PROJ_DIR/.venv/bin/activate" ]; then
    ACT="$ENV_PROJ_DIR/.venv/bin/activate"
else
    echo "[ch6/AutoGen] 找不到 .venv，请先执行： bash bootstrap.sh" >&2
    return 1 2>/dev/null || exit 1
fi
# shellcheck disable=SC1091
source "$ACT"

# --- 把提示符标签换成可辨认的名字 ---
VIRTUAL_ENV_PROMPT='ch6-autogen'
export VIRTUAL_ENV_PROMPT
if [ -n "${PS1:-}" ]; then
    PS1="${PS1#(.venv) }"
    PS1="(ch6-autogen) $PS1"
fi

# --- 核验：激活结果不对就当场报错，别让下一命令去猜 ---
_now="$(command -v python)"
case "$_now" in
    *AutoGenDemo/.venv*) : ;;
    *)
        echo "[ch6/AutoGen] 激活异常：python 仍指向 $_now" >&2
        echo "[ch6/AutoGen]        期望在 $ENV_PROJ_DIR/.venv 下；建议开一个干净终端重来" >&2
        return 1 2>/dev/null || exit 1
        ;;
esac
if ! "$_now" -c "import autogen_ext" >/dev/null 2>&1; then
    echo "[ch6/AutoGen] 路径对了但 autogen_ext 导入失败，依赖没装全" >&2
    echo "[ch6/AutoGen]        重跑： bash bootstrap.sh" >&2
    return 1 2>/dev/null || exit 1
fi

echo "[ch6/AutoGen] venv  : $(python --version 2>&1)"
echo "[ch6/AutoGen] path  : $_now"
echo "[ch6/AutoGen] autogen_ext 可导入 -> 可以跑： python autogen_software_team.py"