from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import openai
import os
from dotenv import load_dotenv
import uuid
from pathlib import Path

app = Flask(__name__)
load_dotenv(r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\.env")
openai.api_key = os.getenv("AIKEY")

# 用於存儲每個用戶的對話記憶
user_memories = {}
# 用於存儲每個用戶的名字
user_names = {}
# 用於存儲每個用戶的日誌檔案路徑
user_log_files = {}
# 用於存儲已結束對話的用戶 ID
ended_chat_users = set()

# 日誌資料夾路徑
LOG_FOLDER = r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log"

def ensure_log_folder():
    """確保日誌資料夾存在"""
    Path(LOG_FOLDER).mkdir(parents=True, exist_ok=True)

def get_user_log_file(user_name):
    """取得用戶日誌檔案路徑"""
    return os.path.join(LOG_FOLDER, f"{user_name}.txt")

def get_system_message():
    """返回系統提示訊息"""
    return {
        "role": "system",
        "content": "You are a knight named Shrimp-Head Knight, and you have sworn to protect all the shrimp in the world. Only use Chinese to talk with user."
    }

def get_or_create_user_memory(user_id):
    """獲取或創建用戶的記憶列表"""
    if user_id not in user_memories:
        user_memories[user_id] = [get_system_message()]
    return user_memories[user_id]

def has_user_provided_name(user_id):
    """檢查用戶是否已提供名字"""
    return user_id in user_names

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
        
        # 獲取或創建用戶 ID
        user_id = data.get("user_id")
        if not user_id:
            user_id = str(uuid.uuid4())
        
        # 取得訊息
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "訊息不能為空"}), 400
        
        # 檢查用戶是否已結束對話
        if user_id in ended_chat_users:
            return jsonify({"error": "對話已結束，無法發送訊息"}), 403
        
        # 獲取該用戶的記憶列表
        user_memory = get_or_create_user_memory(user_id)
        
        # 檢查是否是新用戶（還未提供名字）
        if not has_user_provided_name(user_id):
            # 確保日誌資料夾存在
            ensure_log_folder()
            
            # 這是用戶的第一條訊息，將其作為名字儲存
            user_names[user_id] = user_message
            greeting_reply = f"很高興認識你，{user_message}！我是蝦頭騎士。請問有什麼我可以幫助你的嗎？"
            user_memory.append({"role": "user", "content": user_message})
            user_memory.append({"role": "assistant", "content": greeting_reply})
            
            # 建立用戶日誌檔案
            log_file = get_user_log_file(user_message)
            user_log_files[user_id] = log_file
            
            # 記錄到終端機和用戶日誌
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] 新用戶 {user_id} 名字: {user_message}")
            
            # 寫入用戶日誌檔案
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"=== 對話開始時間: {timestamp} ===\n")
                f.write(f"用戶名字: {user_message}\n\n")
                f.write(f"[{timestamp}] AI: {greeting_reply}\n")
            
            return jsonify({
                "reply": greeting_reply,
                "user_id": user_id,
                "user_name": user_message,
                "timestamp": timestamp,
                "is_name_collection": True
            })
        
        # 正常聊天流程
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 用戶 {user_id} ({user_names[user_id]}): {user_message}")
        user_memory.append({"role": "user", "content": user_message})
        
        # 取得用戶日誌檔案
        if user_id not in user_log_files:
            user_log_files[user_id] = get_user_log_file(user_names[user_id])
        
        log_file = user_log_files[user_id]
        
        # 寫入用戶訊息到日誌檔案
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] 用戶: {user_message}\n")
        
        # 呼叫 OpenAI API
        reply = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=user_memory,
            temperature=0.7,  # 此段為隨機度，從0到1，數值越大越隨機，越小越精確
            )
        ai_reply = (reply["choices"][0]["message"]["content"])
        user_memory.append({"role": "assistant", "content": ai_reply})
        
        # 寫入 AI 回覆到日誌檔案
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] AI: {ai_reply}\n")
        
        # 回傳回覆（包含用戶 ID 和名字）
        return jsonify({
            "reply": ai_reply,
            "user_id": user_id,
            "user_name": user_names[user_id],
            "timestamp": timestamp,
            "is_name_collection": False
        })
    
    except Exception as e:
        # 錯誤處理
        error_msg = f"伺服器錯誤: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

# 初始化端點 - 新用戶時返回問候
@app.route('/init', methods=['POST'])
def init():
    """初始化新用戶並返回問候"""
    try:
        data = request.json
        user_id = data.get("user_id")
        
        if not user_id:
            user_id = str(uuid.uuid4())
        
        # 檢查用戶是否已存在
        if has_user_provided_name(user_id):
            return jsonify({
                "message": "用戶已初始化",
                "user_id": user_id,
                "user_name": user_names[user_id]
            })
        
        # 新用戶 - 返回問候訊息
        greeting = "你好，你叫什麼名字呢？"
        get_or_create_user_memory(user_id)  # 初始化記憶
        
        return jsonify({
            "greeting": greeting,
            "user_id": user_id,
            "message": "請輸入您的名字以開始對話"
        })
    
    except Exception as e:
        error_msg = f"初始化錯誤: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

# 結束對話端點
@app.route('/end_chat', methods=['POST'])
def end_chat():
    """結束用戶對話"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "請求中沒有 JSON 資料"}), 400
        
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id 不能為空"}), 400
        
        # 檢查用戶是否已結束對話
        if user_id in ended_chat_users:
            return jsonify({"error": "對話已結束"}), 400
        
        # 標記用戶對話已結束
        ended_chat_users.add(user_id)
        
        # 獲取用戶名字
        user_name = user_names.get(user_id, "用戶")
        
        # 記錄到日誌檔案
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 用戶 {user_id} ({user_name}) 結束對話")
        
        if user_id in user_log_files:
            log_file = user_log_files[user_id]
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n[{timestamp}] === 對話結束 ===\n")
        
        # 返回結束對話訊息
        closing_message = "感謝今天的對談，祝您生活愉快。"
        
        return jsonify({
            "reply": closing_message,
            "user_id": user_id,
            "timestamp": timestamp
        })
    
    except Exception as e:
        error_msg = f"結束對話錯誤: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

# 重新開始對話端點
@app.route('/restart_chat', methods=['POST'])
def restart_chat():
    """重新開始用戶對話"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "請求中沒有 JSON 資料"}), 400
        
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id 不能為空"}), 400
        
        # 清除用戶狀態
        if user_id in ended_chat_users:
            ended_chat_users.remove(user_id)
        
        if user_id in user_memories:
            del user_memories[user_id]
        
        if user_id in user_names:
            del user_names[user_id]
        
        if user_id in user_log_files:
            del user_log_files[user_id]
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 用戶 {user_id} 重新開始對話")
        
        return jsonify({
            "message": "已重新開始對話",
            "user_id": user_id,
            "timestamp": timestamp
        })
    
    except Exception as e:
        error_msg = f"重新開始對話錯誤: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

# 根路徑 - 簡單的歡迎訊息
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "Flask 伺服器運作中",
        "endpoints": {
            "/health": "健康檢查 (GET)",
            "/init": "初始化新用戶 (POST)",
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
    print("   指令: npx localtunnel --port 5000 --subdomain lochen5511")
    print("=" * 50)
    
    # 啟動伺服器
    app.run(
        host='0.0.0.0',  # 允許外部連線 (Localtunnel 需要)
        port=5000,
        debug=True  # 開發模式，生產環境請改為 False
    )