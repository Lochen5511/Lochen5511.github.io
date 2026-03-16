import argparse
import time
import requests
import os
from datetime import datetime

# ──────────────────────────────────────────
# 接收來自 button.py 的變數
# ──────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--username',   default='未知')
parser.add_argument('--session_id', default='')
parser.add_argument('--log_path',   default='')
args = parser.parse_args()

username   = args.username
session_id = args.session_id
log_path   = args.log_path


# ──────────────────────────────────────────
# 工具函數
# ──────────────────────────────────────────
def _set_thinking(state):
    try:
        requests.post('http://localhost:5000/thinking', json={
            'username': username, 'session_id': session_id, 'thinking': state})
    except: pass

def send(text, delay=0):
    if delay > 0:
        _set_thinking(True); time.sleep(delay); _set_thinking(False)
    try:
        requests.post('http://localhost:5000/push', json={
            'text': text, 'username': username,
            'session_id': session_id, 'log_path': log_path})
    except Exception as e:
        print(f"[送出失敗] {e}")

def send_buttons(labels, delay=0, colors=None, sizes=None, size='medium', button_ids=None):
    if delay > 0:
        _set_thinking(True); time.sleep(delay); _set_thinking(False)
    n = len(labels)
    colors     = colors     or ['gold'] * n
    button_ids = button_ids or labels
    size_list  = sizes if sizes else [size] * n
    parts = ';'.join(
        f'{labels[i]}||{colors[i]}||{size_list[i]}||{button_ids[i]}'
        for i in range(n)
    )
    try:
        requests.post('http://localhost:5000/push', json={
            'text': f'__BUTTONS__{parts}', 'username': username,
            'session_id': session_id, 'log_path': ''})
    except Exception as e:
        print(f"[多按鈕失敗] {e}")

