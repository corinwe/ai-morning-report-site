#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 AI 晨报音频时长，防止 13 分钟以上的“全文朗读”进入推送。"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def duration(path: Path) -> float:
    r = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or 'ffprobe failed')
    return float(r.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('path', help='mp3 path')
    ap.add_argument('--max', type=float, default=720, help='max seconds (default 720 = 12min)')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    p = Path(args.path)
    if not p.exists():
        print(f'❌ 音频不存在：{p}')
        return 1
    try:
        sec = duration(p)
    except Exception as e:  # noqa: BLE001
        print(f'❌ 无法读取音频时长：{e}')
        return 1
    ok = sec <= args.max
    out = {'path': str(p), 'seconds': round(sec, 1), 'minutes': round(sec / 60, 2), 'max_seconds': args.max, 'ok': ok}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"{'✅' if ok else '⛔'} {p.name}: {out['minutes']} 分钟（上限 {args.max/60:.1f} 分钟）")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
