#!/bin/bash
# AI晨报推送脚本 - 将指定日期的晨报推送到GitHub（含TTS语音同步生成）
# 用法: bash /workspace/push_report_to_github.sh YYYY-MM-DD
# Token来源: 1.环境变量GITHUB_TOKEN 2./workspace/.github_token文件
#
# 核心原则：TTS必须同步生成，音频和报告一起推送，绝不放后台
set -e

DATE=$1
if [ -z "$DATE" ]; then
    echo "错误：请提供日期参数，格式 YYYY-MM-DD"
    exit 1
fi

REPORT_FILE="/workspace/ai_morning_report_${DATE}.md"
if [ ! -f "$REPORT_FILE" ]; then
    echo "错误：报告文件不存在 $REPORT_FILE"
    exit 1
fi

# Token获取
if [ -n "$GITHUB_TOKEN" ]; then
    TOKEN="$GITHUB_TOKEN"
elif [ -f "/workspace/.github_token" ]; then
    TOKEN=$(cat /workspace/.github_token | tr -d '[:space:]')
else
    echo "错误：未找到GitHub Token"
    exit 1
fi

REPO_DIR="/tmp/ai-morning-report-site"
GITHUB_USER="corinwe"
REPO_NAME="ai-morning-report-site"
BRANCH="main"

echo "=========================================="
echo "  AI晨报推送 - ${DATE}"
echo "=========================================="

echo ""
echo "[1/5] 克隆仓库..."
rm -rf "$REPO_DIR"
git clone "https://oauth2:${TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git" "$REPO_DIR" 2>&1
echo "  仓库克隆成功"

echo ""
echo "[2/5] 复制报告文件..."
cp "$REPORT_FILE" "${REPO_DIR}/reports/${DATE}.md"
echo "  报告已复制: reports/${DATE}.md"

echo ""
echo "[3/5] 安装edge-tts..."
pip3 install edge-tts -q 2>/dev/null || pip install edge-tts -q 2>/dev/null || true
echo "  edge-tts就绪"

echo ""
echo "[4/5] 构建网站 + 生成TTS语音（同步执行）..."
cd "$REPO_DIR"
python3 build.py
echo "  构建完成"

echo ""
echo "[5/5] 推送到GitHub..."
git config user.name "corinwe"
git config user.email "corinwe@users.noreply.github.com"
git add -A
git commit -m "feat: add ${DATE} AI morning report" || echo "  没有变更需要提交"
git remote set-url origin "https://oauth2:${TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"
git push origin "$BRANCH"
git remote set-url origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
echo "  推送成功"

# 验证音频文件是否在本次提交中
if [ -f "${REPO_DIR}/audio/${DATE}.mp3" ]; then
    SIZE=$(du -h "${REPO_DIR}/audio/${DATE}.mp3" | cut -f1)
    echo ""
    echo "=========================================="
    echo "  ✅ 晨报 ${DATE} 发布成功！"
    echo "  📄 报告: reports/${DATE}.md"
    echo "  🎙️ 语音: audio/${DATE}.mp3 (${SIZE})"
    echo "  🌐 网址: https://corinwe.github.io/ai-morning-report-site/"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "  ⚠️ 晨报 ${DATE} 发布成功，但语音未生成"
    echo "  报告已上线，语音稍后需手动补充"
    echo "=========================================="
fi
