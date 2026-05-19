import argparse
import time
import requests
import os
from datetime import datetime

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

LOG_DIR = r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\log"

# que_set_log 路徑（全域，init_que_log() 設定後使用）
que_log_path = ''


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

def send_checkbox(options, max_select=2, checkbox_id='cb', delay=0):
    if delay > 0:
        _thinking(True); time.sleep(delay); _thinking(False)
    parts = '||'.join(options)
    _post('/push', {
        'text': f'__CHECKBOX__{checkbox_id}||{max_select}||{parts}',
        'username': username, 'session_id': session_id, 'log_path': '',
    })
    _lock(True)
    print(f"[checkbox] max={max_select} opts={options}")

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

def wait_for_user(interval=0.5, timeout=USER_TIMEOUT):
    while True:
        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            _lock(False)
            print(f"[user] {msg[:60]}")
            return msg

        interrupted = _get('/check_interrupted', {'session_id': session_id})
        if interrupted.get('interrupted', False):
            write_log('[中斷] 用戶輸入 ID，流程中斷')
            return '__INTERRUPTED__'

        online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
        if not online.get('online', True):
            write_log('用戶已離開系統')
            return None

        time.sleep(interval)

def write_log(content):
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def is_exit(val):
    return val is None or val == '__INTERRUPTED__'


# ──────────────────────────────────────────
# que_set_log 專用函數
# ──────────────────────────────────────────
def init_que_log():
    """建立 {session_id}_que_set_log.txt，寫入檔頭"""
    global que_log_path
    session_dir  = os.path.dirname(log_path) if log_path else LOG_DIR
    que_log_path = os.path.join(session_dir, f"{session_id}_que_set_log.txt")
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(que_log_path, 'w', encoding='utf-8') as f:
            f.write(f"# que_set_log | session={session_id} | user={username} | 建立時間={ts}\n\n")
        print(f"[que_log] 初始化完成：{que_log_path}")
    except Exception as e:
        print(f"[que_log 初始化失敗] {e}")

