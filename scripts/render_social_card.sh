#!/usr/bin/env bash
# Renders the 1200x630 link-preview image for kurrentpages.org.
#   site/social/og-image.html -> site/public/og-image.png
# Set CHROME to the Chrome binary if it is not on the default path.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
if [ -z "${CHROME:-}" ]; then
  case "$(uname -s)" in
    Darwin) CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ;;
    *) CHROME="$(command -v google-chrome || command -v chromium)" ;;
  esac
fi

"$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1200,630 --virtual-time-budget=2000 \
  --screenshot="$root/site/public/og-image.png" "file://$root/site/social/og-image.html" 2>/dev/null
echo "rendered site/public/og-image.png"
