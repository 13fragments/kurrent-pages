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

The GitHub workflow `.github/workflows/deploy-site.yml` deploys on every push
to `main` that changes `leaderboard/leaderboard.json`, `site/`, or the deploy
script. It then checks that the live `/leaderboard.json` has the same number of
ranked rows. To deploy by hand, run the workflow from the Actions tab, or run
this from the repository root on `main`:

```sh
scripts/deploy_site.sh
```

The workflow needs two repository secrets:

- `CLOUDFLARE_API_TOKEN`: a token from the "Edit Cloudflare Workers" template,
  limited to this account and the `kurrentpages.org` and `kurrentpages.com`
  zones.
- `CLOUDFLARE_ACCOUNT_ID`: the account that owns the `kurrentpages` Worker.

Check after a deploy:

```sh
curl -sI https://kurrentpages.org/ | head -1
curl -sI https://kurrentpages.com/leaderboard/ | grep -i '^location'
```

Rollback: `npx wrangler rollback --config site/wrangler.toml`.

## Link preview image

`public/og-image.png` is the 1200x630 image for social link previews. Its
source is `social/og-image.html`. After you change the source, render the
image again from the repository root:

```sh
scripts/render_social_card.sh
```

Font: STIX Two Text, SIL Open Font License (`public/assets/fonts/OFL.txt`).
