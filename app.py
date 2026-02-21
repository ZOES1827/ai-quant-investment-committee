from flask import Flask, request, jsonify
from flask_cors import CORS
# 导入你已经编译好的多智能体图
from main_workflow import app as agent_app
app = Flask(__name__)
CORS(app)

@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    # 尝试获取前端传来的 JSON 数据
    data = request.get_json()
    if not data or 'ticker' not in data or 'api_key' not in data:
        return jsonify({"status": "error", "message": "缺少股票代码或 API Key"}), 400

    ticker = data['ticker']
    api_key = data['api_key']

    print(f"\n[API 接收请求] 开始为 {ticker} 执行多智能体分析...")

    try:
        inputs = {"ticker": ticker, "api_key": api_key}
        result = agent_app.invoke(inputs)

        # 解决隐患二：使用 .get() 安全读取，缺失时赋予默认值
        final_decision = result.get('final_decision', '未生成最终决议')
        tech_signal = result.get('tech_signal', '技术面分析失败')
        fund_signal = result.get('fund_signal', '基本面分析失败')
        sentiment_signal = result.get('sentiment_signal', '情绪面分析失败')
        risk_signal = result.get('risk_signal', '风控分析失败')

        # 提取我们在 sentiment_agent 中新增的新闻链接列表
        news_links = result.get('news_links', [])

        # 将整理好的安全数据以 JSON 格式返回给前端
        return jsonify({
            "status": "success",
            "ticker": ticker,
            "data": {
                "decision": final_decision,
                "reports": {
                    "technical": tech_signal,
                    "fundamental": fund_signal,
                    "sentiment": sentiment_signal,
                    "risk": risk_signal
                },
                "news_links": news_links
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