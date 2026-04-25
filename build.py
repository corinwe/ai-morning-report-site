#!/usr/bin/env python3
"""
Build script for AI Morning Report site.
Scans reports/ directory, extracts structured metadata, injects into HTML templates.
Generates TTS audio for reports that don't have one yet.
Always reads from .template files and writes to .html files.
"""
import os
import re
import json
import glob
import subprocess
import asyncio

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(SITE_DIR, 'reports')
AUDIO_DIR = os.path.join(SITE_DIR, 'audio')
INDEX_TEMPLATE = os.path.join(SITE_DIR, 'index.template.html')
INDEX_OUTPUT = os.path.join(SITE_DIR, 'index.html')
REPORT_TEMPLATE = os.path.join(SITE_DIR, 'report.template.html')
REPORT_OUTPUT = os.path.join(SITE_DIR, 'report.html')
PLACEHOLDER = 'REPORTS_JSON_PLACEHOLDER'
TTS_VOICE = 'zh-CN-YunyangNeural'  # Professional male voice for news

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
        'has_audio': False,
    }

    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', meta['file'])
    if date_match:
        meta['date'] = date_match.group(1)

    # Check if audio exists
    audio_path = os.path.join(AUDIO_DIR, meta['date'] + '.mp3')
    meta['has_audio'] = os.path.exists(audio_path)

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

