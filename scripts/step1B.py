"""
步骤 1（超星 HTML 版）：超星学习通 HTML → 通用 JSON
使用时复制为 step1_temp.py，补全 TODO，用完删除
"""
import re, json, os, sys, io, shutil

# 修复 Windows GBK 控制台下中文输出乱码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ====== 1. HTML 解析工具函数 ======

def extract_qtContent(html):
    """匹配嵌套 span 提取完整题干 HTML（深度计数，防止内层 </span> 提前截断）"""
    start = html.find('class="qtContent">')
    if start == -1:
        return ''
    start = html.find('>', start) + 1
    depth = 1
    i = start
    while i < len(html) and depth > 0:
        if html[i:i+1] == '<':
            if html[i+1:i+2] == '/':
                depth -= 1
            elif not html[i:i+4] in ('<br>', '<br/', '<img'):
                depth += 1
        i += 1
    return html[start:i-1]


def unescape(s):
    """HTML 实体 → 普通字符"""
    return s.replace('&nbsp;', ' ').replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')


def strip_html(s):
    """<img> → [图]，其余标签删除，HTML 实体转义，合并空白"""
    s = re.sub(r'<img[^>]*>', '[图]', s)   # 先：图 → 占位符
    s = re.sub(r'<[^>]+>', '', s)           # 后：删其余标签
    s = unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ====== 2. 图片处理 ======

def extract_img_filenames(block):
    """从题目 block 中提取所有 <img src> 的文件名"""
    srcs = re.findall(r'<img[^>]*src="([^"]*)"', block)
    return [os.path.basename(s) for s in srcs]


def copy_images(html_path, json_path, questions):
    """
    将每道题引用的图片从 HTML 的 _files 目录复制到输出图片目录，
    重命名为 第XX题-图N.png
    questions 中需有内部字段 _num 和 _images
    """
    html_dir = os.path.dirname(html_path)
    html_basename = os.path.splitext(os.path.basename(html_path))[0]
    files_dir = os.path.join(html_dir, html_basename + '_files')

    if not os.path.isdir(files_dir):
        print(f'⚠ 未找到资源目录: {files_dir}，跳过图片复制')
        return

    img_dir = json_path.replace('.json', '-图片')
    os.makedirs(img_dir, exist_ok=True)

    total = 0
    for q in questions:
        imgs = q.get('_images', [])
        num = q.get('_num', 0)
        for idx, fname in enumerate(imgs):
            src = os.path.join(files_dir, fname)
            dst_name = f'第{num:02d}题-图{idx+1}.png'
            dst = os.path.join(img_dir, dst_name)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                total += 1
            else:
                print(f'  ⚠ 缺失: {fname}')

    if total:
        print(f'📷 复制 {total} 张图片 → {img_dir}')
    else:
        print('📷 无图片需复制')


# ====== 3. 逐题解析 ======

def parse_block(block):
    """解析单个 questionLi 块 → dict 或 None"""
    h3_m = re.search(
        r'<h3 class="mark_name[^"]*">\s*(\d+)\.\s*<span[^>]*>\((\S+?),\s*[\d.]+\s*分\)',
        block
    )
    if not h3_m:
        return None

    qtype_raw = h3_m.group(2)  # 单选题 / 多选题 / 判断题
    qnum = int(h3_m.group(1))   # 题号

    # 图片文件名（内部字段，写 JSON 前清除）
    img_filenames = extract_img_filenames(block)

    # 题干
    stem = strip_html(extract_qtContent(block))

    # 选项
    opt_m = re.search(r'<ul class="mark_letter[^"]*">(.*?)</ul>', block, re.DOTALL)
    options = []
    if opt_m:
        for li in re.findall(r'<li[^>]*>(.*?)</li>', opt_m.group(1), re.DOTALL):
            opt_text = strip_html(li)
            opt_text = re.sub(r'^[A-H][.．]\s*', '', opt_text)  # 去选项字母前缀
            if opt_text:
                options.append(opt_text)

    # 正确答案
    ans_m = re.search(r'<span class="rightAnswerContent">([^<]*)</span>', block)
    answer = ans_m.group(1).strip() if ans_m else ''

    # 题型映射
    if qtype_raw == '单选题':
        qtype = '单选题'
    elif qtype_raw == '多选题':
        qtype = '多选题'
        answer = list(answer) if len(answer) > 1 else answer
    elif qtype_raw == '判断题':
        qtype = '判断题'
        answer = 'A' if answer in ('对', 'A') else 'B'
        options = ['对', '错']
    else:
        qtype = '简答题'

    return {'题干': stem, '题型': qtype, '选项': options, '答案': answer,
            '_num': qnum, '_images': img_filenames}

# ====== 4. 主解析流程 ======

def convert(html_path, json_path):
    """读取 HTML 文件，返回通用 JSON 题目列表"""
    with open(html_path, encoding='utf-8') as f:
        html = f.read()

    blocks = re.split(r'<div class="marBom60 questionLi[^"]*"[^>]*>', html)[1:]
    questions = []
    for block in blocks:
        q = parse_block(block)
        if q:
            questions.append(q)

    # 复制图片并重命名
    copy_images(html_path, json_path, questions)

    # 清除内部字段，保持 JSON 干净
    for q in questions:
        del q['_num']
        del q['_images']

    return questions

# ====== 4. 执行 ======
# TODO: AI 根据文档填写以下两项
HTML_PATH = '源文件/organic/课程名.html'
JSON_PATH = '输出/json-课程名.json'

if __name__ == '__main__':
    os.makedirs('输出', exist_ok=True)
    questions = convert(HTML_PATH, JSON_PATH)

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    # 统计
    type_counts = {}
    for q in questions:
        type_counts[q['题型']] = type_counts.get(q['题型'], 0) + 1
    img_count = sum(1 for q in questions if '[图]' in q['题干'] or any('[图]' in o for o in q['选项']))

    print(f'{len(questions)} 题 → {JSON_PATH}')
    print(f'题型分布: {type_counts}')
    print(f'含图题目: {img_count} 题')

    # 前 2 题样本
    print('\n--- 前 2 题样本验证 ---')
    for q in questions[:2]:
        print(f'  题型: {q["题型"]}')
        print(f'  题干: {q["题干"][:120]}')
        print(f'  选项: {q["选项"]}')
        print(f'  答案: {q["答案"]}')
    print()
