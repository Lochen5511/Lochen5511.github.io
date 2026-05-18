import argparse
import time
import requests
import os
import csv
from datetime import datetime
from dotenv import load_dotenv

# ──────────────────────────────────────────
# 環境變數 & OpenAI
# ──────────────────────────────────────────
load_dotenv(r"C:\Users\Procidens_Pulvis\Desktop\TxT\website_AI\.env")

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

print(f"[va_pd.py] 啟動  user={username}  session={session_id}")

BACKEND      = 'http://localhost:5000'
USER_TIMEOUT = 300
N_TOTAL      = 30
N_GROUP      = 10
N_QUESTIONS  = 8
CORRECT_ANS  = '1'


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

def is_exit(val) -> bool:
    return val is None or val == '__INTERRUPTED__'

def parse_btn(val: str) -> str:
    return val.split(':')[0] if val and ':' in val else val

def write_log(content: str):
    if not log_path:
        return
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {content}\n")
    except Exception as e:
        print(f"[log 寫入失敗] {e}")

def send(text, delay=0):
    if delay > 0:
        _thinking(True)
        time.sleep(delay)
        _thinking(False)
    _post('/push', {
        'text': text, 'username': username,
        'session_id': session_id, 'log_path': log_path,
    })
    print(f"[send] {text[:80]}")

def send_buttons(labels, delay=0, colors=None, size='medium',
                 sizes=None, button_ids=None):
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
        'text': f'__BUTTONS__{parts}', 'username': username,
        'session_id': session_id, 'log_path': '',
    })
    _lock(True)
    print(f"[buttons] {labels}")

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
            _lock(False)
            return '__INTERRUPTED__'

        online = _get('/check_online', {'session_id': session_id, 'timeout': timeout})
        if not online.get('online', True):
            write_log('用戶已離開系統')
            _lock(False)
            return None

        time.sleep(interval)


