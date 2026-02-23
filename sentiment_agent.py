import os
import re
import time as std_time
from datetime import datetime
import requests
import urllib3
from duckduckgo_search import DDGS
from langchain_openai import ChatOpenAI
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
os.environ['ALL_PROXY'] = 'socks5://127.0.0.1:7890'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
URL_SINA_GLOBAL = "https://zhibo.sina.com.cn/api/zhibo/feed?zhibo_id=152&tag_id=0&page=1&page_size=30"
URL_EASTMONEY_NEWS = "https://finance.eastmoney.com/yaowen.html"
URL_10JQKA_REALTIME = "https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize=100"
URL_SINA_ROLL_FUTURES = "https://finance.sina.com.cn/roll/c/56995.shtml"
URL_SINA_HIGHLIGHTS = "https://finance.sina.com.cn/roll/c/56988.shtml"
URL_100PPI = "https://www.100ppi.com/qb/"
URL_MYSTEEL = "https://openapi.mysteel.com/without_sign/newsflash/flashnews/query_by_tags.htm"
URL_WSCN = "https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&client=pc&limit=20"
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
        return {'User-Agent': high_version_ua, 'Referer': 'https://www.100ppi.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Connection': 'keep-alive', 'Cache-Control': 'max-age=0', 'Upgrade-Insecure-Requests': '1'}
    elif source == "mysteel":
        return {'User-Agent': high_version_ua, 'Referer': 'https://www.mysteel.com/', 'Host': 'openapi.mysteel.com',
                'Accept': 'application/json, text/plain, */*', 'Connection': 'keep-alive'}
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
        res = []
        for i in resp.json().get('result', {}).get('data', {}).get('feed', {}).get('list', []):
            # 默认兜底新浪7x24主页
            url = i.get('doc_url') or "https://finance.sina.com.cn/7x24/"
            res.append({
                "title": clean_html(i.get('rich_text', ''))[:60],
                "intro": clean_html(i.get('rich_text', '')),
                "source": "新浪财经",
                "url": url,
                "time_ts": int(datetime.strptime(i.get('create_time'), "%Y-%m-%d %H:%M:%S").timestamp())
            })
        return res
    except:
        return []
def fetch_list_10jqka():
    try:
        resp = requests.get(URL_10JQKA_REALTIME, headers=get_headers(source="10jqka"), timeout=10)
        res = []
        for i in find_news_list_recursively(resp.json())[:30]:
            # 默认兜底同花顺快讯主页
            url = i.get('url') or "https://news.10jqka.com.cn/realtimenews/"
            res.append({
                "title": i.get('title', ''),
                "intro": i.get('digest', i.get('title', '')),
                "source": "同花顺",
                "url": url,
                "time_ts": int(i.get('ctime', std_time.time()))
            })
        return res
    except:
        return []
def fetch_list_wscn():
    try:
        resp = requests.get(URL_WSCN, headers=get_headers(source="wscn"), timeout=10)
        res = []
        for item in resp.json().get('data', {}).get('items', []):
            content = item.get('content_text', '').strip()
            title = item.get('title', '').strip() or (content[:40] + "..." if content else "")

            raw_uri = item.get('uri', '')
            final_url = ""

            # 【修复点】：智能补全华尔街见闻的 https 前缀，去除错误的 Markdown 格式
            if raw_uri:
                final_url = raw_uri if raw_uri.startswith("http") else f"https://wallstreetcn.com{raw_uri}"

            # 检查是否有引用文章的链接
            ref_article = item.get('reference_article')
            if ref_article and isinstance(ref_article, dict) and ref_article.get('uri'):
                ref_uri = ref_article.get('uri')
                final_url = ref_uri if ref_uri.startswith("http") else f"https://wallstreetcn.com{ref_uri}"

            if not final_url and item.get('id'):
                final_url = f"https://wallstreetcn.com/live/global/{item.get('id')}"

            res.append({
                "title": title,
                "intro": content or title,
                "source": "华尔街见闻",
                "url": final_url,
                "time_ts": item.get('display_time', int(std_time.time()))
            })
        return res
    except:
        return []
