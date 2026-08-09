#!/usr/bin/env python3
"""
从晨报原文生成语音 — 物理化修复 2026-08-09
================================================
问题：AI晨报 cron 步骤3 让 LLM "生成语音摘要"，Agent 每次自己改写一段摘要，
导致语音内容 ≠ 原文。本脚本绕过 LLM：
  1. 读取 reports/{date}.md 原文
  2. md_to_speech_text() 转换为朗读文本（逐字保留原文）
  3. edge-tts 生成 mp3

用法：
  python3 scripts/tts_from_report.py 2026-08-09
  python3 scripts/tts_from_report.py --all     # 重生成所有缺失/全部语音
"""
import os
import re
import sys
import glob
import subprocess

SITE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(SITE_DIR, 'reports')
AUDIO_DIR = os.path.join(SITE_DIR, 'audio')
TTS_VOICE = os.environ.get('TTS_VOICE', 'zh-CN-XiaoxiaoNeural')

sys.path.insert(0, SITE_DIR)
from build import md_to_speech_text  # noqa: E402


def generate(date_str, force=False):
    md_path = os.path.join(REPORTS_DIR, date_str + '.md')
    audio_path = os.path.join(AUDIO_DIR, date_str + '.mp3')
    if not os.path.exists(md_path):
        print(f"❌ {date_str}: 报告不存在 {md_path}")
        return False
    if os.path.exists(audio_path) and not force:
        print(f"⏭️ {date_str}: 语音已存在（跳过，--force 可覆盖）")
        return True

    speech_text = md_to_speech_text(md_path)
    if not speech_text or len(speech_text.strip()) < 50:
        print(f"⚠️ {date_str}: 转换后文本太短({len(speech_text or '')}字)，跳过")
        return False

    os.makedirs(AUDIO_DIR, exist_ok=True)
    # edge-tts 建议每段 ≤4500 字符；长文按段落分块
    chunks = []
    if len(speech_text) > 4500:
        parts = speech_text.split('\n\n')
        current = ''
        for part in parts:
            if len(current) + len(part) > 4500 and current:
                chunks.append(current)
                current = part
            else:
                current = current + '\n\n' + part if current else part
        if current:
            chunks.append(current)
    else:
        chunks = [speech_text]

    try:
        if len(chunks) == 1:
            result = subprocess.run(
                ['edge-tts', '--voice', TTS_VOICE, '--text', chunks[0],
                 '--write-media', audio_path],
                capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                print(f"❌ {date_str}: TTS失败 - {result.stderr[:200]}")
                return False
        else:
            temp_files = []
            for i, chunk in enumerate(chunks):
                temp_path = os.path.join(AUDIO_DIR, f'{date_str}_part{i}.mp3')
                result = subprocess.run(
                    ['edge-tts', '--voice', TTS_VOICE, '--text', chunk,
                     '--write-media', temp_path],
                    capture_output=True, text=True, timeout=180)
                if result.returncode != 0:
                    print(f"❌ {date_str} part{i}: TTS失败 - {result.stderr[:200]}")
                    for tf in temp_files:
                        if os.path.exists(tf):
                            os.remove(tf)
                    return False
                temp_files.append(temp_path)
            with open(audio_path, 'wb') as out:
                for tf in temp_files:
                    with open(tf, 'rb') as inp:
                        out.write(inp.read())
                    os.remove(tf)

        size_kb = os.path.getsize(audio_path) / 1024
        print(f"✅ {date_str}: 原文语音已生成 ({size_kb:.0f}KB, {len(speech_text)}字)")
        return True
    except subprocess.TimeoutExpired:
        print(f"❌ {date_str}: TTS超时")
        return False
    except Exception as e:
        print(f"❌ {date_str}: TTS异常 - {e}")
        return False


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    force = '--force' in args
    date_args = [a for a in args if a != '--force']

    if date_args and date_args[0] == '--all':
        ok = 0
        for md_path in sorted(glob.glob(os.path.join(REPORTS_DIR, '*.md')), reverse=True):
            m = re.match(r'(\d{4}-\d{2}-\d{2})', os.path.basename(md_path))
            if m and generate(m.group(1), force=True):
                ok += 1
        print(f"\n完成：{ok} 份语音已生成")
        return 0

    for arg in date_args:
        m = re.match(r'(\d{4}-\d{2}-\d{2})', arg)
        if not m:
            print(f"❌ 无效日期: {arg}")
            continue
        generate(m.group(1), force=force)
    return 0


if __name__ == '__main__':
    sys.exit(main())
