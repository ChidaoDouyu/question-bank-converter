"""
步骤 1：文档 → 通用 JSON
使用时复制为 step1_temp.py，补全 TODO，用完删除

支持两种答案格式：
  A. 内嵌答案（【答案】D / （ D ））—— 原版解析函数
  B. 答案独立成段（"答 案"区域，选项小写字母，判断 ×/∨）—— 新增 parse_*_separate 系列
"""
import re, json

# ====== 1. 题型标题 → 类型名 ======

TYPE_MAP = {
    # TODO: 根据文档实际的题型标题填写
    # 例: '一、单选题': '单选题', '二、多选题': '多选题', '三、判断题': '判断题', '四、填空题': '填空题', '五、简答题': '简答题',
    # 答案独立成段格式例: '一、填空题': '填空题', '二、选择题': '选择题', '三、判断题': '判断题',
}

# ======================================================================
#  A. 内嵌答案解析函数（原版）—— 【答案】D / （ D ） 格式
# ======================================================================

def parse_bracket_style(block, qtype):
    """答案格式：【答案】D 或 【答案】ABCD"""
    ans_m = re.search(r'【答案】([A-E]+)', block)
    if not ans_m:
        return None
    answer = ans_m.group(1) if qtype == '单选题' else list(ans_m.group(1))
    block = block[:ans_m.start()].strip()
    return _parse_options(block, qtype, answer)

def parse_inline_style(block, qtype):
    """答案格式：题干中（ D ）或（ ABCD ）"""
    ans_m = re.search(r'[（(]\s*([A-E]+)\s*[）)]', block)
    if not ans_m:
        return None
    answer = ans_m.group(1) if qtype == '单选题' else list(ans_m.group(1))
    block = block[:ans_m.start()].strip() + block[ans_m.end():].strip()
    return _parse_options(block, qtype, answer)

def _parse_options(block, qtype, answer):
    block = re.sub(r'\n\d+\n', '\n', block)
    block = re.sub(r'^\d+\.', '', block, count=1).strip()

    first_opt = re.search(r'\n?A[.．]', block)
    if not first_opt:
        return None
    # 二次校验：确认后面还存在 B. / B / B．，防止题干内 "A." 被误识别为选项起始
    after_a = block[first_opt.end():]
    if not re.search(r'\n?B[.．\s]', after_a):
        return None
    content = block[:first_opt.start()].strip()
    opt_text = block[first_opt.start():].strip()

    options = []
    for part in re.split(r'\n?(?=[A-H][.．\s])', opt_text.lstrip('\n')):
        part = part.strip()
        m = re.match(r'([A-H])(?:[.．]|\s)\s*(.+)', part, re.DOTALL)
        if m:
            options.append(m.group(2).strip().replace('\n', ''))

    content = content.replace('-\n', '').replace('\n', '')
    return {'题干': content, '题型': qtype, '选项': options, '答案': answer}

def parse_fill(block):
    """简答/论述：支持【答案】标记 或 ？后紧跟答案（无标记）"""
    block = re.sub(r'^\d+[、.]?\s*', '', block.strip())
    # 优先尝试 【答案】 标记格式
    ans_m = re.search(r'【答案】(.+)', block, re.DOTALL)
    if ans_m:
        content = block[:ans_m.start()].strip().replace('\n', '')
        answer = ans_m.group(1).strip().replace('\n', '')
        return {'题干': content, '题型': '简答题', '选项': [], '答案': answer}
    # 无标记格式：题干？答案文本
    parts = re.split(r'[？?]', block, maxsplit=1)
    if len(parts) >= 2:
        content = parts[0].strip() + '？'
        answer = parts[1].strip().replace('\n', '')
        if answer:
            return {'题干': content, '题型': '简答题', '选项': [], '答案': answer}
    return None

def parse_bool(block):
    """判断题：【答案】对 → A，【答案】错 → B"""
    block = re.sub(r'^\d+[、.]?\s*', '', block.strip())
    ans_m = re.search(r'【答案】\s*(对|错)', block)
    if not ans_m:
        return None
    answer = 'A' if ans_m.group(1) == '对' else 'B'
    content = block[:ans_m.start()].strip().replace('\n', '')
    return {'题干': content, '题型': '判断题', '选项': ['对', '错'], '答案': answer}


# ====== 3. 切分并解析（内嵌答案） ======

