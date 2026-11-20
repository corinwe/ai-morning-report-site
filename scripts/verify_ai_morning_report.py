#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 晨报结构 / 证据 / 合规门禁。

用法：
    python3 scripts/verify_ai_morning_report.py reports/2026-11-20.md --date 2026-11-20
    python3 scripts/verify_ai_morning_report.py reports/2026-11-20.md --json
    python3 scripts/verify_ai_morning_report.py --self-test

设计目标：宁可阻断，不静默放过。历史报告可加 --lenient 跳过日期检查。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = [
    ('一', ('今日重磅', '头条')),
    ('二', ('模型',)),
    ('三', ('云竹热点', '热点技术')),
    ('四', ('创业', '商业')),
    ('五', ('中国',)),
    ('六', ('关键信号',)),
]
MIN_ITEMS = {'一': 1, '二': 2, '三': 3, '四': 1, '五': 1}
MIN_URLS = 8
MIN_COMMENTARY = 5
MIN_SIGNALS = 4
MIN_CHARS = 1800
MAX_CHARS = 4500

SENSITIVE = [
    r'\bGAO\b', r'Government Accountability Office', r'大规模伤亡', r'恐怖袭击',
    r'恐袭', r'参议院', r'\bUSCC\b', r'涉华', r'爆炸装置', r'枪支',
    r'电网攻击', r'AI\s*导致.{0,12}(中断|泄露|停飞)',
]
CAPITAL_HEADLINE = re.compile(r'IPO|上市|市值|融资|估值|募资')


def read_sections(text: str):
    matches = list(re.finditer(r'^##\s+([^\n]+)$', text, re.M))
    out = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1).strip(), text[start:end]))
    return out


def section_items(body: str) -> list[str]:
    return [x.strip() for x in re.findall(r'^###\s+(.+)$', body, re.M)]


def signal_rows(body: str) -> list[list[str]]:
    rows = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith('|') or s.count('|') < 2:
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if len(cells) < 2:
            continue
        if all(set(c) <= set('-: ') for c in cells):
            continue
        if cells[0] in ('信号', 'Signal'):
            continue
        rows.append(cells)
    return rows


def check(text: str, date: str | None = None, lenient: bool = False) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict = {}

    if not re.search(r'^#\s+.*AI晨报', text, re.M):
        errors.append('标题缺少 "# ... AI晨报 ..."')

    sections = read_sections(text)
    by_prefix = {}
    for title, body in sections:
        m = re.match(r'([一二三四五六七八九十]+)、', title)
        if m:
            by_prefix[m.group(1)] = (title, body)
    stats['sections'] = [s[0] for s in sections]

    for num, aliases in REQUIRED:
        if num not in by_prefix:
            errors.append(f'缺少板块：{num}、({" / ".join(aliases)})')
            continue
        title, _ = by_prefix[num]
        if not any(a in title for a in aliases):
            errors.append(f'板块 {num} 标题不含关键词：{title}')
        if num in MIN_ITEMS:
            n = len(section_items(by_prefix[num][1]))
            stats[f'items_{num}'] = n
            if n < MIN_ITEMS[num]:
                errors.append(f'板块 {num} 条目不足：{n} < {MIN_ITEMS[num]}')

    if '五' in by_prefix:
        body5 = by_prefix['五'][1]
        required_insights = {
            '洞见': '洞见', '容易出成绩': '容易出成绩', '普通人': '普通人',
            '巨头': '巨头', '值得尝试': '值得尝试',
        }
        for key, label in required_insights.items():
            if key not in body5:
                errors.append(f'中国 AI 创业机会缺少“{label}”段')
        stats['china_insight_len'] = len(re.findall(r'[\u4e00-\u9fff]', body5))

    stats['commentary'] = len(re.findall(r'\*\*一句话点评[：:]\*\*|一句话点评[：:]', text))
    if stats['commentary'] < MIN_COMMENTARY:
        errors.append(f'“一句话点评”不足：{stats["commentary"]} < {MIN_COMMENTARY}')

    urls = sorted(set(re.findall(r'https?://[^\s)\]>]+', text)))
    stats['urls'] = len(urls)
    if stats['urls'] < MIN_URLS:
        errors.append(f'来源链接不足：{stats["urls"]} < {MIN_URLS}')

    if '六' in by_prefix:
        rows = signal_rows(by_prefix['六'][1])
        stats['signals'] = len(rows)
        if len(rows) < MIN_SIGNALS:
            errors.append(f'关键信号不足：{len(rows)} < {MIN_SIGNALS}')

    conclusion = re.search(r'>\s*\*\*本期晨报核心结论[：:]\*\*\s*(.+?)(?:\n\s*\n|\n#|\Z)', text, re.S)
    if not conclusion:
        errors.append('缺少“本期晨报核心结论”blockquote')
        stats['conclusion_len'] = 0
    else:
        c = re.sub(r'\s+', ' ', conclusion.group(1)).strip()
        stats['conclusion_len'] = len(c)
        if not (40 <= len(c) <= 300):
            errors.append(f'核心结论长度不合适：{len(c)} 字（40-300）')

    cn = len(re.findall(r'[\u4e00-\u9fff]', text))
    stats['chars'] = cn
    if not (MIN_CHARS <= cn <= MAX_CHARS):
        errors.append(f'正文中文字数不合适：{cn}（{MIN_CHARS}-{MAX_CHARS}）')

    if date:
        got = re.search(r'抓取[：:]\s*(\d{4}-\d{2}-\d{2})', text)
        src_date = got.group(1) if got else None
        stats['hotspot_date'] = src_date
        if not src_date:
            (warnings if lenient else errors).append('云竹热点缺少“抓取：YYYY-MM-DD”')
        elif src_date != date:
            (warnings if lenient else errors).append(f'云竹热点隔日：{src_date} != {date}')

    for pat in SENSITIVE:
        if re.search(pat, text, re.I):
            errors.append(f'命中敏感/高风险表述：{pat}')

    # 头条不允许资本事件（可放“创业与商业”）
    if '一' in by_prefix:
        items = section_items(by_prefix['一'][1])
        if items and CAPITAL_HEADLINE.search(items[0]):
            errors.append(f'头条是资本事件：{items[0]}')

    # 同题重复
    all_titles = []
    for _, body in sections:
        all_titles += section_items(body)
    norm = [re.sub(r'[\s\W_]+', '', t.lower()) for t in all_titles]
    dup = sorted({t for t in norm if norm.count(t) > 1})
    stats['duplicate_titles'] = len(dup)
    if dup:
        errors.append(f'同题重复：{len(dup)} 组')

    return errors, warnings, stats


