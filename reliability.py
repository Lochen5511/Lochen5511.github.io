# TODO: 信度單元尚未實作，目前僅顯示提示並跳回選單

import argparse
import sys
import time
import subprocess
import os
import requests

# ──────────────────────────────────────────
# 接收來自 button.py 的變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path

print(f"[reliability.py] 啟動  user={username}  session={session_id}")

BACKEND      = 'http://localhost:5000'
USER_TIMEOUT = 300


# ──────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────
def _post(path, body):
    try:
        requests.post(f'{BACKEND}{path}', json=body, timeout=5)
    except Exception as e:
        print(f"[post {path}] {e}")

def _get(path, params=None):
    try:
        res = requests.get(f'{BACKEND}{path}', params=params, timeout=5)
        return res.json()
    except Exception as e:
        print(f"[get {path}] {e}")
        return {}

def _thinking(state):
    _post('/thinking', {'username': username, 'session_id': session_id, 'thinking': state})

def _lock(locked):
    _post('/lock_input', {'session_id': session_id, 'locked': locked})

def is_exit(val) -> bool:
    return val is None or val == '__INTERRUPTED__'

def send(text, delay=0):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    _post('/push', {
        'text': text, 'username': username,
        'session_id': session_id, 'log_path': log_path,
    })
    print(f"[send] {text[:50]}")

def send_alert(message):
    _post('/push', {
        'text': f'__ALERT__{message}', 'username': username,
        'session_id': session_id, 'log_path': '',
    })
    print(f"[alert] {message[:50]}")

def send_buttons(labels, delay=0, colors=None, sizes=None, size='medium', button_ids=None):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    n          = len(labels)
    colors     = colors     or ['gold'] * n
    button_ids = button_ids or labels
    size_list  = sizes if sizes else [size] * n
    parts = ';'.join(
        f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}'
        for i in range(n)
    )
    _post('/push', {
        'text': f'__BUTTONS__{parts}', 'username': username,
        'session_id': session_id, 'log_path': '',
    })
    _lock(True)

def wait_for_user(interval=0.1, timeout=USER_TIMEOUT):
    """
    等待用戶回應。
    中斷與離開事件不經過 main.html，直接印出 log（此模組為佔位頁，暫不寫入檔案）。
    """
    while True:
        interrupted = _get('/check_interrupted', {'session_id': session_id})
        if interrupted.get('interrupted', False):
            print('[reliability] 用戶輸入 ID，流程中斷')
            _lock(False)
            return '__INTERRUPTED__'

        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            _lock(False)
            print(f"[user] {msg[:60]}")
            return msg

        online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
        if not online.get('online', True):
            print('[reliability] 用戶已離開系統')
            _lock(False)
            return None

        time.sleep(interval)


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    send_alert('很抱歉，此單元尚在開發中，請返回選擇其他選項。')

    time.sleep(0.5)
    send_buttons(
        labels     = ['效度', '信度'],
        colors     = ['gray', 'blue'],
        size       = 'small',
        button_ids = ['btn_validity', 'btn_reliability']
    )

    user_reply = wait_for_user()
    if is_exit(user_reply):
        return

    print(f"[用戶點擊] {user_reply}")

    base_args = ['--username', username, '--session_id', session_id, '--log_path', log_path]

    if user_reply == 'btn_validity:效度':
        subprocess.Popen([sys.executable, 'validity.py'] + base_args,
                         cwd=os.path.dirname(os.path.abspath(__file__)))
    elif user_reply == 'btn_reliability:信度':
        # 信度單元尚未開放，顯示訊息後結束，不再自我呼叫避免無限遞迴
        send('此單元尚未開放，請稍後再試。', delay=0.3)
    else:
        print(f"[reliability.py] 未預期的回應: {user_reply}")

    print("[reliability.py 執行完畢]")


if __name__ == '__main__':
    main()