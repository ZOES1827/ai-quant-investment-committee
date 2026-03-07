import os
import baostock as bs
import pandas as pd
import datetime
from langchain_openai import ChatOpenAI
import numpy as np


# ==========================================
# 2. 数据获取与处理 (新增 6 大核心技术因子)
# ==========================================
def get_k_data_with_indicators(code="sh.600000", days=150):  # 将获取天数从 100 增加到 150，确保长周期指标计算准确
    bs.login()
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)

    rs = bs.query_history_k_data_plus(
        code,
        "date,open,high,low,close,volume,pctChg,turn",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        frequency="d",
        adjustflag="3"
    )

    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    bs.logout()

    if not data_list:
        return "暂无 K 线数据", []

    df = pd.DataFrame(data_list, columns=rs.fields)
    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'pctChg', 'turn']
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)

    # --- 因子 1: 均线系统 (MA5, MA20) ---
    df['MA5'] = df['close'].rolling(window=5).mean().round(2)
    df['MA20'] = df['close'].rolling(window=20).mean().round(2)

    # --- 因子 2: MACD (平滑异同移动平均线) ---
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD_DIF'] = (exp1 - exp2).round(3)
    df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean().round(3)
    df['MACD'] = ((df['MACD_DIF'] - df['MACD_DEA']) * 2).round(3)

    # --- 因子 3: RSI (14日相对强弱指数) ---
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs_val = gain / loss
    df['RSI'] = (100 - (100 / (1 + rs_val))).round(2)

    # --- 因子 4: ATR (14日真实波幅) ---
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean().round(3)

    # --- 因子 5: BOLL (布林带 20日2倍标准差) ---
    df['BOLL_MID'] = df['close'].rolling(window=20).mean().round(2)
    std = df['close'].rolling(window=20).std(ddof=0)
    df['BOLL_UP'] = (df['BOLL_MID'] + 2 * std).round(2)
    df['BOLL_LOW'] = (df['BOLL_MID'] - 2 * std).round(2)

    # --- 因子 6: KDJ (9,3,3) ---
    low_list = df['low'].rolling(9, min_periods=1).min()
    high_list = df['high'].rolling(9, min_periods=1).max()
    rsv = (df['close'] - low_list) / (high_list - low_list + 1e-8) * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean().round(2)
    df['D'] = df['K'].ewm(com=2, adjust=False).mean().round(2)
    df['J'] = (3 * df['K'] - 2 * df['D']).round(2)

    # 清理头部计算产生的 NaN 数据，替换为 None
    df = df.replace({np.nan: None})

    # 将包含了全部新因子的数据转换为前端所需的图表数据格式
    # （这里暂不修改前端画图逻辑，但数据已经备好，未来可随时在 ECharts 增加 MACD/RSI 副图）
    chart_data = df[['date', 'open', 'close', 'low', 'high', 'MA5', 'MA20', 'MACD', 'RSI', 'ATR']].to_dict(
        orient='records')

    # 为了避免输入给 LLM 的上下文过长，我们精简喂给大模型的列
    llm_df = df[['date', 'close', 'pctChg', 'MA5', 'MA20', 'MACD', 'RSI', 'ATR', 'BOLL_UP', 'BOLL_LOW', 'J']]

    # 只取最近 15 天的数据喂给大模型
    recent_data = llm_df.tail(15)
    return recent_data.to_string(index=False), chart_data


# ==========================================
# 3. 智能体核心逻辑
# ==========================================
def run_tech_agent(ticker: str, api_key: str) -> dict:
    print(f"[技术组] 正在获取并计算 {ticker} 的 6 大核心量价因子...")
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0.3
    )

    k_data_text, chart_data = get_k_data_with_indicators(ticker)

    # 【修改点】全面升级 Prompt，要求大模型综合 6 大因子进行专业分析
    prompt = f"""
    你是华尔街资深量化技术分析师。以下是该股票最近 15 个交易日的核心技术指标矩阵数据：
    {k_data_text}

    【指标字典参考】：
    - MA5/MA20: 短期与中期均线
    - MACD: 趋势与动能（正负代表多空，变动代表动能增减）
    - RSI: 相对强弱（>70超买，<30超卖）
    - ATR: 真实波动率（用于评估当前市场活跃度及设定止损幅度）
    - BOLL_UP / BOLL_LOW: 布林带上下轨（衡量价格极值与通道运行状况）
    - J: KDJ指标中的J线（最敏锐的情绪指标，>100超买，<0超卖）

    请基于以上 6 大维度的多因子数据，进行严谨的技术面交叉验证分析。
    输出格式要求：
    【技术面总基调】(看涨 / 看跌 / 震荡 / 突破临界)
    【多因子交叉验证】(详细解读均线趋势、MACD动量、RSI与KDJ超买超卖状态、布林带位置的共振或背离现象)
    【波动与风控】(结合 ATR 波动率给出具体的支撑位、阻力位，以及合理的止损点位距离建议)
    【实盘操作建议】(基于当下技术形态的短期操作策略)
    """

    response = llm.invoke(prompt)

    return {
        "technical_data": k_data_text,
        "tech_signal": response.content,
        "chart_data": chart_data
    }


if __name__ == "__main__":
    test_ticker = "sh.600519"  # 测试标的：贵州茅台
    print(f"🚀 启动技术分析智能体独立测试 (目标: {test_ticker})...")

    # 注意：独立测试时请填入你的真实 key
    result = run_tech_agent(test_ticker, "sk-xxxxxx这里换成你的真实key")

    print("\n" + "=" * 50)
    print("📈 提取到的多因子数据矩阵 (最近15天):")
    print(result["technical_data"])
    print("\n" + "=" * 50)
    print("🧠 智能体技术分析报告:")
    print(result["tech_signal"])
    print("=" * 50)