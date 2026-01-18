from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)

# 完整的 CORS 設定，允許從任何來源訪問
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "bypass-tunnel-reminder"]
    }
})

# 健康檢查端點
@app.route('/health', methods=['GET'])
def health():
    """用於檢查伺服器是否正常運作"""
    return jsonify({
        "status": "ok",
        "message": "伺服器運作正常",
        "timestamp": datetime.now().isoformat()
    })

# 主要聊天端點
@app.route('/chat', methods=['POST'])
def chat():
    """處理聊天訊息"""
    try:
        # 檢查是否有 JSON 資料
        data = request.json
        if not data:
            return jsonify({"error": "請求中沒有 JSON 資料"}), 400
        
        # 取得訊息
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "訊息不能為空"}), 400
        
        # 記錄到終端機
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 收到訊息: {user_message}")
        
        # 這裡可以加入你的 AI 邏輯
        # 例如：呼叫 Claude API、本地 AI 模型等
        reply = f"本地電腦已收到：{user_message}"
        
        # 回傳回覆
        return jsonify({
            "reply": reply,
            "timestamp": timestamp
        })
    
    except Exception as e:
        # 錯誤處理
        error_msg = f"伺服器錯誤: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

# 根路徑 - 簡單的歡迎訊息
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Flask 伺服器運作中",
        "endpoints": {
            "/health": "健康檢查 (GET)",
            "/chat": "聊天端點 (POST)"
        }
    })

# 錯誤處理器
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "找不到此端點"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "內部伺服器錯誤"}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Flask 伺服器啟動中...")
    print("=" * 50)
    print("📡 本地網址: http://localhost:5000")
    print("💡 提示: 請使用 Localtunnel 建立公網隧道")
    print("   指令: lt --port 5000 --subdomain lochen5511")
    print("=" * 50)
    
    # 啟動伺服器
    app.run(
        host='0.0.0.0',  # 允許外部連線 (Localtunnel 需要)
        port=5000,
        debug=True  # 開發模式，生產環境請改為 False
    )