def fetch_list_eastmoney():
    try:
        headers = get_headers(source="eastmoney")
        resp = requests.get(URL_EASTMONEY_NEWS, headers=headers, timeout=10, verify=False)
        resp.encoding = 'utf-8'
        pattern = re.compile(
            r'<p class="title"[^>]*>.*?<a\s+[^>]*href="(https?://finance\.eastmoney\.com/a/[^"]+)"[^>]*>(.*?)</a>.*?<p class="time">\s*(\d{1,2}月\d{1,2}日\s+\d{2}:\d{2})\s*</p>',
            re.S
        )
        matches = list(pattern.finditer(resp.text))
        res = []
        current_year = datetime.now().year
        for match in matches:
            title = clean_html(match.group(2)).strip()
            time_str = match.group(3)
            try:
                ts = int(datetime.strptime(f"{current_year}年{time_str}", "%Y年%m月%d日 %H:%M").timestamp())
            except:
                ts = int(std_time.time())
            res.append({"title": title, "intro": title, "url": match.group(1), "time_ts": ts, "source": "东财要闻"})
        return res[:30]
    except Exception as e:
        return []
def parse_sina_roll_page(url, source_name):
    try:
        resp = requests.get(url, headers=get_headers(source="sina_html"), timeout=10)
        resp.encoding = resp.apparent_encoding if resp.apparent_encoding else 'gbk'
        pattern = re.compile(
            r'<a\s+href="([^"]+)"[^>]*target="_blank">([^<]+)</a>.*?\((\d{2}月\d{2}日\s+\d{2}:\d{2})\)', re.S)
        matches = pattern.findall(resp.text)
        res = []
        current_year = datetime.now().year
        for url_path, title, time_str in matches[:30]:
            try:
                ts = int(datetime.strptime(f"{current_year}年{time_str}", "%Y年%m月%d日 %H:%M").timestamp())
            except:
                ts = int(std_time.time())
            res.append(
                {"title": title.strip(), "intro": title.strip(), "url": url_path, "time_ts": ts, "source": source_name})
        return res
    except:
        return []
