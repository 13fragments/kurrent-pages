#!/usr/bin/env bash
# Deploys the kurrentpages.org website with the leaderboard data of this commit.
set -euo pipefail
cd "$(dirname "$0")/.."
cp leaderboard/leaderboard.json site/public/leaderboard.json
wrangler deploy --config site/wrangler.toml
