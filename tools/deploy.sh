#!/usr/bin/env bash
# Build and publish to GitHub Pages (main:/docs). Usage: tools/deploy.sh [base-url]
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="${1:-https://calc.offctrl.ai}"
DOMAIN="${BASE#https://}"; DOMAIN="${DOMAIN%%/*}"
echo "Building for $BASE"
SITE_BASE="$BASE" INDEXNOW_KEY="${INDEXNOW_KEY:-}" python3 build.py
rm -rf docs && cp -r site docs
printf '%s\n' "$DOMAIN" > docs/CNAME
git add -A
git -c user.email=agent@okou.local -c user.name=Okou commit -qm "Rebuild for $BASE" || echo "(nothing to commit)"
git push origin main
echo "Pushed. Redirect check: curl -sI https://singletonye.github.io/paycheck-calculator/ | grep -i location"
