import os
from datetime import datetime
from langchain_openai import ChatOpenAI

# 【关键新增】：直接复用我们在情绪组写好的强大双引擎搜索工具
from sentiment_agent import search_web_context


def get_macro_context(ticker: str, llm: ChatOpenAI) -> str:
    """
    让大模型先识别股票所属行业
    """
    mapping_prompt = f"""
    请告诉我A股股票代码 {ticker} 对应的公司简称以及它所属的细分行业（例如：半导体、新能源、白酒、国防军工等）。
    请只输出“公司简称,行业名称”。
    """
    try:
        mapping_res = llm.invoke(mapping_prompt).content.strip()
        parts = mapping_res.replace('，', ',').split(',')
        if len(parts) >= 2:
            stock_name = parts[0].strip()
            industry = parts[1].strip()
        else:
            stock_name = mapping_res
            industry = "核心资产"
    except:
        stock_name = ticker
        industry = "重点行业"

    print(f"   [宏观组解析] 目标: {stock_name} | 所属行业: {industry}")
    return stock_name, industry


def run_macro_agent(ticker: str, api_key: str) -> dict:
    """
    宏观与国际局势智能体主函数 (已升级联网检索能力)
    """
    print(f"\n[宏观组] 正在从国家战略与地缘政治维度推演 {ticker} 的长期宏观逻辑...")
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0.4
    )

    # 1. 解析公司与行业
    stock_name, industry = get_macro_context(ticker, llm)

    # 2. 【新增】：针对行业构造宏观维度的定向搜索词
    policy_query = f"{industry} 行业 国家政策 扶持 补贴 顶层设计 最新消息"
    geo_query = f"{industry} 出海 关税 制裁 中美博弈 国际局势 最新消息"

    print(f"   [宏观检索] 正在深度挖掘政策面: {policy_query}")
    policy_context, raw_policy_news = search_web_context(policy_query, max_results=3)

    print(f"   [宏观检索] 正在深度挖掘地缘面: {geo_query}")
    geo_context, raw_geo_news = search_web_context(geo_query, max_results=3)

    # 3. 【新增】：合并搜索情报，并提取前端所需的链接格式
    macro_news_context = f"【国内政策面情报】:\n{policy_context}\n\n【国际地缘局势情报】:\n{geo_context}"

    macro_news_links = []
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    for item in raw_policy_news + raw_geo_news:
        macro_news_links.append({
            "title": "【宏观/地缘】" + item.get("title", "宏观动态"),
            "content": item.get("body", "暂无摘要"),
            "url": item.get("href", "#"),
            "source": "顶层定向检索",
            "time": current_time
        })

    # 4. 升级 Prompt，把热乎的联网情报喂给大模型
    prompt = f"""
    你是顶尖智库的【宏观与国家战略总监】。现在正在评估标的：{stock_name}（股票代码：{ticker}，所属行业：{industry}）。

    以下是我们全网最新抓取的关于该行业的【政策与地缘政治情报】：
    {macro_news_context}

    【请结合上述实时情报，从以下三个维度进行硬核推演】：
    1. 国际局势与大国博弈：结合抓取到的地缘情报，该行业当前面临的是制裁打压、关税壁垒还是出海机遇？
    2. 国家宏观政策导向：结合抓取到的政策情报，该行业是否顺应当前国家的顶层战略？
    3. 全球货币与宏观周期：美联储降息/加息、汇率波动对该行业资产定价是利好还是利空？

    【输出格式要求】：
    【宏观战略定调】(战略看多 / 战略看空 / 周期防御 / 宏观中性)
    【地缘与出海逻辑】(基于最新情报，简述国际局势对它的实质影响)
    【国内政策红利/阻力】(基于最新情报，指出国家顶层设计的态度)
    【核心结论】(一句话总结它在当前宏观大背景下的投资价值)
    """

    response = llm.invoke(prompt)

    # 5. 返回时携带 macro_news_links
    return {
        "macro_data": f"标的：{stock_name}，行业：{industry}\n{macro_news_context}",
        "macro_signal": response.content,
        "macro_news_links": macro_news_links  # <--- 将提取到的链接交出去
    }


if __name__ == "__main__":
    # 测试代码保持不变
    test_ticker = "sh.600519"
    result = run_macro_agent(test_ticker, "sk-xxxxxx")
    print("\n🌍 提取到的宏观链接:", result["macro_news_links"])
    print("\n🧠 宏观总监报告:\n", result["macro_signal"])