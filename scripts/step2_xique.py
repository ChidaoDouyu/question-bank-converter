"""
步骤 2：通用 JSON → 喜鹊 CSV
使用时复制为 step2_temp.py，填好文件名，用完删除
"""
import json, csv

HEADER = ['题干','题型','选项A','选项B','选项C','选项D','选项E','选项F','选项G','选项H','正确答案']
EMPTY = [''] * 8

def to_row(q):
    """通用格式 → 喜鹊 CSV 行"""
    answer = q['答案']

    # 填空题：答案数组依次填入选项A/B/C/D... K留空
    if q['题型'] == '填空题':
        ans_arr = answer if isinstance(answer, list) else [answer]
        options = (ans_arr + [''] * 8)[:8]
        answer_col = ''

    else:
        options = (q.get('选项') or []) + [''] * 8
        options = options[:8]

        if q['题型'] == '单选题':
            answer_col = answer
        elif q['题型'] == '多选题':
            answer_col = ''.join(answer)
        elif q['题型'] == '判断题':
            if answer not in ('A', 'B'):
                print(f'WARNING: 判断题答案应为"A"或"B"，实际为: {answer} — 题干: {q["题干"][:40]}...')
            answer_col = answer
        elif q['题型'] == '简答题':
            answer_col = answer
        else:
            answer_col = ''

    # 所有单元格加 \t 前缀，强制 Excel 以文本格式存储
    return [str(x) for x in [q['题干'], q['题型'], *options, answer_col]]

# ====== 执行 ======
# TODO: 修改输入/输出文件名

with open('输出/json-课程名.json', encoding='utf-8') as f:
    questions = json.load(f)

rows = [to_row(q) for q in questions]

with open('输出/喜鹊-课程名.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    w.writerow(HEADER + EMPTY)
    for row in rows:
        w.writerow(row + EMPTY)

# GBK 转码（替换不兼容字符），保留 utf-8 备份
src = open('输出/喜鹊-课程名.csv', encoding='utf-8-sig').read()
src = src.replace('•', '-')   # bullet •
open('输出/喜鹊-课程名-utf8.csv', 'w', encoding='utf-8-sig').write(src)
open('输出/喜鹊-课程名.csv', 'w', encoding='gbk', errors='replace').write(src)

print(f'{len(rows)} 题')
