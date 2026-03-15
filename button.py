import argparse
import time
import requests
from datetime import datetime

# ──────────────────────────────────────────
# 接收來自 name.py 的變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path

print(f"[button.py] 啟動  user={username}  session={session_id}")

BACKEND = 'http://localhost:5000'


# ──────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────
def _post(path: str, body: dict):
    try:
        requests.post(f"{BACKEND}{path}", json=body, timeout=5)
    except Exception as e:
        print(f"[post {path}] {e}")

def _get(path: str, params: dict = None):
    try:
        res = requests.get(f"{BACKEND}{path}", params=params, timeout=5)
        return res.json()
    except Exception as e:
        print(f"[get {path}] {e}")
        return {}

def _thinking(state: bool):
    _post('/thinking', {'username': username, 'session_id': session_id, 'thinking': state})


# ──────────────────────────────────────────
# send：發送訊息
# ──────────────────────────────────────────
def send(text: str, delay: float = 0):
    """等待 delay 秒（顯示思考動畫）後發送訊息"""
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)

    _post('/push', {
        'text':       text,
        'username':   username,
        'session_id': session_id,
        'log_path':   log_path,
    })
    print(f"[send] {text[:50]}")


# ──────────────────────────────────────────
# send_alert：彈出視窗
# ──────────────────────────────────────────
def send_alert(message: str):
    """在網頁彈出提示視窗"""
    _post('/push', {
        'text':       f'__ALERT__{message}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    print(f"[alert] {message[:50]}")


# ──────────────────────────────────────────
# send_button：單一按鈕
# ──────────────────────────────────────────
def send_button(label: str, delay: float = 0,
                color: str = 'gold', size: str = 'medium',
                button_id: str = ''):
    """發送一個可點擊的按鈕"""
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)

    bid = button_id or label
    _post('/push', {
        'text':       f'__BUTTON__{label}||{color}||{size}||{bid}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    print(f"[button] {label}  id={bid}")


# ──────────────────────────────────────────
# send_buttons：多個並排按鈕
# ──────────────────────────────────────────
def send_buttons(labels: list, delay: float = 0,
                 colors: list = None, size: str = 'medium',
                 sizes: list = None, button_ids: list = None):
    """發送多個並排按鈕"""
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)

    n          = len(labels)
    colors     = colors     or ['gold'] * n
    button_ids = button_ids or labels
    size_list  = sizes      or [size]  * n

    parts = ';'.join(
        f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}'
        for i in range(n)
    )
    _post('/push', {
        'text':       f'__BUTTONS__{parts}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    print(f"[buttons] {labels}")


# ──────────────────────────────────────────
# wait_for_user：等待用戶回應
# ──────────────────────────────────────────
def wait_for_user(interval: float = 0.5) -> str:
    """阻塞直到用戶發送訊息或點擊按鈕，回傳用戶說的話"""
    while True:
        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            print(f"[user] {msg[:60]}")
            return msg
        time.sleep(interval)


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    # ↓↓↓ 在這裡加入你的代碼 ↓↓↓

    send(f'你好，{username}！我是艾評。', delay=3)
    send('歡迎來到本系統。', delay=1)
    send('在我們進入正題前，先來幫你做一下概念體檢。', delay=1)
    send('待會，你會完成8題選擇題，每次作答後，評價自己對這個答案的信心。', delay=2)
    send('在你準備好後，就按下開始吧！', delay=1)

    send_buttons(
        labels     = ['效度', '信度'],
        colors     = ['gray', 'blue'],
        size       = 'small',
        button_ids = ['btn_validity', 'btn_reliability']
    )

    user_reply = wait_for_user()

    import os as _os
    base_args = ['--username', username, '--session_id', session_id, '--log_path', log_path]

    if 'btn_validity' in user_reply:
        import subprocess
        subprocess.Popen(['python', 'validity.py'] + base_args,
                         cwd=_os.path.dirname(_os.path.abspath(__file__)))

    elif 'btn_reliability' in user_reply:
        import subprocess
        subprocess.Popen(['python', 'reliability.py'] + base_args,
                         cwd=_os.path.dirname(_os.path.abspath(__file__)))

    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑
    print("[button.py] 執行完畢")


if __name__ == '__main__':
    main()