def wait_for_user(interval=0.5):
    while True:
        try:
            res = requests.get('http://localhost:5000/fetch_user_input',
                               params={'session_id': session_id})
            data = res.json()
            if data.get('message'):
                return data['message']
        except: pass
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
# 題庫（出題順序：V1_GATE→V2_1→V2_2→V1_1→VX_1→V1_2→V3_1→V3_2）
# ──────────────────────────────────────────
QUESTIONS = [
    {
        'item_id': 'V1_GATE',
        'stem': (
            '某位老師要為「國小五年級自然科單元測驗」命題。'
            '她先把本單元的學習目標拆成幾個重點概念，並製作雙向細目表，'
            '確保題目比例能覆蓋所有教學重點。命題完成後，她請同年段兩位自然科老師逐題審查，'
            '確認題幹與選項是否符合教學目標、是否有偏題或遺漏。\n'
            '請問上述做法最主要是在支持哪一種「效度證據」？'
        ),
        'options': {
            'A': '表面效度：因為題目看起來像自然科題目，外觀合理即可',
            'B': '內容效度：因為題目內容與教學目標、內容範圍的對應性被系統性檢核',
            'C': '預測效度：因為這樣做可以讓分數更能預測學生下學期表現',
            'D': '信度就等於效度：只要 Cronbach\'s alpha 很高，效度自然就高',
        },
        'key': 'B',
        'option_to_code': {'A': 'V1a', 'B': None, 'C': 'V1b', 'D': 'V1c'},
    },
    {
        'item_id': 'V2_1',
        'stem': (
            '某研究者自編一份「國中閱讀理解測驗」，想檢查它是否能在同一個時間點反映學生的閱讀理解能力。'
            '他讓同一批學生在同一週內同時完成：(1) 自編測驗；(2) 一份標準化閱讀測驗。'
            '結果發現兩份測驗分數相關很高。\n'
            '這種蒐集證據的做法，最主要是在檢驗哪一種效度？'
        ),
        'options': {
            'A': '同時效度（criterion-related, concurrent）',
            'B': '預測效度（criterion-related, predictive）',
            'C': '內容效度（content-related）',
            'D': '建構效度（construct-related）',
        },
        'key': 'A',
        'option_to_code': {'A': None, 'B': 'V2a', 'C': 'V1b', 'D': 'V3b'},
    },
    {
        'item_id': 'V2_2',
        'stem': (
            '某教育單位設計一份「新生入學適應測驗」，希望用它來預測學生未來在校表現。'
            '研究者在新生入學第一週施測，並在一年後蒐集同一批學生的 GPA 作為外在效標。'
            '結果顯示入學適應測驗分數與一年後 GPA 顯著相關。\n'
            '這種蒐集證據的做法，最主要是在檢驗哪一種效度？'
        ),
        'options': {
            'A': '同時效度（concurrent）',
            'B': '預測效度（predictive）',
            'C': '內容效度（content）',
            'D': '建構效度（construct）',
        },
        'key': 'B',
        'option_to_code': {'A': 'V2a', 'B': None, 'C': 'V1b', 'D': 'V3b'},
    },
    {
        'item_id': 'V1_1',
        'stem': (
            '一位導師設計了一份「學習動機量表」。許多同學一看題目就說：'
            '「這些題目很像在問我想不想學，看起來很合理。」'
            '但這份量表尚未經過專家審查，也尚未做任何統計分析。\n'
            '請問同學們「看起來很合理」的這種評價，最接近下列哪一種？'
        ),
        'options': {
            'A': '內容效度：因為大家覺得題目合理，所以內容效度已經建立',
            'B': '表面效度：因為只是基於外觀直覺的合理感',
            'C': '建構效度：因為只要題目看起來合理，就代表構念被驗證',
            'D': '預測效度：因為看起來合理的量表通常就能預測未來表現',
        },
        'key': 'B',
        'option_to_code': {'A': 'V1a', 'B': None, 'C': 'V3a', 'D': 'V1b'},
    },
    {
        'item_id': 'VX_1',
        'stem': (
            '以下關於「信度」與「效度」的敘述，何者最正確？\n'
            '（注意：此題在考推理關係，而非名詞背誦。）'
        ),
        'options': {
            'A': '只要信度高（例如 alpha 很高），就可以推論效度一定高',
            'B': '只要效度高，就可以推論信度一定高',
            'C': '信度是效度的必要但不充分條件：信度不足時效度不可能高，但信度高不保證效度高',
            'D': '信度與效度完全無關；一個測驗可以同時信度很低但效度很高',
        },
        'key': 'C',
        'option_to_code': {'A': 'X1', 'B': 'X1', 'C': None, 'D': 'X1'},
    },
    {
        'item_id': 'V1_2',
        'stem': (
            '下列哪一項最能作為「內容效度」的合理證據？\n'
            '（注意：題目在問「內容是否充分代表學習目標/內容範圍」的證據。）'
        ),
        'options': {
            'A': '多數學生與家長覺得題目看起來很像這一科，所以應該有效',
            'B': '命題者使用雙向細目表對應教學目標，並由同領域教師審題確認涵蓋範圍與比例',
            'C': '施測後發現分數與「一年後的學業成績」高度相關，所以內容效度很高',
            'D': '試測後 Cronbach\'s alpha 達到 .92，因此可直接判定效度很高',
        },
        'key': 'B',
        'option_to_code': {'A': 'V1a', 'B': None, 'C': 'V1b', 'D': 'V1c'},
    },
    {
        'item_id': 'V3_1',
        'stem': (
            '研究者發展一份「數位素養量表」，理論上包含三個構面：資訊搜尋、資訊評估、以及數位溝通。'
            '為了檢驗題目是否真的形成這三個構面，研究者進行因素分析，'
            '檢查題項是否依預期聚集成三個因素，以及模型配適是否合理。\n'
            '上述做法主要在蒐集哪一種效度證據？'
        ),
        'options': {
            'A': '內容效度：因為只要題目被分成幾個因素，就代表內容涵蓋完整',
            'B': '建構效度：因為因素分析是在檢驗題目是否反映理論構念結構',
            'C': '表面效度：因為題目看起來合理，所以構面也會合理',
            'D': '預測效度：因為因素分析等於在預測外在效標',
        },
        'key': 'B',
        'option_to_code': {'A': 'V3a', 'B': None, 'C': 'V1a', 'D': 'V3b'},
    },
    {
        'item_id': 'V3_2',
        'stem': (
            '研究者想驗證一份「學習自我效能量表」是否真的測到自我效能。'
            '他同時施測：(1) 新的自我效能量表；(2) 應高度相關的「學習動機量表」；'
            '(3) 應較不相關的「外向性人格量表」。\n'
            '結果：自我效能量表與學習動機量表呈高度正相關，但與外向性人格量表相關很低。\n'
            '上述結果最能支持哪一種效度證據？'
        ),
        'options': {
            'A': '內容效度：因為相關高低代表內容涵蓋程度',
            'B': '建構效度（聚斂/區別效度）：因為結果符合理論預期的相關模式',
            'C': '同時效度：因為只要同一時間點有相關，就屬同時效度',
            'D': '重測信度：因為相關高代表量表穩定',
        },
        'key': 'B',
        'option_to_code': {'A': 'V3a', 'B': None, 'C': 'V3b', 'D': 'V1c'},
    },
]


