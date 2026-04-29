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
N_TOTAL      = 30   # 模擬學生總數
N_GROUP      = 8    # 高低分組人數
N_QUESTIONS  = 8    # 題目數
CORRECT_ANS  = '1'  # AnswerMatrix 中 A=1, BCD=0


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
    """前端按鈕回傳格式為 'ID:label'，取冒號前的 ID。"""
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
    """
    讀取 AnswerMatrix.csv，回傳每個學生的作答列表（不含標題列和正確答案列）。
    """
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

        # 第一列：標題（Q1~Q8, 總分）
        # 第二列：正確答案
        # 第三列起：學生作答
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
    """
    計算每題的難度（P）與鑑別度（D）。
    回傳格式：{
        'Q1': {'p': 0.8, 'd': 0.5, 'correct': 24},
        ...
    }
    """
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
# 生成四選一按鈕選項（含正解與干擾）
# ──────────────────────────────────────────
def make_question_choices(correct_q_idx: int) -> tuple:
    """
    顯示全部 8 題，回傳 (labels, button_ids, correct_button_id)。
    """
    labels     = [f'第 {q + 1} 題' for q in range(N_QUESTIONS)]
    button_ids = [f'Q{q + 1}'      for q in range(N_QUESTIONS)]
    correct_id = f'Q{correct_q_idx + 1}'

    return labels, button_ids, correct_id



def _send_result_email(to_addr, username, return_id, pd_result):
    """寄送難度鑑別度結果至學生信箱"""
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
        if d >= 0.4:   return '優異'
        elif d >= 0.25: return '正常'
        else:           return '待加強'

    table_lines = ['題目 | 難度 P | 鑑別度 D | 評價']
    table_lines.append('-' * 32)
    for q_key, val in pd_result.items():
        table_lines.append(
            f"{q_key}   | {val['p']}   | {val['d']}   | {d_label(val['d'])}"
        )
    table_str = '\n'.join(table_lines)

    subject = '孿生AI出題測試結果'
    body = (
        f'{username} 你好，\n\n'
        f'以下是你出題的難度與鑑別度分析結果：\n\n'
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
# 主要執行區塊
# ──────────────────────────────────────────
def parse_pd_input(text: str):
    """
    解析用戶輸入的 (p,d) 格式。
    成功回傳 (p_str, d_str)，失敗回傳 None。
    只接受半形括弧、半形逗點、無空格。
    """
    t = text.strip()
    if not (t.startswith('(') and t.endswith(')')):
        return None
    inner = t[1:-1]
    parts = inner.split(',')
    if len(parts) != 2:
        return None
    return (parts[0], parts[1])


def main():
    session_dir = os.path.dirname(log_path) if log_path else '.'
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")

    send(
        '你已完成 8 題命題，也拿到孿生班級的作答結果了。\n'
        '接下來我們要做「審題」的事情，也就是用數據回頭檢討你每一題的品質。',
        delay=0.5
    )

    send(
        '待會，我們先算難度（p 值）：\n'
        '公式：難度 p = 答對人數 ÷ 30，p 越接近 1 越簡單；p 越接近 0 越困難。',
        delay=0.5
    )

    send(
        '然後再算鑑別度（D 值）：\n'
        'A. 分高低分組（各 8 人）\n'
        'B. D =（高分組答對人數 ÷ 8）−（低分組答對人數 ÷ 8）\n'
        'D 值以 0.125 為刻度變動，這是正常的。',
        delay=0.5
    )

    send('先從第一題開始吧。', delay=0.5)

    # 讀取 AnswerMatrix
    answers = load_answer_matrix()
    if not answers:
        send('（無法讀取作答資料，請聯絡助教。）', delay=0.5)
        return

    # 計算難度與鑑別度
    _thinking(True)
    time.sleep(1)
    _thinking(False)
    pd_result = calc_pd(answers)
    write_log(f'[va_pd] 難度鑑別度計算完成：{pd_result}')

    # ── 逐題驗證 ──────────────────────────────
    for q_idx in range(N_QUESTIONS):
        q_num = q_idx + 1
        q_key = f'Q{q_num}'
        correct_p = pd_result[q_key]['p']
        correct_d = pd_result[q_key]['d']

        if q_idx == 0:
            send(
                f'你算出的第 {q_num} 題的(難度,鑑別度)是多少？\n'
                f'用半形的括弧和逗點發送給我，只計算到小數點後第三位，不需要加入空格，也不要用全形的標點符號，'
                f'不然會視同錯誤',
                delay=0.5
            )
        else:
            send(f'你算出的第 {q_num} 題的(難度,鑑別度)是多少？', delay=0.5)

        _lock(False)
        user_input = wait_for_user()
        if is_exit(user_input):
            return

        parsed = parse_pd_input(user_input)
        user_correct = False
        if parsed:
            try:
                user_p = float(parsed[0])
                user_d = float(parsed[1])
                user_correct = (user_p == correct_p and user_d == correct_d)
            except ValueError:
                pass

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

    # ── 發送難度鑑別度總表 ────────────────────
    def d_label(d):
        if d >= 0.4:
            return '優異'
        elif d >= 0.25:
            return '正常'
        else:
            return '待加強'

    table_lines = ['各題難度與鑑別度總覽：\n']
    table_lines.append('題目｜難度 P｜鑑別度 D｜評價')
    table_lines.append('─' * 28)
    for q_key, val in pd_result.items():
        label = d_label(val['d'])
        table_lines.append(
            f'{q_key}　｜{val["p"]}　｜{val["d"]}　｜{label}'
        )
    send('\n'.join(table_lines), delay=0.5)
    write_log('[va_pd] 發送難度鑑別度總表')

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
        to_addr   = student_email,
        username  = username,
        return_id = rid or '',
        pd_result = pd_result,
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

    # ── 更新 unit 為「出題」────────────────────
    try:
        requests.post(f'{BACKEND}/update_unit',
                      json={'session_id': session_id, 'unit': '出題'}, timeout=5)
        write_log('[va_pd] unit 已更新為「出題」')
        print(f"[va_pd] unit 已更新為「出題」session={session_id}")
    except Exception as e:
        print(f"[va_pd] 更新 unit 失敗：{e}")

    print("[va_pd.py] 執行完畢")


if __name__ == '__main__':
    main()