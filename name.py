from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from collections import defaultdict
import os, subprocess, threading, json, time, uuid
from datetime import datetime

# ──────────────────────────────────────────
# 設定
# ──────────────────────────────────────────
LOG_DIR   = r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log"
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(LOG_DIR, 'session_db.json')

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
input_locked      = set()
interrupted_sessions = set()

USER_TIMEOUT = 300


# ──────────────────────────────────────────
# Session 庫（本地 JSON）
# ──────────────────────────────────────────
DB_LOCK      = threading.Lock()
DB_LOCK_FILE = DB_PATH + '.lock'

def _acquire_db_lock(timeout: float = 10.0) -> bool:
    start = time.time()
    while True:
        try:
            fd = os.open(DB_LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            if time.time() - start > timeout:
                print(f"[db] 鎖定逾時，強制繼續")
                return False
            time.sleep(0.05)

def _release_db_lock():
    try:
        os.remove(DB_LOCK_FILE)
    except: pass

def load_db() -> dict:
    try:
        if os.path.exists(DB_PATH):
            with open(DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[db 讀取失敗] {e}")
    return {}

def save_db(db: dict):
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with open(DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[db 寫入失敗] {e}")

def _db_update(update_fn):
    """
    安全的 DB 更新：取得跨進程鎖 → 讀取 → 修改 → 寫入 → 釋放鎖。
    update_fn(db) 直接修改 db dict，不需回傳值。
    """
    with DB_LOCK:  # 執行緒鎖
        acquired = _acquire_db_lock()  # 跨進程鎖
        try:
            db = load_db()
            update_fn(db)
            save_db(db)
        finally:
            if acquired:
                _release_db_lock()

def register_session(username: str, session_id: str, log_path: str):
    def _update(db):
        db[session_id] = {
            'username':  username,
            'log_path':  log_path,
            'created':   datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'unit':      None,
            'return_id': None,
        }
    _db_update(_update)
    print(f"[db] 登記 session={session_id} user={username}")

def update_session_unit(session_id: str, unit: str):
    def _update(db):
        if session_id in db:
            db[session_id]['unit'] = unit
    _db_update(_update)
    print(f"[db] 更新 session={session_id} unit={unit}")

def generate_return_id(session_id: str) -> str:
    import random, string
    result = {'rid': ''}

    def _update(db):
        existing = {v.get('return_id') for v in db.values()
                    if isinstance(v, dict) and v.get('return_id')}
        while True:
            rid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if rid not in existing:
                break
        if session_id in db:
            db[session_id]['return_id'] = rid
        if '__return_index__' not in db:
            db['__return_index__'] = {}
        db['__return_index__'][rid] = session_id
        result['rid'] = rid

    _db_update(_update)
    print(f"[db] 產生 return_id={result['rid']} for session={session_id}")
    return result['rid']

def lookup_return_id(return_id: str) -> dict | None:
    db = load_db()
    index = db.get('__return_index__', {})
    session_id = index.get(return_id)
    if session_id:
        return db.get(session_id)
    return None

def lookup_session(session_id: str) -> dict | None:
    db = load_db()
    return db.get(session_id)


# ──────────────────────────────────────────
# 工具
# ──────────────────────────────────────────
def write_log(log_path: str, content: str):
    """後端結構化紀錄寫入（含時間戳記）"""
    if not log_path:
        return
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def launch_script(script: str, username: str, session_id: str, log_path: str):
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
    session_id  = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
    session_dir = os.path.join(LOG_DIR, f"{username}_{session_id}")
    os.makedirs(session_dir, exist_ok=True)
    log_path    = os.path.join(session_dir, f"{username}_{session_id}.txt")

    open(log_path, 'a', encoding='utf-8').close()

    register_session(username, session_id, log_path)

    print(f"[enter] username={username} session_id={session_id}")
    return jsonify({'success': True, 'session_id': session_id})


# ── / ───────────────────────────
@app.route('/enter_id', methods=['POST', 'OPTIONS'])
def enter_id():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data      = request.get_json() or {}
    return_id = data.get('return_id', '').strip().upper()

    if not return_id:
        return jsonify({'success': False, 'error': '請輸入 ID'}), 400

    record = lookup_return_id(return_id)
    if not record:
        return jsonify({'success': False, 'error': '未找到記錄，請聯絡助教。'})

    username = record['username']
    log_path = record['log_path']

    session_id = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]

    write_log(log_path, f'[ID 驗證] 以 ID {return_id} 進入第二階段 session={session_id}')
    print(f"[enter_id] return_id={return_id} user={username} new_session={session_id}")

    return jsonify({
        'success':    True,
        'username':   username,
        'session_id': session_id,
        'unit':       record.get('unit', ''),
    })


# ── /greeting_set_que ───────────────────
@app.route('/greeting_set_que', methods=['POST', 'OPTIONS'])
def greeting_set_que():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')

    record   = lookup_session(session_id)
    if record:
        log_path = record.get('log_path', '')
    else:
        session_dir = os.path.join(LOG_DIR, f"{username}_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        log_path = os.path.join(session_dir, f"{username}_{session_id}.txt")

    if session_id and session_id not in launched_sessions:
        launched_sessions.add(session_id)
        threading.Thread(
            target=launch_script,
            args=('va_set_que.py', username, session_id, log_path),
            daemon=True
        ).start()
        print(f"[greeting_set_que] 啟動 set_que.py  session={session_id}")
    else:
        print(f"[greeting_set_que] session={session_id} 已啟動，跳過")

    reply = '> 系統初始化中。\n(若在3分鐘內未跳出下一步，請重新開啟頁面)'
    return jsonify({'reply': reply})

@app.route('/greeting_true_ending', methods=['POST', 'OPTIONS'])
def greeting_true_ending():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')

    record = lookup_session(session_id)
    if record:
        log_path = record.get('log_path', '')
    else:
        session_dir = os.path.join(LOG_DIR, f"{username}_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        log_path = os.path.join(session_dir, f"{username}_{session_id}.txt")

    if session_id and session_id not in launched_sessions:
        launched_sessions.add(session_id)
        threading.Thread(
            target=launch_script,
            args=('true_ending.py', username, session_id, log_path),
            daemon=True
        ).start()
        print(f"[greeting_true_ending] 啟動 true_ending.py  session={session_id}")
    else:
        print(f"[greeting_true_ending] session={session_id} 已啟動，跳過")

    reply = '> 系統初始化中。\n(若在3分鐘內未跳出下一步，請重新開啟頁面)'
    return jsonify({'reply': reply})

# ── /greeting_admin ─────────────────────
@app.route('/greeting_admin', methods=['POST', 'OPTIONS'])
def greeting_admin():
    """Tempus_Aeternum 專用：直接啟動 admin.py"""
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')

    record   = lookup_session(session_id)
    if record:
        log_path = record.get('log_path', '')
    else:
        session_dir = os.path.join(LOG_DIR, f"{username}_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        log_path = os.path.join(session_dir, f"{username}_{session_id}.txt")

    if session_id and session_id not in launched_sessions:
        launched_sessions.add(session_id)
        threading.Thread(
            target=launch_script,
            args=('admin.py', username, session_id, log_path),
            daemon=True
        ).start()
        print(f"[greeting_admin] 啟動 admin.py  session={session_id}")
    else:
        print(f"[greeting_admin] session={session_id} 已啟動，跳過")

    reply = '> 管理員模式初始化中，請稍候…'
    return jsonify({'reply': reply})


# ── /greeting ───────────────────────────
@app.route('/greeting', methods=['POST', 'OPTIONS'])
def greeting():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')

    record   = lookup_session(session_id)
    if record:
        log_path = record.get('log_path', '')
    else:
        session_dir = os.path.join(LOG_DIR, f"{username}_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        log_path = os.path.join(session_dir, f"{username}_{session_id}.txt")

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


# ── /generate_return_id ─────────────────
@app.route('/generate_return_id', methods=['POST', 'OPTIONS'])
def gen_return_id():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    session_id = data.get('session_id', '')
    rid        = generate_return_id(session_id)
    return jsonify({'return_id': rid})


# ── /lock_input ─────────────────────────
@app.route('/lock_input', methods=['POST', 'OPTIONS'])
def lock_input():
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
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    session_id = data.get('session_id', '')
    unit       = data.get('unit', '')

    update_session_unit(session_id, unit)
    return jsonify({'success': True})


# ── /download ───────────────────────────
@app.route('/download', methods=['GET', 'OPTIONS'])
def download_file():
    if request.method == 'OPTIONS':
        return Response(status=200)

    from flask import send_file
    file_path = request.args.get('path', '')

    if not file_path:
        return jsonify({'error': '未指定檔案路徑'}), 400

    # 安全性：只允許下載 LOG_DIR 內的檔案
    abs_path = os.path.abspath(file_path)
    abs_log  = os.path.abspath(LOG_DIR)
    if not abs_path.startswith(abs_log):
        return jsonify({'error': '存取被拒絕'}), 403

    if not os.path.exists(abs_path):
        return jsonify({'error': '檔案不存在'}), 404

    return send_file(abs_path, as_attachment=True,
                     download_name=os.path.basename(abs_path))


# ── /get_session_info ───────────────────
@app.route('/get_session_info', methods=['GET', 'OPTIONS'])
def get_session_info():
    if request.method == 'OPTIONS':
        return Response(status=200)

    session_id = request.args.get('session_id', '')
    record     = lookup_session(session_id)
    if not record:
        return jsonify({'success': False, 'error': '找不到 session'}), 404

    return jsonify({
        'success':   True,
        'username':  record.get('username', ''),
        'unit':      record.get('unit', ''),
        'return_id': record.get('return_id', ''),
    })


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
    if request.method == 'OPTIONS':
        return Response(status=200)

    session_id = request.args.get('session_id', '')

    if session_id in interrupted_sessions:
        interrupted_sessions.discard(session_id)
        return jsonify({'interrupted': True})

    return jsonify({'interrupted': False})


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


# ── /button_click ───────────────────────
@app.route('/button_click', methods=['POST', 'OPTIONS'])
def button_click():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    message    = data.get('message', '').strip()
    session_id = data.get('session_id', '')
    username   = data.get('username', '未知').strip()

    if not message:
        return jsonify({'reply': ''}), 400

    user_input_queues[session_id].append(message)
    print(f"[button_click] session={session_id} message={message[:40]}")
    return jsonify({'reply': ''})


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
# main.html 統一寫入入口
# 修改：接收前端傳入的 timestamp，寫入格式為 [timestamp] 角色：訊息
@app.route('/log', methods=['POST', 'OPTIONS'])
def log_message():
    if request.method == 'OPTIONS':
        return Response(status=200)

    data       = request.get_json() or {}
    username   = data.get('username', '未知').strip()
    session_id = data.get('session_id', '')
    role       = data.get('role', 'unknown')
    message    = data.get('message', '').strip()
    timestamp  = data.get('timestamp', '')  # 修改：接收前端時間戳記

    if not message:
        return jsonify({'success': False}), 400

    log_path = os.path.join(LOG_DIR, f"{username}_{session_id}.txt")
    record   = lookup_session(session_id)
    if record and record.get('log_path'):
        log_path = record['log_path']
    else:
        session_dir = os.path.join(LOG_DIR, f"{username}_{session_id}")
        os.makedirs(session_dir, exist_ok=True)
        log_path = os.path.join(session_dir, f"{username}_{session_id}.txt")
    label    = '用戶' if role == 'user' else 'AI'

    # 修改：若前端有傳入時間戳記則使用，否則由後端產生
    if not timestamp:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {label}：{message}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

    return jsonify({'success': True})


# ──────────────────────────────────────────
# 啟動
# ──────────────────────────────────────────
if __name__ == '__main__':
    print("✅ name.py 伺服器啟動中...")
    print(f"📁 Log 資料夾：{LOG_DIR}")
    print(f"📋 Session 庫：{DB_PATH}")
    app.run(host='0.0.0.0', port=5000, debug=True)