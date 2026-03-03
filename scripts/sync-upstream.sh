#!/bin/bash
# sync-upstream.sh — Safely merge upstream GPT Researcher changes.
# Usage: bash ~/.claude/skills/gpt-researcher/scripts/sync-upstream.sh
#
# This is the ONLY script that touches vendor/gpt-researcher, and only via git merge.
# If merge conflicts occur, it stops and asks the human to resolve.
set -euo pipefail

VENDOR_DIR="$HOME/cc/vendor/gpt-researcher"
VENV_PIP="$HOME/.local/share/gpt-researcher/venv/bin/pip"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== GPT Researcher Upstream Sync ==="
echo ""

# 1. Verify vendor dir
if [ ! -d "$VENDOR_DIR/.git" ]; then
  echo "ERROR: vendor/gpt-researcher is not a git repo"
  exit 1
fi

# 2. Record version before
cd "$VENDOR_DIR"
VERSION_BEFORE=$(git describe --tags --always 2>/dev/null || git rev-parse --short HEAD)
echo "Current version: $VERSION_BEFORE"

# 3. Ensure upstream remote exists
if ! git remote | grep -q '^upstream$'; then
  echo "Adding upstream remote..."
  git remote add upstream https://github.com/assafelovic/gpt-researcher.git
fi

# 4. Fetch upstream
echo "Fetching upstream..."
git fetch upstream

# 5. Show what's new
UPSTREAM_HEAD=$(git rev-parse upstream/master 2>/dev/null || git rev-parse upstream/main 2>/dev/null)
LOCAL_HEAD=$(git rev-parse HEAD)

if [ "$UPSTREAM_HEAD" = "$LOCAL_HEAD" ]; then
  echo "Already up to date. Nothing to merge."
  exit 0
fi

# 6. Determine upstream branch
UPSTREAM_BRANCH="master"
if ! git rev-parse upstream/master >/dev/null 2>&1; then
  UPSTREAM_BRANCH="main"
fi

COMMITS_BEHIND=$(git rev-list HEAD.."upstream/$UPSTREAM_BRANCH" | wc -l | tr -d ' ')
echo "Commits behind upstream/$UPSTREAM_BRANCH: $COMMITS_BEHIND"
echo ""
echo "Merging upstream/$UPSTREAM_BRANCH..."

if ! git merge "upstream/$UPSTREAM_BRANCH" --no-edit; then
  echo ""
  echo "MERGE CONFLICT detected."
  echo "Please resolve conflicts manually in: $VENDOR_DIR"
  echo "Then run:"
  echo "  cd $VENDOR_DIR && git add -A && git merge --continue"
  echo "  bash $SCRIPT_DIR/sync-upstream.sh  # re-run to complete"
  exit 1
fi

# 7. Record version after
VERSION_AFTER=$(git describe --tags --always 2>/dev/null || git rev-parse --short HEAD)
echo ""
echo "Merge complete: $VERSION_BEFORE -> $VERSION_AFTER"

# 8. Reinstall to pick up new deps
echo ""
echo "Reinstalling gpt-researcher (picks up new dependencies)..."
"$VENV_PIP" install -e "$VENDOR_DIR" -q
"$VENV_PIP" install -U ddgs -q  # Re-add our extra dep
echo "Reinstall: OK"

# 9. Health check
echo ""
echo "Running health check..."
bash "$SCRIPT_DIR/health.sh"

echo ""
echo "=== Sync Complete ==="
echo "  Before: $VERSION_BEFORE"
echo "  After:  $VERSION_AFTER"
echo "  Commits merged: $COMMITS_BEHIND"
