import os
import concurrent.futures
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from fund_agent import run_fund_agent
from tech_agent import run_tech_agent
from sentiment_agent import run_sentiment_agent
from risk_agent import run_risk_agent


# ==========================================
# 1. 定义全局共享状态 (State)
# ==========================================
class TraderState(TypedDict):
    ticker: str
    api_key: str
    # --- 数据与初始信号 ---
    technical_data: str
    fundamental_data: str
    news_data: str
    risk_data: str
    news_links: list
    tech_signal: str
    fund_signal: str
    sentiment_signal: str
    risk_signal: str
    chart_data:list
    # --- 【新增】多轮辩论状态 ---
    debate_history: str
    debate_round: int

    # --- 最终决策 ---
    final_decision: str
def gather_node(state: TraderState):
    """【并行节点】利用多线程同时唤醒 4 个部门，大幅提升速度"""
    print(f"\n[调度中心] 正在并行唤醒四大部门对 {state['ticker']} 进行分析...")

    # 使用线程池并发执行 4 个任务
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        f_tech = executor.submit(run_tech_agent, state['ticker'], state['api_key'])
        f_fund = executor.submit(run_fund_agent, state['ticker'], state['api_key'])
        f_sent = executor.submit(run_sentiment_agent, state['ticker'], state['api_key'])
        f_risk = executor.submit(run_risk_agent, state['ticker'], state['api_key'])

        # 等待所有线程完成并获取结果
        res_tech = f_tech.result()
        res_fund = f_fund.result()
        res_sent = f_sent.result()
        res_risk = f_risk.result()

    # 统一合并到状态中
    return {
        "technical_data": res_tech.get("technical_data", ""),
        "tech_signal": res_tech.get("tech_signal", ""),
        "chart_data": res_tech.get("chart_data", []),
        "fundamental_data": res_fund.get("fundamental_data", ""),
        "fund_signal": res_fund.get("fund_signal", ""),
        "news_data": res_sent.get("news_data", ""),
        "news_links": res_sent.get("news_links", []),
        "sentiment_signal": res_sent.get("sentiment_signal", ""),
        "risk_data": res_risk.get("risk_data", ""),
        "risk_signal": res_risk.get("risk_signal", ""),
        "debate_history": "",  # 初始化辩论历史
        "debate_round": 0  # 初始化辩论轮次
    }
def debate_node(state: TraderState):
    """【辩论节点】负责针对各部门报告进行交叉质询"""
    round_count = state.get("debate_round", 0)
    history = state.get("debate_history", "")
    print(f"\n[会议室] 正在进行第 {round_count + 1} 轮多空激辩...")

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=state['api_key'],
        base_url="https://api.deepseek.com",
        temperature=0.6  # 稍微调高温度，让辩论思维更发散和敏锐
    )

    if round_count == 0:
        prompt = f"""
                你现在主持一场严肃的量化投研会议。目标标的：{state['ticker']}。
                以下是四大部门的初始独立报告：
                【基本面】{state['fund_signal']}
                【技术面】{state['tech_signal']}
                【情绪面】{state['sentiment_signal']}
                【风控面】{state['risk_signal']}

                【任务】：
                作为客观且极具批判精神的“魔鬼代言人”，请找出这四份报告中逻辑冲突或过于乐观的地方。
                请基于数据、历史规律或宏观常识提出尖锐的质疑，开启第一轮辩论。
                注意：不要给出最终结论，你的目标是“寻找数据漏洞”和“揭示潜在尾部风险”。
                """
    else:
        prompt = f"""
                针对标的：{state['ticker']} 的投研辩论正在进行。
                以下是之前的辩论记录：
                {history}

                【任务】：
                请针对上一轮的疑点，进行第 {round_count + 1} 轮的反驳。
                要求：
                1. 必须使用科学理性的视角，避免情绪化的主观臆断。
                2. 探讨胜率（Probability of Success）与赔率（Risk-Reward Ratio）。
                3. 模拟不同流派（如价值投资 vs 趋势跟踪）的严谨交锋。
                """

    response = llm.invoke(prompt)
    new_text = f"\n\n=== 第 {round_count + 1} 轮辩论 ===\n" + response.content

    return {
        "debate_history": history + new_text,
        "debate_round": round_count + 1
    }
def should_continue_debate(state: TraderState):
    """【路由守卫】决定是否继续辩论"""
    # 设定我们只进行 2 轮激辩，防止死循环和过度消耗 Token
    if state.get("debate_round", 0) < 3:
        return "continue_debate"
    else:
        return "make_decision"
def decision_node(state: TraderState):
    """【决策节点】CIO 综合所有报告和辩论历史拍板"""
    print("\n[投资委员会] 辩论结束，CIO 正在撰写最终决议...")

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=state['api_key'],
        base_url="https://api.deepseek.com",
        temperature=0.3
    )
    prompt = f"""
    你是对冲基金的首席投资官(CIO)。现在你要为 {state['ticker']} 做出最终决策。

    【核心风控红线】（具有最高优先级）：
    {state.get('risk_signal', '暂无')}

    【前置多轮辩论记录】：
    {state.get('debate_history', '暂无辩论记录')}

    【核心决策原则】：
    1. 风险第一：如果风控报告提示明确的系统性或个体尾部风险，严格执行一票否决。
    2. 期望值思维：评估盈亏比（赔率）和确定性（胜率），寻找“安全边际”。
    3. 综合辩论：不偏听偏信单一指标，依据多轮辩论中未被成功驳倒的核心逻辑进行决策。

    【输出格式要求】：
    # 🏆 最终决议：(强力买入 / 逢低分批建仓 / 观望 / 减仓 / 清仓)
    # 📊 建议仓位暴露：(精确到个位数的百分比，如 15%)
    # ⚖️ 科学决策复盘：(详细说明你是如何基于“胜率与赔率”的权衡，综合基本面估值与技术面趋势，做出的理性裁决)
    # 🛡️ 严格执行计划：(必须包含具体的入场区间、止盈目标位和硬性止损价)
    """

    response = llm.invoke(prompt)
    return {"final_decision": response.content}
workflow = StateGraph(TraderState)

# 1. 添加节点
workflow.add_node("gather_agents", gather_node)
workflow.add_node("debate_room", debate_node)
workflow.add_node("decision_maker", decision_node)

# 2. 定义边 (Edges)
workflow.add_edge(START, "gather_agents")  # 起点先让四大部门并行干活
workflow.add_edge("gather_agents", "debate_room")  # 干完活进入会议室辩论

# 3. 定义条件边 (循环辩论核心)
workflow.add_conditional_edges(
    "debate_room",
    should_continue_debate,
    {
        "continue_debate": "debate_room",  # 条件满足，继续绕回辩论室
        "make_decision": "decision_maker"  # 条件不满足（满2轮），交给 CIO 决策
    }
)

workflow.add_edge("decision_maker", END)  # CIO 决策完毕，流程结束

# 编译成可执行应用
app = workflow.compile()

# ==========================================
# 4. 运行完整多智能体系统测试
# ==========================================
if __name__ == "__main__":
    target_ticker = "sh.600519"

    print("=" * 60)
    print(f"🚀 [系统启动] 正在为 {target_ticker} 召开多智能体投资决策会议...")
    print("=" * 60)

    # 替换成你的真实 API key 进行独立测试
    inputs = {"ticker": target_ticker, "api_key": "sk-xxxxxx"}

    result = app.invoke(inputs)

    print("\n\n" + "★" * 60)
    print(" " * 20 + "CEO 桌面上的最终报告")
    print("★" * 60)
    print(result['final_decision'])
    print("★" * 60)