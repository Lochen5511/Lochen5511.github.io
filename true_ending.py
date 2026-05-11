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
BACKEND = 'http://localhost:5000'

load_dotenv(r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\.env")
openai.api_key = os.getenv("AIKEY")


print(f"[true_ending.py] 啟動  user={username}  session={session_id}")

# ──────────────────────────────────────────
# 路徑設定
# ──────────────────────────────────────────
# 從 log_path 反推舊 session_id 與題庫路徑
session_dir     = os.path.dirname(log_path)
old_folder_name = os.path.basename(session_dir)
old_session_id  = old_folder_name.replace(f"{username}_", "", 1)

pd_txt_path  = log_path
que_log_path = os.path.join(session_dir, f"{old_session_id}_que_set_log.txt")

print(f"[true_ending] PD 報告路徑：{pd_txt_path}")
print(f"[true_ending] 題庫路徑：  {que_log_path}")

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
    """發送一個可點擊的按鈕，並鎖定聊天框"""
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
    _lock(True)
    print(f"[buttons] {labels}")


# ──────────────────────────────────────────
# wait_for_user：等待用戶回應
# ──────────────────────────────────────────
def wait_for_user(interval: float = 0.5, timeout: int = 300, wait_limit: int = None) -> str | None:
    """
    等待用戶回應。
    timeout   : 無 /poll 超過此秒數視為離線，回傳 None
    wait_limit: 等待作答的上限秒數（不管是否在線），超過回傳 None
    注意：check_online 依賴前端 poll 更新 last_seen，
          因此前幾秒不做離線判斷，避免 last_seen 尚未建立就誤判離線。
    """
    import time as _time
    start = _time.time()
    ONLINE_CHECK_DELAY = 10  # 啟動後前 10 秒不做離線判斷

    while True:
        elapsed = _time.time() - start

        if wait_limit and elapsed > wait_limit:
            print(f"[wait_for_user] 等待超時 wait_limit={wait_limit}s")
            _write_log(f'[逾時] 等待作答超過 {wait_limit} 秒，流程中斷')
            _lock(False)
            return None

        # 優先取用戶輸入，減少延遲
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

        # 前 ONLINE_CHECK_DELAY 秒內不判斷離線，等待前端 poll 建立 last_seen
        if elapsed >= ONLINE_CHECK_DELAY:
            online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
            if not online.get('online', True):
                print(f"[wait_for_user] 用戶已離開 session={session_id}")
                _write_log('用戶已離開系統')
                _lock(False)
                return None

        time.sleep(interval)


def _write_log(content: str):
    """寫入後端結構化 log（含時間戳記）"""
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def update_unit(unit: str):
    """更新 session 庫中的單元記錄"""
    _post('/update_unit', {'session_id': session_id, 'unit': unit})
    print(f"[unit] 記錄單元={unit}")

def _lock(locked: bool):
    """鎖定或解鎖聊天框"""
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
    """
    讀取 AnswerMatrix.csv，回傳每列作答清單
    每列格式：['1', '0', '1', ...] 共 8 欄
    """
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")
    if not os.path.exists(matrix_path):
        print(f"[true_ending] AnswerMatrix 不存在：{matrix_path}")
        return []
    try:
        with open(matrix_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows   = list(reader)
        # 跳過標題行
        return [row for row in rows[1:] if row]
    except Exception as e:
        print(f"[true_ending] AnswerMatrix 讀取失敗：{e}")
        return []


def load_validity_wide_table() -> list:
    """
    讀取 logs 資料夾中的 validity_wide_table.csv
    回傳所有列的 dict 清單
    """
    logs_dir   = os.path.dirname(session_dir)   # session_dir 的上層即 logs 資料夾
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


def pick_student(answers: list, q_idx: int, target: str) -> dict | None:
    """
    回傳格式：
    {
        'row_index':             5,
        'admin_session_id':      'xxx',
        'accuracy':              '0.75',
        'avg_confidence':        '0.8',
        'low_conf_ratio':        '0.2',
        'high_conf_wrong_ratio': '0.1',
        'V1a': '0', 'V1b': '0', 'V1c': '1',
        'V2a': '0', 'V2b': '0', 'X1':  '0',
        'V3a': '1', 'V3b': '0',
    }
    或 None（找不到）
    """
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
        '你答對了這題，回答時必須展現出正確的理解。'
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
    """
    完整問答環節：發送問題選單 → 取得用戶選擇 → 呼叫AI → 發送回應
    label: '答錯' 或 '答對'（用於顯示）
    """
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

    # 解析按鈕 id
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
# 讀取 PD 報告，回傳 dict
# {'Q1': {'p': 0.7, 'd': 0.9, 'label': '優異'}, ...}
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

    # 跳過標題行與分隔線，解析資料行
    # 格式：Q1　｜0.7　｜0.9　｜優異
    for line in lines:
        line = line.strip()
        if not line or line.startswith('題目') or line.startswith('─'):
            continue

        parts = [p.strip() for p in line.split('｜')]
        if len(parts) < 4:
            continue

        q_key = parts[0].replace('\u3000', '').replace(' ', '')  # 去除全形空格
        try:
            p_val = float(parts[1])
            d_val = float(parts[2])
        except ValueError:
            continue

        label = parts[3]
        result[q_key] = {'p': p_val, 'd': d_val, 'label': label}

    print(f"[true_ending] 讀取 PD 報告：{len(result)} 題")
    return result


# ──────────────────────────────────────────
# 讀取題庫 log，回傳 dict
# {'Q1': {'stem': ..., 'correct': ..., 'options': {...}, ...}, ...}
# ──────────────────────────────────────────
def load_que_log(path: str) -> dict:
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

    # 以 [QN_START] ... [QN_END] 切割每題區塊
    blocks = re.findall(r'\[Q(\d+)_START\](.*?)\[Q\1_END\]', content, re.DOTALL)

    for num_str, block in blocks:
        q_key  = f'Q{num_str}'
        q_data = {}

        for line in block.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            # 格式：[QN] 欄位名=值
            m = re.match(r'\[Q\d+\]\s*(.+?)=(.+)', line)
            if not m:
                continue

            field = m.group(1).strip()
            value = m.group(2).strip()

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

            key = field_map.get(field)
            if key:
                q_data[key] = value

        result[q_key] = q_data

    print(f"[true_ending] 讀取題庫：{len(result)} 題")
    return result


# ──────────────────────────────────────────
# 篩選 D < 0.25 的題目，對照題庫合併資訊
# ──────────────────────────────────────────
def find_weak_questions(pd_data: dict, que_data: dict, threshold=0.25) -> list:
    """
    回傳清單，每筆為 dict：
    {
        'q_key':          'Q2',
        'p':              1.0,
        'd':              0.0,
        'label':          '待加強',
        'concept':        '表面效度',
        'stem':           '某學生看到…',
        'correct':        '表面效度',
        'opt_b':          '內容效度',
        'opt_c':          '建構效度',
        'opt_d':          '效標關聯效度',
        'distractor_1':   'B. 內容效度',
        'distractor_2':   'C. 建構效度',
        'misconception_1':'將直覺合理誤當內容代表性（V1a）',
        'misconception_2':'將外觀合理誤當構念驗證（V3a）',
        'clues':          '看起來合理、直覺判斷',
    }
    """
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
            # 合併題庫資訊（若題庫有該題）
            entry.update(que_data.get(q_key, {}))
            weak.append(entry)

    return weak


# ──────────────────────────────────────────
# 主程式（目前僅做讀取與印出，供後續開發驗證）
# ──────────────────────────────────────────
def main():
    pd_data  = load_pd_report(pd_txt_path)
    que_data = load_que_log(que_log_path)
    weak     = find_weak_questions(pd_data, que_data)

    send(f'歡迎回來，{username}！我是艾評。', delay=1)
    send('上次課程中，我們已經完成了鑑別度的計算。', delay=0.5)
    send('今天，我們就要一起對鑑別度較低的題目進行修改。', delay=0.5)
    send('先來回顧一下上次的紀錄吧！', delay=0.5)
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
    send('接下來，我們要開始修改鑑別度未達標的題目。\n你可以從列表中選擇你想先改的題目：', delay=0.5)

    weak_options = [f"{q['q_key']}｜{q.get('concept', '未知概念')}｜D={q['d']}" for q in weak]
    send_dropdown(
        options      = weak_options,
        placeholder  = '請選擇想修改的題目…',
        dropdown_id  = 'select_weak_q',
        delay        = 0.3,
    )
    remaining_weak = weak.copy()
    
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

        # 從回傳字串解析題號，例如 'Q6｜信度與效度關係｜D=0.0'
        match = _re.match(r'(Q\d+)', user_input.strip())
        if not match:
            send('請從列表中選擇題目。', delay=0.3)
            continue

        selected_key = match.group(1)
        selected_q   = next((q for q in remaining_weak if q['q_key'] == selected_key), None)
        if not selected_q:
            send('請從列表中選擇題目。', delay=0.3)
            continue

        # 從清單移除
        remaining_weak = [q for q in remaining_weak if q['q_key'] != selected_key]

        # ── 發送問題診斷選單 ──
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

        # ── 讀取作答矩陣 ──
        answers   = load_answer_matrix(session_dir, username)
        q_idx     = int(selected_key.replace('Q', '')) - 1   # Q6 → 5

        wrong_idx,  wrong_wide  = pick_student(answers, q_idx, target='0')
        correct_idx, correct_wide = pick_student(answers, q_idx, target='1')

        wrong_student   = pick_student(answers, q_idx, target='0')
        correct_student = pick_student(answers, q_idx, target='1')

        print(f"[true_ending] 答錯學生：{wrong_student}")
        print(f"[true_ending] 答對學生：{correct_student}")
        
        # ── 讀取作答矩陣 ──
        answers = load_answer_matrix(session_dir, username)
        q_idx   = int(selected_key.replace('Q', '')) - 1
        q_info  = selected_q  # 已包含題庫資訊

        wrong_student   = pick_student(answers, q_idx, target='0')
        correct_student = pick_student(answers, q_idx, target='1')

        if wrong_student:
            wrong_student['_target'] = '0'
        if correct_student:
            correct_student['_target'] = '1'

        # ── 組合可用按鈕 ──
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

        has_both = len(btn_labels) == 2
        interviewed = set()  # 記錄已問過的學生

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

        # ── 召喚另一個學生 ──
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

if __name__ == '__main__':
    main()