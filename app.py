from flask import Flask, request, jsonify
from flask_cors import CORS
from main_workflow import app as agent_app
app = Flask(__name__)
CORS(app)

@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    data = request.get_json()
    if not data or 'ticker' not in data or 'api_key' not in data:
        return jsonify({"status": "error", "message": "缺少股票代码或 API Key"}), 400

    ticker = data['ticker']
    api_key = data['api_key']

    print(f"\n[API 接收请求] 开始为 {ticker} 执行多智能体分析...")

    try:
        inputs = {"ticker": ticker, "api_key": api_key}
        result = agent_app.invoke(inputs)
        debate_history = result.get('debate_history', '未获取到辩论记录')
        # 解决隐患二：使用 .get() 安全读取，缺失时赋予默认值
        final_decision = result.get('final_decision', '未生成最终决议')
        tech_signal = result.get('tech_signal', '技术面分析失败')
        fund_signal = result.get('fund_signal', '基本面分析失败')
        sentiment_signal = result.get('sentiment_signal', '情绪面分析失败')
        risk_signal = result.get('risk_signal', '风控分析失败')
        macro_signal = result.get('macro_signal', '宏观面分析失败')
        chart_data = result.get('chart_data', [])

        # 提取我们在 sentiment_agent 中新增的新闻链接列表
        news_links = result.get('news_links', [])
        macro_news_links = result.get('macro_news_links', [])
        return jsonify({
            "status": "success",
            "ticker": ticker,
            "data": {
                "decision": final_decision,
                "debate_history":debate_history,
                "chart_data":chart_data,
                "reports": {
                    "macro":macro_signal,
                    "technical": tech_signal,
                    "fundamental": fund_signal,
                    "sentiment": sentiment_signal,
                    "risk": risk_signal
                },
                "news_links": news_links,
                "macro_news_links":macro_news_links
            }
        })

    except Exception as e:
        # 解决隐患一：捕获所有未知异常，防止服务器宕机
        print(f"[API 异常] 分析 {ticker} 时发生错误: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"后端分析过程中发生错误：{str(e)}"
        }), 500
if __name__ == '__main__':
    # 启动 Flask 服务，开启 debug 模式方便你在开发时查看日志
    print("🚀 正在启动多智能体交易 API 服务...")
    app.run(host='0.0.0.0', port=5000, debug=True)