def md_to_speech_text(filepath):
    """Convert markdown report to clean speech text for TTS."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract date from filename
    basename = os.path.basename(filepath)
    date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', basename)
    if not date_match:
        return None

    year, month, day = date_match.groups()
    speech = f"全球AI晨报，{year}年{int(month)}月{int(day)}日。"

    # Remove the title line and horizontal rules
    content = re.sub(r'^# .+\n', '', content)
    content = re.sub(r'^---+\s*$', '', content, flags=re.MULTILINE)

    # Process section by section
    sections = re.split(r'^## ', content, flags=re.MULTILINE)

    for section in sections:
        if not section.strip():
            continue

        # Get section title (first line)
        lines = section.strip().split('\n')
        title = lines[0].strip()
        title = re.sub(r'\*\*', '', title)  # Remove bold markers
        title = re.sub(r'【.*?】', '', title)  # Remove bracket tags

        # Add section intro
        section_num_match = re.match(r'[一二三四五六七八九十]、(.+)', title)
        if section_num_match:
            speech += f"\n\n{title}。"
        else:
            speech += f"\n\n{title}。"

        # Process subsections
        body = '\n'.join(lines[1:])
        subsections = re.split(r'^### ', body, flags=re.MULTILINE)

        for subsec in subsections:
            if not subsec.strip():
                continue
            sub_lines = subsec.strip().split('\n')
            sub_title = sub_lines[0].strip()
            sub_title = re.sub(r'\*\*', '', sub_title)

            # Skip pure number titles like "1.1"
            if re.match(r'^\d+\.\d+\s*', sub_title):
                sub_title_clean = re.sub(r'^\d+\.\d+\s*', '', sub_title)
                if sub_title_clean:
                    speech += f"\n{sub_title_clean}。"

            # Process table content into speech
            sub_body = '\n'.join(sub_lines[1:])
            for line in sub_body.split('\n'):
                line = line.strip()
                if not line or line.startswith('|---') or line.startswith('|-'):
                    continue
                if line.startswith('|') and line.endswith('|'):
                    # Parse table row
                    cells = [c.strip() for c in line.split('|')[1:-1]]
                    # Skip header rows with bold markers
                    if all(re.match(r'\*\*.*\*\*', c) for c in cells if c):
                        # Read header as context
                        headers = [re.sub(r'\*\*', '', c) for c in cells if c]
                        continue
                    # Read data rows
                    clean_cells = [re.sub(r'\*\*', '', c) for c in cells if c]
                    if clean_cells:
                        speech += '，'.join(clean_cells) + '。'
                elif line.startswith('>'):
                    # Blockquote - read as emphasis
                    line = re.sub(r'^>\s*', '', line)
                    line = re.sub(r'\*\*.*?\*\*', lambda m: m.group(0).replace('**', ''), line)
                    if line.strip():
                        speech += f"\n{line.strip()}。"
                elif line.startswith('- ') or line.startswith('* '):
                    # List items
                    item = re.sub(r'^[-*]\s*', '', line)
                    item = re.sub(r'\*\*', '', item)
                    if item:
                        speech += f"{item}。"

    # Clean up any remaining markdown
    speech = re.sub(r'\*\*', '', speech)
    speech = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', speech)  # Links -> text
    speech = re.sub(r'[#`~]', '', speech)
    speech = re.sub(r'\n{3,}', '\n\n', speech)

    return speech

def generate_tts_for_report(filepath):
    """Generate TTS audio for a single report using edge-tts."""
    basename = os.path.basename(filepath)
    date_match = re.match(r'(\d{4}-\d{2}-\d{2})', basename)
    if not date_match:
        return False

    date_str = date_match.group(1)
    audio_path = os.path.join(AUDIO_DIR, date_str + '.mp3')

    # Skip if audio already exists
    if os.path.exists(audio_path):
        return True

    # Convert markdown to speech text
    speech_text = md_to_speech_text(filepath)
    if not speech_text or len(speech_text.strip()) < 50:
        print(f"   ⚠️ {date_str}: 报告内容太少，跳过TTS生成")
        return False

    # edge-tts has a limit, split if text is too long
    # Max ~5000 chars per request is safe; split by sections
    chunks = []
    if len(speech_text) > 4500:
        parts = speech_text.split('\n\n')
        current_chunk = ''
        for part in parts:
            if len(current_chunk) + len(part) > 4500 and current_chunk:
                chunks.append(current_chunk)
                current_chunk = part
            else:
                current_chunk += '\n\n' + part if current_chunk else part
        if current_chunk:
            chunks.append(current_chunk)
    else:
        chunks = [speech_text]

    try:
        os.makedirs(AUDIO_DIR, exist_ok=True)

        if len(chunks) == 1:
            # Single chunk - direct generation
            result = subprocess.run(
                ['edge-tts', '--voice', TTS_VOICE, '--text', chunks[0],
                 '--write-media', audio_path],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                print(f"   ❌ {date_str}: TTS失败 - {result.stderr[:100]}")
                return False
        else:
            # Multiple chunks - generate parts and concatenate
            temp_files = []
            for i, chunk in enumerate(chunks):
                temp_path = os.path.join(AUDIO_DIR, f'{date_str}_part{i}.mp3')
                result = subprocess.run(
                    ['edge-tts', '--voice', TTS_VOICE, '--text', chunk,
                     '--write-media', temp_path],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode != 0:
                    print(f"   ❌ {date_str} part{i}: TTS失败")
                    # Cleanup temp files
                    for tf in temp_files:
                        if os.path.exists(tf):
                            os.remove(tf)
                    return False
                temp_files.append(temp_path)

            # Concatenate MP3 files (simple binary concat works for MP3)
            with open(audio_path, 'wb') as outfile:
                for tf in temp_files:
                    with open(tf, 'rb') as infile:
                        outfile.write(infile.read())
                    os.remove(tf)

        size_kb = os.path.getsize(audio_path) / 1024
        print(f"   🎙️ {date_str}: TTS生成成功 ({size_kb:.0f}KB)")
        return True

    except subprocess.TimeoutExpired:
        print(f"   ❌ {date_str}: TTS超时")
        return False
    except Exception as e:
        print(f"   ❌ {date_str}: TTS异常 - {e}")
        return False

def generate_all_tts(reports):
    """Generate TTS for reports that don't have audio yet."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    generated = 0
    skipped = 0
    failed = 0

    for r in reports:
        audio_path = os.path.join(AUDIO_DIR, r['date'] + '.mp3')
        if os.path.exists(audio_path):
            skipped += 1
            continue

        md_path = os.path.join(REPORTS_DIR, r['file'])
        if generate_tts_for_report(md_path):
            r['has_audio'] = True
            generated += 1
        else:
            failed += 1

    print(f"\n🎙️ TTS生成完成: {generated}新增, {skipped}已有, {failed}失败")

def build_all(reports):
    reports_json = json.dumps(reports, ensure_ascii=False, indent=2)

    # First run: if templates don't exist, create them from current .html files
    for tpl, out in [(INDEX_TEMPLATE, INDEX_OUTPUT), (REPORT_TEMPLATE, REPORT_OUTPUT)]:
        if not os.path.exists(tpl):
            with open(out, 'r', encoding='utf-8') as f:
                content = f.read()
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
            print(f"Created template: {os.path.basename(tpl)}")

    # Build from templates
    build(INDEX_TEMPLATE, INDEX_OUTPUT, reports_json)
    print(f"✅ Built index.html with {len(reports)} reports")

    build(REPORT_TEMPLATE, REPORT_OUTPUT, reports_json)
    print(f"✅ Built report.html with {len(reports)} reports")

    for r in reports:
        audio_mark = '🎙️' if r['has_audio'] else '  '
        print(f"   {audio_mark} {r['date']} | {r['word_count']}字 | {len(r['sections'])}板块 | {len(r['highlights'])}信号")

if __name__ == '__main__':
    reports = scan_reports()

    # Generate TTS audio for reports without audio
    generate_all_tts(reports)

    # Re-scan to update has_audio flags
    reports = scan_reports()

    build_all(reports)
