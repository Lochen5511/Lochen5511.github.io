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

BACKEND      = 'http://localhost:5000'
USER_TIMEOUT = 300


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

def _lock(locked):
    _post('/lock_input', {'session_id': session_id, 'locked': locked})

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
    _lock(True)
    print(f"[buttons] {labels}")

def send_dropdown(options, placeholder='請選擇…',
                  dropdown_id='dropdown', delay=0):
    if delay > 0:
        _thinking(True); time.sleep(delay); _thinking(False)
    parts = '||'.join(options)
    _post('/push', {
        'text': f'__DROPDOWN__{dropdown_id}||{placeholder}||{parts}',
        'username': username, 'session_id': session_id, 'log_path': '',
    })
    _lock(True)
    print(f"[dropdown] {options}")

def wait_for_user(interval=0.1, timeout=USER_TIMEOUT):
    """等待用戶回應，離開回傳 None，被中斷回傳 '__INTERRUPTED__'"""
    while True:
        # 先檢查中斷
        interrupted = _get('/check_interrupted', {'session_id': session_id})
        if interrupted.get('interrupted', False):
            write_log('[中斷] 用戶輸入 ID，流程中斷')
            return '__INTERRUPTED__'

        # 先取用戶輸入（優先）
        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            _lock(False)
            print(f"[user] {msg[:60]}")
            return msg

        # 再檢查是否在線
        online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
        if not online.get('online', True):
            write_log('用戶已離開系統')
            return None

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

    send((
        f'嗨，{username}歡迎回來。我們進到下一步了。\n'
        '現在要請你扮演「命題者」，練習把所學的概念變成題目。'
        '我會用三個小關卡帶你走。\n'
        '你不用一次就寫得很完美，只要一關一關完成就好。'
    ), delay=1)

    send_buttons(
        labels     = ['開始命題'],
        colors     = ['gold'],
        size       = 'medium',
        button_ids = ['btn_start_que']
    )

    user_reply = wait_for_user()
    if user_reply is None or user_reply == '__INTERRUPTED__':
        return

    send('請先選1個想命題的概念，當做這題的標籤。', delay=1)

    send_dropdown(
        options     = [
            '內容效度',
            '表面效度',
            '同時效度',
            '預測效度',
            '建構效度（因素分析／聚斂區別）',
            '信度—效度關係（必要但不充分）',
        ],
        placeholder = '請選擇概念標籤…',
        dropdown_id = 'dd_concept',
    )

    concept = wait_for_user()
    if concept is None or concept == '__INTERRUPTED__':
        return
    print(f"[set_que] 概念標籤={concept}")

    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑
    print("[set_que.py] 執行完畢")


if __name__ == '__main__':
    main()