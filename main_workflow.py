import os
import concurrent.futures
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from fund_agent import run_fund_agent
from tech_agent import run_tech_agent
from sentiment_agent import run_sentiment_agent
from risk_agent import run_risk_agent
from macro_agent import run_macro_agent
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
    macro_data: str
    macro_signal: str
    macro_news_links:list
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
        f_macro = executor.submit(run_macro_agent, state['ticker'], state['api_key'])
        # 等待所有线程完成并获取结果
        res_tech = f_tech.result()
        res_fund = f_fund.result()
        res_sent = f_sent.result()
        res_risk = f_risk.result()
        res_macro = f_macro.result()
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
        "macro_data": res_macro.get("macro_data", ""),
        "macro_signal": res_macro.get("macro_signal", ""),
        "macro_news_links": res_macro.get("macro_news_links", []),
        "debate_history": "",  # 初始化辩论历史
        "debate_round": 0  # 初始化辩论轮次
    }
def debate_node(state: TraderState):
    """【辩论节点】四个部门总监互相质询，CIO 每轮总结并调整临时策略"""
    round_count = state.get("debate_round", 0)
    history = state.get("debate_history", "")
    print(f"\n[会议室] 正在进行第 {round_count + 1} 轮多空激辩...")

    # 我们依然使用 deepseek-chat，稍微调高一点温度让辩论更激烈
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=state['api_key'],
        base_url="https://api.deepseek.com",
        temperature=0.6
    )

    # 1. 定义四个部门的角色和他们的初始观点
    roles = {
        "🌍 宏观政策总监": state.get('macro_signal', ''),
        "📈 技术面总监": state.get('tech_signal', ''),
        "📊 基本面总监": state.get('fund_signal', ''),
        "🌐 情绪面总监": state.get('sentiment_signal', ''),
        "🛡️ 首席风控官(CRO)": state.get('risk_signal', '')
    }

    # 定义单个智能体发言的函数
    def agent_speak(role_name, original_signal):
        prompt = f"""
        你是投研委员会的 {role_name}。目前大家正在对标的 {state['ticker']} 进行第 {round_count + 1} 轮激辩。

        你的初始核心观点是：
        {original_signal}

        目前的会议记录/辩论历史：
        {history if history else '这是第一轮辩论，目前还没有历史记录。请直接抛出你的核心论点，并预判其他部门可能的盲区。'}

        【任务】：
        请基于你的专业领域，犀利地反驳其他部门在历史记录中可能存在的逻辑漏洞。
        坚守或修正你的观点。字数控制在 150 字以内，语气要专业且具有战斗力。
        """
        response = llm.invoke(prompt)
        return f"【{role_name}】:\n{response.content}"

    # 2. 【多线程并发】让四个总监同时思考并作出反驳，节省时间
    print(f"   -> 正在等待 5 位总监构思第 {round_count + 1} 轮发言...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(agent_speak, role, signal) for role, signal in roles.items()]
        round_speeches = [f.result() for f in futures]

    # 将四个总监的发言拼接起来
    round_dialogue = "\n\n".join(round_speeches)

    # 3. 唤醒 CIO 进行本轮总结和策略制定
    print(f"   -> 4 位总监发言完毕，CIO 正在做第 {round_count + 1} 轮总结...")
    cio_prompt = f"""
        你是首席投资官(CIO)。现在是第 {round_count + 1} 轮辩论结束。标的：{state['ticker']}。
        本轮各部门负责人的激烈交锋如下：
        {round_dialogue}

        【任务与原则】：
        1. 各大部门地位完全平等。风控官(CRO)仅负责提示风险，没有一票否决权。你需要像一个真正的对冲基金大佬一样，综合衡量“基本面/技术面的向上赔率”与“风控官提示的向下风险”。
        2. 简要总结本轮辩论的核心冲突点（谁的逻辑更占优，是否出现了值得冒险的预期差）。
        3. 给出本轮的【临时投资策略】。明确输出：做多 / 做空 / 观望，并给出建议的仓位比例（如 20%）。如果赔率足够吸引人，请敢于在风险可控的前提下分配仓位。
        """
    cio_summary = llm.invoke(cio_prompt).content
    cio_text = f"\n\n👨‍💼【CIO 第 {round_count + 1} 轮总结与临时决议】:\n{cio_summary}"

    # 4. 组装本轮所有的文本，追加到历史记录中
    new_text = f"\n\n{'=' * 15} 第 {round_count + 1} 轮辩论开始 {'=' * 15}\n" + round_dialogue + cio_text + f"\n{'=' * 45}\n"

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
    """【决策节点】CIO 综合所有报告和辩论历史拍板 (采用科学激进、计算风险的风格)"""
    print("\n[投资委员会] 辩论结束，CIO 正在撰写最终决议...")

    # 可以稍微把温度从 0.3 调高到 0.4，让 CIO 思维更活跃、更敢于博取超额收益
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=state['api_key'],
        base_url="https://api.deepseek.com",
        temperature=0.4
    )

    prompt = f"""
    你是全球顶尖对冲基金的首席投资官(CIO)。现在你要为 {state['ticker']} 做出最终决策。

    【核心风控评估】：
    {state.get('risk_signal', '暂无')}

    【前置多轮辩论记录】：
    {state.get('debate_history', '暂无辩论记录')}
    【核心决策原则】：
    1. 部门平权原则：四大投研部门（宏观、技术、基本面、情绪）与风控部门地位平等。风控报告仅作为计算仓位的安全垫参考，绝不具有一票否决权。
    2. 科学拥抱风险（非绝对保守）：投资是给风险定价的游戏，在“高赔率、非对称收益”的机会面前，允许适当承担合理的回撤风险（Calculated Risk）。
    3. 期望值与动态算仓：不盲目追求绝对安全。如果基本面爆发力或技术面趋势足够强，即使大盘环境有波动，也要敢于通过调整“仓位大小”来参与，而不是一味观望。
    4. 寻找 Alpha 收益：综合多轮辩论，挖掘未被市场充分定价的预期差，大胆假设，小心求证。
    【输出格式要求】：
    # 🏆 最终决议：(强力买入 / 逢低分批建仓 / 激进试错 / 观望 / 减仓 / 清仓)
    # 📊 建议仓位暴露：(精确到个位数的百分比。高风险高赔率可给小仓位买彩票，低风险高确定性可给重仓)
    # ⚖️ 科学决策复盘：(详细说明你是如何打破常规，基于“胜率、赔率与风险补偿”的权衡，做出的带有一点冒险精神但绝对理性的裁决)
    # 🛡️ 严格执行计划：(必须包含具体的入场区间、分批止盈目标位和铁血止损价，用风控纪律为冒险托底)
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