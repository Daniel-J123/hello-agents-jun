#!/usr/bin/env python3
"""
Push 触发的 AI 代码审查脚本（零第三方依赖）。

流程：
  1. 用 git 取本次 push 的 diff（prefer 事件对比区间，回退 HEAD~1）
  2. 调 OpenAI 兼容接口让模型审查代码
  3. 结果写入 GitHub Step Summary（$GITHUB_STEP_SUMMARY），并可选评论到 commit

所需环境变量：
  LLM_API_KEY    必填，LLM 服务商密钥
  LLM_BASE_URL   选填，默认 https://api.deepseek.com/v1
  LLM_MODEL_ID   选填，默认 deepseek-chat
  BEFORE/AFTER   GitHub push 事件自带的 commit 区间（可选）
"""

import json
import os
import subprocess
import sys
import urllib.request

MAX_DIFF_CHARS = 60_000  # 超长 diff 截断，保护 token 消耗

SYSTEM_PROMPT = """你是严格的代码审查员。审查下面的 git diff，用中文按以下固定格式输出（三段标题必须原样保留，便于程序解析）：

## 必须修复
逻辑错误、密钥硬编码、异常吞掉、资源泄漏等必须修改的问题，每条注明文件与行号。
若没有，此段只写两个字：无

## 建议改进
命名、重复代码、可读性等方面的非阻塞建议。

## 亮点
值得肯定的做法；若没有则写：无

保持简洁，不要复述 diff 内容。"""


def run_git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=False)
    return r.stdout if r.returncode == 0 else ""


def get_diff() -> tuple[str, str]:
    """返回 (diff文本, 说明)。优先用 push 事件区间，否则 HEAD~1。"""
    before, after = os.getenv("BEFORE", ""), os.getenv("AFTER", "")
    if before and after and before != "0" * 40:
        diff = run_git("diff", f"{before}..{after}")
        desc = f"{before[:8]}..{after[:8]}"
        if diff.strip():
            return diff, desc
    diff = run_git("diff", "HEAD~1..HEAD")
    return diff, "HEAD~1..HEAD"


def call_llm(diff: str) -> str:
    base = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL_ID", "deepseek-chat")
    key = os.environ["LLM_API_KEY"]

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"```diff\n{diff}\n```"},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def has_blockers(review: str) -> bool:
    """解析'## 必须修复'段，非'无'即视为存在必须修复的问题。"""
    import re

    m = re.search(r"##\s*必须修复\s*\n(.*?)(?=\n##|\Z)", review, re.DOTALL)
    if not m:
        return False
    section = m.group(1).strip()
    return section not in ("", "无")


def main() -> int:
    if not os.environ.get("LLM_API_KEY"):
        print("::warning::未配置 LLM_API_KEY secret，跳过 AI 审查")
        return 0

    diff, desc = get_diff()
    if not diff.strip():
        print("没有可审查的 diff（可能是分支删除或空提交），跳过。")
        return 0
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n... (diff 过长，已截断)"
    print(f"审查范围: {desc}，diff 长度 {len(diff)} 字符")

    try:
        review = call_llm(diff)
    except Exception as e:  # noqa: BLE001 — 网络/配额等任何失败都不应阻塞 CI
        print(f"::error::AI 审查调用失败: {e}")
        return 1

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"## 🤖 AI 代码审查（{desc}）\n\n{review}\n")

    print("\n" + "=" * 50 + "\n" + review + "\n" + "=" * 50)

    if has_blockers(review):
        print("::error::AI 审查发现【必须修复】级问题（本地 pre-push 会中止 push）")
        return 2  # 2 = 有阻塞问题；pre-push 钩子据此拦截
    return 0


if __name__ == "__main__":
    sys.exit(main())
