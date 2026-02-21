import os
import re
import time as std_time
from datetime import datetime
import requests
import urllib3
from duckduckgo_search import DDGS
from langchain_openai import ChatOpenAI

# 禁用 HTTPS 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 抓取源常量配置
URL_SINA_GLOBAL = "https://zhibo.sina.com.cn/api/zhibo/feed?zhibo_id=152&tag_id=0&page=1&page_size=30"
URL_EASTMONEY_NEWS = "https://finance.eastmoney.com/yaowen.html"
URL_10JQKA_REALTIME = "https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize=100"
URL_SINA_ROLL_FUTURES = "https://finance.sina.com.cn/roll/c/56995.shtml"
URL_SINA_HIGHLIGHTS = "https://finance.sina.com.cn/roll/c/56988.shtml"
URL_100PPI = "https://www.100ppi.com/qb/"
URL_MYSTEEL = "https://openapi.mysteel.com/without_sign/newsflash/flashnews/query_by_tags.htm"
URL_WSCN = "https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&client=pc&limit=20"


# ==========================================
# 2. 爬虫工具函数 (完美继承你的 Backend 逻辑)
# ==========================================
def get_headers(referer="https://www.baidu.com", source="default"):
    base_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    high_version_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0'
    if source == "10jqka":
        return {'User-Agent': high_version_ua, 'Referer': referer, 'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01', 'Connection': 'keep-alive'}
    elif source == "eastmoney":
        return {'User-Agent': high_version_ua, 'Referer': 'https://finance.eastmoney.com/', 'Accept': '*/*',
                'Connection': 'keep-alive'}
    elif source == "sina_html":
        return {'User-Agent': high_version_ua, 'Referer': 'https://finance.sina.com.cn/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive'}
    elif source == "100ppi":
        return {'User-Agent': high_version_ua, 'Referer': 'https://www.100ppi.com/', 'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1'}
    elif source == "wscn":
        return {'User-Agent': high_version_ua, 'Referer': 'https://wallstreetcn.com/',
                'Origin': 'https://wallstreetcn.com', 'Connection': 'keep-alive'}
    return {'User-Agent': base_ua, 'Referer': referer, 'Accept': '*/*', 'Connection': 'keep-alive'}


def clean_html(text):
    if not text: return ""
    return re.sub(r'<[^>]+>', '', text).strip()


def find_news_list_recursively(data):
    if isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], dict):
            if any(k in data[0].keys() for k in ['content', 'title', 'digest', 'ctime', 'publishTime']): return data
        for item in data:
            res = find_news_list_recursively(item)
            if res: return res
    elif isinstance(data, dict):
        for key in ['list', 'data', 'items', 'result']:
            if key in data:
                res = find_news_list_recursively(data[key])
                if res: return res
        for value in data.values():
            if isinstance(value, (dict, list)):
                res = find_news_list_recursively(value)
                if res: return res
    return []


# --- 各大网站爬虫模块 ---
def fetch_list_sina():
    try:
        resp = requests.get(URL_SINA_GLOBAL, headers=get_headers(), timeout=10, verify=False)
        return [{"title": clean_html(i.get('rich_text', ''))[:60], "intro": clean_html(i.get('rich_text', '')),
                 "source": "新浪财经",
                 "time_ts": int(datetime.strptime(i.get('create_time'), "%Y-%m-%d %H:%M:%S").timestamp())} for i in
                resp.json().get('result', {}).get('data', {}).get('feed', {}).get('list', [])]
    except:
        return []


def fetch_list_10jqka():
    try:
        resp = requests.get(URL_10JQKA_REALTIME, headers=get_headers(source="10jqka"), timeout=10)
        return [{"title": i.get('title', ''), "intro": i.get('digest', i.get('title', '')), "source": "同花顺",
                 "time_ts": int(i.get('ctime', std_time.time()))} for i in find_news_list_recursively(resp.json())[:30]]
    except:
        return []


def fetch_list_wscn():
    try:
        resp = requests.get(URL_WSCN, headers=get_headers(source="wscn"), timeout=10)
        res = []
        for item in resp.json().get('data', {}).get('items', []):
            content = item.get('content_text', '').strip()
            title = item.get('title', '').strip() or (content[:40] + "..." if content else "")
            res.append({"title": title, "intro": content or title, "source": "华尔街见闻",
                        "time_ts": item.get('display_time', int(std_time.time()))})
        return res
    except:
        return []


# ==========================================
# 3. 定向搜索与深度抓取 (DuckSearch)
# ==========================================
def fetch_url_content_realtime(url, source="default"):
    if not url or not url.startswith("http"): return ""
    try:
        resp = requests.get(url, headers=get_headers(url, source=source), timeout=10, verify=False)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        paragraphs = re.findall(r'<p.*?>(.*?)</p>', resp.text, re.S)
        return "\n".join([clean_html(p) for p in paragraphs if len(clean_html(p)) > 10])[:800]
    except:
        return ""


