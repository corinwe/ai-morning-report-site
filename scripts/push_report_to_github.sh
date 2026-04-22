#!/bin/bash
# AI晨报推送脚本 - 将指定日期的晨报推送到GitHub
# 用法: bash scripts/push_report_to_github.sh YYYY-MM-DD
# Token来源: 1.环境变量GITHUB_TOKEN 2./workspace/.github_token文件（必须存在其一）
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

# Token获取: 环境变量 > 文件（必须提供其中一种）
if [ -n "$GITHUB_TOKEN" ]; then
    TOKEN="$GITHUB_TOKEN"
elif [ -f "/workspace/.github_token" ]; then
    TOKEN=$(cat /workspace/.github_token | tr -d '[:space:]')
else
    echo "错误：未找到GitHub Token。请设置GITHUB_TOKEN环境变量或创建/workspace/.github_token文件"
    exit 1
fi

REPO_DIR="/tmp/ai-morning-report-site"
GITHUB_USER="corinwe"
REPO_NAME="ai-morning-report-site"
BRANCH="main"

echo "步骤1: 准备仓库..."
rm -rf "$REPO_DIR"
git clone "https://oauth2:${TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git" "$REPO_DIR" 2>&1
echo "仓库克隆成功"

echo "步骤2: 复制报告文件..."
cp "$REPORT_FILE" "${REPO_DIR}/reports/${DATE}.md"
echo "报告已复制到 reports/${DATE}.md"

echo "步骤3: 构建网站..."
cd "$REPO_DIR"
python3 build.py
echo "网站构建完成"

echo "步骤4: 推送到GitHub..."
git config user.name "corinwe"
git config user.email "corinwe@users.noreply.github.com"
git add -A
git commit -m "feat: add ${DATE} AI morning report" || echo "没有变更需要提交"
git remote set-url origin "https://oauth2:${TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"
git push origin "$BRANCH"
git remote set-url origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
echo "推送成功"

echo ""
echo "晨报 ${DATE} 已成功发布到 GitHub Pages！"
