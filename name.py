from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from collections import defaultdict
import os, subprocess, threading
from datetime import datetime

# ──────────────────────────────────────────
# 設定
# ──────────────────────────────────────────
LOG_DIR  = r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

@app.after_request
def cors_headers(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# ──────────────────────────────────────────
# 狀態（記憶體）
# ──────────────────────────────────────────
message_queues    = defaultdict(list)   # session_id -> [訊息]
thinking_states   = {}                  # session_id -> bool
user_input_queues = defaultdict(list)   # session_id -> [用戶輸入]
launched_sessions = set()               # 已啟動 button.py 的 session


# ──────────────────────────────────────────
# 工具
# ──────────────────────────────────────────
def write_log(log_path: str, content: str):
    if not log_path:
        return
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(content + '\n')
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def launch_button(username, session_id, log_path):
    subprocess.Popen(
        ['python', 'button.py',
         '--username',   username,
         '--session_id', session_id,
         '--log_path',   log_path],
        cwd=BASE_DIR
    )


# ──────────────────────────────────────────
# Routes
# ──────────────────────────────────────────

# ── /enter ──────────────────────────────
@app.route('/enter', methods=['POST', 'OPTIONS'])
def enter():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data     = request.get_json() or {}
    username = data.get('username', '').strip()

    if not username:
        return jsonify({'success': False, 'error': '名字不能為空'}), 400

    os.makedirs(LOG_DIR, exist_ok=True)
    session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path   = os.path.join(LOG_DIR, f"{username}_{session_id}.txt")

    # 建立空 log 檔
    open(log_path, 'a', encoding='utf-8').close()

    print(f"[enter] username={username} session_id={session_id}")
    return jsonify({'success': True, 'session_id': session_id})


# ── /greeting ───────────────────────────
@app.route('/greeting', methods=['POST', 'OPTIONS'])
def greeting():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')
    log_path   = os.path.join(LOG_DIR, f"{username}_{session_id}.txt")

    if session_id and session_id not in launched_sessions:
        launched_sessions.add(session_id)
        threading.Thread(
            target=launch_button,
            args=(username, session_id, log_path),
            daemon=True
        ).start()
        print(f"[greeting] 啟動 button.py  session={session_id}")
    else:
        print(f"[greeting] session={session_id} 已啟動，跳過")

    reply = '> 系統初始化中。\n(若在3分鐘內未跳出下一步，請重新開啟頁面，或聯絡助教)\n助教信箱：u11301126@go.utaipei.edu.tw'
    return jsonify({'reply': reply})


# ── /push（button.py 推送訊息）──────────
@app.route('/push', methods=['POST', 'OPTIONS'])
def push():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    text       = data.get('text', '').strip()
    session_id = data.get('session_id', '')
    log_path   = data.get('log_path', '')

    if not text:
        return jsonify({'success': False}), 400

    message_queues[session_id].append(text)
    print(f"[push] session={session_id} queue_len={len(message_queues[session_id])} text={text[:40]}")

    # 寫入 log（按鈕訊息不寫）
    if log_path and not text.startswith('__'):
        write_log(log_path, f"AI：{text}")

    return jsonify({'success': True})


# ── /poll（前端輪詢）────────────────────
@app.route('/poll', methods=['GET', 'OPTIONS'])
def poll():
    if request.method == 'OPTIONS':
        return Response(status=200)

    session_id  = request.args.get('session_id', '')
    queue       = message_queues.get(session_id, [])
    is_thinking = thinking_states.get(session_id, False)

    if queue:
        text = queue.pop(0)
        print(f"[poll] session={session_id} 取出訊息 text={text[:40]}")
        return jsonify({'message': text, 'thinking': False})

    return jsonify({'message': None, 'thinking': is_thinking})


# ── /thinking（button.py 控制動畫）──────
@app.route('/thinking', methods=['POST', 'OPTIONS'])
def thinking():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    session_id = data.get('session_id', '')
    state      = data.get('thinking', False)
    thinking_states[session_id] = state
    return jsonify({'success': True})


# ── /chat（用戶訊息送入隊列）────────────
@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    message    = data.get('message', '').strip()
    session_id = data.get('session_id', '')
    username   = data.get('username', '未知').strip()

    if not message:
        return jsonify({'reply': ''}), 400

    log_path = os.path.join(LOG_DIR, f"{username}_{session_id}.txt")
    write_log(log_path, f"用戶：{message}")

    user_input_queues[session_id].append(message)
    print(f"[chat] session={session_id} message={message[:40]}")

    return jsonify({'reply': ''})


# ── /fetch_user_input（button.py 取用戶輸入）──
@app.route('/fetch_user_input', methods=['GET', 'OPTIONS'])
def fetch_user_input():
    if request.method == 'OPTIONS':
        return Response(status=200)

    session_id = request.args.get('session_id', '')
    queue      = user_input_queues.get(session_id, [])

    if queue:
        msg = queue.pop(0)
        print(f"[fetch_user_input] session={session_id} message={msg[:40]}")
        return jsonify({'message': msg})

    return jsonify({'message': None})


# ── /log（前端記錄訊息）─────────────────
@app.route('/log', methods=['POST', 'OPTIONS'])
def log_message():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')
    role       = data.get('role', 'unknown')
    message    = data.get('message', '').strip()

    if not message:
        return jsonify({'success': False}), 400

    log_path = os.path.join(LOG_DIR, f"{username}_{session_id}.txt")
    label    = '用戶' if role == 'user' else 'AI'
    write_log(log_path, f"{label}：{message}")

    return jsonify({'success': True})


# ──────────────────────────────────────────
# 啟動
# ──────────────────────────────────────────
if __name__ == '__main__':
    print("✅ name.py 伺服器啟動中...")
    print(f"📁 Log 資料夾：{LOG_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=True)