# ──────────────────────────────────────────
# 讀取 AnswerMatrix
# ──────────────────────────────────────────
def load_answer_matrix() -> list:
    session_dir = os.path.dirname(log_path) if log_path else '.'
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")

    if not os.path.exists(matrix_path):
        print(f"[va_pd] AnswerMatrix 不存在：{matrix_path}")
        return []

    answers = []
    try:
        with open(matrix_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows   = list(reader)

        for row in rows[1:]:
            if len(row) >= N_QUESTIONS:
                answers.append(row[:N_QUESTIONS])
    except Exception as e:
        print(f"[va_pd] AnswerMatrix 讀取失敗：{e}")

    print(f"[va_pd] 讀取 {len(answers)} 筆學生作答")
    return answers


# ──────────────────────────────────────────
# 計算難度與鑑別度
# ──────────────────────────────────────────
def calc_pd(answers: list) -> dict:
    n = len(answers)
    if n == 0:
        return {}

    scores = []
    for row in answers:
        score = sum(1 for ans in row if ans == CORRECT_ANS)
        scores.append(score)

    indexed      = sorted(enumerate(scores), key=lambda x: x[1])
    low_indices  = [i for i, _ in indexed[:N_GROUP]]
    high_indices = [i for i, _ in indexed[-N_GROUP:]]

    result = {}
    for q_idx in range(N_QUESTIONS):
        q_key = f'Q{q_idx + 1}'

        correct_count = sum(1 for row in answers if row[q_idx] == CORRECT_ANS)
        p = round(correct_count / n, 3)

        high_correct = sum(1 for i in high_indices if answers[i][q_idx] == CORRECT_ANS)
        low_correct  = sum(1 for i in low_indices  if answers[i][q_idx] == CORRECT_ANS)
        d = round(high_correct / N_GROUP - low_correct / N_GROUP, 3)

        result[q_key] = {
            'p':       p,
            'd':       d,
            'correct': correct_count,
        }

    return result


# ──────────────────────────────────────────
# 寄送 email
# ──────────────────────────────────────────
def _send_result_email(to_addr, username, return_id, pd_result, user_pd_results):
    """
    寄送難度鑑別度結果至學生信箱。
    user_pd_results: dict，格式 {'Q1': {'user_p': ..., 'user_d': ..., 'correct': bool}, ...}
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.header import Header

    TAMAIL   = os.getenv('TAMAIL')
    MAILPASS = os.getenv('MAILPASS')

    if not TAMAIL or not MAILPASS:
        print("[email] 缺少 TAMAIL 或 MAILPASS，無法寄信")
        write_log('[EMAIL] 寄送失敗：缺少 TAMAIL 或 MAILPASS')
        return False

    def d_label(d):
        if d >= 0.4:    return '優異'
        elif d >= 0.25: return '正常'
        else:           return '待加強'

    table_lines = ['題目 | 難度 P | 鑑別度 D | 評價 | 你計算的p,D值 | p,D計算是否正確']
    table_lines.append('-' * 60)
    for q_key, val in pd_result.items():
        ur      = user_pd_results.get(q_key, {})
        user_p  = ur.get('user_p', '—')
        user_d  = ur.get('user_d', '—')
        correct = '✓' if ur.get('correct', False) else '✗'
        table_lines.append(
            f"{q_key}   | {val['p']}   | {val['d']}   | {d_label(val['d'])} "
            f"| ({user_p},{user_d}) | {correct}"
        )
    table_str = '\n'.join(table_lines)

    subject = '孿生AI出題測試結果'
    body = (
        f'{username} 你好，\n\n'
        f'以下是你出題的難度與鑑別度分析結果，以及你的作答紀錄：\n\n'
        f'{table_str}\n\n'
        f'你的下次學習代碼為：{return_id}\n'
        f'下次登入時，請於登入介面輸入此代碼進入下一階段。'
    )

    msg = MIMEMultipart()
    msg['From']    = f'塔伯特 <{TAMAIL}>'
    msg['To']      = to_addr
    msg['Subject'] = Header(subject, 'utf-8').encode()
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        smtp = smtplib.SMTP('smtp.gmail.com', 587)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(TAMAIL, MAILPASS)
        smtp.sendmail(TAMAIL, to_addr, msg.as_string())
        smtp.quit()
        print(f"[email] 已寄送至 {to_addr}")
        write_log(f'[EMAIL] 寄送成功 → {to_addr}')
        return True
    except Exception as e:
        print(f"[email 寄送失敗] {e}")
        write_log(f'[EMAIL] 寄送失敗：{e}')
        return False


# ──────────────────────────────────────────
# 解析 (p,d) 輸入
# ──────────────────────────────────────────
def parse_pd_input(text: str):
    t = text.strip()
    if not (t.startswith('(') and t.endswith(')')):
        return None
    inner = t[1:-1]
    parts = inner.split(',')
    if len(parts) != 2:
        return None
    return (parts[0], parts[1])


# ──────────────────────────────────────────
# 表格對齊工具
# ──────────────────────────────────────────
def _is_wide(c: str) -> bool:
    """判斷字元是否為全形（佔兩個半形寬度）"""
    cp = ord(c)
    return (
        0x1100 <= cp <= 0x115F or   # Hangul Jamo
        0x2E80 <= cp <= 0x303E or   # CJK Radicals / Kangxi
        0x3041 <= cp <= 0x33BF or   # Hiragana, Katakana, Bopomofo, CJK Compat
        0x33FF <= cp <= 0xA4CF or   # CJK Unified Ideographs Extension
        0xA960 <= cp <= 0xA97F or   # Hangul Jamo Extended-A
        0xAC00 <= cp <= 0xD7FF or   # Hangul Syllables + Jamo Extended-B
        0xF900 <= cp <= 0xFAFF or   # CJK Compatibility Ideographs
        0xFE10 <= cp <= 0xFE1F or   # Vertical Forms
        0xFE30 <= cp <= 0xFE6F or   # CJK Compatibility Forms / Small Forms
        0xFF01 <= cp <= 0xFF60 or   # Fullwidth Latin / Halfwidth Katakana
        0xFFE0 <= cp <= 0xFFE6 or   # Fullwidth Signs
        0x1B000 <= cp <= 0x1B0FF or # Kana Supplement
        0x1F004 <= cp <= 0x1F0CF or # Mahjong / Playing Cards
        0x1F200 <= cp <= 0x1F2FF or # Enclosed CJK Letters Supplement
        0x20000 <= cp <= 0x2FFFD or # CJK Unified Ideographs Extension B-F
        0x30000 <= cp <= 0x3FFFD    # CJK Unified Ideographs Extension G+
    )

def display_width(s: str) -> int:
    """計算字串的顯示寬度（全形字算2個半形）"""
    return sum(2 if _is_wide(c) else 1 for c in str(s))

def pad_to(val_str: str, max_len: int) -> str:
    """在字串右側補空格至 max_len 個半形字元寬"""
    s = str(val_str)
    return s + ' ' * max(0, max_len - display_width(s))

def _col(text, width):
    """填滿至指定半形寬度（相容舊介面）"""
    return pad_to(str(text), width)


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    session_dir = os.path.dirname(log_path) if log_path else '.'
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")

    send(
        '你已完成 8 題命題，接下來你可以下載上面的作答分數記錄，或是點擊右邊的頁籤檢視詳細資料。\n'
        '接下來我們要來「審題」，也就是用數據確認你每一題的品質。',
        delay=0.5
    )

    send(
        '待會，我們先算難度（p 值）：\n'
        '公式：難度 p = 答對人數 ÷ 30，p 越接近 1 越簡單；p 越接近 0 越困難。',
        delay=0.5
    )

    send(
        '然後再算鑑別度（D 值）：\n'
        'A. 分高低分組（各 10 人）\n'
        'B. D =（高分組答對人數 ÷ 10）−（低分組答對人數 ÷ 10）\n',
        delay=0.5
    )

    send('先從第一題開始吧。', delay=0.5)

    answers = load_answer_matrix()
    if not answers:
        send('（無法讀取作答資料，請聯絡助教。）', delay=0.5)
        return

    _thinking(True)
    time.sleep(1)
    _thinking(False)
    pd_result = calc_pd(answers)
    write_log(f'[va_pd] 難度鑑別度計算完成：{pd_result}')

    # ── 逐題驗證，同時記錄學生作答 ──────────────
    user_pd_results = {}   # {'Q1': {'user_p': ..., 'user_d': ..., 'correct': bool}, ...}

    for q_idx in range(N_QUESTIONS):
        q_num = q_idx + 1
        q_key = f'Q{q_num}'
        correct_p = pd_result[q_key]['p']
        correct_d = pd_result[q_key]['d']

        if q_idx == 0:
            send(
                f'你算出的第 {q_num} 題的(難度,鑑別度)是多少？\n'
                f'用半形的括弧和逗點發送給我（例如，(1,0)），最多只計算到小數點後第三位，不需要加入空格，也不要用全形的標點符號，'
                f'不然會視同錯誤',
                delay=0.5
            )
        else:
            send(f'你算出的第 {q_num} 題的(難度,鑑別度)是多少？', delay=0.5)

        _lock(False)
        user_input = wait_for_user()
        if is_exit(user_input):
            return

        parsed       = parse_pd_input(user_input)
        user_correct = False
        user_p_val   = '—'
        user_d_val   = '—'

        if parsed:
            user_p_val = parsed[0]
            user_d_val = parsed[1]
            try:
                user_p = round(float(parsed[0]), 3)
                user_d = round(float(parsed[1]), 3)
                user_correct = (user_p == correct_p and user_d == correct_d)
            except ValueError:
                pass

        user_pd_results[q_key] = {
            'user_p':  user_p_val,
            'user_d':  user_d_val,
            'correct': user_correct,
        }

        if user_correct:
            send(f'第 {q_num} 題答對了！', delay=0.3)
            write_log(f'[va_pd] 第{q_num}題 用戶答對，輸入={user_input}')
        else:
            send(
                f'第 {q_num} 題答錯了。\n'
                f'正確答案是 ({correct_p},{correct_d})（難度 p={correct_p}，鑑別度 D={correct_d}）。',
                delay=0.3
            )
            write_log(f'[va_pd] 第{q_num}題 用戶答錯，輸入={user_input}，正解=({correct_p},{correct_d})')

    # ── 發送難度鑑別度總表（HTML 版）──────────────
    def d_label(d):
        if d >= 0.4:    return '優異'
        elif d >= 0.25: return '正常'
        else:           return '待加強'

    # 深色介面配色
    LABEL_COLOR = {
        '優異':   ('rgba(106,191,105,0.18)', '#6abf69'),
        '正常':   ('rgba(106,170,191,0.18)', '#6aaabf'),
        '待加強': ('rgba(201,168,76,0.18)',  '#c9a84c'),
    }

    TD  = 'padding:7px 12px;border:1px solid rgba(201,168,76,0.25);color:#f8f4ec;'
    TDC = TD + 'text-align:center;'

    rows_html = []
    for q_key, val in pd_result.items():
        ur         = user_pd_results.get(q_key, {})
        user_p     = ur.get('user_p', '—')
        user_d     = ur.get('user_d', '—')
        is_correct = ur.get('correct', False)
        label      = d_label(val['d'])
        bg, fg     = LABEL_COLOR.get(label, ('rgba(255,255,255,0.08)', '#f8f4ec'))
        ok_symbol  = '✓' if is_correct else '✗'
        ok_color   = '#6abf69' if is_correct else '#bf6a6a'
        ok_bg      = 'rgba(106,191,105,0.18)' if is_correct else 'rgba(191,106,106,0.18)'
        # 合併後的顯示字串：(p,d) 答對→綠底✓，答錯→紅底✗ + 正確答案
        st = f'background:{ok_bg};color:{ok_color};padding:2px 8px;border-radius:4px;'
        symbol = '✓' if is_correct else '✗'
        ans_span = f'<span style="{st}">({user_p},{user_d}) {symbol}</span>'
        if is_correct:
            merged_inner = ans_span
        else:
            hint_st = 'font-size:11px;color:rgba(248,244,236,0.5);'
            correct_hint = f'<br><span style="{hint_st}">答案：({val["p"]},{val["d"]})</span>'
            merged_inner = ans_span + correct_hint
        rows_html.append(
            f'<tr>'
            f'<td style="{TD}">{q_key}</td>'
            f'<td style="{TD}">{val["p"]}</td>'
            f'<td style="{TD}">{val["d"]}</td>'
            f'<td style="{TD}">'
            f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:4px;font-size:13px;">{label}</span>'
            f'</td>'
            f'<td style="{TDC}padding:6px 12px;">{merged_inner}</td>'
            f'</tr>'
        )

    TH  = 'padding:8px 12px;border:1px solid rgba(201,168,76,0.35);background:rgba(201,168,76,0.1);color:#c9a84c;text-align:left;font-weight:400;letter-spacing:0.05em;'
    THC = TH + 'text-align:center;'
    html = (
        '__HTML__'
        '<p style="margin:0 0 10px;color:#c9a84c;letter-spacing:0.1em;font-size:14px;">各題難度與鑑別度總覽：</p>'
        '<table style="border-collapse:collapse;width:100%;font-size:14px;font-family:Noto Serif TC,serif;">'
        '<thead><tr>'
        f'<th style="{TH}">題目</th>'
        f'<th style="{TH}">難度P</th>'
        f'<th style="{TH}">鑑別度D</th>'
        f'<th style="{TH}">評價</th>'
        f'<th style="{THC}">p,D值計算與批改</th>'
        '</tr></thead>'
        '<tbody>' + ''.join(rows_html) + '</tbody>'
        '</table>'
    )

    send(html, delay=0.5)
    write_log('[va_pd] 發送難度鑑別度總表（HTML，含學生作答）')

    for q_key, ur in user_pd_results.items():
        write_log(
            f'[va_pd] {q_key} 作答=({ur["user_p"]},{ur["user_d"]}) '
            f'正確={ur["correct"]}'
        )

    # ── 產生 Return ID ────────────────────────
    rid = None
    try:
        res = requests.post(f'{BACKEND}/generate_return_id',
                            json={'session_id': session_id}, timeout=5)
        rid = res.json().get('return_id')
    except Exception as e:
        print(f"[va_pd] 產生 Return ID 失敗：{e}")

    if rid:
        send(
            f'你的學習 ID 是：{rid}\n'
            f'請記下這組 ID，下次課程可以用它繼續學習。',
            delay=0.5
        )
        write_log(f'[va_pd] Return ID 已產生：{rid}')
    else:
        send('（Return ID 產生失敗，請聯絡助教。）', delay=0.5)

    # ── 更新 unit 為「出題」────────────────────
    try:
        requests.post(f'{BACKEND}/update_unit',
                      json={'session_id': session_id, 'unit': '出題'}, timeout=5)
        write_log('[va_pd] unit 已更新為「出題」')
        print(f"[va_pd] unit 已更新為「出題」session={session_id}")
    except Exception as e:
        print(f"[va_pd] 更新 unit 失敗：{e}")

    # ── 收集 email 並寄送結果 ──────────────────
    while True:
        send(
            '請輸入完整信箱，'
            '我會把代碼和結果寄送到你的信箱！',
            delay=0.5
        )

        email_reply = wait_for_user()
        if is_exit(email_reply):
            return

        student_email = email_reply.strip()

        send(f'確定信箱無誤嗎？\n{student_email}', delay=0.3)
        send_buttons(
            labels     = ['正確無誤', '需要修改'],
            colors     = ['green', 'gray'],
            size       = 'medium',
            button_ids = ['btn_email_ok', 'btn_email_edit']
        )

        confirm = wait_for_user()
        if is_exit(confirm):
            return

        confirm_id = parse_btn(confirm)
        if confirm_id == 'btn_email_ok':
            write_log(f'[EMAIL] 學生確認信箱：{student_email}')
            break

    success = _send_result_email(
        to_addr         = student_email,
        username        = username,
        return_id       = rid or '',
        pd_result       = pd_result,
        user_pd_results = user_pd_results,
    )

    if success:
        send('已寄出！請記得檢查你的信箱（包含垃圾郵件匣）。', delay=0.5)
    else:
        send('郵件寄送失敗，請手動記錄代碼後再關閉此介面。', delay=0.5)

    send_buttons(
        labels     = ['回到上一頁'],
        colors     = ['gold'],
        size       = 'medium',
        button_ids = ['btn_goto_enter']
    )

    print("[va_pd.py] 執行完畢")


if __name__ == '__main__':
    main()