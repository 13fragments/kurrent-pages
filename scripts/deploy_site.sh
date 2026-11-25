#!/usr/bin/env bash
# Deploys the kurrentpages.org website with the leaderboard data of this commit.
# CI sets WRANGLER; locally it defaults to an installed wrangler.
set -euo pipefail
cd "$(dirname "$0")/.."
cp leaderboard/leaderboard.json site/public/leaderboard.json
${WRANGLER:-wrangler} deploy --config site/wrangler.toml
