# kurrentpages.org

Static website for the benchmark: an overview page and the leaderboard. A
Cloudflare Worker serves `public/` on `kurrentpages.org` and redirects
`www.kurrentpages.org`, `kurrentpages.com`, and `www.kurrentpages.com` there
with a 301.

The pages read `/leaderboard.json`. The deploy script copies it from
`leaderboard/leaderboard.json`, so the site always shows the data of the
commit you deploy. The copy is not tracked.

## Preview

```sh
cp leaderboard/leaderboard.json site/public/leaderboard.json
python3 -m http.server --directory site/public 8080
```

## Deploy

Run from the repository root, on `main`, after the leaderboard data changes:

```sh
scripts/deploy_site.sh
```

Then check:

```sh
curl -sI https://kurrentpages.org/ | head -1
curl -sI https://kurrentpages.com/leaderboard/ | grep -i '^location'
```

Rollback: `npx wrangler rollback --config site/wrangler.toml`.

Font: STIX Two Text, SIL Open Font License (`public/assets/fonts/OFL.txt`).