def search_web_context(query, max_results=5):
    """使用 DuckDuckGo 进行全网定向搜索"""
    print(f"   [DuckSearch] 正在全网检索关键词: '{query}'")
    results = []
    try:
        with DDGS(timeout=15) as ddgs:
            results = list(ddgs.text(query, region='wt-wt', safesearch='off', timelimit='w', max_results=max_results))
    except Exception as e:
        print(f"   ⚠️ 搜索警告: {e}")

    if not results:
        return "（未搜到近期强相关的定向资讯）",[]

    context_str = ""
    raw_news_list = []
    for i, res in enumerate(results):
        # 提取相关字段，注意 DuckDuckGo 返回的链接字段通常是 'href'
        title = res.get('title', '未知标题')
        url = res.get('href', '#')  # 抓取原网址
        body = res.get('body', '')
        published = res.get('published', '近期')

        context_str += f"[{i + 1}] 来源: {title}\n    时间: {published}\n    内容: {body}\n\n"

        # 新增：将字典存入列表
        raw_news_list.append({
            "title": title,
            "url": url,
            "content": body,
            "time": published
        })
    return context_str, raw_news_list


# ==========================================
# 4. 智能体核心逻辑
# ==========================================
def run_sentiment_agent(ticker: str,api_key:str) -> dict:
    print(f"\n[情绪组] 正在全网搜集 {ticker} 的新闻资讯与散户舆情...")
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,  # 使用参数传过来的 key
        base_url="https://api.deepseek.com",
        temperature=0.3  # （注意：各个agent原有的温度保留不变，比如risk是0.1）
    )
    # 步骤 A: 抓取全网最新宏观快讯
    print("   [爬虫集群] 正在拉取 新浪/同花顺/华尔街见闻 实时滚动快讯...")
    raw_news = fetch_list_sina() + fetch_list_10jqka() + fetch_list_wscn()
    raw_news.sort(key=lambda x: x['time_ts'], reverse=True)

    # 去重并提取前 15 条作为宏观背景
    macro_background = []
    seen = set()
    for item in raw_news:
        if item['title'] not in seen:
            seen.add(item['title'])
            macro_background.append(f"[{item['source']}] {item['title']}")
        if len(macro_background) >= 15: break

    macro_text = "\n".join(macro_background)

    # 步骤 B: 针对标的定向搜索 (使用 DuckDuckGo)
    stock_code = ticker.split('.')[-1] if '.' in ticker else ticker
    search_query = f"{stock_code} 股票 突发 最新消息 涨跌原因"
    specific_news_text, raw_news_list = search_web_context(search_query, max_results=4)
    n_data = f"""
    【1. 标的定向微观情报 (DuckDuckGo 搜索)】:
    {specific_news_text}

    【2. 当前大盘宏观背景 (7x24小时全网财经快讯)】:
    {macro_text}
    """

    # 步骤 C: 调用 DeepSeek 分析情绪
    print("   [大脑思考] 正在综合微观个股与宏观大势，评估市场情绪...")
    prompt = f"""
    你是资深市场情绪与行为金融学分析师。以下是关于标的代码 {ticker} 的近期特定新闻，以及当前全市场的宏观资讯快报：
    {n_data}

    请执行以下“情绪过滤协议”：
    1. 评估微观事件的量级：该标的自身的新闻是实质性利好/利空，还是噪音？
    2. 结合宏观背景：当前大盘情绪（根据快讯判断）是在配合该标的上涨，还是压制该标的？
    3. 评估散户/主力的博弈状态（贪婪 vs 恐慌）。

    输出格式要求：
    【情绪指数】贪婪 / 恐慌 / 中性分化
    【核心驱动力】(指出是哪条微观新闻或宏观逻辑在主导)
    【情绪与大盘共振】(该股票当前情绪是顺应大盘还是逆势博弈？)
    """

    response = llm.invoke(prompt)

    return {
        "news_data": n_data,
        "sentiment_signal": response.content,
        "news_links": raw_news_list  # 新增：把带有 URL 的新闻列表传递出去
    }


# ==========================================
# 5. 独立测试入口
# ==========================================
if __name__ == "__main__":
    test_ticker = "sh.600519"  # 测试标的：贵州茅台
    print(f"🚀 启动【全网版】市场情绪智能体独立测试 (目标: {test_ticker})")
    print("-" * 50)

    result = run_sentiment_agent(test_ticker, "sk-xxxxxx这里换成你的真实key")

    print("\n" + "=" * 50)
    print("🌐 搜集到的原始舆情与爬虫聚合数据:")
    print(result["news_data"])
    print("\n" + "=" * 50)
    print("🧠 智能体情绪分析报告:")
    print(result["sentiment_signal"])
    print("=" * 50)