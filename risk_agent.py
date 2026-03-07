import os
import baostock as bs
import pandas as pd
import datetime
import numpy as np
from langchain_openai import ChatOpenAI

# ==========================================
# 2. 数据获取与指标计算
# ==========================================
def get_market_and_volatility_data(code="sh.600000", days=20):
    """
    获取大盘指数走势，以及个股的真实波动率
    """
    bs.login()
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    # 1. 获取个股数据计算波动率
    rs_stock = bs.query_history_k_data_plus(
        code, "date,close,pctChg", start_date=start_str, end_date=end_str, frequency="d", adjustflag="3"
    )
    stock_data = []
    while (rs_stock.error_code == '0') & rs_stock.next():
        stock_data.append(rs_stock.get_row_data())

    df_stock = pd.DataFrame(stock_data, columns=rs_stock.fields)

    # 2. 获取上证指数 (sh.000001) 看系统性风险
    rs_index = bs.query_history_k_data_plus(
        "sh.000001", "date,close,pctChg", start_date=start_str, end_date=end_str, frequency="d"
    )
    index_data = []
    while (rs_index.error_code == '0') & rs_index.next():
        index_data.append(rs_index.get_row_data())

    bs.logout()

    df_index = pd.DataFrame(index_data, columns=rs_index.fields)

    # --- 数据处理与指标计算 ---
    report = "【获取风控数据失败】"
    if not df_stock.empty and not df_index.empty:
        # 计算个股近期波动率 (简单实现：取涨跌幅的标准差)
        df_stock['pctChg'] = pd.to_numeric(df_stock['pctChg'])
        volatility = round(df_stock['pctChg'].std(), 2)

        # 查看大盘近5天的累计涨跌
        df_index['pctChg'] = pd.to_numeric(df_index['pctChg'])
        index_recent_chg = round(df_index['pctChg'].tail(5).sum(), 2)

        # 模拟真实的账户风控状态
        account_status = """
        - 当前账户总仓位: 60%
        - 距离风控清盘线: 还有 8% 的安全垫
        - 单票最大允许仓位: 20%
        """

        report = f"""
        【1. 宏观系统性风险】
        - 上证指数近5天累计涨跌幅: {index_recent_chg}% (若小于 -3% 视为大盘环境恶劣)

        【2. 标的资产风险敞口】
        - 该标的近期日化波动率: {volatility}% (若大于 3% 视为高波动极高风险)
        - 近3日极端下跌次数(跌幅>5%): {sum(df_stock['pctChg'].tail(3) < -5)} 次

        【3. 账户合规与风控限制】
        {account_status}
        """
    return report


# ==========================================
# 3. 智能体核心逻辑
# ==========================================
def run_risk_agent(ticker: str,api_key:str) -> dict:
    """
    风控智能体主函数
    """
    print(f"\n[风控组] 正在评估 {ticker} 的交易风险敞口与大盘环境...")
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,  # 使用参数传过来的 key
        base_url="https://api.deepseek.com",
        temperature=0.3  # （注意：各个agent原有的温度保留不变，比如risk是0.1）
    )
    # 1. 获取风控数据
    risk_data = get_market_and_volatility_data(ticker)

    prompt = f"""
        你是专业且客观的对冲基金首席风控官(CRO)。你的职责是【量化并客观提示风险】，为投资委员会提供风险敞口评估，而不是直接否决交易。

        以下是当前大盘环境、标的 {ticker} 的波动率以及当前账户状态：
        {risk_data}

        请基于数据执行风险审查：
        1. 评估大盘系统性风险水平。
        2. 评估该股票近期的波动率和极端下跌概率。
        3. 检查账户仓位是否健康。

        请输出你的客观风控评估：
        【风险评级】低风险环境 / 中等风险(提示波动) / 高风险(需极高预期收益补偿，否则不建议重仓)
        【风险揭示逻辑】(客观陈述当前面临的最大潜在风险点是什么，不要使用“禁止”、“强制”等情绪化词汇)
        【安全仓位建议】(在不考虑基本面利好的极端情况下，单凭风控模型建议的持仓上限，例如 5%, 10%, 20%)
        """

    # 3. 调用大模型
    response = llm.invoke(prompt)

    # 4. 返回结果字典
    return {
        "risk_data": risk_data,
        "risk_signal": response.content
    }


# ==========================================
# 4. 独立测试入口
# ==========================================
if __name__ == "__main__":
    test_ticker = "sh.600519"  # 测试标的：贵州茅台
    print(f"🚀 启动风控智能体独立测试 (目标: {test_ticker})")
    print("-" * 50)

    result = run_risk_agent(test_ticker, "sk-xxxxxx这里换成你的真实key")

    print("\n" + "=" * 50)
    print("🛡️ 提取到的量化风控与大盘数据:")
    print(result["risk_data"])
    print("\n" + "=" * 50)
    print("🧠 首席风控官(CRO) 审查报告:")
    print(result["risk_signal"])
    print("=" * 50)