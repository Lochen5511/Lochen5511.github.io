from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from collections import defaultdict
import os, subprocess, threading, json, time
from datetime import datetime

# ──────────────────────────────────────────
# 設定
# ──────────────────────────────────────────
LOG_DIR   = r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log"
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(LOG_DIR, 'session_db.json')  # session 庫

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
message_queues    = defaultdict(list)
thinking_states   = {}
user_input_queues = defaultdict(list)
launched_sessions = set()
last_seen         = {}
interrupted       = set()
input_locked      = set()   # 聊天框鎖定的 session（按鈕出現時）

USER_TIMEOUT = 300


# ──────────────────────────────────────────
# Session 庫（本地 JSON）
# ──────────────────────────────────────────
def load_db() -> dict:
    """讀取 session 庫"""
    try:
        if os.path.exists(DB_PATH):
            with open(DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[db 讀取失敗] {e}")
    return {}

def save_db(db: dict):
    """寫入 session 庫"""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[db 寫入失敗] {e}")

def register_session(username: str, session_id: str, log_path: str):
    """登記新 session 到庫"""
    db = load_db()
    db[session_id] = {
        'username': username,
        'log_path': log_path,
        'created':  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'unit':     None,  # 待填入
    }
    save_db(db)
    print(f"[db] 登記 session={session_id} user={username}")

def update_session_unit(session_id: str, unit: str):
    """更新 session 的單元記錄"""
    db = load_db()
    if session_id in db:
        db[session_id]['unit'] = unit
        save_db(db)
        print(f"[db] 更新 session={session_id} unit={unit}")

def lookup_session(session_id: str) -> dict | None:
    """查找 session，回傳 {'username', 'log_path'} 或 None"""
    db = load_db()
    return db.get(session_id)


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

def launch_script(script: str, username: str, session_id: str, log_path: str):
    """啟動指定 Python 腳本"""
    subprocess.Popen(
        ['python', script,
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

    open(log_path, 'a', encoding='utf-8').close()

    # 登記到 session 庫
    register_session(username, session_id, log_path)

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
            target=launch_script,
            args=('button.py', username, session_id, log_path),
            daemon=True
        ).start()
        print(f"[greeting] 啟動 button.py  session={session_id}")
    else:
        print(f"[greeting] session={session_id} 已啟動，跳過")

    reply = '> 系統初始化中。\n(若在3分鐘內未跳出下一步，請重新開啟頁面)'
    return jsonify({'reply': reply})


# ── /lock_input ─────────────────────────
@app.route('/lock_input', methods=['POST', 'OPTIONS'])
def lock_input():
    """button.py 呼叫，鎖定或解鎖聊天框"""
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    session_id = data.get('session_id', '')
    locked     = data.get('locked', False)

    if locked:
        input_locked.add(session_id)
    else:
        input_locked.discard(session_id)

    print(f"[lock_input] session={session_id} locked={locked}")
    return jsonify({'success': True})


# ── /update_unit ────────────────────────
@app.route('/update_unit', methods=['POST', 'OPTIONS'])
def update_unit():
    """button.py 呼叫，記錄用戶選擇的單元"""
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    session_id = data.get('session_id', '')
    unit       = data.get('unit', '')

    update_session_unit(session_id, unit)
    return jsonify({'success': True})


# ── /push ───────────────────────────────
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

    if log_path and not text.startswith('__'):
        write_log(log_path, f"AI：{text}")

    return jsonify({'success': True})


# ── /poll ───────────────────────────────
@app.route('/poll', methods=['GET', 'OPTIONS'])
def poll():
    if request.method == 'OPTIONS':
        return Response(status=200)

    session_id  = request.args.get('session_id', '')
    queue       = message_queues.get(session_id, [])
    is_thinking = thinking_states.get(session_id, False)

    last_seen[session_id] = time.time()

    if queue:
        text = queue.pop(0)
        print(f"[poll] session={session_id} 取出訊息 text={text[:40]}")
        return jsonify({'message': text, 'thinking': False, 'input_locked': session_id in input_locked})

    return jsonify({'message': None, 'thinking': is_thinking, 'input_locked': session_id in input_locked})


# ── /check_online ───────────────────────
@app.route('/check_online', methods=['GET', 'OPTIONS'])
def check_online():
    if request.method == 'OPTIONS':
        return Response(status=200)

    session_id = request.args.get('session_id', '')
    timeout    = float(request.args.get('timeout', USER_TIMEOUT))
    seen       = last_seen.get(session_id)

    if seen is None or (time.time() - seen) > timeout:
        return jsonify({'online': False})
    return jsonify({'online': True})


# ── /check_interrupted ──────────────────
@app.route('/check_interrupted', methods=['GET', 'OPTIONS'])
def check_interrupted():
    """腳本輪詢此端點，確認是否被 ID 輸入中斷"""
    if request.method == 'OPTIONS':
        return Response(status=200)

    session_id = request.args.get('session_id', '')
    return jsonify({'interrupted': session_id in interrupted})


# ── /thinking ───────────────────────────
@app.route('/thinking', methods=['POST', 'OPTIONS'])
def thinking():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    session_id = data.get('session_id', '')
    state      = data.get('thinking', False)
    thinking_states[session_id] = state
    return jsonify({'success': True})


# ── /chat ───────────────────────────────
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

    # ── 偵測 ID 輸入（格式 YYYYMMDD_HHMMSS）──
    import re
    if re.fullmatch(r'\d{8}_\d{6}', message.strip()):
        input_id = message.strip()
        record   = lookup_session(input_id)

        if record:
            # 找到記錄：標記中斷，啟動 set_que.py
            target_username = record['username']
            target_log_path = record['log_path']

            interrupted.add(session_id)
            write_log(target_log_path, f'[ID 驗證] 用戶 {username} 以 ID {input_id} 重新進入')

            threading.Thread(
                target=launch_script,
                args=('set_que.py', target_username, input_id, target_log_path),
                daemon=True
            ).start()
            print(f"[chat] ID 驗證成功 input_id={input_id} → 啟動 set_que.py")

        else:
            # 找不到記錄
            message_queues[session_id].append('未找到記錄，請聯絡助教。')
            # 標記此 session 停止回應
            interrupted.add(session_id)
            print(f"[chat] ID 未找到 input_id={input_id}")

        return jsonify({'reply': ''})

    # 一般訊息：若聊天框鎖定則忽略
    if session_id in input_locked:
        print(f"[chat] session={session_id} 輸入框鎖定，忽略訊息: {message[:40]}")
        return jsonify({'reply': ''})

    user_input_queues[session_id].append(message)
    print(f"[chat] session={session_id} message={message[:40]}")
    return jsonify({'reply': ''})


# ── /fetch_user_input ───────────────────
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


# ── /log ────────────────────────────────
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
    print(f"📋 Session 庫：{DB_PATH}")
    app.run(host='0.0.0.0', port=5000, debug=True)