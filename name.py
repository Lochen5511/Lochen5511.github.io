from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
from collections import defaultdict
import os, subprocess, threading, json, time, uuid, random, string
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
message_queues        = defaultdict(list)
thinking_states       = {}
user_input_queues     = defaultdict(list)
launched_sessions     = set()
last_seen             = {}
input_locked          = set()
interrupted_sessions  = set()

USER_TIMEOUT = 300


# ──────────────────────────────────────────
# 工具函式
# ──────────────────────────────────────────
def norm_sid(v):
    """統一 session_id / return_id 格式"""
    return str(v or '').strip().upper()


# ──────────────────────────────────────────
# Session DB
# ──────────────────────────────────────────
DB_LOCK      = threading.Lock()
DB_LOCK_FILE = DB_PATH + ".lock"


def _acquire_db_lock(timeout=10):
    start = time.time()
    while True:
        try:
            fd = os.open(DB_LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            if time.time() - start > timeout:
                print("[db] lock timeout")
                return False
            time.sleep(0.05)


def _release_db_lock():
    try:
        os.remove(DB_LOCK_FILE)
    except:
        pass


def load_db():
    try:
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print("[db read fail]", e)
    return {}


def save_db(db):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[db save fail]", e)


def _db_update(fn):
    with DB_LOCK:
        locked = _acquire_db_lock()
        try:
            db = load_db()
            fn(db)
            save_db(db)
        finally:
            if locked:
                _release_db_lock()


def register_session(username, session_id, log_path):
    def _update(db):
        db[session_id] = {
            "username": username,
            "log_path": log_path,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "unit": None,
            "return_id": None
        }
    _db_update(_update)


def update_session_unit(session_id, unit):
    def _update(db):
        if session_id in db:
            db[session_id]["unit"] = unit
    _db_update(_update)


def generate_return_id(session_id):
    result = {"rid": ""}

    def _update(db):
        used = set()

        for v in db.values():
            if isinstance(v, dict):
                rid = v.get("return_id")
                if rid:
                    used.add(rid)

        while True:
            rid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if rid not in used:
                break

        if session_id in db:
            db[session_id]["return_id"] = rid

        db.setdefault("__return_index__", {})
        db["__return_index__"][rid] = session_id
        result["rid"] = rid

    _db_update(_update)
    return result["rid"]


def lookup_return_id(return_id):
    db = load_db()
    idx = db.get("__return_index__", {})
    sid = idx.get(norm_sid(return_id))
    if sid:
        return sid, db.get(sid)
    return None, None


def lookup_session(session_id):
    """
    強化版：
    1. 可直接查 session_id
    2. 若傳入 return_id，自動轉換
    """
    sid = norm_sid(session_id)
    db = load_db()

    if sid in db:
        return db[sid]

    idx = db.get("__return_index__", {})
    real_sid = idx.get(sid)

    if real_sid:
        return db.get(real_sid)

    return None


def resolve_session_id(session_id):
    """
    回傳真正 session_id
    """
    sid = norm_sid(session_id)
    db = load_db()

    if sid in db:
        return sid

    idx = db.get("__return_index__", {})
    return idx.get(sid, sid)


def write_log(log_path, text):
    if not log_path:
        return

    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")
    except Exception as e:
        print("[log fail]", e)


def launch_script(script, username, session_id, log_path):
    subprocess.Popen(
        [
            "python", script,
            "--username", username,
            "--session_id", session_id,
            "--log_path", log_path
        ],
        cwd=BASE_DIR
    )


# ──────────────────────────────────────────
# Routes
# ──────────────────────────────────────────

@app.route("/enter", methods=["POST", "OPTIONS"])
def enter():
    if request.method == "OPTIONS":
        return Response(status=200)

    data = request.get_json() or {}
    username = str(data.get("username", "")).strip()

    if not username:
        return jsonify({"success": False, "error": "名字不能為空"}), 400

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]

    session_dir = os.path.join(LOG_DIR, f"{username}_{session_id}")
    os.makedirs(session_dir, exist_ok=True)

    log_path = os.path.join(session_dir, f"{username}_{session_id}.txt")
    open(log_path, "a", encoding="utf-8").close()

    register_session(username, session_id, log_path)

    return jsonify({
        "success": True,
        "session_id": session_id
    })