def fetch_list_100ppi():
    try:
        t_param = int(std_time.time() * 1000)
        target_url = f"{URL_100PPI}?_t={t_param}"
        resp = requests.get(target_url, headers=get_headers(source="100ppi"), timeout=15, verify=False)
        html = resp.content.decode('utf-8', errors='ignore')
        item_pattern = re.compile(r'(\d{2}:\d{2}).*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
        matches = list(item_pattern.finditer(html))
        res = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        for i, match in enumerate(matches):
            try:
                time_str = match.group(1)
                initial_url = match.group(2)
                raw_title_html = match.group(3)
                start_pos = match.end()
                end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(html)
                content_block = html[start_pos:end_pos]

                # 获取点击详情的真实链接
                detail_match = re.search(r'href="([^"]+)"[^>]*>\s*点击详情', content_block)
                final_url = detail_match.group(1) if detail_match else initial_url

                # 【修复点】：为生意社的残缺相对路径强制补全 https 前缀
                if not final_url.startswith("http"):
                    final_url = f"https://www.100ppi.com{final_url}" if final_url.startswith(
                        "/") else f"https://www.100ppi.com/{final_url}"

                title_text = clean_html(raw_title_html).strip()
                summary_text = clean_html(content_block).replace("点击详情", "").strip()
                intro = summary_text if len(summary_text) > 5 else title_text
                try:
                    ts = int(datetime.strptime(f"{today_str} {time_str}:00", "%Y-%m-%d %H:%M:%S").timestamp())
                except:
                    ts = int(std_time.time())
                res.append({"title": title_text, "intro": intro, "url": final_url, "time_ts": ts, "source": "生意社"})
            except:
                continue
        return res
    except:
        return []
def fetch_list_mysteel():
    try:
        params = {"advertisementFlag": "0", "keyword": "", "pageNo": "1", "pageSize": "30", "sortByScore": "false",
                  "columnIds": "[[2,84,584]]"}
        resp = requests.get(URL_MYSTEEL, headers=get_headers(source="mysteel"), params=params, timeout=10)
        items = find_news_list_recursively(resp.json())
        res = []
        for item in items[:30]:
            ts_ms = item.get('publishTime') or item.get('createTime') or 0
            ts = int(ts_ms / 1000) if ts_ms > 10000000000 else int(std_time.time())

            link = item.get('linkUrl') or item.get('wapUrl') or ""
            if not link and 'id' in item:
                link = f"https://news.mysteel.com/{item['id']}.html"

            # 【修复点】：复原了你原本后端里的默认跳转兜底逻辑
            if not link:
                link = "https://www.mysteel.com/fastcomment/#/"

            res.append({"title": item.get('title', '').strip(),
                        "intro": clean_html(item.get('content', '') or item.get('summary', '')), "url": link,
                        "time_ts": ts, "source": "我的钢铁"})
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
def llm_pre_process_news(raw_text_block, ticker, llm):
    """
    第一阶段：利用大模型对原始新闻进行语义级的去噪和标签化
    """
    print(f"   [语义过滤] 正在让大模型对 {ticker} 的资讯进行初步鉴定与标签化...")

    prompt = f"""
    你是一个无情的新闻过滤器。以下是抓取到的关于 {ticker} 的原始杂乱资讯：

    {raw_text_block}

    【你的任务】：
    1. 剔除所有与 {ticker} 核心基本面/股价无关的噪音（如日常闲聊、不相干的广告、无意义的重复通稿）。
    2. 对保留下来的高价值新闻进行压缩，并打上标签。可选标签：[政策宏观]、[财报业绩]、[突发事件]、[市场情绪]。

    【输出格式】：
    请直接输出保留下来的高价值新闻列表，每条一行，格式必须为：
    标签：[xxx] | 核心事件：(用一句话概括) | 潜在影响：(偏多/偏空/中性)
    如果全部都是噪音，请回复“无高价值增量信息”。
    """

    # 调用大模型进行预处理
    response = llm.invoke(prompt)
    return response.content
def filter_and_clean_news(raw_news_list, company_keyword=None, max_count=10):
    """
    【数据清洗管道】负责过滤爬虫抓取到的噪音数据，并保留时间字段
    """
    cleaned_news = []
    seen_titles = set()

    for news in raw_news_list:
        title = news.get("title", "") or news.get("name", "")
        content = news.get("content", "") or news.get("snippet", "") or news.get("intro", "")
        url = news.get("url", "") or news.get("link", "")
        source = news.get("source", "网络")

        # --- 新增：提取并格式化时间 ---
        raw_time = news.get("time") or news.get("time_ts")
        if isinstance(raw_time, int):
            # 如果是时间戳，转为易读的字符串格式
            from datetime import datetime
            time_str = datetime.fromtimestamp(raw_time).strftime('%Y-%m-%d %H:%M')
        else:
            time_str = raw_time or "近期"

        if not title or title in seen_titles:
            continue
        if len(content) < 15 and len(title) < 5:
            continue
        if company_keyword and (company_keyword not in title and company_keyword not in content):
            continue

        seen_titles.add(title)

        # 统一标准化格式并保留源链接（新增 time 字段）
        cleaned_news.append({
            "title": title,
            "content": content,
            "url": url,
            "source": source,
            "time": time_str  # 解决前端 undefined 的问题
        })

        if len(cleaned_news) >= max_count:
            break

    return cleaned_news
def run_sentiment_agent(ticker: str, api_key: str) -> dict:
    print(f"\n[情绪组] 正在全网搜集 {ticker} 的新闻资讯与散户舆情...")
    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0.3
    )

    # ==========================================
    # 步骤 A: 抓取全网最新宏观快讯
    # ==========================================
    print("   [爬虫集群] 正在拉取 新浪/同花顺/华尔街见闻 实时滚动快讯...")
    raw_macro_news = (
            fetch_list_sina() +
            fetch_list_eastmoney() +
            fetch_list_10jqka() +
            parse_sina_roll_page(URL_SINA_ROLL_FUTURES, "新浪期货-滚动") +
            parse_sina_roll_page(URL_SINA_HIGHLIGHTS, "新浪期货-要闻") +
            fetch_list_100ppi() +
            fetch_list_mysteel() +
            fetch_list_wscn()
    )
    # 假设你的原始数据里有 time_ts 这个字段用于排序
    raw_macro_news.sort(key=lambda x: x.get('time_ts', 0), reverse=True)

    # 清洗宏观新闻 (不需要传入 ticker 作为过滤词，以保留大盘政策信息)
    cleaned_macro = filter_and_clean_news(raw_macro_news, max_count=15)
    macro_text = ""
    for item in cleaned_macro:
        macro_text += f"[{item['source']}] {item['title']}\n"

    # ==========================================
    # 步骤 B: 针对标的定向搜索 (DuckDuckGo)
    # ==========================================
    stock_code = ticker.split('.')[-1] if '.' in ticker else ticker
    search_query = f"{stock_code} 股票 突发 最新消息 涨跌原因"
    print(f"   [定向搜索] 正在通过 DuckDuckGo 深度挖掘: {search_query}")

    # 假设 search_web_context 返回 (纯文本摘要, 原始字典列表)
    _, raw_specific_news = search_web_context(search_query, max_results=8)

    # 清洗微观情报
    # 清洗微观情报
    cleaned_specific = filter_and_clean_news(raw_specific_news, max_count=8)
    specific_news_text = ""
    for i, news in enumerate(cleaned_specific, 1):
        specific_news_text += f"【新闻 {i}】标题：{news['title']}\n摘要：{news['content']}\n\n"

    # ==========================================
    # 步骤 B.5: 组装展示给前端的新闻列表并增加标识
    # (注意：这段代码必须在 for 循环的外面！！！)
    # ==========================================
    # 1. 如果微观（个股）新闻没搜到（如网络超时），增加一条系统提示
    if not cleaned_specific:
        cleaned_specific = [{
            "title": f"⚠️ 未检索到 {ticker} 的定向微观新闻",
            "content": "个股定向搜索接口可能超时或被拦截。以下为您展示全网最新的宏观大盘与行业快讯，作为市场环境参考。",
            "url": "javascript:void(0);",
            "source": "系统提示",
            "time": datetime.now().strftime('%Y-%m-%d %H:%M')
        }]

    # 2. 给宏观新闻加上醒目的前缀，防止误会
    for item in cleaned_macro:
        if not item['title'].startswith("【宏观大势】"):
            item['title'] = "【宏观大势】" + item['title']

    # 合并高质量新闻，用于返回给前端展示可点击的链接
    final_news_links = cleaned_specific + cleaned_macro[:5]
    # ==========================================
    # 步骤 C: 调用 DeepSeek 分析情绪
    # ==========================================
    print("   [大脑思考] 正在综合微观个股与宏观大势，评估市场情绪...")

    # 【全面升级的 Prompt：既有宏观，又有微观】
    n_data = f"""
        【1. 标的定向微观情报】:
        {specific_news_text}

        【2. 当前大盘宏观背景】:
        {macro_text}
        """
    cleaned_and_tagged_news = llm_pre_process_news(n_data, ticker, llm)

    print(f"   [过滤完成] 提炼出的高价值标签化情报如下：\n{cleaned_and_tagged_news}")

    # ==========================================
    # 步骤 C: 调用 DeepSeek 分析情绪 (修改最终的 Prompt)
    # ==========================================
    print("   [大脑思考] 正在基于高纯度情报评估最终市场情绪...")

    # 【修改点】：将最终的 Prompt 替换成喂给它“洗好的标签化数据”
    prompt = f"""
        你是资深的量化对冲基金舆情分析师。
        以下是我为你提供经过严格预清洗和标签化的关于标的 {ticker} 的核心高价值情报：

        {cleaned_and_tagged_news}
    【任务要求】
    1. 结合宏观大势和微观个股情报，分析整体情绪。
    2. 忽略中性的日常公告，请像猎犬一样精准定位对股价有实质性影响的事件。

    【输出格式要求】（请严格按此格式输出）
    【情绪观点】看涨/看跌/震荡中性
    【核心驱动事件】(提取最具影响力的关键新闻，并简述其潜在的看多/看空逻辑)
    【潜在情绪风险】(当前是否存在舆论上的隐患、“买预期，卖事实”的风险或系统性大盘风险？)
    """

    response = llm.invoke(prompt)

    return {
        "news_data": specific_news_text + "\n" + macro_text,
        "news_links": final_news_links,
        "sentiment_signal": response.content
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