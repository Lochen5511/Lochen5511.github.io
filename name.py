from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)
CORS(app)

LOG_DIR = r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log"

# 每個 session 有自己獨立的訊息隊列
message_queues = defaultdict(list)

@app.route('/push', methods=['POST'])
def push():
    """button.py 呼叫此端點，將訊息放進該 session 的隊列"""
    data       = request.get_json()
    text       = data.get('text', '').strip()
    session_id = data.get('session_id', '')
    username   = data.get('username', '未知').strip()
    log_path   = data.get('log_path', '')

    if not text:
        return jsonify({'success': False}), 400

    # 放進隊列
    message_queues[session_id].append(text)

    # 同步寫入 log
    if log_path:
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] AI：{text}\n")
        except Exception as e:
            print(f"[log 寫入失敗] {e}")

    return jsonify({'success': True})


@app.route('/poll', methods=['GET'])
def poll():
    """main.html 定期呼叫此端點，取出最新一則訊息"""
    session_id = request.args.get('session_id', '')
    queue = message_queues.get(session_id, [])

    if queue:
        text = queue.pop(0)
        return jsonify({'message': text})

    return jsonify({'message': None})


@app.route('/log', methods=['POST'])
def log_message():
    data = request.get_json()
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')
    role       = data.get('role', 'unknown')   # 'user' 或 'ai'
    message    = data.get('message', '').strip()

    if not message:
        return jsonify({'success': False, 'error': '訊息為空'}), 400

    os.makedirs(LOG_DIR, exist_ok=True)

    # 使用與登入時相同的帶時間戳檔名
    filename = f"{username}_{session_id}.txt" if session_id else f"{username}.txt"
    log_path = os.path.join(LOG_DIR, filename)

    label = '用戶' if role == 'user' else 'AI'
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {label}：{message}\n")

    return jsonify({'success': True})


@app.route('/greeting', methods=['POST'])
def greeting():
    import subprocess, threading

    data       = request.get_json() or {}
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')
    log_path   = os.path.join(LOG_DIR, f"{username}_{session_id}.txt") if session_id else os.path.join(LOG_DIR, f"{username}.txt")

    # 在背景執行 button.py，傳入變數作為命令列參數
    def run_button():
        subprocess.Popen(
            ['python', 'button.py',
             '--username',   username,
             '--session_id', session_id,
             '--log_path',   log_path],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

    threading.Thread(target=run_button, daemon=True).start()

    return jsonify({'reply': '> 系統初始化中。\n（若在3分鐘內，未跳出下一步訊息，請重新開啟頁面。刷新未生效時，請通知助教）'})


@app.route('/enter', methods=['POST'])
def enter():
    data = request.get_json()
    username = data.get('username', '').strip()

    if not username:
        return jsonify({'success': False, 'error': '名字不能為空'}), 400

    # 建立 log 資料夾（若不存在）
    os.makedirs(LOG_DIR, exist_ok=True)

    # 建立 {username}_{日期}_{時間}.txt，每次登入產生獨立檔案
    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{username}_{session_id}.txt"
    log_path = os.path.join(LOG_DIR, filename)
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"[登入] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 回傳 session_id 讓前端後續 log 使用
    return jsonify({'success': True, 'session_id': session_id})


if __name__ == '__main__':
    print("✅ name.py 伺服器啟動中...")
    print(f"📁 Log 資料夾：{LOG_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=True)