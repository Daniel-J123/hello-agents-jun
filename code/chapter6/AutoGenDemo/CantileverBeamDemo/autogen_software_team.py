"""
AutoGen Cantilever Beam Team: 悬臂梁挠度应力计算应用
Physics locked, SI units, Euler-Bernoulli, small deflection.
标点用英文, 汉字用中文.
"""
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_agentchat.teams import SelectorGroupChat

from tools.file_tools import write_file, verify_python_syntax, read_file

def create_openai_model_client():
    """创建 OpenAI 模型客户端."""
    return OpenAIChatCompletionClient(
        model=os.getenv("LLM_MODEL_ID", "gpt-4o"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        max_tokens=4096,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        model_info={
            "function_calling": True,
            "context_length": 200000,
            "vision": False,
            "json_output": True,
            "family": "qwen",
            "structured_output": True
        }
    )

# 物理基准(所有角色必须遵守, 不许编造):
# 坐标: x in [0, L], x=0 为固支端, x=L 为自由端, 向下为正挠度 w.
# 矩形截面: b 为宽度, h 为高度, c=h/2, I=b*h**3/12.
# 符号约定: V=-dM/dx, M 以固支端为最大, 自由端 M=0.
# 尖端集中力 P(自由端向下, 单位 N):
#   w(x)=P*x**2*(3*L-x)/(6*E*I), w_max=P*L**3/(3*E*I),
#   theta_max=P*L**2/(2*E*I), M(x)=P*(L-x), M_max=P*L(固支端 x=0),
#   sigma_max=6*P*L/(b*h**2)(x=0 截面上下表面 z=±h/2, 纯弯曲, 忽略应力集中与剪切).
#   V(x)=P(0<=x<L 为常数), 固支端反力 R=P.
# 全跨均布载荷 q(向下, 单位 N/m):
#   w(x)=q*x**2*(6*L**2-4*L*x+x**2)/(24*E*I), w_max=q*L**4/(8*E*I),
#   theta_max=q*L**3/(6*E*I), M(x)=q*(L-x)**2/2, M_max=q*L**2/2(固支端 x=0),
#   sigma_max=3*q*L**2/(b*h**2)(x=0 截面上下表面 z=±h/2).
#   V(x)=q*(L-x), 固支端反力 R=q*L.
# 叠加: P 与 q 可同时非零, 结果线性叠加.
# 参考校验(钢 E=200GPa, L=1m, b=50mm, h=100mm, SI 下计算):
#   P=1000N -> I=4.1667e-6 m4, w_max=0.40mm, theta_max=0.60mrad, sigma_max=12.0MPa.
#   q=1000N/m -> w_max=0.15mm, theta_max=0.20mrad, sigma_max=6.0MPa.
#   P+q 叠加 -> w_max=0.55mm, theta_max=0.80mrad, sigma_max=18.0MPa.
# 单位: L 用 m, b/h 用 mm(程序内除以 1000 转 m), E 用 GPa(乘 1e9 转 Pa), P 用 N, q 用 N/m.
# 约束: L>0, b>0, h>0, E>0, P>=0, q>=0, not(P==0 and q==0).
# 告警(SI 下比较, 转 mm 之前): w_max/L>=0.1 时告警(以 w/L 为转角代理指标, 尖端力对应 theta 约 1.5*w/L, 均布对应约 1.33*w/L, 此时几何非线性误差约 3%); h/L>0.1 时告警剪切变形不可忽略.
# 语言: 汉字用中文, 标点用英文(, . : ; () [] 等半角), 禁止全角标点.

def create_product_manager(model_client):
    system_message = """你是一位 CAE 产品经理, 只管要做什么, 不管怎么做.

职责:
1. 拆需求: 输入(L, b, h, E, P, q, 载荷类型)、输出(w_max, theta_max, sigma_max, 曲线 V/M, 单位换算)、边界校验.
2. 排优先级: P0 数值正确(公式+单位换算), P1 曲线正确, P2 美观.
3. 定义验收: 默认钢算例(E=200GPa, L=1m, b=50mm, h=100mm) P=1000N 时 w_max=0.40mm(容差 1%), theta_max=0.60mrad, sigma_max=12.0MPa; q=1000N/m 时 w_max=0.15mm, theta_max=0.20mrad, sigma_max=6.0MPa; P+q 叠加时 w_max=0.55mm, theta_max=0.80mrad, sigma_max=18.0MPa; 非法输入要报错不崩溃. V 图默认显示, 可用 checkbox 关闭.
4. 约束写法: 禁写 P+q>0(量纲非法), 必须写 not(P==0 and q==0).

禁止: 禁止锁定公式细节与技术栈, 禁止编造物理量, 标点用英文半角, 汉字用中文.
完成后说: 需求初稿完成, 请架构师评审. 收到需求REQUEST_CHANGES 就改, 直到需求APPROVE."""
    return AssistantAgent(
        name="ProductManager",
        description="拆悬臂梁需求、定优先级与验收标准, 不管技术选型",
        model_client=model_client,
        system_message=system_message,
        model_client_stream=True,
    )

def create_architect(model_client):
    system_message = """你是 CAE 架构师(Tech Lead), 需求第二门禁, 只审需求与技术选型, 不写代码.

物理基准(必须逐条核对, 错一条就打回):
1. 坐标: x in [0, L], x=0 固支, x=L 自由, 向下为正.
2. 矩形截面: I=b*h**3/12, c=h/2.
3. 尖端 P(N): w_max=P*L**3/(3*E*I), theta_max=P*L**2/(2*E*I), M(x)=P*(L-x), M_max=P*L(固支端 x=0), sigma_max=6*P*L/(b*h**2)(x=0 截面上下表面 z=±h/2, 纯弯曲), V(x)=P, 反力 R=P.
4. 均布 q(N/m): w_max=q*L**4/(8*E*I), theta_max=q*L**3/(6*E*I), M(x)=q*(L-x)**2/2, M_max=q*L**2/2(固支端 x=0), sigma_max=3*q*L**2/(b*h**2)(x=0 截面上下表面), V(x)=q*(L-x), 反力 R=q*L. 符号约定 V=-dM/dx.
5. 参考: 钢 E=200GPa, L=1m, b=50mm, h=100mm, P=1000N -> w=0.40mm, theta=0.60mrad, sigma=12.0MPa; q=1000N/m -> w=0.15mm, theta=0.20mrad, sigma=6.0MPa; 叠加 -> w=0.55mm, theta=0.80mrad, sigma=18.0MPa.
6. 单位: L(m), b/h(mm 除以 1000 转 m), E(GPa 乘 1e9 转 Pa), P(N), q(N/m). 约束 L>0, b>0, h>0, E>0, P>=0, q>=0, not(P==0 and q==0). 禁写 P+q>0.
7. 技术栈锁定: Streamlit + numpy + matplotlib(禁 plotly 动态依赖), 纯本地计算禁外部 API, 落盘 output/app.py. V 图默认显示, 可用 checkbox 关闭.

规则: 有问题只输出 需求REQUEST_CHANGES: + 分条; 无问题输出 需求APPROVE: + 锁定的公式与单位换算. 禁调工具, 禁 TERMINATE, 标点用英文."""
    return AssistantAgent(
        name="Architect",
        description="核悬臂梁公式、单位换算与技术选型, 通过说需求APPROVE",
        model_client=model_client,
        system_message=system_message,
        model_client_stream=True,
    )

def create_engineer(m):
    s = """你是 CAE 计算工程师, 只贴代码, 禁落盘.

铁律(违反即返工):
1. 只在需求APPROVE 后开工, 按架构师锁定的公式实现, 禁自创公式.
2. 公式: I=b_m*h_m**3/12; P: w=P*x**2*(3*L-x)/(6*E*I), M=P*(L-x), w_max=P*L**3/(3*E*I), th=P*L**2/(2*E*I), sg=6*P*L/(b*h**2); q: w=q*x**2*(6*L**2-4*L*x+x**2)/(24*E*I), M=q*(L-x)**2/2, w_max=q*L**4/(8*E*I), th=q*L**3/(6*E*I), sg=3*q*L**2/(b*h**2).
3. 单位: L(m), b/h(mm 转 m 除以 1000), E(GPa 乘 1e9), P(N), q(N/m); 输出 w(mm), th(mrad), sg(MPa); 计算全用 SI, 只在显示时转.
4. 校验: L>0, b>0, h>0, E>0, P>=0, q>=0, not(P==0 and q==0), 否则 st.error 并 return; 告警必须在 SI 下比较(转 mm 之前): w_max/L>=0.1 时 st.warning(以 w/L 为转角代理指标, 此时几何非线性误差约 3%); h/L>0.1 时 st.warning 剪切变形不可忽略.
5. 叠加: P 与 q 可同时非零, 结果线性叠加, 曲线各 200 点, V/M/w 图正确(V(x): P 为常数 P, q 为 q*(L-x)), V 图默认显示可用 checkbox 关闭.
6. Streamlit: set_page_config 放顶层第一行, 不用 session_state 状态机, 按钮即 rerun, 图用 matplotlib, 标点英文, 汉字中文.
7. 每次贴完整 ```python 代码, 结尾说请代码审查员检查. 禁工具, 禁 TERMINATE, 禁说已保存."""
    return AssistantAgent(name="Engineer", description="按锁定公式写 Streamlit 计算, 只贴码不落盘", model_client=m, system_message=s, model_client_stream=True)

def create_code_reviewer(m):
    s = """你是 CAE 校核工程师, 只审本轮 Engineer 贴出的代码块, 不写整码.

核对表(错一条就打回):
1. 公式: P 的 3 与 6 系数, q 的 8/6/24 系数, M 分布 P*(L-x) 与 q*(L-x)**2/2, 应力 6 与 3 系数, 有无漏平方.
2. 单位: b/h 是否除 1000, E 是否乘 1e9, 输出是否 w(mm)/th(mrad)/sg(MPa), 有无量纲混用.
3. 物理: x=0 固支 w=0/M 最大, x=L 自由 w 最大/M=0; P+q 叠加; 非物理(负刚度、随 x 增大挠度减小)直接打回.
4. 参考: 钢 E=200, L=1, b=50, h=100, P=1000 -> w=0.40mm, th=0.60mrad, sg=12.0MPa; q=1000 -> w=0.15mm, th=0.20mrad, sg=6.0MPa; 叠加 -> w=0.55mm, th=0.80mrad, sg=18.0MPa, 容差 1%%.
5. 工程: 非法输入拦截(not(P==0 and q==0)), 告警在 SI 下比较(w_max/L>=0.1 注明代理指标, 另查 h/L>0.1), set_page_config 顶层, markdown 含 div 必须 unsafe_allow_html.

输出: 有问题说 代码REQUEST_CHANGES: + 定位到函数与公式行; 通过说 代码APPROVE: + 实测参考值, 并说请Publisher落盘. 禁贴整码, 禁工具, 标点英文."""
    return AssistantAgent(name="CodeReviewer", description="核公式系数、单位换算与物理合理性", model_client=m, system_message=s, model_client_stream=True)

def create_publisher(m):
    s = """你是 Publisher, 唯一有写文件工具的人, 绝不自己写码.

流程:
1. 只在代码APPROVE 后行动, 从 Engineer 最近 ```python 块提取完整代码.
2. 依次调 write_file(filename="app.py", content="..."), verify_python_syntax(filename="app.py").
3. 通过说代码已保存到 output/app.py, 语法通过, 请用户代理验证; 失败说落盘失败, 请 Engineer 修复, 并贴错.
4. 绝不改码, 绝不 TERMINATE."""
    return AssistantAgent(name="Publisher", description="APPROVE 后落盘 output/app.py 并语法检查", model_client=m, tools=[write_file, verify_python_syntax, read_file], system_message=s)

def create_user_proxy():
    return UserProxyAgent(name="UserProxy", description="落盘后验收悬臂梁参考值, 通过说 TERMINATE")

selector_prompt = """你是调度员, 只返回一个名字.
- 刚启动 -> ProductManager
- PM 出完/改完需求 -> Architect
- Architect 说需求REQUEST_CHANGES -> ProductManager
- Architect 说需求APPROVE 且 Engineer 未贴码 -> Engineer
- Engineer 刚贴码 -> CodeReviewer
- CodeReviewer 说代码REQUEST_CHANGES -> Engineer
- CodeReviewer 说代码APPROVE -> Publisher
- Publisher 失败 -> Engineer
- Publisher 说请用户代理验证 -> UserProxy
- 全程跳过 UserProxy, 除非已落盘. 当前对话: {history}
"""

async def run_team():
    print("init model...")
    mc = create_openai_model_client()
    print("init team...")
    pm = create_product_manager(mc)
    ar = create_architect(mc)
    en = create_engineer(mc)
    cr = create_code_reviewer(mc)
    pu = create_publisher(mc)
    up = create_user_proxy()
    term = TextMentionTermination("TERMINATE") | MaxMessageTermination(max_messages=40)
    team = SelectorGroupChat(participants=[pm, ar, en, cr, pu, up], model_client=mc, selector_prompt=selector_prompt, termination_condition=term, allow_repeated_speaker=True)
    task = """开发悬臂梁挠度应力计算应用, 要求如下:

输入: L(m), b(mm), h(mm), E(GPa), 载荷类型(P 尖端集中力 N / q 全跨均布 N/m, 可叠加), 默认钢算例 L=1, b=50, h=100, E=200, P=1000.
输出: w_max(mm), theta_max(mrad), sigma_max(MPa), w(x)/M(x)/V(x) 曲线(V 图默认显示, 可用 checkbox 关闭), 非法输入报错, 告警在 SI 下比较(w_max/L>=0.1, h/L>0.1).
物理: Euler-Bernoulli, 小挠度, 矩形截面 I=b*h**3/12, P: w_max=P*L**3/(3*E*I), sg=6*P*L/(b*h**2); q: w_max=q*L**4/(8*E*I), sg=3*q*L**2/(b*h**2). 约束 not(P==0 and q==0).
技术: Streamlit + numpy + matplotlib, 纯本地, 落盘 output/app.py, 标点英文, 汉字中文.
请从需求分析到实现."""
    print("run team...")
    print("=" * 60)
    result = await Console(team.run_stream(task=task))
    print("\n" + "=" * 60)
    print("done.")
    return result

if __name__ == "__main__":
    try:
        r = asyncio.run(run_team())
        print(f"agents: 6, done: {bool(r)}")
    except ValueError as e:
        print(f"config error: {e}")
    except Exception as e:
        print(f"run error: {e}")
        import traceback
        traceback.print_exc()
