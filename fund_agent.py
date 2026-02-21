import os
import baostock as bs
import pandas as pd
import datetime
from langchain_openai import ChatOpenAI

def get_finance_data(code="sh.600000"):
    """
    获取基本面数据：近期盈利能力
    """
    bs.login()

    # 动态计算上一个年份，确保能稳定取到数据
    current_year = datetime.datetime.now().year
    target_year = current_year - 1
    target_quarter = 3  # 默认取三季报演示

    rs = bs.query_profit_data(code=code, year=target_year, quarter=target_quarter)
    data = []
    while (rs.error_code == '0') & rs.next():
        data.append(rs.get_row_data())
    bs.logout()

    if not data:
        return f"暂无 {code} {target_year}年Q{target_quarter} 财报数据"

    return pd.DataFrame(data, columns=rs.fields).to_string()


# ==========================================
# 3. 智能体核心逻辑
# ==========================================
def run_fund_agent(ticker: str, api_key: str) -> dict:
    """
    基本面智能体的主执行函数。
    ...
    """
    print(f"[基本面组] 正在审计 {ticker} 的财务报表...")
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key, # 使用参数传过来的 key
        base_url="https://api.deepseek.com",
        temperature=0.3  # （注意：各个agent原有的温度保留不变，比如risk是0.1）
    )

    # 1. 获取基础数据
    f_data = get_finance_data(ticker)

    # 2. 构建给 DeepSeek 的提示词 (Prompt)
    prompt = f"""
    你是资深行业研究员。根据以下财务数据（重点关注 ROE, 净利率等）：
    {f_data}

    请判断该公司的盈利能力和成长性。
    输出格式要求：
    【观点】看好/看空/中性
    【核心数据】(简述核心指标的表现)
    【理由】(详细的分析逻辑)
    """

    # 3. 调用大模型
    response = llm.invoke(prompt)

    # 4. 返回结果字典
    return {
        "fundamental_data": f_data,
        "fund_signal": response.content
    }


# ==========================================
# 4. 独立测试入口
# ==========================================
# 只有当你直接运行 python fund_agent.py 时，下面的代码才会执行。
# 这非常适合你进行单步调试。
if __name__ == "__main__":
    test_ticker = "sh.600519"  # 拿贵州茅台做测试
    print(f"🚀 启动基本面智能体独立测试 (目标: {test_ticker})...")
    result = run_fund_agent(test_ticker, "sk-xxxxxx这里换成你的真实key")
    print("\n" + "=" * 40)
    print("📊 提取到的原始财务数据:")
    print(result["fundamental_data"])
    print("\n" + "=" * 40)
    print("🧠 智能体分析报告:")
    print(result["fund_signal"])
    print("=" * 40)