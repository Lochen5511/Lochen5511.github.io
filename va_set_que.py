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
TOTAL_QUE    = 8


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
        interrupted = _get('/check_interrupted', {'session_id': session_id})
        if interrupted.get('interrupted', False):
            write_log('[中斷] 用戶輸入 ID，流程中斷')
            return '__INTERRUPTED__'

        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            _lock(False)
            print(f"[user] {msg[:60]}")
            return msg

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

def is_exit(val):
    """統一檢查是否為離開或中斷"""
    return val is None or val == '__INTERRUPTED__'


# ──────────────────────────────────────────
# 單題流程
# ──────────────────────────────────────────
def make_question(n, total):
    """
    執行第 n 題的完整命題流程。
    回傳 True 表示完成，False 表示用戶離開或中斷。
    """
    write_log(f'\n── 第 {n}/{total} 題開始 ──')

    # ── 概念選擇 ──
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
        dropdown_id = f'dd_concept_{n}',
    )
    concept = wait_for_user()
    if is_exit(concept): return False
    print(f"[set_que] 題{n} 概念={concept}")

    # ── 關卡一：題幹 ──
    send((
        '再來，請你寫出一個「看得懂、問得清楚」的題幹。'
        '你可以先不用想選項，先把題幹寫出來就好。\n\n'
        '如果你卡住，我給你三個很容易開始的題幹套路，選一個套進去就行：\n'
        '・套路 A：證據判讀型\n'
        '「老師用了___來檢核題目品質，這主要支持哪種效度證據？」\n\n'
        '・套路 B：時間線索型（同時 vs 預測）\n'
        '「測驗分數與___（當下／一年後）表現相關，這是哪種效度？」\n\n'
        '・套路 C：推論型（信度≠效度）\n'
        '「α很高／分數很穩定，能不能推論效度一定高？」\n\n'
        '你想用哪一種？或你直接開始寫也可以。'
        '一個完整的題幹，字數 ≥ 40 字，「2–4 句情境 + 1 句問句」'
        '（請直接於聊天框輸入完整的題目。）'
    ), delay=1)

    stem = wait_for_user()
    if is_exit(stem): return False
    print(f"[set_que] 題{n} 題幹={stem[:60]}")

    # ── 線索 ──
    send((
        '對了，你希望作答的人從題幹中核心判斷的線索是什麼？\n'
        '例如：「同一時間點」「一年後」「雙向細目表」「因素分析」「α很高」'
    ), delay=1)

    clue = wait_for_user()
    if is_exit(clue): return False
    print(f"[set_que] 題{n} 線索={clue[:60]}")

    write_log(f'[命題{n}] 概念={concept} | 題幹={stem} | 線索={clue}')

    # ── 關卡二：選項 ──
    send((
        '好，我們進到關卡二。\n'
        '這一關只做一件事：把你的四個選項寫出來，並且讓至少兩個錯選項「有意義」，'
        '也就是能代表常見的錯誤想法。\n\n'
        '小提示：如果你不知道錯選項怎麼寫，你可以考慮把正確概念改一個關鍵詞，'
        '就會變成典型迷思。例如：把「當下」換成「一年後」。\n\n'
        f'再看一次你的題幹：\n{stem}'
    ), delay=1)

    options = wait_for_user()
    if is_exit(options): return False
    write_log(f'[命題{n}] 選項草稿={options}')

    send('請告訴我，你心中的正確答案：', delay=1)

    answer = wait_for_user()
    if is_exit(answer): return False
    print(f"[set_que] 題{n} 正確答案={answer[:60]}")

    # ── 三個錯誤選項（逐一確認）──
    send('接著，請依序輸入三個錯誤的選項。', delay=1)

    wrong_options = []
    for i in range(1, 4):
        while True:
            send(f'請輸入第 {i} 個錯誤選項：', delay=0.5)
            wrong = wait_for_user()
            if is_exit(wrong): return False

            send(f'你輸入的第 {i} 個錯誤選項是：\n{wrong}', delay=0.5)
            send_buttons(
                labels     = ['確認無誤', '我想修改'],
                colors     = ['green', 'gray'],
                size       = 'small',
                button_ids = ['btn_confirm', 'btn_edit']
            )
            confirm = wait_for_user()
            if is_exit(confirm): return False

            if 'btn_confirm' in confirm:
                wrong_options.append(wrong)
                write_log(f'[命題{n}] 錯誤選項{i}={wrong}')
                break

    # ── 完整題目確認 ──
    while True:
        full_question = (
            f'以下是你完成的題目：\n\n'
            f'【題幹】\n{stem}\n\n'
            f'A. {answer}\n'
            f'B. {wrong_options[0]}\n'
            f'C. {wrong_options[1]}\n'
            f'D. {wrong_options[2]}\n\n'
            f'（A 為正確答案）'
        )
        send(full_question, delay=1)
        send_buttons(
            labels     = ['正確無誤', '我想修改'],
            colors     = ['green', 'gray'],
            size       = 'medium',
            button_ids = ['btn_final_confirm', 'btn_final_edit']
        )
        final = wait_for_user()
        if is_exit(final): return False

        if 'btn_final_confirm' in final:
            write_log(f'[命題{n}完成] stem={stem} | A={answer} | B={wrong_options[0]} | C={wrong_options[1]} | D={wrong_options[2]}')
            break

        # 修改
        send('請發送完整的題幹：', delay=0.5)
        v = wait_for_user()
        if is_exit(v): return False
        stem = v

        send('請發送正確選項：', delay=0.5)
        v = wait_for_user()
        if is_exit(v): return False
        answer = v

        send('請發送錯誤選項（B）：', delay=0.5)
        v = wait_for_user()
        if is_exit(v): return False
        wrong_options[0] = v

        send('請發送錯誤選項（C）：', delay=0.5)
        v = wait_for_user()
        if is_exit(v): return False
        wrong_options[1] = v

        send('請發送錯誤選項（D）：', delay=0.5)
        v = wait_for_user()
        if is_exit(v): return False
        wrong_options[2] = v

    # ── 關卡三：易錯選項分析 ──
    send((
        '接下來我想請你挑出兩個「最容易讓人選錯」的選項。\n'
        '你不用挑全部，只要挑兩個就好。'
    ), delay=1)

    send_buttons(
        labels     = [
            f'B. {wrong_options[0]}',
            f'C. {wrong_options[1]}',
            f'D. {wrong_options[2]}',
        ],
        colors     = ['gold', 'gold', 'gold'],
        size       = 'medium',
        button_ids = ['btn_pick_B', 'btn_pick_C', 'btn_pick_D']
    )

    first_pick = wait_for_user()
    if is_exit(first_pick): return False
    if 'btn_pick_B' in first_pick:
        first_label, first_option = f'B. {wrong_options[0]}', wrong_options[0]
    elif 'btn_pick_C' in first_pick:
        first_label, first_option = f'C. {wrong_options[1]}', wrong_options[1]
    else:
        first_label, first_option = f'D. {wrong_options[2]}', wrong_options[2]

    second_pick = wait_for_user()
    if is_exit(second_pick): return False
    if 'btn_pick_B' in second_pick:
        second_label, second_option = f'B. {wrong_options[0]}', wrong_options[0]
    elif 'btn_pick_C' in second_pick:
        second_label, second_option = f'C. {wrong_options[1]}', wrong_options[1]
    else:
        second_label, second_option = f'D. {wrong_options[2]}', wrong_options[2]

    write_log(f'[命題{n}] 易錯選項1={first_label} | 易錯選項2={second_label}')

    send(
        f'好，那我們先看「{first_option}」。\n'
        '如果有人選了它，你猜他最可能是怎麼想的？',
        delay=1
    )
    guess_first = wait_for_user()
    if is_exit(guess_first): return False
    write_log(f'[命題{n}] 易錯推測1={guess_first}')

    send(
        f'再來看「{second_option}」。\n'
        '你覺得選它的人最可能是哪種想法搞錯？',
        delay=1
    )
    guess_second = wait_for_user()
    if is_exit(guess_second): return False
    write_log(f'[命題{n}] 易錯推測2={guess_second}')

    # ── 易錯分析確認 ──
    while True:
        summary = (
            f'以下是你分析的兩個易錯選項：\n\n'
            f'【{first_label}】\n推測想法：{guess_first}\n\n'
            f'【{second_label}】\n推測想法：{guess_second}'
        )
        send(summary, delay=1)
        send_buttons(
            labels     = ['正確無誤', '我想修改'],
            colors     = ['green', 'gray'],
            size       = 'medium',
            button_ids = ['btn_guess_confirm', 'btn_guess_edit']
        )
        confirm = wait_for_user()
        if is_exit(confirm): return False

        if 'btn_guess_confirm' in confirm:
            write_log(f'[命題{n}] 易錯分析確認完成')
            break

        send(f'請重新輸入「{first_label}」的易錯推測：', delay=0.5)
        v = wait_for_user()
        if is_exit(v): return False
        guess_first = v

        send(f'請重新輸入「{second_label}」的易錯推測：', delay=0.5)
        v = wait_for_user()
        if is_exit(v): return False
        guess_second = v

        write_log(f'[命題{n}] 易錯推測修改 | 1={guess_first} | 2={guess_second}')

    return True


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
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
    if is_exit(user_reply):
        return

    # ── 8 題迴圈 ──
    for n in range(1, TOTAL_QUE + 1):
        if n > 1:
            remaining = TOTAL_QUE - (n - 1)
            send((
                f'接著，請再出 {remaining} 題'
                f'（我們總共要出 {TOTAL_QUE} 題），'
                f'讓我們繼續出第 {n} 題。'
            ), delay=1)

        ok = make_question(n, TOTAL_QUE)
        if not ok:
            print(f"[set_que.py] 第 {n} 題中斷，結束流程")
            return

    send(
        '很好，現在你已經完成命題，讓我召喚「孿生AI學生」來試做你的題目吧！',
        delay=1
    )

    import subprocess
    base_args = ['--username', username, '--session_id', session_id, '--log_path', log_path]
    subprocess.Popen(
        ['python', 'va_que_ana.py'] + base_args,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

    print("[set_que.py] 全部 8 題完成，已啟動 que_ana.py")


if __name__ == '__main__':
    main()