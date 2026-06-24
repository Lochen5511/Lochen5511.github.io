import argparse
import os
import re
import time
import requests
from datetime import datetime
import re as _re
import csv
import random
from dotenv import load_dotenv
import openai
import json

# ──────────────────────────────────────────
# 接收變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
parser.add_argument('--que_log',    default='')
parser.add_argument('--round',      type=int, default=1)
args = parser.parse_args()

username            = args.username
session_id          = args.session_id
log_path            = args.log_path
revised_que_log_arg = args.que_log
current_round       = args.round
BACKEND             = 'http://localhost:5000'

from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
openai.api_key = os.getenv("AIKEY")

print(f"[true_ending.py] 啟動  user={username}  session={session_id}")

# ──────────────────────────────────────────
# 路徑設定
# ──────────────────────────────────────────
session_dir     = os.path.dirname(log_path)
old_folder_name = os.path.basename(session_dir)
old_session_id  = old_folder_name.replace(f"{username}_", "", 1)

pd_txt_path = log_path
if revised_que_log_arg and os.path.exists(revised_que_log_arg):
    que_log_path = revised_que_log_arg
else:
    que_log_path = os.path.join(session_dir, f"{old_session_id}_que_set_log.txt")

print(f"[true_ending] PD 報告路徑：{pd_txt_path}")
print(f"[true_ending] 題庫路徑：  {que_log_path}")

# 若 que_set_log 不存在，嘗試在 session_dir 中尋找任意 "*_que_set_log.txt" 作為 fallback
if not os.path.exists(que_log_path):
    try:
        candidates = []
        for fn in os.listdir(session_dir):
            if fn.endswith('_que_set_log.txt'):
                full = os.path.join(session_dir, fn)
                candidates.append((os.path.getmtime(full), full))
        if candidates:
            candidates.sort(reverse=True)
            que_log_path = candidates[0][1]
            print(f"[true_ending] que_set_log 未找到，使用最新備援：{que_log_path}")
        else:
            print(f"[true_ending] que_set_log 備援也找不到，session_dir={session_dir}")
    except Exception as e:
        print(f"[true_ending] 檢查 session_dir 時發生錯誤：{e}")

# ──────────────────────────────────────────
# que_set_log_r2 路徑（程式啟動時就確定，全域共用）
# ──────────────────────────────────────────
ts_start          = datetime.now().strftime('%Y%m%d_%H%M%S')
REVISED_QUE_LOG_PATH = os.path.join(
    session_dir,
    f"{session_id}_que_set_log_r2_{ts_start}.txt"
)
print(f"[true_ending] que_set_log_r2 路徑：{REVISED_QUE_LOG_PATH}")

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

def send(text: str, delay: float = 0):
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

