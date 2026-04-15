#!/usr/bin/env python3
"""
Build script for AI Morning Report site.
Scans reports/ directory, generates report registry, and injects into index.html.
"""
import os
import re
import json
import glob

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(SITE_DIR, 'reports')
INDEX_FILE = os.path.join(SITE_DIR, 'index.html')

def extract_summary(filepath):
    """Extract a brief summary from the markdown report."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(3000)  # Read first 3000 chars
        # Find the first blockquote or the first paragraph after h1
        # Look for key conclusion block
        match = re.search(r'>\s*\*\*本期晨报核心结论[：:]\*\*\s*(.+?)(?:\n|$)', content)
        if match:
            return match.group(1).strip()[:120]
        # Fallback: first paragraph after h1
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('##') and i > 0:
                # Return lines between h1 and first h2
                summary_lines = []
                for j in range(1, i):
                    l = lines[j].strip()
                    if l and not l.startswith('#') and not l.startswith('---'):
                        summary_lines.append(l)
                    if len(summary_lines) >= 2:
                        break
                if summary_lines:
                    return ' '.join(summary_lines)[:120]
                break
    except Exception:
        pass
    return None

def scan_reports():
    """Scan reports directory and build registry."""
    reports = []
    pattern = os.path.join(REPORTS_DIR, '*.md')
    for filepath in sorted(glob.glob(pattern), reverse=True):
        filename = os.path.basename(filepath)
        date_match = re.match(r'(\d{4}-\d{2}-\d{2})', filename)
        if not date_match:
            continue
        date = date_match.group(1)
        summary = extract_summary(filepath)
        reports.append({
            'date': date,
            'file': filename,
            'summary': summary
        })
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

if __name__ == '__main__':
    reports = scan_reports()
    build_index(reports)
