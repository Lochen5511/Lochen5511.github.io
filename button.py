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
def send_button(label: str, delay: float = 0, color: str = 'gold', size: str = 'medium', button_id: str = ''):
    """發送一個可點擊的按鈕
    
    參數：
        label     : 按鈕文字
        delay     : 等待秒數
        color     : 顏色 'gold'（預設）| 'red' | 'green' | 'blue' | 'gray'
        size      : 大小 'small' | 'medium'（預設）| 'large'
        button_id : 按鈕的唯一識別碼（用於 log 記錄）
    """
    if delay > 0:
        _set_thinking(True)
        time.sleep(delay)
        _set_thinking(False)

    bid = button_id if button_id else label  # 若未指定 ID，以文字作為 ID

    try:
        requests.post('http://localhost:5000/push', json={
            'text':       f'__BUTTON__{label}||{color}||{size}||{bid}',
            'username':   username,
            'session_id': session_id,
            'log_path':   '',
        })
        print(f"[按鈕] {label} (id={bid}, color={color}, size={size})")
    except Exception as e:
        print(f"[按鈕送出失敗] {e}")


# ──────────────────────────────────────────
# 工具函數：等待用戶回應
# ──────────────────────────────────────────
def send_buttons(labels: list, delay: float = 0, colors: list = None, sizes: list = None, size: str = 'medium', button_ids: list = None):
    """發送多個並排按鈕
    
    參數：
        labels     : 按鈕文字列表，如 ['開始', '略過', '確認']
        delay      : 等待秒數
        colors     : 每個按鈕的顏色列表，如 ['green', 'gray', 'blue']
        sizes      : 每個按鈕的大小列表（優先於 size）
        size       : 統一大小（當 sizes 未指定時使用）
        button_ids : 每個按鈕的 ID 列表
    """
    if delay > 0:
        _set_thinking(True)
        time.sleep(delay)
        _set_thinking(False)

    # 補齊預設值
    n = len(labels)
    colors     = colors     or ['gold'] * n
    button_ids = button_ids or labels
    if sizes:
        size_list = sizes
    else:
        size_list = [size] * n

    # 用 ';' 分隔每個按鈕的資料，整包以 __BUTTONS__ 前綴送出
    parts = ';'.join(
        f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}'
        for i in range(n)
    )

    try:
        requests.post('http://localhost:5000/push', json={
            'text':       f'__BUTTONS__{parts}',
            'username':   username,
            'session_id': session_id,
            'log_path':   '',
        })
        print(f"[多按鈕] {labels}")
    except Exception as e:
        print(f"[多按鈕送出失敗] {e}")


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
    send_buttons(['效度', '信度'], colors=['gray', 'blue'], size='small')

    user_reply = wait_for_user()    # 回傳格式：'按鈕ID:按鈕文字'
    print(f"[用戶點擊] {user_reply}")

    send('好的，讓我們開始吧！', delay=1)

    # ↑↑↑ 在這裡加入你的代碼 ↑↑↑
    print("[button.py 執行完畢]")


if __name__ == '__main__':
    main()