#!/bin/bash
# 将当前项目迁移到新仓库（不带 Git 历史）

NEW_REPO_URL="https://github.com/YoWuwuuuw/github-repo-report-bot.git"

echo "? 开始迁移到新仓库..."
echo "   新仓库地址: $NEW_REPO_URL"
echo ""

# 检查是否有未提交的更改（排除迁移脚本本身）
UNCOMMITTED=$(git status --porcelain | grep -v "migrate_to_new_repo.sh" || true)
if [ -n "$UNCOMMITTED" ]; then
    echo "??  检测到未提交的更改，请先提交或暂存"
    echo "   执行: git add . && git commit -m 'your message'"
    exit 1
fi

# 备份当前的 .git 目录（以防万一）
echo "? 备份当前 Git 配置..."
if [ -d .git ]; then
    cp -r .git .git.backup
    echo "   ? 已备份到 .git.backup"
fi

# 删除 .git 目录
echo "??  删除 Git 历史记录..."
rm -rf .git

# 重新初始化 Git
echo "? 重新初始化 Git 仓库..."
git init

# 添加所有文件
echo "? 添加文件..."
git add .

# 创建初始提交
echo "? 创建初始提交..."
git commit -m "Initial commit: GitHub Repo Report Bot

- Automated GitHub repository analysis tool
- AI-powered PR analysis using Qwen
- Support for Issues, PRs, and Discussions
- Configurable via GitHub Secrets"

# 添加新的远程仓库
echo "? 添加远程仓库..."
git remote add origin "$NEW_REPO_URL"

# 设置默认分支为 main
echo "? 设置分支为 main..."
git branch -M main

# 推送到新仓库
echo "? 推送到新仓库..."
git push -u origin main

echo ""
echo "? 迁移完成！"
echo ""
echo "? 如果推送失败，可能需要："
echo "   1. 检查新仓库是否已创建"
echo "   2. 确认有推送权限"
echo "   3. 如果仓库不为空，使用: git push -u origin main --force"
echo ""
echo "? 如果需要恢复原 Git 历史，可以："
echo "   rm -rf .git && mv .git.backup .git"

