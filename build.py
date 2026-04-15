#!/usr/bin/env python3
"""
Build script for AI Morning Report site.
Scans reports/ directory, extracts structured metadata, generates report registry.
"""
import os
import re
import json
import glob

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(SITE_DIR, 'reports')
INDEX_FILE = os.path.join(SITE_DIR, 'index.html')

def extract_metadata(filepath):
    """Extract structured metadata from a markdown report."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None

    meta = {
        'date': '',
        'file': os.path.basename(filepath),
        'summary': '',
        'highlights': [],      # Key signals / 核心信号
        'sections': [],        # Section titles with anchors
        'word_count': 0,
    }

    # Date from filename
    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', meta['file'])
    if date_match:
        meta['date'] = date_match.group(1)

    # Word count (Chinese chars + English words)
    text_only = re.sub(r'[#*`\[\]|>]', '', content)
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text_only))
    en_words = len(re.findall(r'[a-zA-Z]+', text_only))
    meta['word_count'] = cn_chars + en_words

    # Extract sections (h2 level)
    for m in re.finditer(r'^## ([^\n]+)', content, re.MULTILINE):
        title = m.group(1).strip()
        # Clean markdown formatting
        title = re.sub(r'\*\*', '', title)
        anchor = re.sub(r'[^\w\u4e00-\u9fff]+', '-', title).lower().strip('-')
        meta['sections'].append({'title': title, 'anchor': anchor})

    # Extract summary from core conclusion blockquote
    conclusion_match = re.search(
        r'>\s*\*\*本期晨报核心结论[：:]\*\*\s*(.+?)(?:\n\n|\n[^>]|\Z)', content, re.DOTALL
    )
    if conclusion_match:
        summary = conclusion_match.group(1).strip()
        summary = re.sub(r'\n', ' ', summary)
        summary = re.sub(r'\s+', ' ', summary)
        meta['summary'] = summary[:200]
    else:
        # Fallback: first substantial paragraph after h1
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('##') and i > 0:
                para_lines = []
                for j in range(1, i):
                    l = lines[j].strip()
                    if l and not l.startswith('#') and not l.startswith('---'):
                        para_lines.append(l)
                    if len(para_lines) >= 2:
                        break
                if para_lines:
                    meta['summary'] = ' '.join(para_lines)[:200]
                break

    # Extract key signals (## 五、今日关键信号 table rows)
    signal_section = re.search(
        r'##\s*五.*?关键信号(.+?)(?=\n## |\Z)', content, re.DOTALL
    )
    if signal_section:
        signals_text = signal_section.group(1)
        for m in re.finditer(r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|', signals_text):
            signal_title = m.group(1).strip()
            signal_desc = m.group(2).strip()
            if signal_title and signal_title != '信号':
                meta['highlights'].append({
                    'title': signal_title,
                    'desc': signal_desc[:80]
                })

    # Fallback highlights from bold items in first section
    if not meta['highlights']:
        for m in re.finditer(r'\*\*(.+?)\*\*', content[:5000]):
            text = m.group(1).strip()
            if 8 < len(text) < 60 and not text.startswith('|') and not text.startswith('#'):
                meta['highlights'].append({'title': text, 'desc': ''})
                if len(meta['highlights']) >= 4:
                    break

    return meta

def scan_reports():
    """Scan reports directory and build registry."""
    reports = []
    pattern = os.path.join(REPORTS_DIR, '*.md')
    for filepath in sorted(glob.glob(pattern), reverse=True):
        meta = extract_metadata(filepath)
        if meta and meta['date']:
            reports.append(meta)
    return reports

def build_index(reports):
    """Inject report registry into index.html."""
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    reports_json = json.dumps(reports, ensure_ascii=False, indent=2)
    html = html.replace('REPORTS_JSON_PLACEHOLDER', reports_json)

    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ Built index.html with {len(reports)} reports")
    for r in reports:
        print(f"   📄 {r['date']} | {r['word_count']}字 | {len(r['sections'])}板块 | {len(r['highlights'])}信号")

if __name__ == '__main__':
    reports = scan_reports()
    build_index(reports)