def send_panel(target: str):
    """target: 'stats' | 'students' | 'stats_close' | 'students_close'"""
    _post('/push', {
        'text':       f'__PANEL__{target}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    print(f'[panel] {target}')

def send_alert(message: str):
    _post('/push', {
        'text':       f'__ALERT__{message}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    print(f"[alert] {message[:50]}")

def send_button(label: str, delay: float = 0,
                color: str = 'gold', size: str = 'medium',
                button_id: str = ''):
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
    _lock(True)
    print(f"[button] {label}  id={bid}")

def send_buttons(labels: list, delay: float = 0,
                 colors: list = None, size: str = 'medium',
                 sizes: list = None, button_ids: list = None):
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
    _lock(True)
    print(f"[buttons] {labels}")

def wait_for_user(interval: float = 0.5, timeout: int = 300, wait_limit: int = None) -> str | None:
    import time as _time
    start = _time.time()
    ONLINE_CHECK_DELAY = 10

    while True:
        elapsed = _time.time() - start

        if wait_limit and elapsed > wait_limit:
            print(f"[wait_for_user] 等待超時 wait_limit={wait_limit}s")
            _write_log(f'[逾時] 等待作答超過 {wait_limit} 秒，流程中斷')
            _lock(False)
            return None

        data = _get('/fetch_user_input', {'session_id': session_id})
        msg  = data.get('message')
        if msg:
            _lock(False)
            print(f"[user] {msg[:60]}")
            return msg

        interrupted = _get('/check_interrupted', {'session_id': session_id})
        if interrupted.get('interrupted', False):
            print(f"[wait_for_user] session={session_id} 被 ID 輸入中斷")
            _write_log('[中斷] 用戶輸入 ID，流程中斷')
            _lock(False)
            return '__INTERRUPTED__'

        if elapsed >= ONLINE_CHECK_DELAY:
            online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
            if not online.get('online', True):
                print(f"[wait_for_user] 用戶已離開 session={session_id}")
                _write_log('用戶已離開系統')
                _lock(False)
                return None

        time.sleep(interval)

def _write_log(content: str):
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def update_unit(unit: str):
    _post('/update_unit', {'session_id': session_id, 'unit': unit})
    print(f"[unit] 記錄單元={unit}")

def _lock(locked: bool):
    _post('/lock_input', {'session_id': session_id, 'locked': locked})

def send_dropdown(options: list, placeholder: str = '請選擇…',
                  dropdown_id: str = 'dropdown', delay: float = 0):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    parts = '||'.join(options)
    _post('/push', {
        'text':       f'__DROPDOWN__{dropdown_id}||{placeholder}||{parts}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    _lock(True)
    print(f"[dropdown] {options}")

def load_answer_matrix(session_dir: str, username: str) -> list:
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")
    if not os.path.exists(matrix_path):
        print(f"[true_ending] AnswerMatrix 不存在：{matrix_path}")
        return []
    try:
        with open(matrix_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows   = list(reader)
        return [row for row in rows[1:] if row]
    except Exception as e:
        print(f"[true_ending] AnswerMatrix 讀取失敗：{e}")
        return []

def load_validity_wide_table() -> list:
    logs_dir   = os.path.dirname(session_dir)
    table_path = os.path.join(logs_dir, 'validity_wide_table.csv')
    if not os.path.exists(table_path):
        print(f"[true_ending] validity_wide_table 不存在：{table_path}")
        return []
    try:
        with open(table_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"[true_ending] validity_wide_table 讀取失敗：{e}")
        return []

def _push_existing_answer_matrix():
    """讀取第一輪 AnswerMatrix.csv，重新推送 __DATA__ 讓側邊欄顯示第一輪資料。"""
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")
    if not os.path.exists(matrix_path):
        print(f"[_push_existing] AnswerMatrix 不存在：{matrix_path}")
        return

    all_answers = []
    try:
        with open(matrix_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows   = list(reader)
        for row in rows[1:]:
            if not row:
                continue
            answers = ['A' if cell == '1' else 'B' for cell in row[:8]]
            all_answers.append(answers)
    except Exception as e:
        print(f"[_push_existing] 讀取失敗：{e}")
        return

    if not all_answers:
        print("[_push_existing] AnswerMatrix 無資料")
        return

    correct_answers = ['A'] * 8
    stats = {}
    for q_idx in range(8):
        key    = f'Q{q_idx+1}'
        counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for row in all_answers:
            ans = row[q_idx] if q_idx < len(row) else None
            if ans in counts:
                counts[ans] += 1
        stats[key] = counts

    students = [
        {
            'id':      i + 1,
            'answers': row,
            'score':   sum(1 for qi, a in enumerate(row) if qi < 8 and a == correct_answers[qi]),
        }
        for i, row in enumerate(all_answers)
    ]

    push_data = json.dumps({
        'type':       'answer_matrix',
        'stats':      stats,
        'n_students': len(all_answers),
        'students':   students,
        'correct':    correct_answers,
    }, ensure_ascii=False)

    _post('/push', {
        'text':       f'__DATA__{push_data}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })
    print(f"[_push_existing] 已推送第一輪資料，共 {len(all_answers)} 筆")


def pick_student(answers: list, q_idx: int, target: str) -> dict | None:
    n      = len(answers)
    low    = list(range(0,            min(10, n)))
    mid    = list(range(10,           min(20, n)))
    high   = list(range(max(0, n-10), n))

    groups = [low, mid, high] if target == '0' else [high, mid, low]

    wide_table = load_validity_wide_table()
    FIELDS     = ['admin_session_id', 'accuracy', 'avg_confidence',
                  'low_conf_ratio', 'high_conf_wrong_ratio',
                  'V1a', 'V1b', 'V1c', 'V2a', 'V2b', 'X1', 'V3a', 'V3b']

    for group in groups:
        candidates = [i for i in group if i < len(answers) and answers[i][q_idx] == target]
        if candidates:
            chosen_idx = random.choice(candidates)
            raw_row    = wide_table[chosen_idx] if chosen_idx < len(wide_table) else {}

            result = {'row_index': chosen_idx}
            for field in FIELDS:
                result[field] = raw_row.get(field, '')

            print(f"[true_ending] 挑選學生 列索引={chosen_idx} target={target} data={result}")
            return result

    print(f"[true_ending] 找不到 target={target} 的學生")
    return None


def call_ai_student(student: dict, q_info: dict, user_question: str) -> str:
    is_wrong = student.get('_target') == '0'
    role_constraint = (
        '你答錯了這題，回答時必須展現出錯誤的理解，不能說出正確答案或承認自己錯了。'
        if is_wrong else
        '你答對了這題，回答時必須展現出正確的理解，並解釋你為何沒選別的選項'
    )

    system_prompt = f"""你是一位正在接受測驗的學生，請依據以下認知數值扮演這位學生。
回答只能使用繁體中文，語氣自然像真實學生，不要透露你是AI。

{role_constraint}

以下是你的認知數值：
accuracy                = {student.get('accuracy', '')}（答對率）
avg_confidence          = {student.get('avg_confidence', '')}（平均信心）
low_conf_ratio          = {student.get('low_conf_ratio', '')}（低信心比例）
high_conf_wrong_ratio   = {student.get('high_conf_wrong_ratio', '')}（自信但答錯比例）
V1a = {student.get('V1a', '')}（用外觀直覺當主要效度證據）
V1b = {student.get('V1b', '')}（把效標關聯誤當內容效度或反之）
V1c = {student.get('V1c', '')}（把信度指標當效度證據）
V2a = {student.get('V2a', '')}（同時效度與預測效度顛倒）
V2b = {student.get('V2b', '')}（忽略時間線索）
X1  = {student.get('X1',  '')}（信度—效度關係推論錯誤）
V3a = {student.get('V3a', '')}（把建構效度誤當內容效度）
V3b = {student.get('V3b', '')}（把建構效度誤當效標關聯效度）

以下是你剛才作答的題目：
題幹：{q_info.get('stem', '')}
選項A（正確答案）：{q_info.get('correct', '')}
選項B：{q_info.get('opt_b', '')}
選項C：{q_info.get('opt_c', '')}
選項D：{q_info.get('opt_d', '')}
關鍵線索：{q_info.get('clues', '')}
"""

    try:
        response = openai.ChatCompletion.create(
            model       = 'gpt-4o',
            temperature = 0.7,
            messages    = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_question},
            ]
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"[true_ending] AI 呼叫失敗：{e}")
        return '（學生暫時無法回應，請稍後再試。）'


def interview_student(student: dict, q_info: dict, label: str):
    send(f'你想要問這位{label}的學生什麼呢？', delay=0.5)
    send_buttons(
        labels     = ['你為什麼會選那個選項？',
                      '你在題幹裡抓到的線索是什麼？',
                      '如果題幹某一句改得更清楚，你會改選哪個？',
                      '我要自己問'],
        colors     = ['gold', 'gold', 'gold', 'gray'],
        size       = 'medium',
        button_ids = ['btn_q_why', 'btn_q_clue', 'btn_q_rewrite', 'btn_q_custom'],
        delay      = 0.3,
    )

    choice = wait_for_user()
    if choice is None or choice == '__INTERRUPTED__':
        return

    choice_id = choice.split(':')[0] if ':' in choice else choice

    if choice_id == 'btn_q_custom':
        send('請輸入問題。', delay=0.3)
        _lock(False)
        user_question = wait_for_user()
        if user_question is None or user_question == '__INTERRUPTED__':
            return
    else:
        btn_label_map = {
            'btn_q_why':     '你為什麼會選那個選項？',
            'btn_q_clue':    '你在題幹裡抓到的線索是什麼？',
            'btn_q_rewrite': '如果題幹某一句改得更清楚，你會改選哪個？',
        }
        user_question = btn_label_map.get(choice_id, choice)

    _thinking(True)
    ai_reply = call_ai_student(student, q_info, user_question)
    _thinking(False)
    send(ai_reply)


# ──────────────────────────────────────────
# 收集並確認單筆輸入（含重試迴圈）
# ──────────────────────────────────────────
def collect_confirmed_input(prompt: str) -> str | None:
    while True:
        send(prompt, delay=0.3)
        _lock(False)
        user_input = wait_for_user()
        if user_input is None or user_input == '__INTERRUPTED__':
            return user_input

        send(f'你輸入的內容是：\n\n{user_input}\n\n確認無誤嗎？', delay=0.3)
        send_buttons(
            labels     = ['確認，繼續', '需要修改'],
            colors     = ['green', 'gray'],
            size       = 'medium',
            button_ids = ['btn_confirm_ok', 'btn_confirm_redo'],
            delay      = 0.3,
        )
        confirm = wait_for_user()
        if confirm is None or confirm == '__INTERRUPTED__':
            return confirm

        confirm_id = confirm.split(':')[0] if ':' in confirm else confirm
        if confirm_id == 'btn_confirm_ok':
            return user_input
        # btn_confirm_redo：繼續迴圈，重新輸入


# ──────────────────────────────────────────
# 題目修改流程
# ──────────────────────────────────────────
def revise_question(q_info: dict) -> dict:
    send('現在把你剛剛問到的線索用在改題上。', delay=0.5)
    send('你只需要改兩個地方其中之一（或兩個都改）：', delay=0.3)
    send_buttons(
        labels     = ['改題幹', '改選項', '兩個都改'],
        colors     = ['gold', 'gold', 'gold'],
        size       = 'medium',
        button_ids = ['btn_revise_stem', 'btn_revise_options', 'btn_revise_both'],
        delay      = 0.3,
    )

    revise_choice = wait_for_user()
    if revise_choice is None or revise_choice == '__INTERRUPTED__':
        return {}

    revise_id = revise_choice.split(':')[0] if ':' in revise_choice else revise_choice

    revised = {
        'revised_stem':    q_info.get('stem',    ''),
        'revised_correct': q_info.get('correct', ''),
        'revised_opt_b':   q_info.get('opt_b',   ''),
        'revised_opt_c':   q_info.get('opt_c',   ''),
        'revised_opt_d':   q_info.get('opt_d',   ''),
    }

    do_stem    = revise_id in ('btn_revise_stem',    'btn_revise_both')
    do_options = revise_id in ('btn_revise_options', 'btn_revise_both')

    if do_stem:
        result = collect_confirmed_input('請將修改後的完整題幹發送：')
        if result is None or result == '__INTERRUPTED__':
            return {}
        revised['revised_stem'] = result

    if do_options:
        if do_stem:
            send('接著，請發送四個選項。', delay=0.3)
        else:
            send('請發送修改後的四個選項。', delay=0.3)

        for label, key in [
            ('正確答案 A', 'revised_correct'),
            ('錯誤選項 B', 'revised_opt_b'),
            ('錯誤選項 C', 'revised_opt_c'),
            ('錯誤選項 D', 'revised_opt_d'),
        ]:
            result = collect_confirmed_input(f'請輸入修改後的【{label}】：')
            if result is None or result == '__INTERRUPTED__':
                return {}
            revised[key] = result

    summary_lines = [f'✅ 第 {q_info.get("q_key", "")} 題修改完成！\n']
    summary_lines.append(f'題幹：{revised["revised_stem"]}')
    summary_lines.append(f'A（正確）：{revised["revised_correct"]}')
    summary_lines.append(f'B：{revised["revised_opt_b"]}')
    summary_lines.append(f'C：{revised["revised_opt_c"]}')
    summary_lines.append(f'D：{revised["revised_opt_d"]}')
    send('\n'.join(summary_lines), delay=0.5)

    print(f"[revise_question] 修改結果：{revised}")
    return revised


# ──────────────────────────────────────────
# 讀取 PD 報告
# ──────────────────────────────────────────
def load_pd_report(path: str) -> dict:
    result = {}
    if not os.path.exists(path):
        print(f"[true_ending] PD 報告不存在：{path}")
        return result

    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[true_ending] PD 報告讀取失敗：{e}")
        return result

    for line in lines:
        line = line.strip()
        if not line or line.startswith('題目') or line.startswith('─'):
            continue
        parts = [p.strip() for p in line.split('｜')]
        if len(parts) < 4:
            continue
        q_key = parts[0].replace('\u3000', '').replace(' ', '')
        try:
            p_val = float(parts[1])
            d_val = float(parts[2])
        except ValueError:
            continue
        label = parts[3]
        result[q_key] = {'p': p_val, 'd': d_val, 'label': label}

    print(f"[true_ending] 讀取 PD 報告：{len(result)} 題")
    return result


def _extract_pd_from_log(logfile: str) -> dict:
    out = {}
    if not os.path.exists(logfile):
        return out
    try:
        with open(logfile, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '｜' not in line:
                    continue
                parts = [p.strip() for p in line.split('｜')]
                if len(parts) < 4:
                    continue
                key = parts[0].replace('\u3000','').replace(' ','')
                try:
                    p_val = float(parts[1])
                    d_val = float(parts[2])
                except ValueError:
                    continue
                out[key] = {'p': p_val, 'd': d_val, 'label': parts[3]}
    except Exception as e:
        print(f"[true_ending] 從 log 擷取 PD 失敗：{e}")
    if out:
        print(f"[true_ending] 從 session log 擷取到 PD：{len(out)} 題")
    return out


def _compute_pd_from_answer_matrix(session_dir: str, user_name: str) -> dict:
    CORRECT_ANS = '1'
    N_GROUP     = 10

    matrix_path = os.path.join(session_dir, f"{user_name}_AnswerMatrix.csv")
    if not os.path.exists(matrix_path):
        print(f"[true_ending] AnswerMatrix 不存在：{matrix_path}")
        return {}

    answers       = []
    question_keys = []
    try:
        with open(matrix_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows   = list(reader)
        if rows:
            header        = rows[0]
            question_keys = [h for h in header if re.match(r'^Q\d+$', h)]
        for row in rows[1:]:
            if not row:
                continue
            answers.append(row[:len(question_keys)])
    except Exception as e:
        print(f"[true_ending] 讀取 AnswerMatrix 失敗：{e}")
        return {}

    n = len(answers)
    if n == 0:
        print("[true_ending] AnswerMatrix 無作答資料")
        return {}

    scores       = [sum(1 for ans in row if ans == CORRECT_ANS) for row in answers]
    indexed      = sorted(enumerate(scores), key=lambda x: x[1])
    low_indices  = [i for i, _ in indexed[:N_GROUP]]
    high_indices = [i for i, _ in indexed[-N_GROUP:]]

    result = {}
    for q_idx, q_key in enumerate(question_keys):
        correct_count = sum(1 for row in answers if q_idx < len(row) and row[q_idx] == CORRECT_ANS)
        p = round(correct_count / n, 3)

        high_correct = sum(1 for i in high_indices if q_idx < len(answers[i]) and answers[i][q_idx] == CORRECT_ANS)
        low_correct  = sum(1 for i in low_indices  if q_idx < len(answers[i]) and answers[i][q_idx] == CORRECT_ANS)
        d = round(high_correct / N_GROUP - low_correct / N_GROUP, 3)

        result[q_key] = {'p': p, 'd': d, 'label': ''}

    print(f"[true_ending] 從 AnswerMatrix 計算 PD：{len(result)} 題")
    return result


# ──────────────────────────────────────────
# 讀取題庫 log
# ──────────────────────────────────────────
def load_que_log(path: str) -> dict:
    """
    回傳 {q_key_str: {英文field: value}} dict，key 為 'Q1'、'Q2'…字串。
    相容有時間戳（原始格式）與無時間戳（write_revised_que_log 寫出格式）兩種。
    """
    result = {}
    if not os.path.exists(path):
        print(f"[true_ending] 題庫不存在：{path}")
        return result

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[true_ending] 題庫讀取失敗：{e}")
        return result

    # 剝除每行的時間戳前綴，統一格式後再解析
    clean_lines = []
    for line in content.splitlines():
        stripped = re.sub(r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*', '', line)
        clean_lines.append(stripped)
    clean_content = '\n'.join(clean_lines)

    blocks = re.findall(r'\[Q(\d+)_START\](.*?)\[Q\1_END\]', clean_content, re.DOTALL)
    print(f"[load_que_log] 找到 {len(blocks)} 個題目區塊")

    field_map = {
        '題幹':     'stem',
        '概念標籤': 'concept',
        '關鍵線索': 'clues',
        '正確答案A': 'correct',
        '錯誤選項B': 'opt_b',
        '錯誤選項C': 'opt_c',
        '錯誤選項D': 'opt_d',
        '易錯選項1': 'distractor_1',
        '易錯選項2': 'distractor_2',
        '易錯推測1': 'misconception_1',
        '易錯推測2': 'misconception_2',
    }

    for num_str, block in blocks:
        q_key  = f'Q{num_str}'
        q_data = {}

        for line in block.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r'\[Q\d+\]\s*(.+?)=(.+)', line)
            if not m:
                continue
            field = m.group(1).strip()
            value = m.group(2).strip()
            key   = field_map.get(field)
            if key:
                q_data[key] = value

        result[q_key] = q_data
        print(f"[load_que_log] {q_key}: stem={q_data.get('stem','')[:20]}...")

    print(f"[true_ending] 讀取題庫：{len(result)} 題")
    return result


# ──────────────────────────────────────────
# 篩選 D < 0.25 的題目
# ──────────────────────────────────────────
def find_weak_questions(pd_data: dict, que_data: dict, threshold=0.25) -> list:
    weak = []
    for q_key, pd_info in sorted(pd_data.items(),
                                  key=lambda x: int(x[0].replace('Q', ''))):
        if pd_info['d'] < threshold:
            entry = {
                'q_key': q_key,
                'p':     pd_info['p'],
                'd':     pd_info['d'],
                'label': pd_info['label'],
            }
            entry.update(que_data.get(q_key, {}))
            weak.append(entry)
    return weak


# ──────────────────────────────────────────
# 將單題修改結果立刻追加寫入 que_set_log_r2
# ──────────────────────────────────────────
ENGLISH_TO_CN = {
    'stem':            '題幹',
    'concept':         '概念標籤',
    'clues':           '關鍵線索',
    'correct':         '正確答案A',
    'opt_b':           '錯誤選項B',
    'opt_c':           '錯誤選項C',
    'opt_d':           '錯誤選項D',
    'distractor_1':    '易錯選項1',
    'distractor_2':    '易錯選項2',
    'misconception_1': '易錯推測1',
    'misconception_2': '易錯推測2',
}


def append_revised_question(q_key: str, orig_q: dict, rev: dict) -> bool:
    """
    將單題修改結果追加寫入 REVISED_QUE_LOG_PATH。
    orig_q 使用英文 key（來自 load_que_log）。
    rev 使用 revised_* key（來自 revise_question）。
    寫入失敗時回傳 False，並透過 send_alert 報錯。
    """
    q_key_str = str(q_key) if str(q_key).startswith('Q') else f'Q{q_key}'

    # 以原始資料為底，套上修改值
    merged = {cn: orig_q.get(en, '') for en, cn in ENGLISH_TO_CN.items()}
    merged['題幹']      = rev.get('revised_stem',    merged.get('題幹',      ''))
    merged['正確答案A'] = rev.get('revised_correct', merged.get('正確答案A', ''))
    merged['錯誤選項B'] = rev.get('revised_opt_b',   merged.get('錯誤選項B', ''))
    merged['錯誤選項C'] = rev.get('revised_opt_c',   merged.get('錯誤選項C', ''))
    merged['錯誤選項D'] = rev.get('revised_opt_d',   merged.get('錯誤選項D', ''))

    block_lines = [f'[{q_key_str}_START]']
    for cn_key, value in merged.items():
        block_lines.append(f'[{q_key_str}] {cn_key}={value}')
    block_lines.append(f'[{q_key_str}_END]')
    block_lines.append('')   # 題目之間空一行
    block_text = '\n'.join(block_lines)

    try:
        with open(REVISED_QUE_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(block_text + '\n')
        print(f"[append_revised_question] {q_key_str} 已追加寫入 {REVISED_QUE_LOG_PATH}")
        _write_log(f'[true_ending] {q_key_str} 修改已追加寫入 que_set_log_r2')
        return True
    except Exception as e:
        err_msg = f'{q_key_str} 修改寫入失敗：{e}'
        print(f"[append_revised_question] {err_msg}")
        _write_log(f'[true_ending] {err_msg}')
        send_alert(f'⚠️ {err_msg}\n請通知系統管理員，流程中止。')
        return False


# ──────────────────────────────────────────
# 主程式
# ──────────────────────────────────────────
def main():
    pd_data = load_pd_report(pd_txt_path)
    if not pd_data:
        pd_data = _extract_pd_from_log(pd_txt_path)
    if not pd_data:
        pd_data = _compute_pd_from_answer_matrix(session_dir, username)
        if pd_data:
            print(f"[true_ending] 已從 AnswerMatrix 產生 PD 報告，共 {len(pd_data)} 題")

    que_data = load_que_log(que_log_path)
    weak     = find_weak_questions(pd_data, que_data)

    # ── 推送 PD／題庫資料 ──
    try:
        if pd_data:
            _post('/push', {
                'text':       f"__DATA__{json.dumps({'type':'pd_report','items':pd_data}, ensure_ascii=False)}",
                'username':   username,
                'session_id': session_id,
                'log_path':   '',
            })
        if que_data:
            _post('/push', {
                'text':       f"__DATA__{json.dumps({'type':'que_log','questions':que_data}, ensure_ascii=False)}",
                'username':   username,
                'session_id': session_id,
                'log_path':   '',
            })
    except Exception as e:
        print(f"[true_ending] 推送 PD/題庫失敗：{e}")

    # ══════════════════════════════════════════
    # round == 1：完整開場（第一次進入）
    # round >= 2：跳過歡迎語與 PD 總覽，直接進修題
    # ══════════════════════════════════════════
    if current_round == 1:
        send(f'歡迎回來，{username}！我是艾評。', delay=1)
        _push_existing_answer_matrix()
        send_panel('stats')
        send_panel('students')
        send('上次課程中，我們已經完成了鑑別度的計算。', delay=0.5)
        send('今天，我們就要一起對鑑別度較低的題目進行修改。', delay=0.5)
        send('先來回顧一下上次的紀錄吧！\n請注意，右側欄只反映答對與答錯，選擇A則為記錄上答對，選擇B則為答錯。', delay=0.5)

        def d_label(d):
            if d >= 0.4:    return '優異'
            elif d >= 0.25: return '正常'
            else:           return '待加強'

        table_lines = ['各題難度與鑑別度總覽：\n']
        table_lines.append('題目｜難度 P｜鑑別度 D｜評價')
        table_lines.append('─' * 32)
        for q_key, val in pd_data.items():
            label = d_label(val['d'])
            table_lines.append(f"{q_key}｜{val['p']}｜{val['d']}｜{label}")
        send('\n'.join(table_lines), delay=0.5)

        r1_pd_path = os.path.join(session_dir, f"{old_session_id}_r1_pd_report.txt")
        try:
            with open(r1_pd_path, 'w', encoding='utf-8') as f:
                f.write('題目｜難度 P｜鑑別度 D｜評價\n')
                f.write('─' * 32 + '\n')
                for q_key, val in pd_data.items():
                    label = d_label(val['d'])
                    f.write(f"{q_key}｜{val['p']}｜{val['d']}｜{label}\n")
        except Exception as e:
            print(f"[true_ending] r1 PD 寫出失敗：{e}")

        if not weak:
            send('恭喜！所有題目的鑑別度均已達標（D ≥ 0.25），不需要進行修改。', delay=0.5)
            print(pd_data)
            send(f'課程流程到此完成，{username}，謝謝你的參與！', delay=0.5)
            return

        send('接下來，我們要開始修改鑑別度未達標的題目。\n你可以從列表中選擇你想先改的題目：', delay=0.5)

    else:
        # round >= 2：重新從最新 AnswerMatrix 計算 PD，重建 weak 清單
        pd_data = _compute_pd_from_answer_matrix(session_dir, username) or pd_data
        weak    = find_weak_questions(pd_data, que_data)

        send('好，我們繼續！', delay=0.5)

        if not weak:
            send('所有題目的鑑別度都已達標（D ≥ 0.25），不需要再修改了。', delay=0.5)
            send('整個流程到此圓滿完成，謝謝你的參與！', delay=0.5)
            return

        send(f'以下 {len(weak)} 題仍需修改，請從列表中選擇：', delay=0.5)

    remaining_weak = weak.copy()
    all_revised    = {}

    while remaining_weak:
        weak_options = [f"{q['q_key']}｜{q.get('concept', '未知概念')}｜D={q['d']}" for q in remaining_weak]
        send_dropdown(
            options     = weak_options,
            placeholder = '請選擇想修改的題目…',
            dropdown_id = 'select_weak_q',
            delay       = 0.3,
        )

        user_input = wait_for_user()
        if user_input is None or user_input == '__INTERRUPTED__':
            return

        match = _re.match(r'(Q\d+)', user_input.strip())
        if not match:
            send('請從列表中選擇題目。', delay=0.3)
            continue

        selected_key = match.group(1)
        selected_q   = next((q for q in remaining_weak if q['q_key'] == selected_key), None)
        if not selected_q:
            send('請從列表中選擇題目。', delay=0.3)
            continue

        remaining_weak = [q for q in remaining_weak if q['q_key'] != selected_key]

        q_preview = (
            f'讓我們來看看這一題：\n\n'
            f'【題幹】\n{selected_q.get("stem", "（無題幹）")}\n\n'
            f'A. {selected_q.get("correct", "")}\n'
            f'B. {selected_q.get("opt_b",   "")}\n'
            f'C. {selected_q.get("opt_c",   "")}\n'
            f'D. {selected_q.get("opt_d",   "")}'
        )
        send(q_preview, delay=0.5)

        send(f'那麼首先，你覺得第 {selected_key} 題要先改哪裡？', delay=0.5)
        send_buttons(
            labels     = ['題幹不清楚／線索不夠',
                          '正確答案不夠明確／可能有多個類似正確答案的答案',
                          '某個錯誤選項太誘答（很多人選）',
                          '某個錯誤選項太弱（幾乎沒人選）'],
            colors     = ['gold', 'gold', 'gold', 'gold'],
            size       = 'medium',
            button_ids = ['btn_fix_stem', 'btn_fix_correct',
                          'btn_fix_distractor_strong', 'btn_fix_distractor_weak'],
            delay      = 0.3,
        )

        fix_choice = wait_for_user()
        if fix_choice is None or fix_choice == '__INTERRUPTED__':
            return

        send('好，問題已經列清楚了。接下來，我們來問問看作答的AI孿生學生為何這麼作答吧！', delay=0.5)

        answers = load_answer_matrix(session_dir, username)
        q_idx   = int(selected_key.replace('Q', '')) - 1
        q_info  = selected_q

        wrong_student   = pick_student(answers, q_idx, target='0')
        correct_student = pick_student(answers, q_idx, target='1')

        print(f"[true_ending] 答錯學生：{wrong_student}")
        print(f"[true_ending] 答對學生：{correct_student}")

        if wrong_student:
            wrong_student['_target'] = '0'
        if correct_student:
            correct_student['_target'] = '1'

        btn_labels = []
        btn_ids    = []
        btn_colors = []
        if wrong_student:
            btn_labels.append('召喚答錯的學生')
            btn_ids.append('btn_call_wrong')
            btn_colors.append('red')
        if correct_student:
            btn_labels.append('召喚答對的學生')
            btn_ids.append('btn_call_correct')
            btn_colors.append('green')

        if not btn_labels:
            send('（找不到可召喚的學生，跳過此題。）', delay=0.3)
            continue

        has_both    = len(btn_labels) == 2
        interviewed = set()

        send_buttons(labels=btn_labels, colors=btn_colors,
                     size='medium', button_ids=btn_ids, delay=0.3)

        btn_choice = wait_for_user()
        if btn_choice is None or btn_choice == '__INTERRUPTED__':
            return

        btn_choice_id = btn_choice.split(':')[0] if ':' in btn_choice else btn_choice

        if btn_choice_id == 'btn_call_wrong' and wrong_student:
            interview_student(wrong_student, q_info, '答錯')
            interviewed.add('wrong')
        elif btn_choice_id == 'btn_call_correct' and correct_student:
            interview_student(correct_student, q_info, '答對')
            interviewed.add('correct')

        if has_both and len(interviewed) < 2:
            other_label = '答對的學生' if 'wrong' in interviewed else '答錯的學生'
            send_buttons(
                labels     = [f'召喚另一個學生（{other_label}）'],
                colors     = ['gold'],
                size       = 'medium',
                button_ids = ['btn_call_other'],
                delay      = 0.5,
            )

            other_choice = wait_for_user()
            if other_choice is None or other_choice == '__INTERRUPTED__':
                return

            other_id = other_choice.split(':')[0] if ':' in other_choice else other_choice
            if other_id == 'btn_call_other':
                if 'wrong' in interviewed and correct_student:
                    interview_student(correct_student, q_info, '答對')
                elif 'correct' in interviewed and wrong_student:
                    interview_student(wrong_student, q_info, '答錯')

        q_info['q_key'] = selected_key
        revised = revise_question(q_info)
        if not revised:
            return

        # ── 每題改完立刻追加寫入 que_set_log_r2 ──
        orig_q = que_data.get(selected_key, {})
        ok = append_revised_question(selected_key, orig_q, revised)
        if not ok:
            return   # send_alert 已在函式內發送，直接中止

        all_revised[selected_key] = revised

    run_second_round(all_revised)


# ──────────────────────────────────────────
# 第二輪核心：AI 孿生作答
# ──────────────────────────────────────────

# ── 修復：動態 system prompt，根據實際題數產生，避免 GPT 固定輸出 8 個答案 ──
def _qa_build_system_prompt(n_questions: int) -> str:
    return f"""\
請依據以下註釋與學生的認知數值，預測這個學生回答以下題目的答案。

本次考卷共 {n_questions} 題，你必須輸出恰好 {n_questions} 個答案，不多不少。

accuracy = 答對題數 ÷ 總題數。例如答對 6 題共 {n_questions} 題 → accuracy ≈ {round(6/n_questions, 2)}。
avg_confidence = 所有題目的信心分數（1-5）加總 ÷ 題數。反映用戶對自己答案的整體把握程度。
low_conf_ratio = 信心分數 ≤ 2 的題目數 ÷ 總題數。比例越高代表用戶越不確定自己的答案。
high_conf_wrong_ratio = 信心分數 ≥ 4 但答錯的題目數 ÷ 總題數。這是最重要的指標之一，反映用戶「自信但錯誤」的程度，也就是迷思概念最強固的狀態。
V1a = V_FACE_OVERUSE（用外觀直覺當主要效度證據）
V1b = V_CONTENT_CRITERION_CONFUSE（把效標關聯/相關/預測的證據誤當內容效度或反之）
V1c = V_RELIABILITY_AS_VALIDITY（把信度指標/α 當效度證據）
V2a = V_CONCUR_PRED_SWAP（同時效度與預測效度顛倒）
V2b = V_TIME_BLIND（忽略時間線索，只要看到「相關」就固定選某一類）
X1 = X_REL_VALID_RELATION_ERROR（信度—效度關係推論錯：必要但不充分不懂/推反/否認關係）
V3a = V_CONSTRUCT_CONTENT_CONFUSE（把建構效度證據誤當內容效度）
V3b = V_CONSTRUCT_CRITERION_CONFUSE（把建構效度證據誤當效標關聯效度）

【重要輸出要求】
- 只輸出答案，不輸出任何其他文字、說明或標點以外的內容
- 答案必須用英文逗號分隔，例如（{n_questions} 題時）：A,B,A,C,B,A,D{"" if n_questions <= 6 else ",A"}{"" if n_questions <= 7 else "," + ",".join(["B"]*(n_questions-7))}
- 答案數量必須恰好是 {n_questions} 個，對應題目 1 到 {n_questions}
- 每個答案必須是單一大寫字母，只能是 A、B、C 或 D 其中之一
"""


MAX_STUDENTS_R2 = 30


def _qa_load_wide_table() -> list:
    logs_dir   = os.path.dirname(session_dir)
    table_path = os.path.join(logs_dir, 'validity_wide_table.csv')
    lock_path  = table_path + '.lock'

    import time as _time
    start    = _time.time()
    acquired = False
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            acquired = True
            break
        except FileExistsError:
            if _time.time() - start > 10.0:
                print('[wide_table] 鎖定逾時，強制繼續')
                break
            _time.sleep(0.05)

    rows = []
    try:
        with open(table_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows   = list(reader)
        print(f'[wide_table] 讀取 {len(rows)} 筆')
    except Exception as e:
        print(f'[wide_table 讀取失敗] {e}')
    finally:
        if acquired:
            try: os.remove(lock_path)
            except: pass

    return rows


def _qa_que_info_summary(que_data: dict) -> str:
    if not que_data:
        return ''
    lines = ['【出題者提供的額外資訊】']
    for n in sorted(que_data.keys()):
        q = que_data[n]
        lines.append(
            f"第{n}題｜概念：{q.get('概念標籤','')}｜"
            f"關鍵線索：{q.get('關鍵線索','')}｜"
            f"易錯選項：{q.get('易錯選項1','')} / {q.get('易錯選項2','')}｜"
            f"易錯推測：{q.get('易錯推測1','')} / {q.get('易錯推測2','')}"
        )
    return '\n'.join(lines)


def _qa_row_to_prompt(row: dict, questions: list, que_data: dict) -> str:
    stats = (
        f"accuracy={row.get('accuracy','')}  "
        f"avg_confidence={row.get('avg_confidence','')}  "
        f"low_conf_ratio={row.get('low_conf_ratio','')}  "
        f"high_conf_wrong_ratio={row.get('high_conf_wrong_ratio','')}\n"
        f"V1a={row.get('V1a','')}  V1b={row.get('V1b','')}  V1c={row.get('V1c','')}  "
        f"V2a={row.get('V2a','')}  V2b={row.get('V2b','')}  X1={row.get('X1','')}  "
        f"V3a={row.get('V3a','')}  V3b={row.get('V3b','')}"
    )
    ques = '\n'.join(
        f"題{i+1}：{q['stem']}\n選項：{', '.join(f'{k}. {v}' for k, v in q['options'].items())}"
        for i, q in enumerate(questions)
    )
    extra  = _qa_que_info_summary(que_data)
    prompt = f"學生數值：\n{stats}\n\n題目（共 {len(questions)} 題，請輸出恰好 {len(questions)} 個答案）：\n{ques}"
    if extra:
        prompt += f"\n\n{extra}"
    return prompt


def _qa_build_questions(que_data: dict) -> list:
    """
    從 _load_revised_que_data 回傳的 dict（key 為 int，value 為中文 key）
    組裝 questions list。
    """
    questions = []
    for n in sorted(que_data.keys()):
        q = que_data[n]
        if all(k in q for k in ('題幹', '正確答案A', '錯誤選項B', '錯誤選項C', '錯誤選項D')):
            questions.append({
                'q_key':   f'Q{n}' if isinstance(n, int) or str(n).isdigit() else str(n),
                'stem':    q['題幹'],
                'options': {
                    'A': q['正確答案A'],
                    'B': q['錯誤選項B'],
                    'C': q['錯誤選項C'],
                    'D': q['錯誤選項D'],
                }
            })
    return questions


def _qa_save_answer_matrix(answers: list, question_keys: list, round_tag: str = 'r2') -> str:
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(session_dir, f"{username}_AnswerMatrix_{round_tag}_{ts}.csv")
    header   = question_keys + ['Total']
    try:
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for row in answers:
                binary = [1 if ans == 'A' else 0 for ans in row[:len(question_keys)]]
                writer.writerow(binary + [sum(binary)])
        print(f'[AnswerMatrix_r2] 已儲存：{out_path}（{len(answers)} 筆）')
        _write_log(f'[true_ending] AnswerMatrix_r2 已儲存：{out_path}')
    except Exception as e:
        print(f'[AnswerMatrix_r2 儲存失敗] {e}')
        return ''
    return out_path


def _qa_run_twins(revised_que_data: dict) -> tuple[list, list]:
    rows = _qa_load_wide_table()
    if not rows:
        return [], []

    questions = _qa_build_questions(revised_que_data)
    if len(questions) == 0:
        print(f'[_qa_run_twins] 題數不足：{len(questions)}')
        return [], questions

    n_questions    = len(questions)
    # ── 修復：每次呼叫時動態產生 system prompt，題數正確注入 ──
    system_prompt  = _qa_build_system_prompt(n_questions)
    print(f'[_qa_run_twins] 題數={n_questions}，system prompt 已動態產生')

    target_rows    = rows[:MAX_STUDENTS_R2]
    all_answers    = []

    for idx, row in enumerate(target_rows):
        user_prompt = _qa_row_to_prompt(row, questions, revised_que_data)
        try:
            response = openai.ChatCompletion.create(
                model       = 'gpt-4o',
                temperature = 0.3,
                messages    = [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user',   'content': user_prompt},
                ]
            )
            reply = response.choices[0].message['content'].strip()
        except Exception as e:
            print(f'[_qa_run_twins] 第 {idx+1} 筆 OpenAI 失敗：{e}')
            continue

        parts = [p.strip().upper() for p in reply.split(',')]
        if len(parts) == n_questions and all(p in 'ABCD' for p in parts):
            all_answers.append(parts)
            print(f'[_qa_run_twins] 第 {idx+1} 筆：{parts}')
        else:
            print(f'[_qa_run_twins] 第 {idx+1} 筆格式異常（預期 {n_questions} 題，收到 {len(parts)} 個），跳過：{reply}')

    return all_answers, questions


# ──────────────────────────────────────────
# 第二輪：讓孿生班級重新作答修改後的考卷
# ──────────────────────────────────────────
def run_second_round(all_revised: dict):
    send('你已經完成了所有弱題的修改，做得很好！', delay=1)
    send('接下來是最關鍵的一步：', delay=0.5)
    send('讓孿生班級把你的「修題後考卷」再寫一次，驗證修改是否真的讓題目變得更好。', delay=0.5)

    # ── 確認 que_set_log_r2 確實存在 ──
    if not os.path.exists(REVISED_QUE_LOG_PATH):
        send_alert(f'⚠️ que_set_log_r2 不存在（{REVISED_QUE_LOG_PATH}），無法進行第二輪，請通知系統管理員。')
        _write_log(f'[true_ending] run_second_round 中止：que_set_log_r2 不存在 {REVISED_QUE_LOG_PATH}')
        return

    send_button(
        label     = '讓孿生班級再寫一次',
        color     = 'gold',
        size      = 'medium',
        button_id = 'btn_run_second_round',
        delay     = 0.5,
    )

    choice = wait_for_user()
    if choice is None or choice == '__INTERRUPTED__':
        return

    choice_id = choice.split(':')[0] if ':' in choice else choice
    if choice_id != 'btn_run_second_round':
        return

    send('好的！孿生班級正在用修改後的考卷作答中，請稍候……', delay=0.3)
    _thinking(True)

    # ── 讀取修改後的 que_data ──
    revised_que_data = _load_revised_que_data(REVISED_QUE_LOG_PATH)
    if not revised_que_data:
        _thinking(False)
        send_alert(f'⚠️ que_set_log_r2 讀取失敗（{REVISED_QUE_LOG_PATH}），請通知系統管理員。')
        _write_log(f'[true_ending] _load_revised_que_data 回傳空值，流程中止')
        return

    print(f"[run_second_round] revised_que_data 題數：{len(revised_que_data)}")

    # ── 驅動孿生班級作答 ──
    all_answers, questions = _qa_run_twins(revised_que_data)
    _thinking(False)

    if not all_answers:
        send('孿生班級作答失敗，進入結束流程', delay=0.3)
        send(f'課程流程到此完成，{username}，謝謝你的參與！', delay=0.5)

    # ── 儲存作答矩陣 ──
    question_keys = [q['q_key'] for q in questions]
    matrix_path   = _qa_save_answer_matrix(all_answers, question_keys)
    if not matrix_path:
        send_alert('⚠️ 作答矩陣儲存失敗，請通知系統管理員。')
        return

    # ── 推送統計資料到前端 ──
    question_count  = len(all_answers[0]) if all_answers else 0
    correct_answers = ['A'] * question_count
    stats = {}
    for q_idx in range(question_count):
        key    = f'Q{q_idx+1}'
        counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for row in all_answers:
            ans = row[q_idx] if q_idx < len(row) else None
            if ans in counts:
                counts[ans] += 1
        stats[key] = counts

    students = [
        {
            'id':      i + 1,
            'answers': row,
            'score':   sum(1 for qi, a in enumerate(row) if qi < question_count and a == correct_answers[qi]),
        }
        for i, row in enumerate(all_answers)
    ]
    push_data = json.dumps({
        'type':       'answer_matrix',
        'stats':      stats,
        'n_students': len(all_answers),
        'students':   students,
        'correct':    correct_answers,
    }, ensure_ascii=False)
    _post('/push', {
        'text':       f'__DATA__{push_data}',
        'username':   username,
        'session_id': session_id,
        'log_path':   '',
    })

    send(
        f'✅ 孿生班級已完成作答！共生成 {len(all_answers)} 份答案。\n'
        f'__LINK__{matrix_path}||AnswerMatrix_r2.csv',
        delay=0.5,
    )
    _write_log(f'[true_ending] 第二輪作答完成，共 {len(all_answers)} 筆')

    # ── 啟動 te_pd.py ──
    import sys
    import subprocess

    script_dir_abs = os.path.dirname(os.path.abspath(__file__))
    base_args      = [
        '--username',   username,
        '--session_id', session_id,
        '--log_path',   log_path,
        '--que_log',    REVISED_QUE_LOG_PATH,
    ]
    try:
        subprocess.Popen(
            [sys.executable, 'te_pd.py'] + base_args,
            cwd=script_dir_abs,
        )
        print('[run_second_round] 已啟動 te_pd.py')
        _write_log('[true_ending] te_pd.py 已啟動')
    except Exception as e:
        print(f'[run_second_round] 啟動 te_pd.py 失敗：{e}')
        send_alert(f'⚠️ te_pd.py 啟動失敗，請通知系統管理員。\n錯誤訊息：{e}')


# ──────────────────────────────────────────
# 讀取修改版 que_set_log（無時間戳格式）
# ──────────────────────────────────────────
def _load_revised_que_data(revised_que_log_path: str) -> dict:
    result = {}
    try:
        with open(revised_que_log_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f'[_load_revised_que_data] 讀取失敗：{e}')
        return result

    blocks = re.findall(r'\[Q(\d+)_START\](.*?)\[Q\1_END\]', content, re.DOTALL)
    if not blocks:
        print(f'[_load_revised_que_data] 找不到任何題目區塊：{revised_que_log_path}')
        return result

    CN_FIELDS = {
        '題幹', '概念標籤', '關鍵線索',
        '正確答案A', '錯誤選項B', '錯誤選項C', '錯誤選項D',
        '易錯選項1', '易錯選項2', '易錯推測1', '易錯推測2',
    }

    for num_str, block in blocks:
        n      = int(num_str)
        q_data = {}
        for line in block.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r'\[Q\d+\]\s*(.+?)=(.+)', line)
            if m:
                field = m.group(1).strip()
                value = m.group(2).strip()
                if field in CN_FIELDS:
                    q_data[field] = value
        result[n] = q_data

    print(f'[_load_revised_que_data] 讀取 {len(result)} 題')
    return result


if __name__ == '__main__':
    main()