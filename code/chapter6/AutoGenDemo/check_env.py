"""AutoGenDemo 环境自检：不联网、不发真实请求。

两件事：把 autogen_software_team.py 用到的符号全部导入一遍；
确认同目录 .env 里三项配置读得到（只打印前缀，不泄露完整密钥）。

用法： python check_env.py        （由 bootstrap.sh 自动调用）
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def guard_right_venv() -> None:
    """第一个检查：确认自检跑在本目录的 .venv 里。

    主环境 local-dev/.venv 与本章 .venv 在提示符里都显示成 (.venv),
    激活错了就会得到一句和第 6 章毫无关系的 ModuleNotFoundError。
    """
    expect = os.path.join(HERE, ".venv")
    got = sys.prefix
    if os.path.normcase(os.path.abspath(expect)) != os.path.normcase(os.path.abspath(got)):
        print("  [环境不对] 当前解释器不在本目录的 .venv 里")
        print(f"      期望： {expect}")
        print(f"      实际： {got}")
        print("      修法： 在本目录执行  . ./env.sh   （开头是点+空格），")
        print("             或先 deactivate 再 source, 见 README 的常见问题。")
        raise SystemExit(2)


def check_imports() -> None:
    import autogen_agentchat
    import autogen_core
    import openai  # noqa: F401  验证与 autogen-ext 的兼容跳不会炸
    from autogen_ext.models.openai import OpenAIChatCompletionClient  # noqa: F401
    from autogen_agentchat.agents import AssistantAgent, UserProxyAgent  # noqa: F401
    from autogen_agentchat.teams import SelectorGroupChat  # noqa: F401
    from autogen_agentchat.conditions import TextMentionTermination  # noqa: F401
    from autogen_agentchat.ui import Console  # noqa: F401

    print(f"  Python             {sys.version.split()[0]}")
    print(f"  autogen-core       {autogen_core.__version__}")
    print(f"  autogen-agentchat  {autogen_agentchat.__version__}")
    print(f"  openai             {openai.__version__}")
    print("  符号               AssistantAgent / UserProxyAgent / "
          "SelectorGroupChat / TextMentionTermination / Console 均可导入")


def check_case_objects() -> None:
    """直接调用案例自己的工厂函数，比只看 import 更能暴露签名不匹配。"""
    import autogen_software_team as demo

    client = demo.create_openai_model_client()
    agents = [
        demo.create_product_manager(client),
        demo.create_engineer(client),
        demo.create_code_reviewer(client),
        demo.create_user_proxy(),
    ]
    team = demo.SelectorGroupChat(
        agents,
        termination_condition=demo.TextMentionTermination("TERMINATE"),
        max_turns=20,
    )
    print(f"  装配               4 个 agent 构造成功 -> "
          f"{[a.name for a in team._participants]}")


def check_env_file() -> None:
    from dotenv import load_dotenv

    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        print(f"  [警告] 没有找到 {path}，正式运行前需要配置")
        return
    load_dotenv(path, override=True)
    for key in ("LLM_MODEL_ID", "LLM_API_KEY", "LLM_BASE_URL"):
        val = os.getenv(key) or ""
        label = "OK  " if val else "缺失"
        shown = val[:12] + ("..." if len(val) > 12 else "")
        print(f"  [{label}] {key:13}= {shown}")
        if val.startswith("${") or val == '""':
            print(f"         注意：{key} 是未展开的引用或空串。python-dotenv 的"
                  "插值要求被引用变量已存在于进程中，"
                  "请先 . ./env.sh 再运行。")


if __name__ == "__main__":
    guard_right_venv()
    check_imports()
    try:
        check_case_objects()
    except Exception as exc:  # noqa: BLE001
        print(f"  [失败] 案例装配出错：{type(exc).__name__}: {exc}")
        raise SystemExit(1)
    check_env_file()
    print("自检通过。")