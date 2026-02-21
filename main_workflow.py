import os
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from fund_agent import run_fund_agent
from tech_agent import run_tech_agent
from sentiment_agent import run_sentiment_agent
from risk_agent import run_risk_agent


# ==========================================
# 2. 定义全局共享状态 (State)
# ==========================================
class TraderState(TypedDict):
    ticker: str
    api_key:str
    # --- 各部门收集的数据 (用于追溯) ---
    technical_data: str
    fundamental_data: str
    news_data: str
    risk_data: str
    news_links: list
    # --- 各部门提交的报告/信号 ---
    tech_signal: str
    fund_signal: str
    sentiment_signal: str
    risk_signal: str

    # --- 最终决策结果 ---
    final_decision: str


# ==========================================
# 3. 封装节点 (Nodes)
# ==========================================
# LangGraph 的节点函数只需接收 state，并返回需要更新的字典字段即可，它会自动合并状态。
def tech_node(state: TraderState):
    return run_tech_agent(state['ticker'], state['api_key'])

def fund_node(state: TraderState):
    return run_fund_agent(state['ticker'], state['api_key'])

def sentiment_node(state: TraderState):
    return run_sentiment_agent(state['ticker'], state['api_key'])

def risk_node(state: TraderState):
    return run_risk_agent(state['ticker'], state['api_key'])

def decision_node(state: TraderState):
    print("\n[投资委员会] 正在汇总四大部门报告，进行最终多空辩论...")

    # 【新增逻辑：因为把顶部的 llm 删了，我们需要在这里临时创建一个】
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=state['api_key'], # 【核心：使用刚刚从前端传到状态里的 key】
        base_url="https://api.deepseek.com",
        temperature=0.3
    )
    prompt = f"""
    你是对冲基金的首席投资官(CIO)和基金经理。现在你的桌面上放着四份来自不同部门的独立报告，目标标的为：{state['ticker']}。

    【1. 基本面研究员的报告】：
    {state.get('fund_signal', '暂无')}

    【2. 技术面分析师的报告】：
    {state.get('tech_signal', '暂无')}

    【3. 市场情绪分析师的报告】：
    {state.get('sentiment_signal', '暂无')}

    【4. 首席风控官(CRO)的报告】（具有最高优先级）：
    {state.get('risk_signal', '暂无')}

    请你主持一场“多空辩论”，综合各方观点，并输出最终的交易决议。

    【核心决策原则】：
    - 如果风控官亮起红灯，无论其他部门多么看好，必须一票否决（空仓/卖出）。
    - 如果技术面和基本面冲突，请权衡短期赔率与长期胜率。
    - 情绪面可以作为入场时机的辅助验证。

    【输出格式要求】：
    # 🏆 最终决议：(买入 / 卖出 / 观望)
    # 📊 建议仓位：(0% - 100%)
    # ⚖️ 多空辩论总结：(说明你是如何调和部门间矛盾的，采纳了谁的观点，驳回了谁的观点)
    # 🛡️ 核心执行逻辑：(给出具体的交易指令和止损建议)
    """

    response = llm.invoke(prompt)
    return {"final_decision": response.content}


# ==========================================
# 4. 构建并行计算图 (Workflow Graph)
# ==========================================
workflow = StateGraph(TraderState)

# 添加所有节点
workflow.add_node("tech", tech_node)
workflow.add_node("fund", fund_node)
workflow.add_node("sentiment", sentiment_node)
workflow.add_node("risk", risk_node)
workflow.add_node("decision_maker", decision_node)

# 依次执行，避免数据接口冲突和 API 并发频率限制
workflow.add_edge(START, "tech")          # 1. 起点先交给技术组
workflow.add_edge("tech", "fund")         # 2. 技术组弄完给基本面组
workflow.add_edge("fund", "sentiment")    # 3. 基本面组弄完给情绪组
workflow.add_edge("sentiment", "risk")    # 4. 情绪组弄完给风控组
workflow.add_edge("risk", "decision_maker") # 5. 最后统一交给投资委员会
workflow.add_edge("decision_maker", END)  # 6. 做出决定，流程结束

# 编译成可执行应用
app = workflow.compile()

# ==========================================
# 5. 运行完整多智能体系统
# ==========================================
if __name__ == "__main__":
    target_ticker = "sh.600519"  # 依然使用贵州茅台做测试

    print("=" * 60)
    print(f"🚀 [系统启动] 正在为 {target_ticker} 召开多智能体投资决策会议...")
    print("=" * 60)

    # 传入初始状态
    inputs = {"ticker": target_ticker}

    # invoke 会自动执行图逻辑
    result = app.invoke(inputs)

    print("\n\n" + "★" * 60)
    print(" " * 20 + "CEO 桌面上的最终报告")
    print("★" * 60)
    print(result['final_decision'])
    print("★" * 60)