# ──────────────────────────────────────────
# 出題流程
# ──────────────────────────────────────────
def ask_question(q, index, total):
    send(f'第 {index}/{total} 題\n\n{q["stem"]}', delay=1)

    time.sleep(0.3)
    send_buttons(
        labels     = [f'{k}. {v}' for k, v in q['options'].items()],
        colors     = ['gold', 'gold', 'gold', 'gold'],
        size       = 'medium',
        button_ids = [f'ans_{k}' for k in q['options'].keys()]
    )

    ans_reply  = wait_for_user()
    chosen_key = ans_reply.split(':')[0].replace('ans_', '').strip()
    print(f"[作答] item={q['item_id']} answer={chosen_key}")

    time.sleep(0.3)
    send('請評估你對這個答案的把握度：', delay=0)
    time.sleep(0.3)
    send_buttons(
        labels     = ['1 分', '2 分', '3 分', '4 分', '5 分'],
        colors     = ['gray', 'gray', 'gray', 'gray', 'gray'],
        size       = 'small',
        button_ids = ['conf_1', 'conf_2', 'conf_3', 'conf_4', 'conf_5']
    )

    conf_reply = wait_for_user()
    confidence = int(conf_reply.split(':')[0].replace('conf_', '').strip())
    print(f"[信心] item={q['item_id']} confidence={confidence}")

    is_correct   = (chosen_key == q['key'])
    mistake_code = q['option_to_code'].get(chosen_key)

    write_log(
        f'[{q["item_id"]}] '
        f'answer={chosen_key} | '
        f'is_correct={is_correct} | '
        f'confidence={confidence} | '
        f'mistake_code={mistake_code if mistake_code else "none"}'
    )

    return {
        'item_id':      q['item_id'],
        'answer':       chosen_key,
        'is_correct':   is_correct,
        'confidence':   confidence,
        'mistake_code': mistake_code,
    }


# ──────────────────────────────────────────
# 主要執行區塊
# ──────────────────────────────────────────
def main():
    total   = len(QUESTIONS)
    results = []

    send('好的，現在開始效度概念的快篩題組，共 8 題。', delay=1)
    send('每題作答後，請同時評估你的把握度（1–5 分）。', delay=1)

    for i, q in enumerate(QUESTIONS, start=1):
        result = ask_question(q, i, total)
        results.append(result)
        time.sleep(0.5)

    correct_count = sum(1 for r in results if r['is_correct'])
    avg_conf      = sum(r['confidence'] for r in results) / total
    mistake_codes = [r['mistake_code'] for r in results if r['mistake_code']]

    summary = (
        f'題組完成！共答對 {correct_count}/{total} 題，'
        f'平均把握度 {avg_conf:.1f} 分。'
    )
    send(summary, delay=1)

    write_log(
        f'[摘要] correct={correct_count}/{total} | '
        f'avg_confidence={avg_conf:.2f} | '
        f'mistakes={mistake_codes}'
    )

    from validity_analyze import analyze
    from final_va import export
    report = analyze(results, username, session_id, log_path)
    export(report, results, username, session_id, log_path)

    print(f"[validity.py 執行完畢] {summary}")


if __name__ == '__main__':
    main()