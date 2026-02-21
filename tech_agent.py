import os
import baostock as bs
import pandas as pd
import datetime
from langchain_openai import ChatOpenAI

# ==========================================
# 2. 数据获取与处理 (Baostock + Pandas)
# ==========================================
def get_k_data_with_indicators(code="sh.600000", days=60):
    """
    获取 K 线数据，并计算常用的技术指标（如移动平均线）
    """
    bs.login()

    # 获取过去几天的日期范围
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)

    rs = bs.query_history_k_data_plus(
        code,
        "date,open,high,low,close,volume,pctChg,turn",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        frequency="d",
        adjustflag="3"  # 3：后复权，适合看长期趋势
    )

    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    bs.logout()

    if not data_list:
        return "暂无 K 线数据"

    # 转换为 DataFrame 并转换数据类型
    df = pd.DataFrame(data_list, columns=rs.fields)
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'pctChg', 'turn']
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)

    # 增加技术指标：5日均线和20日均线
    df['MA5'] = df['close'].rolling(window=5).mean().round(2)
    df['MA20'] = df['close'].rolling(window=20).mean().round(2)

    # 只取最近 15 天的数据喂给大模型（避免上下文过长）
    recent_data = df.tail(15)

    return recent_data.to_string(index=False)


# ==========================================
# 3. 智能体核心逻辑
# ==========================================
def run_tech_agent(ticker: str, api_key: str) -> dict:
    """
    技术分析智能体的主执行函数。

    参数:
        ticker: 股票代码，例如 'sh.600519'
    返回:
        包含原始数据和分析信号的字典
    """
    print(f"[技术组] 正在获取并分析 {ticker} 的量价走势与均线系统...")
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,  # 使用参数传过来的 key
        base_url="https://api.deepseek.com",
        temperature=0.3  # （注意：各个agent原有的温度保留不变，比如risk是0.1）
    )
    k_data = get_k_data_with_indicators(ticker)

    # 2. 构建给 DeepSeek 的提示词 (Prompt)
    prompt = f"""
    你是资深技术分析师。以下是该股票最近 15 个交易日的日 K 线数据（包含 MA5 和 MA20 均线）：
    {k_data}

    请根据价格走势、成交量变化以及均线系统（如金叉、死叉、多头/空头排列）进行技术面分析。

    输出格式要求：
    【观点】看涨/看跌/震荡观望
    【形态与指标】(简述均线状态、支撑位或阻力位、量价配合情况)
    【操作建议】(短期内的交易倾向)
    """

    # 3. 调用大模型
    response = llm.invoke(prompt)

    # 4. 返回结果字典
    return {
        "technical_data": k_data,
        "tech_signal": response.content
    }


# ==========================================
# 4. 独立测试入口
# ==========================================
if __name__ == "__main__":
    test_ticker = "sh.600519"  # 测试标的：贵州茅台
    print(f"🚀 启动技术分析智能体独立测试 (目标: {test_ticker})...")

    result = run_tech_agent(test_ticker,"sk-xxxxxx这里换成你的真实key")

    print("\n" + "=" * 50)
    print("📈 提取到的 K 线与均线数据 (最近15天):")
    print(result["technical_data"])
    print("\n" + "=" * 50)
    print("🧠 智能体技术分析报告:")
    print(result["tech_signal"])
    print("=" * 50)