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
CORRECT_ANS  = 'A'  # 每題正確答案固定為 A


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
        for row in rows[2:]:
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



# ──────────────────────────────────────────
# 核對流程
# ──────────────────────────────────────────
def verify_flow(pd_result: dict):
    """三題核對互動流程"""

    all_idx = list(range(N_QUESTIONS))  # [0..7]

    # ── 預先算出正解 ──────────────────────────
    # 核對題 1：鑑別度最低（D 最小）的題目
    lowest_d_idx  = min(all_idx, key=lambda i: pd_result[f'Q{i+1}']['d'])

    # 核對題 2：難度最極端（|p - 0.5| 最大）的題目
    extreme_p_idx = max(all_idx, key=lambda i: abs(pd_result[f'Q{i+1}']['p'] - 0.5))

    focus_q_key = f'Q{lowest_d_idx + 1}'

    # ── 核對題 1 ──────────────────────────────
    send('接下來，我們先做一個「核對」吧～看你算得跟我一不一樣？', delay=0.8)
    send(
        '請選出「你最需要優先修改」的那一題（也就是鑑別度最低的那題）。',
        delay=0.5
    )

    labels_1, ids_1, correct_id_1 = make_question_choices(lowest_d_idx)
    send_buttons(labels_1, button_ids=ids_1, size='small', delay=0.3)

    ans_1 = wait_for_user()
    if is_exit(ans_1):
        return
    ans_1 = parse_btn(ans_1)

    if ans_1 == correct_id_1:
        send('沒錯，我也覺得這題應該先修改，他的鑑別度太低了。', delay=0.5)
        write_log(f'[va_pd] 核對題1 答對，選={ans_1}')
    else:
        d_val = pd_result[focus_q_key]['d']
        send(
            f'根據我的計算，第 {lowest_d_idx + 1} 題的鑑別度更低（D={d_val}），更應該先修改。',
            delay=0.5
        )
        write_log(f'[va_pd] 核對題1 答錯，選={ans_1}，正解={correct_id_1}')

    send_buttons(['下一題'], colors=['blue'], delay=0.5)
    if is_exit(wait_for_user()):
        return

    # ── 核對題 2 ──────────────────────────────
    send(
        '接著，請選出「難度最極端」的那一題（最簡單或最困難都算）。',
        delay=0.5
    )

    labels_2, ids_2, correct_id_2 = make_question_choices(extreme_p_idx)
    send_buttons(labels_2, button_ids=ids_2, size='small', delay=0.3)

    ans_2 = wait_for_user()
    if is_exit(ans_2):
        return
    ans_2 = parse_btn(ans_2)

    if ans_2 == correct_id_2:
        p_val     = pd_result[f'Q{extreme_p_idx+1}']['p']
        direction = '太高' if p_val > 0.5 else '太低'
        send(f'沒錯！這題的難度{direction}了！', delay=0.5)
        write_log(f'[va_pd] 核對題2 答對，選={ans_2}')
    else:
        p_val     = pd_result[f'Q{extreme_p_idx+1}']['p']
        direction = '太簡單' if p_val > 0.5 else '太困難'
        send(
            f'其實第 {extreme_p_idx + 1} 題的難度更極端，來到了 {p_val}，'
            f'這題是更需要修改的。',
            delay=0.5
        )
        write_log(f'[va_pd] 核對題2 答錯，選={ans_2}，正解={correct_id_2}')

    send_buttons(['下一題'], colors=['blue'], delay=0.5)
    if is_exit(wait_for_user()):
        return

    # ── 過渡：進入改題 ────────────────────────
    send(
        '接下來，我們要進入「改題」。\n'
        '而且我會解鎖一個很有用的功能：你可以把孿生學生叫出來，'
        '直接問他為什麼會選那個選項，這樣你改題會快很多。',
        delay=0.8
    )
    send(
        '接下來我們不會把 8 題都拿來改，因為那會浪費力氣。\n'
        '我們只改「真的需要改」的題目（含選項）。',
        delay=0.5
    )

    send_buttons(['開始改題'], colors=['gold'], delay=0.5)
    if is_exit(wait_for_user()):
        return

    write_log('[va_pd] 核對流程完成，進入改題')


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    session_dir = os.path.dirname(log_path) if log_path else '.'
    matrix_path = os.path.join(session_dir, f"{username}_AnswerMatrix.csv")

    send(
        '你已完成 8 題命題，也拿到孿生班級的作答結果了。\n'
        '接下來我們要做「審題」的事情，也就是用數據回頭檢討你每一題的品質。',
        delay=0.5
    )

    send(
        f'我先把原始作答資料準備好了。\n'
        f'__LINK__/download?path={matrix_path}||下載：AnswerMatrix.csv\n'
        f'（30 位孿生學生 × 8 題，每題選了哪個選項）\n'
        f'你先把檔案下載下來，用它來算難度與鑑別度。',
        delay=0.5
    )

    send(
        '先算難度（p 值）：對每一題看 30 個人裡面，有幾個人答對。\n'
        '公式：難度 p = 答對人數 ÷ 30\n'
        '理解方式：p 越接近 1 越簡單；p 越接近 0 越困難。',
        delay=0.5
    )

    send(
        '再算鑑別度（D 值），這一步你只要做兩件事：\n\n'
        'A. 先把 30 個人分成兩群：\n'
        '   先算每個人的總分（0–8），依總分排序後分成兩群：\n'
        '   高分組（分數最高的 8 人）、低分組（分數最低的 8 人）。\n\n'
        'B. 對每一題算「兩群差距」：\n'
        '   鑑別度 D =（高分組答對人數 ÷ 8）−（低分組答對人數 ÷ 8）\n\n'
        '小提醒：因為每群只有 8 人，D 值會以 0.125 為刻度變動，這是正常的。',
        delay=0.5
    )

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

    # 顯示結果
    summary_lines = ['各題難度與鑑別度：\n']
    for q_key, val in pd_result.items():
        summary_lines.append(
            f'{q_key}｜難度 P = {val["p"]:.3f}｜鑑別度 D = {val["d"]:.3f}'
        )
    send('\n'.join(summary_lines), delay=0.3)
    write_log(f'[va_pd] 難度鑑別度計算完成：{pd_result}')

    # 核對流程入口
    send_buttons(['開始核對'], colors=['gold'], delay=0.8)
    btn = wait_for_user()
    if is_exit(btn):
        return

    verify_flow(pd_result)

    # ↓↓↓ 後續流程在此繼續開發 ↓↓↓

    print("[va_pd.py] 執行完畢")


if __name__ == '__main__':
    main()