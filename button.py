import argparse
import time
import requests
from datetime import datetime

# ──────────────────────────────────────────
# 接收來自 name.py 的變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知', help='使用者名稱')
parser.add_argument('--session_id', default='',    help='登入時間戳')
parser.add_argument('--log_path',   default='',    help='對應的 log 檔路徑')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path

print(f"[button.py 啟動]")
print(f"  使用者：{username}")
print(f"  Session ID：{session_id}")
print(f"  Log 路徑：{log_path}")
print(f"  時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("─" * 40)


# ──────────────────────────────────────────
# 工具函數：顯示／隱藏思考動畫
# ──────────────────────────────────────────
def _set_thinking(state: bool):
    try:
        requests.post('http://localhost:5000/thinking', json={
            'username':   username,
            'session_id': session_id,
            'thinking':   state
        })
    except Exception as e:
        print(f"[thinking 通知失敗] {e}")


# ──────────────────────────────────────────
# 工具函數：發送訊息
# ──────────────────────────────────────────
def send(text: str, delay: float = 0):
    """等待 delay 秒（顯示思考動畫）後發送訊息"""
    if delay > 0:
        _set_thinking(True)
        time.sleep(delay)
        _set_thinking(False)

    try:
        requests.post('http://localhost:5000/push', json={
            'text':       text,
            'username':   username,
            'session_id': session_id,
            'log_path':   log_path,
        })
        print(f"[送出] {text}")
    except Exception as e:
        print(f"[送出失敗] {e}")


# ──────────────────────────────────────────
# 工具函數：發送按鈕
# ──────────────────────────────────────────
def send_button(label: str, delay: float = 0):
    """發送一個可點擊的按鈕，用戶點擊後視同發送該文字"""
    if delay > 0:
        _set_thinking(True)
        time.sleep(delay)
        _set_thinking(False)

    try:
        requests.post('http://localhost:5000/push', json={
            'text':       f'__BUTTON__{label}',
            'username':   username,
            'session_id': session_id,
            'log_path':   '',  # 按鈕本身不寫入 log
        })
        print(f"[按鈕] {label}")
    except Exception as e:
        print(f"[按鈕送出失敗] {e}")


# ──────────────────────────────────────────
# 工具函數：等待用戶回應
# ──────────────────────────────────────────
def wait_for_user(interval: float = 0.5) -> str:
    """阻塞直到用戶發送訊息或點擊按鈕，回傳用戶說的話"""
    while True:
        try:
            res = requests.get('http://localhost:5000/fetch_user_input',
                               params={'session_id': session_id})
            data = res.json()
            if data.get('message'):
                return data['message']
        except Exception as e:
            print(f"[等待用戶失敗] {e}")
        time.sleep(interval)


# ──────────────────────────────────────────
# 主要執行區塊（在此放置你的代碼）
# ──────────────────────────────────────────
def main():
    # ↓↓↓ 在這裡加入你的代碼 ↓↓↓

    send(f'你好，{username}！我是艾評。', delay=10)
    send('歡迎來到本系統。', delay=2)
    send('在我們進入正題前，先來幫你做一下概念體檢。', delay=3)
    send('待會，你會完成8題選擇題，每次作答後，評價自己對這個答案的信心。', delay=2)
    send('在你準備好後，就按下開始吧！', delay=1)

    # ── 示範：發送按鈕，等待用戶點擊 ──
    send_button('開始')

    user_reply = wait_for_user()    # 等待用戶點擊按鈕
    print(f"[用戶點擊] {user_reply}")

    send('好的，讓我們開始吧！', delay=1)

    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑
    print("[button.py 執行完畢]")


if __name__ == '__main__':
    main()