@app.route("/enter_id", methods=["POST", "OPTIONS"])
def enter_id():
    if request.method == "OPTIONS":
        return Response(status=200)

    data = request.get_json() or {}
    return_id = norm_sid(data.get("return_id"))

    if not return_id:
        return jsonify({"success": False, "error": "請輸入 ID"}), 400

    session_id, record = lookup_return_id(return_id)

    if not record:
        return jsonify({"success": False, "error": "未找到記錄"})

    return jsonify({
        "success": True,
        "username": record["username"],
        "session_id": session_id
    })


@app.route("/greeting_set_que", methods=["POST", "OPTIONS"])
def greeting_set_que():
    if request.method == "OPTIONS":
        return Response(status=200)

    data = request.get_json() or {}

    username = str(data.get("username", "未知")).strip()
    session_id = resolve_session_id(data.get("session_id"))

    print("[greeting_set_que] raw =", data.get("session_id"))
    print("[greeting_set_que] real=", session_id)

    record = lookup_session(session_id)

    if record:
        log_path = record.get("log_path", "")
        unit = record.get("unit", "")
    else:
        session_dir = os.path.join(LOG_DIR, f"{username}_{session_id}")
        os.makedirs(session_dir, exist_ok=True)

        log_path = os.path.join(session_dir, f"{username}_{session_id}.txt")
        unit = ""

    script = "true_ending.py" if unit == "出題" else "va_set_que.py"

    if session_id and session_id not in launched_sessions:
        launched_sessions.add(session_id)

        threading.Thread(
            target=launch_script,
            args=(script, username, session_id, log_path),
            daemon=True
        ).start()

        print("[launch]", script, session_id)

    reply = "> 系統初始化中。\n(若在3分鐘內未跳出下一步，請重新開啟頁面)"
    return jsonify({"reply": reply})


@app.route("/generate_return_id", methods=["POST", "OPTIONS"])
def gen_return():
    if request.method == "OPTIONS":
        return Response(status=200)

    data = request.get_json() or {}
    session_id = resolve_session_id(data.get("session_id"))

    rid = generate_return_id(session_id)

    return jsonify({
        "return_id": rid
    })


@app.route("/update_unit", methods=["POST", "OPTIONS"])
def update_unit():
    if request.method == "OPTIONS":
        return Response(status=200)

    data = request.get_json() or {}
    session_id = resolve_session_id(data.get("session_id"))
    unit = str(data.get("unit", "")).strip()

    update_session_unit(session_id, unit)

    return jsonify({"success": True})


@app.route("/get_session_info", methods=["GET", "OPTIONS"])
def get_session_info():
    if request.method == "OPTIONS":
        return Response(status=200)

    session_id = resolve_session_id(request.args.get("session_id"))
    record = lookup_session(session_id)

    if not record:
        return jsonify({"success": False}), 404

    return jsonify({
        "success": True,
        "username": record.get("username", ""),
        "unit": record.get("unit", ""),
        "return_id": record.get("return_id", "")
    })


@app.route("/download", methods=["GET", "OPTIONS"])
def download():
    if request.method == "OPTIONS":
        return Response(status=200)

    file_path = request.args.get("path", "")

    if not file_path:
        return jsonify({"error": "未指定檔案"}), 400

    abs_path = os.path.abspath(file_path)
    abs_log = os.path.abspath(LOG_DIR)

    if not abs_path.startswith(abs_log):
        return jsonify({"error": "拒絕存取"}), 403

    if not os.path.exists(abs_path):
        return jsonify({"error": "檔案不存在"}), 404

    return send_file(abs_path, as_attachment=True)


# ──────────────────────────────────────────
# 啟動
# ──────────────────────────────────────────
if __name__ == "__main__":
    print("server start")
    app.run(host="0.0.0.0", port=5000, debug=False)