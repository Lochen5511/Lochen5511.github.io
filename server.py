from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid
import os
from pathlib import Path
from name import create_user_file

# 獲取當前檔案所在的絕對路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# 用於存儲每個用戶的名字
user_names = {}
# 用於存儲每個用戶的對話記憶（可選，如果需要記憶功能）
user_messages = {}

# 日誌資料夾路徑
LOG_FOLDER = r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log"

def ensure_log_folder():
    """確保日誌資料夾存在"""
    Path(LOG_FOLDER).mkdir(parents=True, exist_ok=True)

# 完整的 CORS 設定，允許從任何來源訪問
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# 健康檢查端點
@app.route('/api/health', methods=['GET'])
def health():
    """用於檢查伺服器是否正常運作"""
    return jsonify({
        "status": "ok",
        "message": "伺服器運作正常",
        "timestamp": datetime.now().isoformat()
    })

# 儲存名字端點
@app.route('/api/save-name', methods=['POST'])
def save_name():
    """處理名字儲存請求"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "請求中沒有 JSON 資料"}), 400
        
        user_name = data.get('name', '')
        
        # 呼叫 name.py 的函式建立檔案
        success, result = create_user_file(user_name)
        
        if success:
            # 回傳成功
            return jsonify({
                'success': True,
                'message': '檔案已建立',
                'file_path': result
            }), 200
        else:
            # 回傳錯誤
            return jsonify({
                'success': False,
                'message': result
            }), 400
    
    except Exception as e:
        error_msg = f"伺服器錯誤: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

# 聊天端點（基本版本，可以根據需求擴展）
@app.route('/api/init', methods=['POST'])
def init():
    """用戶進入頁面時自動觸發，AI 先開口"""
    try:
        data = request.json
        user_id = data.get('user_id') or str(uuid.uuid4())
        user_name = data.get('user_name', '用戶')

        user_names[user_id] = user_name

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        opening_message = f"嗨{user_name}！我是本次學習的主持人「艾評」！"

        print(f"[{timestamp}] {user_name} 進入系統")

        return jsonify({
            "reply": opening_message,
            "user_id": user_id,
            "timestamp": timestamp
        }), 200

    except Exception as e:
        return jsonify({"error": f"初始化錯誤: {str(e)}"}), 500

# 提供 HTML 檔案
@app.route('/')
def index():
    """返回入口頁面"""
    index_path = os.path.join(BASE_DIR, 'index.html')
    print(f"🔍 嘗試讀取: {index_path}")
    
    if not os.path.exists(index_path):
        return jsonify({
            "error": "找不到 index.html",
            "searched_path": index_path,
            "current_dir": BASE_DIR,
            "files_in_dir": os.listdir(BASE_DIR)
        }), 404
    
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return jsonify({"error": f"讀取檔案失敗: {str(e)}"}), 500

@app.route('/main.html')
def main_page():
    """返回主頁面"""
    main_path = os.path.join(BASE_DIR, 'main.html')
    print(f"🔍 嘗試讀取: {main_path}")
    
    if not os.path.exists(main_path):
        return jsonify({
            "error": "找不到 main.html",
            "searched_path": main_path,
            "current_dir": BASE_DIR,
            "files_in_dir": os.listdir(BASE_DIR)
        }), 404
    
    try:
        with open(main_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        return jsonify({"error": f"讀取檔案失敗: {str(e)}"}), 500

# 錯誤處理器
@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "內部伺服器錯誤"}), 500

if __name__ == '__main__':
    ensure_log_folder()  # 確保日誌資料夾存在
    
    print("=" * 50)
    print("🚀 Flask 伺服器啟動中...")
    print("=" * 50)
    print(f"📁 工作資料夾: {BASE_DIR}")
    print(f"📄 檔案列表: {os.listdir(BASE_DIR)}")
    print("📡 本地網址: http://localhost:8000")
    print("📁 日誌資料夾:", LOG_FOLDER)
    print("💡 按 Ctrl+C 停止伺服器")
    print("=" * 50)
    
    # 啟動伺服器
    app.run(
        host='0.0.0.0',  # 允許外部連線
        port=8000,
        debug=True  # 開發模式
    )