def write_que_log(content):
    """寫入 que_set_log（含時間戳記）"""
    if not que_log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(que_log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[que_log 寫入失敗] {e}")

def record_question(n, concept, stem, clue, answer,
                    wrong_options, first_label, second_label,
                    guess_first, guess_second):
    """將單題所有出題資訊以結構化格式寫入 que_set_log"""
    write_que_log(f"[Q{n}_START]")
    write_que_log(f"[Q{n}] 題號={n}")
    write_que_log(f"[Q{n}] 概念標籤={concept}")
    write_que_log(f"[Q{n}] 題幹={stem}")
    write_que_log(f"[Q{n}] 關鍵線索={clue}")
    write_que_log(f"[Q{n}] 正確答案A={answer}")
    write_que_log(f"[Q{n}] 錯誤選項B={wrong_options[0]}")
    write_que_log(f"[Q{n}] 錯誤選項C={wrong_options[1]}")
    write_que_log(f"[Q{n}] 錯誤選項D={wrong_options[2]}")
    write_que_log(f"[Q{n}] 易錯選項1={first_label}")
    write_que_log(f"[Q{n}] 易錯選項2={second_label}")
    write_que_log(f"[Q{n}] 易錯推測1={guess_first}")
    write_que_log(f"[Q{n}] 易錯推測2={guess_second}")
    write_que_log(f"[Q{n}_END]\n")
    print(f"[que_log] 第 {n} 題已記錄")


# ──────────────────────────────────────────
# 單題流程
# ──────────────────────────────────────────
def make_question(n, total, used_concepts):
    ALL_CONCEPTS = [
        '內容效度',
        '表面效度',
        '同時效度',
        '預測效度',
        '建構效度（因素分析／聚斂區別）',
        '信度—效度關係（必要但不充分）',
        '效標關聯效度',
        '情境題',
    ]

    write_log(f'\n── 第 {n}/{total} 題開始 ──')

    remaining_concepts = [c for c in ALL_CONCEPTS if c not in used_concepts]

    if remaining_concepts:
        send('請選1個想命題的概念，當做這題的標籤。', delay=1)
        send_dropdown(
            options     = remaining_concepts,
            placeholder = '請選擇概念標籤…',
            dropdown_id = f'dd_concept_{n}',
        )
        concept = wait_for_user()
        if is_exit(concept): return False
    else:
        send('接下來，請在聊天框輸入你想要用來命題的核心觀念。', delay=1)
        concept = wait_for_user()
        if is_exit(concept): return False

    used_concepts.add(concept)
    print(f"[set_que] 題{n} 概念={concept}")

    send((
        '再來，請寫出一個清楚易讀的題幹。'
        '現在只想問題就好，還不需要思考選項。\n\n'
        '以下是三種範例：\n'
        '・範例 A：證據判讀型\n'
        '「老師用了___來檢核題目品質，這主要支持哪種效度證據？」\n\n'
        '・範例 B：時間線索型（同時 vs 預測）\n'
        '「測驗分數與___（當下／一年後）表現相關，這是哪種效度？」\n\n'
        '・範例 C：推論型（信度≠效度）\n'
        '「α很高／分數很穩定，能不能推論效度一定高？」\n\n'
        '請寫出完整的題幹，字數 ≥ 40 字，「2–4 句情境 + 1 句問句」'
        '（請直接於聊天框輸入完整的題目。）'
    ), delay=1)

    stem = wait_for_user()
    if is_exit(stem): return False
    print(f"[set_que] 題{n} 題幹={stem[:60]}")

    send((
        '在你的題幹中，學生判讀答案的關鍵字是什麼？\n'
        '例如：「同一時間點」「一年後」「雙向細目表」「因素分析」「α很高」'
    ), delay=1)

    clue = wait_for_user()
    if is_exit(clue): return False
    print(f"[set_que] 題{n} 線索={clue[:60]}")

    write_log(f'[命題{n}] 概念={concept} | 題幹={stem} | 線索={clue}')

    while True:
        send((
            f'再看一次你的題幹：\n{stem}'
        ), delay=1)
        send_buttons(
            labels     = ['正確無誤', '需要修改'],
            colors     = ['green', 'gray'],
            size       = 'small',
            button_ids = ['btn_stem_ok', 'btn_stem_edit']
        )
        stem_check = wait_for_user()
        if is_exit(stem_check): return False
        if 'btn_stem_ok' in stem_check:
            break
        send('請重新輸入題幹：', delay=0.5)
        new_stem = wait_for_user()
        if is_exit(new_stem): return False
        stem = new_stem
        write_log(f'[命題{n}] 題幹修改={stem}')
    send("接著我們來寫選項。\n"
         "在四個選項中，排除正確的選項，至少要有兩個錯誤選項有「誘答力」，也就是能代表常見迷思。"
         "如果你不知道怎麼寫，可以把正確觀念改掉一個關鍵字，就會變成迷思。"
            , delay=0.5
         )
    send('首先，請告訴我，你心中的正確答案：', delay=1)
    answer = wait_for_user()
    if is_exit(answer): return False
    print(f"[set_que] 題{n} 正確答案={answer[:60]}")

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

    send((
        '接下來，請你挑出兩個「最容易讓人選錯」的選項。'
    ), delay=1)

    send_checkbox(
        options     = [
            f'B. {wrong_options[0]}',
            f'C. {wrong_options[1]}',
            f'D. {wrong_options[2]}',
        ],
        max_select  = 2,
        checkbox_id = f'cb_pick_{n}',
    )

    first_pick = wait_for_user()
    if is_exit(first_pick): return False
    first_raw    = first_pick.replace('cb_first:', '').strip()
    first_label  = first_raw
    first_option = first_raw.split('. ', 1)[-1] if '. ' in first_raw else first_raw

    _lock(True)
    second_pick = wait_for_user()
    if is_exit(second_pick): return False
    second_raw    = second_pick.replace('cb_second:', '').strip()
    second_label  = second_raw
    second_option = second_raw.split('. ', 1)[-1] if '. ' in second_raw else second_raw

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

    # ── 所有資訊寫入 que_set_log ──
    record_question(
        n, concept, stem, clue, answer,
        wrong_options, first_label, second_label,
        guess_first, guess_second
    )

    return True


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    # 出題開始前先建立 que_set_log
    init_que_log()

    send((
        f'嗨，{username}，歡迎回來！\n'
        '現在要請你扮演「命題者」，練習把所學的概念變成題目。'
        '我會用三個小關卡指引你。\n'
        '你不用一次就寫得很完美，只要逐題完成就好。'
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

    used_concepts = set()
    for n in range(1, TOTAL_QUE + 1):
        if n > 1:
            send((
                f'完成進度：{n-1}/{TOTAL_QUE} 題\n'
            ), delay=1)

        ok = make_question(n, TOTAL_QUE, used_concepts)
        if not ok:
            print(f"[set_que.py] 第 {n} 題中斷，結束流程")
            return

    send(
        '很好，現在你已經完成命題，讓我召喚「孿生AI學生」來試做你的題目吧！',
        delay=1
    )

    import subprocess
    base_args = [
        '--username',   username,
        '--session_id', session_id,
        '--log_path',   log_path,
        '--que_log',    que_log_path,   # ← 傳遞 que_set_log 路徑
    ]
    subprocess.Popen(
        ['python', 'va_que_ana.py'] + base_args,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )

    print("[set_que.py] 全部 8 題完成，已啟動 que_ana.py")


if __name__ == '__main__':
    main()