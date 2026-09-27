import ast

from hello_agents import (
    Config,
    HelloAgentsLLM,
    Message,
    PlanAndSolveAgent,
)

PLANNER_PROMPT_TEMPLATE = """
你是一个顶级的AI规划专家。你的任务是将用户提出的复杂问题分解成一个由多个简单步骤组成的行动计划。
请确保计划中的每个步骤都是一个独立的、可执行的子任务，并且严格按照逻辑顺序排列。
你的输出必须是一个Python列表, 其中每个元素都是一个描述子任务的字符串。

问题: {question}

请严格按照以下格式输出你的计划，```python与```作为前后缀是必要的:
```python
["步骤1", "步骤2", "步骤3", ...]
```
"""


class MyPlanner:
    """规划器: 将复杂问题分解为步骤列表 (重写自 hello_agents.agents.plan_solve_agent.MyPlanner)"""

    def __init__(self, llm_client: HelloAgentsLLM, prompt_template: str | None = None):
        self.llm_client = llm_client
        # 自定义模板优先, 否则用本文件定义的模板
        self.prompt_template = prompt_template or PLANNER_PROMPT_TEMPLATE

    def make_plan(self, question: str, **kwargs) -> list[str]:
        prompt = self.prompt_template.format(question=question)
        # 添加了角色扮演的系统提示词
        messages = [{"role": "user", "content": prompt}]

        print("\n--- 正在生成计划 ---")
        # 注意: 用 invoke(返回完整字符串) 而不是 think(返回流式迭代器)
        response_text = self.llm_client.invoke(messages, **kwargs) or ""
        print(f"✅ 计划已生成:\n{response_text}")

        try:
            plan_str = response_text.split("```python")[1].split("```")[0].strip()
            plan = ast.literal_eval(plan_str)
            return plan if isinstance(plan, list) else []
        except (ValueError, SyntaxError, IndexError) as e:
            print(f"❌ 解析计划时出错: {e}")
            print(f"原始响应: {response_text}")
            return []
        except Exception as e:  # noqa: BLE001 — 解析兜底, 教学代码故意捕获所有异常
            print(f"❌ 解析计划时发生未知错误: {e}")
            return []


EXECUTOR_PROMPT_TEMPLATE = """
你是一位顶级的AI执行专家。你的任务是严格按照给定的计划, 一步步地解决问题。
你将收到原始问题、完整的计划、以及到目前为止已经完成的步骤和结果。
请你专注于解决“当前步骤”，并仅输出该步骤的最终答案，不要输出任何额外的解释或对话。

# 原始问题:
{question}

# 完整计划:
{plan}

# 历史步骤与结果:
{history}

# 当前步骤:
{current_step}

请仅输出针对“当前步骤”的回答:
"""
class MyExecutor:
    """执行器: 按计划逐步执行并汇总结果 (重写自 hello_agents 的 MyExecutor)"""

    def __init__(self, llm_client: HelloAgentsLLM, prompt_template: str | None = None):
        self.llm_client = llm_client
        self.prompt_template = prompt_template or EXECUTOR_PROMPT_TEMPLATE

    def make_execute(self, question: str, plan: list[str], **kwargs) -> str:
        history = ""
        final_answer = ""

        print("\n--- 正在执行计划 ---")
        for i, step in enumerate(plan, 1):
            print(f"\n-> 正在执行步骤 {i}/{len(plan)}: {step}")
            prompt = self.prompt_template.format(
                question=question, 
                plan=plan, 
                history=history if history else "无", 
                current_step=step
            )
            messages = [{"role": "user", "content": prompt}]

            response_text = self.llm_client.invoke(messages, **kwargs) or ""

            # 累加每个步骤的执行结果, 推进LLM执行下一步
            history += f"步骤 {i}: {step}\n结果: {response_text}\n\n"
            final_answer = response_text
            print(f"✅ 步骤 {i} 已完成，结果: {final_answer}")

        return final_answer


class MyPlanAndSolveAgent(PlanAndSolveAgent):
    """
    重写PlanAndSolve智能体: 先计划, 再严格按照计划执行

    与父类的差异:
    1. 用本文件的 MyPlanner/MyExecutor 覆盖父类组件(换零件)
    2. 重写 run() 修复基类局限(换流程):
       - 计划生成失败自动重试, 而不是直接终止
       - 计划本身写入对话历史(基类丢弃), 支持多轮追问
       - 执行阶段异常容错, 一步失败不影响返回诊断信息
    """

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: str | None = None,
        config: Config | None = None,
        custom_prompts: dict[str, str] | None = None,
    ):
        # 1. 先让父类完成基础初始化(名字/llm/config/历史记录等)
        super().__init__(name, llm, system_prompt, config, custom_prompts)

        # 2. 再用本文件的自定义组件覆盖父类的 planner/executor
        #    (custom_prompts 里有对应模板就用它, 没有就用本文件默认模板)
        prompts = custom_prompts or {}
        # 这里会覆盖基类的组件, 使用派生类的组件功能
        self.planner = MyPlanner(llm, prompts.get("planner"))
        self.executor = MyExecutor(llm, prompts.get("executor"))

    def run(self, input_text: str, max_plan_retries: int = 1, **kwargs) -> str:
        """
        重写运行编排:

        Args:
            input_text: 要解决的问题
            max_plan_retries: 计划生成失败时的最大重试次数(基类无重试)
            **kwargs: 透传给 MyPlanner/MyExecutor 的 LLM 调用参数

        Returns:
            最终答案
        """
        print(f"\n🤖 {self.name} 开始处理问题:\n {input_text}")

        # ---- 1. 生成计划(失败自动重试, 基类是直接终止) ----
        plan = self.planner.make_plan(input_text, **kwargs)
        retries = 0
        while not plan and retries < max_plan_retries:
            retries += 1
            print(f"⚠️ 计划为空, 进行第 {retries}/{max_plan_retries} 次重试...")
            plan = self.planner.make_plan(input_text, **kwargs)

        if not plan:
            final_answer = "无法生成有效的行动计划, 任务终止。"
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(final_answer, "assistant"))
            return final_answer

        # self.add_message 目的是将对话过程加追加进记忆

        # ---- 2. 展示计划(基类不展示, 黑盒执行) ----
        print(f"\n📋 生成了 {len(plan)} 个步骤:")
        for i, step in enumerate(plan, 1):
            print(f"    {i}. {step}")

        # ---- 3. 执行计划(异常容错: 一步崩溃返回诊断, 而不是向上抛)----
        try:
            final_answer = self.executor.make_execute(input_text, plan, **kwargs)
        except Exception as e:  # noqa: BLE001 — 执行失败应返回诊断信息而非中断程序
            final_answer = f"计划执行中断: {e}"
            print(f"❌ {final_answer}")

        # ---- 4. 历史入库(计划+答案都存, 基类只存答案) ----
        #      这样多轮对话时可以追问"你当时为什么这样规划"
        plan_text = "\n".join(f"{i}. {s}" for i, s in enumerate(plan, 1))
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(f"[计划]\n{plan_text}\n\n[最终答案]\n{final_answer}", "assistant"))

        print(f"\n--- 任务完成 ---\n最终答案: {final_answer}")
        return final_answer



