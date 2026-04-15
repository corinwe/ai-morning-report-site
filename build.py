#!/usr/bin/env python3
"""
Build script for AI Morning Report site.
Scans reports/ directory, extracts structured metadata, injects into HTML templates.
Always reads from .template files and writes to .html files.
"""
import os
import re
import json
import glob

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(SITE_DIR, 'reports')
INDEX_TEMPLATE = os.path.join(SITE_DIR, 'index.template.html')
INDEX_OUTPUT = os.path.join(SITE_DIR, 'index.html')
REPORT_TEMPLATE = os.path.join(SITE_DIR, 'report.template.html')
REPORT_OUTPUT = os.path.join(SITE_DIR, 'report.html')
PLACEHOLDER = 'REPORTS_JSON_PLACEHOLDER'

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
        'highlights': [],
        'sections': [],
        'word_count': 0,
    }

    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', meta['file'])
    if date_match:
        meta['date'] = date_match.group(1)

    text_only = re.sub(r'[#*`\[\]|>]', '', content)
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text_only))
    en_words = len(re.findall(r'[a-zA-Z]+', text_only))
    meta['word_count'] = cn_chars + en_words

    for m in re.finditer(r'^## ([^\n]+)', content, re.MULTILINE):
        title = m.group(1).strip()
        title = re.sub(r'\*\*', '', title)
        anchor = re.sub(r'[^\w\u4e00-\u9fff]+', '-', title).lower().strip('-')
        meta['sections'].append({'title': title, 'anchor': anchor})

    conclusion_match = re.search(
        r'>\s*\*\*本期晨报核心结论[：:]\*\*\s*(.+?)(?:\n\n|\n[^>]|\Z)', content, re.DOTALL
    )
    if conclusion_match:
        summary = conclusion_match.group(1).strip()
        summary = re.sub(r'\n', ' ', summary)
        summary = re.sub(r'\s+', ' ', summary)
        meta['summary'] = summary[:200]
    else:
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

    signal_section = re.search(
        r'##\s*五.*?关键信号(.+?)(?=\n## |\Z)', content, re.DOTALL
    )
    if signal_section:
        signals_text = signal_section.group(1)
        for m in re.finditer(r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|', signals_text):
            signal_title = m.group(1).strip()
            signal_desc = m.group(2).strip()
            if signal_title and signal_title != '信号':
                meta['highlights'].append({'title': signal_title, 'desc': signal_desc[:80]})

    if not meta['highlights']:
        for m in re.finditer(r'\*\*(.+?)\*\*', content[:5000]):
            text = m.group(1).strip()
            if 8 < len(text) < 60 and not text.startswith('|') and not text.startswith('#'):
                meta['highlights'].append({'title': text, 'desc': ''})
                if len(meta['highlights']) >= 4:
                    break

    return meta

def scan_reports():
    reports = []
    pattern = os.path.join(REPORTS_DIR, '*.md')
    for filepath in sorted(glob.glob(pattern), reverse=True):
        meta = extract_metadata(filepath)
        if meta and meta['date']:
            reports.append(meta)
    return reports

def build(template_path, output_path, reports_json):
    """Read template, inject data, write output."""
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()
    html = html.replace(PLACEHOLDER, reports_json)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

def build_all(reports):
    reports_json = json.dumps(reports, ensure_ascii=False, indent=2)

    # First run: if templates don't exist, create them from current .html files
    # by restoring the placeholder (replace the injected JSON back)
    for tpl, out in [(INDEX_TEMPLATE, INDEX_OUTPUT), (REPORT_TEMPLATE, REPORT_OUTPUT)]:
        if not os.path.exists(tpl):
            # Read current built file and find the injected data to reverse
            with open(out, 'r', encoding='utf-8') as f:
                content = f.read()
            # Replace the injected JSON array back to placeholder
            # Find the const assignment and replace its value
            if 'const REPORTS = [' in content:
                content = re.sub(
                    r'const REPORTS = \[.*?\];',
                    'const REPORTS = ' + PLACEHOLDER + ';',
                    content, flags=re.DOTALL
                )
            if 'const REPORT_LIST = [' in content:
                content = re.sub(
                    r'const REPORT_LIST = \[.*?\];',
                    'REPORT_LIST = ' + PLACEHOLDER + ';',
                    content, flags=re.DOTALL
                )
            with open(tpl, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"📝 Created template: {os.path.basename(tpl)}")

    # Build from templates
    build(INDEX_TEMPLATE, INDEX_OUTPUT, reports_json)
    print(f"✅ Built index.html with {len(reports)} reports")

    build(REPORT_TEMPLATE, REPORT_OUTPUT, reports_json)
    print(f"✅ Built report.html with {len(reports)} reports")

    for r in reports:
        print(f"   📄 {r['date']} | {r['word_count']}字 | {len(r['sections'])}板块 | {len(r['highlights'])}信号")

if __name__ == '__main__':
    reports = scan_reports()
    build_all(reports)
