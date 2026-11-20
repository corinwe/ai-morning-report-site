#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集 AI/数字化科技热点，供 AI 晨报在 08:30 前直接消费。

设计原则：
- 不依赖云竹的 08:15 扫描（它是下游，且 08:35 才拿到晨报）。
- 只取过去 N 小时的 Hacker News 一手讨论（分数/评论/原文链接），
  可选合并前一晚云竹热词研究中的技术条目。
- 输出结构化 JSON + 可直接嵌入晨报的 Markdown 片段。

用法：
    python3 scripts/collect_hotspots.py --date 2026-11-20
    python3 scripts/collect_hotspots.py --date 2026-11-20 --hours 36 --limit 5
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

SITE = Path('/root/ai-morning-report-site')
OUT_JSON = SITE / 'data' / 'hotspots'
OUT_MD = SITE / 'reports'
HN_API = 'https://hn.algolia.com/api/v1/search_by_date'

AI_TERMS = [
    'AI', 'LLM', 'agent', 'Agent', 'model', 'OpenAI', 'Anthropic', 'Claude',
    'Gemini', 'ChatGPT', 'Copilot', 'MCP', 'RAG', 'harness', 'prompt',
    'inference', 'training', 'neural', 'transformer', 'diffusion', 'embedding',
    'coding', 'code', 'robot', 'autonomous', 'reasoning', 'alignment',
]
EXCLUDE = [
    'raises', 'raise', 'funding', 'valuation', 'IPO', 'acquisition', 'acquires',
    'stock', 'shares', 'layoff', 'lawsuit', 'senate', 'congress', 'policy',
    'regulation', 'government', 'white house', 'election', 'chip', 'GPU',
    'Nvidia', 'data center', 'semiconductor', 'export control',
    'Nasdaq', 'debut', 'fuck', 'porn', 'sex',
]
CATEGORY_RULES = [
    ('研究', ['research', 'paper', 'physics', 'black hole', 'benchmark', 'study', 'prove']),
    ('工程', ['reverse engineering', 'codebase', 'coding', 'developer', 'harness', 'MCP', 'tool']),
    ('产品', ['launch', 'release', 'model', 'agent', 'Copilot', 'Gemini', 'Claude', 'ChatGPT']),
]


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'ai-morning-hotspots/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8', errors='ignore'))


def norm(s: str) -> str:
    return re.sub(r'[\s\W_]+', '', (s or '').lower())


def is_ai(title: str) -> bool:
    low = (title or '').lower()
    if any(x.lower() in low for x in EXCLUDE):
        return False
    # 短词（AI/LLM/MCP/RAG）必须按词边界匹配，避免 "against" 命中 "AI"
    for term in AI_TERMS:
        t = term.lower()
        if len(t) <= 4:
            if re.search(rf'(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])', low):
                return True
        elif t in low:
            return True
    return False


def category(title: str) -> str:
    low = (title or '').lower()
    for name, words in CATEGORY_RULES:
        if any(w.lower() in low for w in words):
            return name
    return '技术'


def fetch_hn(hours: int, pages: int = 2, min_points: int = 30) -> list[dict]:
    since = int(time.time()) - hours * 3600
    hits: list[dict] = []
    for page in range(pages):
        q = urllib.parse.urlencode({
            'tags': 'story',
            'numericFilters': f'created_at_i>{since},points>{min_points}',
            'hitsPerPage': 100,
            'page': page,
        })
        try:
            data = fetch_json(f'{HN_API}?{q}')
        except Exception as e:  # noqa: BLE001
            print(f'[warn] HN page {page} failed: {e}')
            continue
        hits.extend(data.get('hits', []))
    return hits


def collect(date: str, hours: int = 36, limit: int = 5) -> dict:
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    items: list[dict] = []
    for h in fetch_hn(hours):
        title = (h.get('title') or '').strip()
        if not title or not is_ai(title):
            continue
        url = (h.get('url') or '').strip()
        hn_url = f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        key = norm(title)
        if key in seen_titles or (url and url in seen_urls):
            continue
        seen_titles.add(key)
        if url:
            seen_urls.add(url)
        created = h.get('created_at_i') or 0
        published = dt.datetime.fromtimestamp(created, tz=dt.timezone.utc).strftime('%Y-%m-%d')
        items.append({
            'title': title,
            'url': url or hn_url,
            'hn_url': hn_url,
            'source': 'Hacker News',
            'source_type': 'community',
            'points': int(h.get('points') or 0),
            'comments': int(h.get('num_comments') or 0),
            'published_at': published,
            'category': category(title),
        })
    items.sort(key=lambda x: (x['points'] + x['comments'] * 0.3), reverse=True)
    items = items[:limit]
    return {
        'date': date,
        'generated_at': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'window_hours': hours,
        'source': 'Hacker News Algolia (past window)',
        'items': items,
    }


def render_md(payload: dict) -> str:
    lines = [
        '## 三、云竹热点（AI/数字化科技）',
        '',
        f"> 来源：{payload['source']} ｜ 抓取：{payload['date']} ｜ 生成：{payload['generated_at']} ｜ 窗口：过去 {payload['window_hours']} 小时 ｜ 只取技术/产品/工程，排除资本/政策/人物/硬件",
        '',
    ]
    if not payload['items']:
        lines += ['> 今日未采集到可用技术热点（不编造）。', '']
        return '\n'.join(lines)
    for i, it in enumerate(payload['items'], 1):
        lines.append(f"### {i}. {it['title']}（{it['points']}p / {it['comments']}c · {it['published_at']}）")
        lines.append(f"- 来源：[Hacker News]({it['hn_url']}) ｜ [原文]({it['url']})")
        lines.append(f"- 分类：{it['category']}")
        lines.append('')
    return '\n'.join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=dt.date.today().isoformat())
    ap.add_argument('--hours', type=int, default=36)
    ap.add_argument('--limit', type=int, default=5)
    args = ap.parse_args()

    payload = collect(args.date, args.hours, args.limit)
    OUT_JSON.mkdir(parents=True, exist_ok=True)
    OUT_MD.mkdir(parents=True, exist_ok=True)
    jp = OUT_JSON / f'{args.date}.json'
    mp = OUT_MD / f'_hotspots_{args.date}.md'
    jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    mp.write_text(render_md(payload), encoding='utf-8')
    print(f'✅ {args.date}: {len(payload["items"])} 条热点')
    print(f'JSON: {jp}')
    print(f'MD:   {mp}')
    for it in payload['items']:
        print(f"- {it['title']} ({it['points']}p/{it['comments']}c)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
