# test_plan_solve_agent.py
from dotenv import load_dotenv
from hello_agents.core.llm import HelloAgentsLLM
from my_plan_solve_agent import MyPlanAndSolveAgent

# 加载环境变量
load_dotenv()

# 创建LLM实例
llm = HelloAgentsLLM()

# 创建自定义PlanAndSolveAgent
agent = MyPlanAndSolveAgent(
    name="规划执行智能体",
    llm=llm
)

# 测试复杂问题
# question = "一个水果店周一卖出了15个苹果。周二卖出的苹果数量是周一的两倍。周三卖出的数量比周二少了5个。请问这三天总共卖出了多少个苹果?"
question2 = "一个旅行者计划用3天游览一座城市: 第1天参观博物馆并记录门票价格, 第2天参观的景点数量是第1天的2倍, 第3天把前两天看到的所有门票费用加总后乘以2作为总预算。若博物馆门票为60元且各景点票价相同, 总预算是多少元?"
result = agent.run(question2)
print(f"\n最终结果: {result}")

# 查看对话历史
print(f"对话历史: {len(agent.get_history())} 条消息")