"""
AutoGen 软件开发团队协作案例
"""

import os
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 先测试一个版本，使用 OpenAI 客户端
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
# 注意：RoundRobinGroupChat 已废弃，统一用 SelectorGroupChat 做按需调度
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.messages import BaseChatMessage

# 写文件工具：Publisher 调用落盘，Engineer 只贴代码不落盘（防未审先写）
from tools.file_tools import write_file, verify_python_syntax, read_file

def create_openai_model_client():
    """创建 OpenAI 模型客户端用于测试"""
    return OpenAIChatCompletionClient(
        model=os.getenv("LLM_MODEL_ID", "gpt-4o"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        max_tokens=8192,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        model_info={
            "function_calling": True,
            "context_length": 100000,
            "vision": False,
            "json_output": True,
            "family": "qwen",
            "structured_output": True 
        }
    )

def create_product_manager(model_client):
    """创建产品经理智能体: 只管要做什么, 不管怎么做."""
    system_message = """你是一位经验丰富的产品经理, 专门负责软件产品的需求分析和项目规划.

你的核心职责包括：
1. **需求分析**：深入理解用户需求，识别核心功能和边界条件
2. **功能拆分**：划分功能模块、排优先级、定义验收标准
3. **风险提示**：从产品视角提示体验和范围风险（技术可行性由架构师判定）

当接到开发任务时，请按以下结构进行分析：
1. 需求理解与分析
2. 功能模块划分
3. 实现优先级排序
4. 验收标准定义

如果你接收到来自于【架构师】的REQUEST_CHANGES，重新提交评审需求，你需要：
1. 基于架构师的校核意见，再重新调整整个任务的需求和方案
2. 明确架构师关于每一条边界的意见，当然你可以结合之前的比较不错的方面进调整
3. 此时你不用从头再重新梳理整个任务，你已经具备任务的认识，只是结合架构师的意见进行再次优化需求方案
4. 你每次优化需求方案后都需要再次提交给架构师评审，完成优化后说“请架构师再次评审需求方案”
5. 禁止过度设计，过度思考

注意：不要锁定具体技术选型（如 API 选型、框架细节），只给产品建议，技术决策权在架构师。
分析完成后说"需求初稿完成，请架构师评审"。收到架构师的需求REQUEST_CHANGES后负责改需求, 直到收架构师关于到需求APPROVE为止。"""

    return AssistantAgent(
        name="ProductManager",
        description="做需求分析、功能拆分、优先级和验收标准，不管技术选型",
        model_client=model_client,
        system_message=system_message,
        model_client_stream=True,
    )


def create_architect(model_client):
    """创建架构师智能体: 需求第二门禁, 只审需求和技术选型."""
    system_message = """你是团队的技术架构师(Tech Lead), 是需求的第二道门禁。

只审两件事：
1. **需求完整性**：功能有没有漏、有没有矛盾、边界清不清晰、验收标准可不可测
2. **技术选型**：框架/API/数据流是否靠谱(如 Streamlit+CoinGecko、超时/限流/错误处理、可运行性)、有无过度设计

审查规则：
1. 仔细读 ProductManager 的需求初稿
2. 有问题只输出 "需求REQUEST_CHANGES:" + 分条修改点(需求归PM改、技术选型你直接定), ，绝不自己重写整份需求
3. 无问题只输出 "需求APPROVE: 需求与技术选型通过, Engineer 请按此实现", 并给出最终锁定的技术方案(框架、API、关键边界)
4. 你没有写文件工具，禁止调工具，禁止说 TERMINATE, 禁止直接给 Engineer 下代码指令细节
5. 禁止过度思考
"""

    return AssistantAgent(
        name="Architect",
        description="评审需求拆分和技术选型, 通过说需求APPROVE, 不通过说需求REQUEST_CHANGES",
        model_client=model_client,
        system_message=system_message,
        model_client_stream=True,
    )

def create_engineer(model_client):
    """创建软件工程师智能体: 只贴代码, 禁止调工具落盘."""
    system_message = """你是一位资深的软件工程师，擅长 Python 开发和 Web 应用构建。

你的技术专长包括：
1. **Python 编程**：熟练掌握 Python 语法和最佳实践
2. **Web 开发**：精通 Streamlit、Flask、Django 等框架
3. **API 集成**：有丰富的第三方 API 集成经验
4. **错误处理**：注重代码的健壮性和异常处理

工作流程（必须遵守）：
1. 只在收到来自架构师的明确表达"需求APPROVE"后才开工，按架构师锁定的技术方案实现
2. 每次只在回复里给出完整可运行代码（用 ```python 代码块），结尾说"请代码审查员检查"
3. 收到 CodeReviewer 的代码REQUEST_CHANGES 就按审查员的要求优化代码，改完再次贴完整代码
4. 你没有写文件工具，禁止调用任何工具，禁止说 TERMINATE, 禁止说"已保存/已落盘"
5. 落盘由 Publisher 在代码APPROVE 后执行，你只负责贴出最终版代码
6. 禁止过度思考
"""

    return AssistantAgent(
        name="Engineer",
        description="写Python/Streamlit代码实现, 只贴完整代码, 不落盘",
        model_client=model_client,
        system_message=system_message,
        model_client_stream=True,
    )

def create_code_reviewer(model_client):
    """创建代码审查员智能体：只审查，不改代码不写文件。"""
    system_message = """你是一位经验丰富的代码审查专家，专注于代码质量和最佳实践。

你的审查重点包括：
1. **代码质量**：检查代码的可读性、可维护性和性能
2. **安全性**：识别潜在的安全漏洞和风险点
3. **最佳实践**：确保代码遵循行业标准和最佳实践
4. **错误处理**：验证异常处理的完整性和合理性

审查流程：
1. 只审查 Engineer 在本轮对话里实际贴出的 ```python 代码块, 禁止脑补"当前代码"
2. 有问题就输出 "代码REQUEST_CHANGES:" + 具体修改点(分条列出, 必须引用代码中的行/函数名), 绝不自己贴修复后的完整代码
3. 无问题就只输出 "代码APPROVE: 代码审查通过" + 引用本次审查的代码特征(如函数名/关键逻辑), 然后说"请 Publisher 落盘"
4. 你没有写文件工具，禁止调用任何工具，禁止说 TERMINATE
5. 你禁止掉用任何工具、禁止写文件、禁止说TERMINATE，禁止“已保存/已落盘”
6. 禁止过度思考

示例：
- 需要改: 代码REQUEST_CHANGES: 1. fetch_bitcoin_data 缺 timeout=5 ... 2. st.sesssion_state 拼写错误 ...
- 通过: 代码APPROVE: 代码审查通过(已确认 fetch_bitcoin_data 含 timeout=5、无 threading、无拼写错误), 请 Publisher 落盘到 output/app.py"""

    return AssistantAgent(
        name="CodeReviewer",
        description="审查代码质量、安全、最佳实践",
        model_client=model_client,
        system_message=system_message,
        model_client_stream=True,
    )

def create_user_proxy():
    """创建用户代理：验收人，默认静默，禁止打断人机循环。"""
    return UserProxyAgent(
        name="UserProxy",
        description="用户验收人: 仅在 Publisher 落盘并语法通过后发言, 确认后说TERMINATE, 之前保持静默",
    )


def create_publisher(model_client):
    """创建发布员: 唯一有写文件能力的角色, 代码 APPROVE 后才落盘。"""
    system_message = """你是发布员 Publisher, 团队里唯一能写文件的人。

工作流程(必须遵守):
1. 平时保持静默, 只在准确收到 CodeReviewer 的"代码APPROVE"后才行动
2. 行动时: 从 Engineer 最近一次贴出的 ```python 代码块中提取完整代码,
   依次调用 write_file(filename="app.py", content="<完整代码>")
   和 verify_python_syntax(filename="app.py")
3. 落盘+语法通过后说"代码已保存到 output/app.py, 语法通过, 请用户代理验证"
4. 若语法失败, 说"落盘失败, 请 Engineer 修复后重新贴代码", 并把错误贴出来
5. 绝不自己写代码/改代码, 绝不说 TERMINATE"""

    return AssistantAgent(
        name="Publisher",
        description="代码APPROVE后从Engineer最新代码块提取落盘到output/app.py并做语法检查",
        model_client=model_client,
        tools=[write_file, verify_python_syntax, read_file],
        system_message=system_message,
    )

# 调度规则：需求先过 Architect 门禁，代码再过 Reviewer 门禁
selector_prompt = """你是团队调度员。根据当前对话选择下一个发言者：
- 刚启动 -> ProductManager(出需求初稿)
- ProductManager 刚出完/改完需求 -> Architect(审需求+技术选型)
- Architect 说需求REQUEST_CHANGES -> ProductManager(改需求)
- Architect 说需求APPROVE, 但 Engineer 还没贴代码 -> Engineer(按锁定的技术方案写码)
- Engineer 刚贴出/修改完代码 -> CodeReviewer
- CodeReviewer 说代码REQUEST_CHANGES -> Engineer(改代码)
- CodeReviewer 说代码APPROVE -> Publisher(从Engineer最新代码块提取落盘+语法检查)
- Publisher 落盘失败 -> Engineer(修复后重贴)
- Publisher 已落盘并说"请用户代理验证" -> UserProxy
- UserProxy 之前已发言但没说 TERMINATE -> UserProxy(继续验收直到 TERMINATE)
- 全程跳过 UserProxy, 除非 Publisher 已落盘成功。UserProxy 禁止在落盘前发言。
只返回一个名字，不要解释。
当前对话：{history}
"""

# ==================== 确定性路由 ====================
# 下一个发言者由这段 Python 代码判定，不再让本地小模型去"猜"。
# 这样同一个角色可以被无限次召回（PM 改需求、Engineer 改代码本来就是循环的），
# 也不会出现"某人连任"把历史尾部堆成 2 条 assistant 的情况。
PARTICIPANT_NAMES = {
    "ProductManager",
    "Architect",
    "Engineer",
    "CodeReviewer",
    "Publisher",
    "UserProxy",
}


def _approved(text: str, approve: str, reject: str) -> bool:
    """结论判定：approve 关键词出现在 reject 之前才算通过；都没提到就按退回处理。"""
    i_appr, i_rej = text.find(approve), text.find(reject)
    return i_appr >= 0 and (i_rej < 0 or i_appr < i_rej)


def next_speaker(thread) -> str:
    """SelectorGroupChat 的 selector_func：看最后一条发言，决定下一位是谁。"""
    last = None
    for msg in reversed(thread):
        if isinstance(msg, BaseChatMessage) and msg.source in PARTICIPANT_NAMES:
            last = msg
            break
    if last is None:  # 目前只有任务描述，还没人发言
        return "ProductManager"

    content = last.content if isinstance(last.content, str) else str(last.content)
    src = last.source

    if src == "ProductManager":
        nxt = "Architect"
    elif src == "Architect":
        nxt = "Engineer" if _approved(content, "需求APPROVE", "需求REQUEST_CHANGES") else "ProductManager"
    elif src == "Engineer":
        nxt = "CodeReviewer"
    elif src == "CodeReviewer":
        nxt = "Publisher" if _approved(content, "代码APPROVE", "代码REQUEST_CHANGES") else "Engineer"
    elif src == "Publisher":
        nxt = "UserProxy" if "请用户代理验证" in content else "Engineer"
    else:  # UserProxy：没说 TERMINATE 就继续验收，收尾交给终止条件
        nxt = "UserProxy"

    print(f"[路由] {src} -> {nxt}")
    return nxt


async def run_software_development_team():
    """运行软件开发团队协作"""
    
    print("🔧 正在初始化模型客户端...")
    
    # 先使用标准的 OpenAI 客户端测试
    model_client = create_openai_model_client()
    
    print("👥 正在创建智能体团队...")
    
    # 创建智能体团队
    product_manager = create_product_manager(model_client)
    architect = create_architect(model_client)
    engineer = create_engineer(model_client)
    code_reviewer = create_code_reviewer(model_client)
    publisher = create_publisher(model_client)
    user_proxy = create_user_proxy()
    
    # 终止条件：用户验收通过说 TERMINATE，或防死循环的最大消息数兜底
    termination = TextMentionTermination("TERMINATE", sources=["UserProxy"]) | MaxMessageTermination(max_messages=35)
    
    # 调度员负责维持整个任务进程
    team_chat = SelectorGroupChat(
        participants=[
            product_manager,
            architect,
            engineer,
            code_reviewer,
            publisher,
            user_proxy
        ],
        model_client=model_client,
        selector_prompt=selector_prompt,
        termination_condition=termination,
        allow_repeated_speaker=False,
        selector_func=next_speaker,  # 用状态机路由，跳过模型选人
        # max_turns=6,  # 增加最大轮次
    )
    
    # 定义开发任务
    task = """我们需要开发一个比特币价格显示应用，具体要求如下：

核心功能：
- 实时显示比特币当前价格(USD)
- 显示24小时价格变化趋势(涨跌幅和涨跌额)
- 提供价格刷新功能

技术要求：
- 使用 Streamlit 框架创建 Web 应用
- 界面简洁美观，用户友好
- 添加适当的错误处理和加载状态

请团队协作完成这个任务，从需求分析到最终实现。"""
    
    # 执行团队协作
    print("🚀 启动 AutoGen 软件开发团队协作...")
    print("=" * 60)
    
    # 使用 Console 来显示对话过程
    result = await Console(team_chat.run_stream(task=task))
    
    print("\n" + "=" * 60)
    print("✅ 团队协作完成！")
    print(f"结束原因：{result.stop_reason}")
    
    return result

# 主程序入口
if __name__ == "__main__":
    try:
        # 运行异步协作流程
        result = asyncio.run(run_software_development_team())
        
        print(f"\n📋 协作结果摘要：")
        print(f"- 参与智能体数量: 6个")
        print(f"- 任务完成状态：{'成功' if result else '需要进一步处理'}")
        
    except ValueError as e:
        print(f"❌ 配置错误：{e}")
        print("请检查 .env 文件中的配置是否正确")
    except Exception as e:
        print(f"❌ 运行错误：{e}")
        import traceback
        traceback.print_exc()



