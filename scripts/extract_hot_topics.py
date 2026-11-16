#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从知识库「每日热点研究」提取技术类热点，生成 AI 晨报的一个章节。

用法：
    python3 scripts/extract_hot_topics.py [YYYY-MM-DD]

数据源优先级：
  1) /root/weiwuji-knowledge-base/11-实践派认知升级/每日热点研究/<date>.md
  2) /root/shared/hot-topic-research.md（取当日段落）

原则：
  - 只取有一手热度（NNNp / NNNc）的条目；
  - 排除资本/政策/人物/硬件等非技术项；
  - 同题去重，按热度降序，最多 5 条；
  - 不足 3 条时补「新登记词」（标注待验证）；
  - 无数据时如实输出「无」，不编造。
"""
from __future__ import annotations

import re
import sys
from datetime import date as date_cls
from pathlib import Path

KB_DIR = Path('/root/weiwuji-knowledge-base/11-实践派认知升级/每日热点研究')
SHARED = Path('/root/shared/hot-topic-research.md')

EXCLUDE = [
    '涉政', '政策', '监管', '融资', '估值', 'IPO', '并购', '收购', '亿美元',
    '资本', '硬件', '芯片', 'GPU', '算力', '人物', '辞职', '丑闻', '裁员',
    '跑分', '权重指纹', '发布族', '模型发布族', '非 AI', '非AI',
]
INCLUDE = [
    '技术', '机制', 'Agent', '智能体', '模型路由', '路由', '验证', '形式化',
    '安全', '权限', '记忆', '上下文', '代码', '编程', '推理', '训练',
    '协议', 'MCP', '开源', '工具', '框架', '架构', '评测', '数据',
    '搜索', '浏览器', '部署', '并发', '编排', '自主', 'AI', '模型',
]
CORE_TECH = ['技术', '机制', 'Agent', '模型路由', '验证', '形式化', '编排', '协议']
MIN_SCORE = 50
HEADER_WORDS = {'帖', '#', '词 / 信号', '事件', '词/信号', '项目'}


def clean_title(s: str) -> str:
    s = s.replace('**', '').replace('`', '').strip()
    s = re.sub(r'^\d+\.\s*', '', s)          # 去掉 "1. "
    s = re.sub(r'^[#\s]+', '', s)
    return s.strip()


def _shared_section(text: str, day: str) -> str:
    """截取 shared 中某一天的全部块（晨间/多源/晚间），到下一个不同日期为止。"""
    out = []
    on = False
    for line in text.splitlines():
        if line.startswith('## '):
            if line.startswith(f'## {day}'):
                on = True
                out.append(line)
                continue
            if on and re.match(r'##\s*20\d\d-\d\d', line):
                break
        if on:
            out.append(line)
    return '\n'.join(out)


def load_text(day: str) -> tuple[str, str]:
    """当天文件优先；否则用 shared 的当天段落；再补前一天的晚间分析。"""
    parts: list[str] = []
    srcs: list[str] = []

    f = KB_DIR / f'{day}.md'
    if f.exists():
        parts.append(f.read_text(encoding='utf-8', errors='ignore'))
        srcs.append(str(f))
    elif SHARED.exists():
        sec = _shared_section(SHARED.read_text(encoding='utf-8', errors='ignore'), day)
        if sec:
            parts.append(sec)
            srcs.append(f'{SHARED} (当天段落)')

    # 前一天的晚间分析（21:00）—— 次日晨报要一起带上
    try:
        from datetime import timedelta
        prev = (date_cls.fromisoformat(day) - timedelta(days=1)).isoformat()
    except Exception:
        prev = ''
    if prev:
        pf = KB_DIR / f'{prev}.md'
        if pf.exists():
            parts.append(pf.read_text(encoding='utf-8', errors='ignore'))
            srcs.append(str(pf))
        elif SHARED.exists():
            sec = _shared_section(SHARED.read_text(encoding='utf-8', errors='ignore'), prev)
            if sec:
                parts.append(sec)
                srcs.append(f'{SHARED} ({prev} 段落)')

    return '\n\n'.join(parts), ' + '.join(srcs)


def parse_rows(text: str):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('|') or line.count('|') < 3:
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 3:
            continue
        if all(set(c) <= set('-: ') for c in cells):
            continue
        joined = ' '.join(cells)
        hm = re.search(r'(\d{1,4})\s*p\s*/\s*(\d{1,4})\s*c', joined, re.I)
        if not hm:
            continue
        # 标题：优先第一个非纯数字、非表头单元格
        title = ''
        for c in cells[:3]:
            t = clean_title(c)
            if t and t not in HEADER_WORDS and not re.fullmatch(r'[\d\s.]+', t):
                title = t
                break
        if not title:
            continue
        score = int(hm.group(1))
        comments = int(hm.group(2))
        heat = f'{score}p / {comments}c'
        dm = re.search(r'(\d{2}-\d{2})', joined)
        post_date = dm.group(1) if dm else ''
        qual = clean_title(cells[-1])[:220]
        rows.append({
            'title': title,
            'score': score,
            'comments': comments,
            'heat': heat,
            'date': post_date,
            'qual': qual,
        })
    return rows


def is_tech(row) -> bool:
    blob = f"{row['title']} {row['qual']}"
    if row.get('score', 0) < MIN_SCORE:
        return False
    if any(k in blob for k in EXCLUDE):
        return False
    return any(k in row['title'] for k in INCLUDE) or any(k in row['qual'] for k in CORE_TECH)


def _norm_title(s: str) -> str:
    return re.sub(r'[\s，。；：、,.!?！？「」『』（）()《》<>"“”\-—…]+', '', s).lower()


def dedupe(rows):
    kept = []
    for r in sorted(rows, key=lambda x: x['score'], reverse=True):
        key = _norm_title(r['title'])
        if not key:
            continue
        dup = False
        for k in kept:
            other = _norm_title(k['title'])
            if key == other or (len(key) >= 10 and len(other) >= 10 and (key in other or other in key)):
                dup = True
                break
        if not dup:
            kept.append(r)
    return kept


def new_terms(text: str, limit: int = 3):
    terms = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith(('-', '*')):
            continue
        if '🆕' not in s:
            continue
        s = re.sub(r'^[-*]\s*', '', s)
        s = s.replace('🆕', '').strip()
        s = re.sub(r'^\*\*|\*\*$', '', s).strip()
        if len(s) > 4:
            terms.append(s[:140])
    out, seen = [], set()
    for t in terms:
        k = t[:20]
        if k not in seen:
            seen.add(k)
            out.append(t)
        if len(out) >= limit:
            break
    return out


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else date_cls.today().isoformat()
    text, src = load_text(day)
    if not text:
        print('## 🧪 热点技术（知识库每日研究）\n')
        print(f'> 未找到 {day} 的知识库热点研究（不编造）。')
        return 0

    rows = dedupe([r for r in parse_rows(text) if is_tech(r)])[:5]
    print('## 🧪 热点技术（知识库每日研究）\n')
    print(f'> 来源：`{src}` ｜ 日期：{day} ｜ 只取一手热度；资本/政策/人物/硬件类已排除\n')

    if rows:
        for i, r in enumerate(rows, 1):
            suffix = f" · {r['date']}" if r['date'] else ''
            print(f"### {i}. {r['title']}（{r['heat']}{suffix}）")
            print(f"- {r['qual'] or '一手热度条目'}\n")
    else:
        print('> 今日无可用的技术类一手热度条目。\n')

    if len(rows) < 3:
        terms = new_terms(text)
        if terms:
            print('### 待验证新词（只登记，未开题）')
            for t in terms:
                print(f'- {t}')
            print()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
