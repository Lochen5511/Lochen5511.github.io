import argparse
import time
import requests
import os

# ──────────────────────────────────────────
# 接收變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path

print(f"[set_que.py] 啟動  user={username}  session={session_id}")

BACKEND = 'http://localhost:5000'


# ──────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────
def _post(path, body):
    try:
        requests.post(f"{BACKEND}{path}", json=body, timeout=5)
    except Exception as e:
        print(f"[post {path}] {e}")

def _get(path, params=None):
    try:
        res = requests.get(f"{BACKEND}{path}", params=params, timeout=5)
        return res.json()
    except Exception as e:
        print(f"[get {path}] {e}")
        return {}

def _thinking(state):
    _post('/thinking', {'username': username, 'session_id': session_id, 'thinking': state})

def send(text, delay=0):
    if delay > 0:
        _thinking(True); time.sleep(delay); _thinking(False)
    _post('/push', {
        'text': text, 'username': username,
        'session_id': session_id, 'log_path': log_path,
    })
    print(f"[send] {text[:50]}")

def send_buttons(labels, delay=0, colors=None, size='medium',
                 sizes=None, button_ids=None):
    if delay > 0:
        _thinking(True); time.sleep(delay); _thinking(False)
    n          = len(labels)
    colors     = colors     or ['gold'] * n
    button_ids = button_ids or labels
    size_list  = sizes      or [size]  * n
    parts = ';'.join(
        f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}'
        for i in range(n)
    )
    _post('/push', {
        'text': f'__BUTTONS__{parts}', 'username': username,
        'session_id': session_id, 'log_path': '',
    })

def wait_for_user(interval=0.5, timeout=300):
    while True:
        online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
        if not online.get('online', True):
            write_log('用戶已離開系統')
            return None
        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            print(f"[user] {msg[:60]}")
            return msg
        time.sleep(interval)

def write_log(content):
    if not log_path:
        return
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(content + '\n')
    except Exception as e:
        print(f"[log 寫入失敗] {e}")


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    # ↓↓↓ 在這裡加入你的代碼 ↓↓↓

    send("> 檢測到ID輸入，正在檢索記錄......", delay=0.5)
    send((
        f'嗨，{username}歡迎回來。我們進到下一步了。\n'
        '現在要請你扮演「命題者」，練習把所學的概念變成題目。'
        '我會用三個小關卡帶你走。\n'
        '你不用一次就寫得很完美，只要一關一關完成就好。'
    ), delay=5)

    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑
    print("[set_que.py] 執行完畢")


if __name__ == '__main__':
    main()