def classify_question(block):
    """不依赖题型标题，根据块内容自动推断题型。
    决策顺序：选项数 → 答案特征 → 题型。
    """
    ans_m = re.search(r'【答案】(.+)', block, re.DOTALL)
    if not ans_m:
        return None, None
    answer_text = ans_m.group(1).strip()

    # 找选项标识（A. B. C. ...），去重保持顺序
    opt_letters = []
    for m in re.finditer(r'(?:^|\n)([A-H])[.．\s]', block, re.MULTILINE):
        if m.group(1) not in opt_letters:
            opt_letters.append(m.group(1))

    # 无选项 → 简答题
    if not opt_letters:
        return '简答题', None

    # 只有 A、B 两个选项 → 判断题
    if opt_letters == ['A', 'B'] and re.search(r'[对错]', answer_text):
        return '判断题', None

    # 选项 ≥3 个 → 按答案字母数区分单选/多选
    if len(opt_letters) >= 3:
        ans_letters = re.findall(r'[A-E]', answer_text)
        if len(ans_letters) == 1:
            return '单选题', None
        elif len(ans_letters) >= 2:
            return '多选题', None

    return None, None


def convert_auto(text):
    """无 TYPE_MAP 时的回退模式：按题号拆块，逐题推断类型并解析。
    选择题优先尝试括号式，失败再尝试内嵌式。
    """
    questions = []
    for block in re.split(r'\n(?=\d+[、.](?!\d))', text):
        block = block.strip()
        qtype, _ = classify_question(block)
        if not qtype:
            continue

        if qtype in ('单选题', '多选题'):
            q = parse_bracket_style(block, qtype) or parse_inline_style(block, qtype)
        elif qtype == '判断题':
            q = parse_bool(block)
        elif qtype == '简答题':
            q = parse_fill(block)
        else:
            q = None

        if q:
            questions.append(q)
    return questions


def _convert_with_map(text, parse_choice):
    """按 TYPE_MAP 的题型标题切分解析"""
    sections = re.split(r'\n(' + '|'.join(re.escape(k) for k in TYPE_MAP) + r')\n?', text)
    questions = []
    for i in range(1, len(sections), 2):
        label = sections[i].strip()
        content = sections[i+1].strip() if i+1 < len(sections) else ''
        qtype = TYPE_MAP[label]

        if qtype in ('单选题', '多选题'):
            for block in re.split(r'\n(?=\d+\.)', content):
                q = parse_choice(block.strip(), qtype)
                if q:
                    questions.append(q)
        elif qtype == '判断题':
            for block in re.split(r'\n(?=\d+[、.](?!\d))', content):
                q = parse_bool(block.strip())
                if q:
                    questions.append(q)
        elif qtype in ('简答题', '填空题'):
            for block in re.split(r'\n(?=\d+[、.](?!\d))', content):
                q = parse_fill(block.strip())
                if q:
                    questions.append(q)
    return questions


# ======================================================================
#  B. 答案独立成段解析函数（新增）—— "答 案"区域格式
#     适用: 选项小写字母 a. b. c. d. ，判断题答案 ×/∨，填空题答案独立
# ======================================================================

def parse_answers_separate(answer_text):
    """解析答案区块: 1．xxx  2．xxx ...
    用 \\s+(?=\\d+[．.]) 切分为各题答案，再提取题号和答案文本。
    """
    answers = {}
    for part in re.split(r'\s+(?=\d+[．.](?!\d))', answer_text.strip()):
        m = re.match(r'(\d+)[．.]\s*(.*)', part, re.DOTALL)
        if m:
            answers[int(m.group(1))] = m.group(2).strip()
    return answers


def parse_choice_separate(block, qnum, answers):
    """选择题：小写选项 a. b. c. d. → 映射到 A/B/C/D"""
    opt_start = re.search(r'\n?[aａ][.、．]', block)
    if not opt_start:
        return None

    stem = block[:opt_start.start()].strip()
    stem = re.sub(r'^\d+[.、．]\s*', '', stem)
    stem = stem.replace('\n', ' ').replace('  ', ' ')
    stem = re.sub(r'[（(]\s*[）)]\s*$', '', stem).strip()

    opt_part = block[opt_start.start():].strip()
    options = []
    for om in re.finditer(r'([a-eａ-ｅ])[.、．]\s*(.+?)(?=\n?[a-eａ-ｅ][.、．]|\Z)', opt_part, re.DOTALL):
        opt_text = om.group(2).strip().replace('\n', ' ')
        options.append(opt_text)

    raw_answer = answers.get(qnum, '')
    raw_answer = raw_answer.split('\n')[0].strip()  # 只取首行，过滤 Page 标记等噪音
    ans_letters = re.findall(r'[a-eA-E]', raw_answer.upper())

    if len(ans_letters) >= 2:
        return {'题干': stem, '题型': '多选题', '选项': options, '答案': ans_letters}
    elif len(ans_letters) == 1:
        return {'题干': stem, '题型': '单选题', '选项': options, '答案': ans_letters[0]}
    return None


