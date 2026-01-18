from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime

app = Flask(__name__)
# 允許來自 GitHub Pages 的請求
CORS(app)

@app.route('/chat', methods=['POST']) # 改成 /chat
def chat_handler():
    data = request.json
    user_text = data.get('message', '')
    
    # --- 這裡儲存資料到你的電腦 ---
    with open("log.txt", "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] 用戶: {user_text}\n")
    
    # --- 這裡可以接你的 AI 邏輯 ---
    # 範例：簡單的回傳邏輯
    ai_reply = f"已收到您的訊息：'{user_text}'。這筆資料已存入我的電腦硬碟中。"
    
    return jsonify({"reply": ai_reply})

if __name__ == '__main__':
    # 運行在 5000 端口
    app.run(port=5000)