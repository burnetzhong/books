#!/bin/bash
# 书房仓库自动同步：拉取网页上保存的新标记，提交本地改动并推送到 GitHub。
# 用法：autosync.sh        提交 + 拉取 + 推送
#      autosync.sh pull   只拉取
# 出错时只记日志（log/autosync.log），不打断正在进行的工作。
cd "$(dirname "$0")/.." || exit 0
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
mkdir -p log
LOG=log/autosync.log
note() { echo "$(date '+%F %T') $*" >> "$LOG"; }

if [ "$1" != "pull" ]; then
  git add -A
  if ! git diff --cached --quiet; then
    files=$(git diff --cached --name-only | sed 's|.*/||' | head -3 | awk '{printf "%s%s", (NR>1 ? "、" : ""), $0}')
    n=$(git diff --cached --name-only | wc -l | tr -d ' ')
    [ "$n" -gt 3 ] && files="$files 等 $n 个文件"
    git commit -q -m "自动保存：$files" || note "提交失败"
  fi
fi

if ! git pull --rebase -q 2>>"$LOG"; then
  git rebase --abort 2>/dev/null
  note "拉取失败（可能有冲突或网络问题），本地改动已保留，需要手动处理"
  exit 0
fi

if [ "$1" != "pull" ] && [ -n "$(git log '@{u}..' --oneline 2>/dev/null)" ]; then
  git push -q 2>>"$LOG" || note "推送失败，下次同步会重试"
fi
exit 0