def parse_bool_separate(block, qnum, answers):
    """判断题：×/X → B(错), ∨/√/✓ → A(对)"""
    block = re.sub(r'^\d+[.、．]\s*', '', block)
    content = block.strip().replace('\n', ' ')
    raw = answers.get(qnum, '').split('\n')[0].strip()  # 只取首行
    if raw and raw[0] in '×xX✕':
        answer = 'B'
    else:
        answer = 'A'
    return {'题干': content, '题型': '判断题', '选项': ['对', '错'], '答案': answer}


def parse_fill_separate(block, qnum, answers):
    """填空题：答案用 ；切分为数组"""
    block = re.sub(r'^\d+[.、．]\s*', '', block)
    content = block.strip().replace('\n', ' ')
    answer_raw = answers.get(qnum, '').split('\n')[0].strip()  # 只取首行
    # 按中文/英文分号切分每个空
    answer_arr = re.split(r'[；;]', answer_raw) if answer_raw else ['']
    answer_arr = [a.strip() for a in answer_arr if a.strip()]
    if not answer_arr:
        answer_arr = [answer_raw] if answer_raw else ['']
    return {'题干': content, '题型': '填空题', '选项': [], '答案': answer_arr}


def convert_separate_answers(text, type_map, header_titles):
    """
    解析"答案独立成段"格式。
    type_map: 题型标题 → 类型名的映射，如 {'一、填空题': '填空题', '二、选择题': '选择题', ...}
    header_titles: 需要处理的题型标题列表（用于构建 header_pattern）
    """
    questions = []
    header_pattern = r'\n(' + '|'.join(re.escape(k) for k in header_titles) + r')\n?'

    parts = re.split(header_pattern, text)

    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        content = parts[i+1] if i+1 < len(parts) else ''

        qtype_base = type_map.get(header)
        if not qtype_base:
            continue

        # 切分题目区 / 答案区
        qa = re.split(r'\n答\s*案\n?', content, maxsplit=1)
        q_text = qa[0].strip() if len(qa) > 0 else ''
        a_text = qa[1].strip() if len(qa) > 1 else ''

        answers = parse_answers_separate(a_text)

        # 按题号切分
        for block in re.split(r'\n(?=\d+[.、．](?!\d))', q_text):
            block = block.strip()
            if not block:
                continue

            qnum_m = re.match(r'(\d+)[.、．]', block)
            if not qnum_m:
                continue
            qnum = int(qnum_m.group(1))

            if qtype_base == '选择题':
                q = parse_choice_separate(block, qnum, answers)
            elif qtype_base == '判断题':
                q = parse_bool_separate(block, qnum, answers)
            else:
                q = parse_fill_separate(block, qnum, answers)

            if q:
                questions.append(q)

    return questions


# ====== 主入口 ======

def convert(text, parse_choice):
    """TYPE_MAP 为空 或 解析出 0 题时，回退到自动推断"""
    if TYPE_MAP:
        questions = _convert_with_map(text, parse_choice)
        if questions:
            return questions
    return convert_auto(text)


# ====== 4. 执行 ======
if __name__ == '__main__':
    # TODO: AI 根据文档填写以下四项
    TXT_PATH = '_temp.txt'  # PDF 提取的临时文本文件，用完删除
    TYPE_MAP = {
        # AI 填写，例: '一、单选题': '单选题', '二、多选题': '多选题',
    }
    parse_choice = parse_bracket_style    # AI 选择: parse_bracket_style 或 parse_inline_style
    JSON_PATH = '输出/json-课程名.json'

    raw = open(TXT_PATH, encoding='utf-8').read()

    # 若 TYPE_MAP 中的标题匹配"答案独立成段"格式，自动使用该解析路径
    SEPARATE_HEADERS = ['一、填空题', '一、填充题', '二、选择题', '三、判断题']
    if any(k in TYPE_MAP for k in SEPARATE_HEADERS) and '选择题' in TYPE_MAP.values():
        questions = convert_separate_answers(raw, TYPE_MAP, list(TYPE_MAP.keys()))
    else:
        questions = convert(raw, parse_choice)

    import os
    os.makedirs('输出', exist_ok=True)
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    # 统计
    from collections import Counter
    type_counts = Counter(q['题型'] for q in questions)
    print(f'总题数: {len(questions)}')
    for t, c in type_counts.items():
        print(f'  {t}: {c}')

    # 前 2 题样本
    for i, q in enumerate(questions[:2]):
        print(f'\n--- 样本 {i+1} ---')
        for k, v in q.items():
            print(f'  {k}: {v}')