def self_test() -> int:
    good = '''# 🤖 AI晨报 | 2026年11月20日

## 一、今日重磅
### A
FACT。
**一句话点评：** 判断。

## 二、模型与应用
### B
FACT。
**一句话点评：** 判断。
### C
FACT。
**一句话点评：** 判断。

## 三、云竹热点（AI/数字化科技）
> 来源：HN ｜ 抓取：2026-11-20 ｜ 窗口：过去 36 小时
### 1. D（100p / 10c · 11-20）
- 来源：[HN](https://example.com/1) ｜ [原文](https://example.com/2)
- **一句话点评：** 判断。
### 2. E（90p / 9c · 11-20）
- 来源：[HN](https://example.com/3) ｜ [原文](https://example.com/4)
- **一句话点评：** 判断。
### 3. F（80p / 8c · 11-20）
- 来源：[HN](https://example.com/5) ｜ [原文](https://example.com/6)
- **一句话点评：** 判断。

## 四、创业与商业
### G
FACT。
**一句话点评：** 判断。
| 事件 | 金额 | 意义 |
|:--|:--|:--|
| H | 1 | 2 |
| I | 3 | 4 |

### OPC 项目
本期无新增。

## 五、中国 AI/Agent 机会
### 今日新信号
J
**一句话点评：** 判断。
### 洞见：测试洞见
测试。
### 哪里容易出成绩：三个缝隙
1. A
2. B
3. C
### 普通人还是巨头的机会？
普通人做垂直交付，巨头做底座。
### 今天值得尝试
做垂直 Agent。
### 风险
项目制陷阱。

## 六、今日关键信号
| 信号 | 含义 |
|:--|:--|
| **S1** | M1 |
| **S2** | M2 |
| **S3** | M3 |
| **S4** | M4 |

> **本期晨报核心结论：** 自测结论：先做样本，再用证据验收；答案不是等出来的，是走出来的。这里补足到四十字以上，确保门禁可以通过。
'''
    extra = '\n'.join(f'[x](https://example.com/extra{i})' for i in range(8))
    good += '\n' + extra + '\n'
    good += '\n' + '测试内容，用于满足门禁字数。' * 140 + '\n'
    errors, warnings, stats = check(good, '2026-11-20')
    print('self-test good:', 'PASS' if not errors else 'FAIL', errors, stats)
    bad = good.replace('> **本期晨报核心结论：**', '> 没有结论：')
    bad_errors, _, _ = check(bad, '2026-11-20')
    print('self-test bad:', 'PASS (correctly blocked)' if bad_errors else 'FAIL (not blocked)')
    return 0 if not errors and bad_errors else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('path', nargs='?')
    ap.add_argument('--date')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--lenient', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.path:
        ap.error('需要报告路径，或使用 --self-test')
    text = Path(args.path).read_text(encoding='utf-8')
    errors, warnings, stats = check(text, args.date, args.lenient)
    result = {'ok': not errors, 'errors': errors, 'warnings': warnings, 'stats': stats}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('✅ PASS' if not errors else '⛔ FAIL')
        for e in errors:
            print('❌', e)
        for w in warnings:
            print('⚠️', w)
        print('stats:', json.dumps(stats, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
