---
read_when: You change repository visibility, export the repository, or add files that name people, hosts, or addresses.
---

# Release boundary scan (benchmark v1.0, blocker B3)

**Status: release-v1 working tree clean; git history has hits.** Scanned
2026-11-06 on the local branch `release-v1`. Publish from a fresh
single-commit export of this branch, not from the existing history. The owner
decides (see "Recommendation").

## Method

1. `uv run python scripts/check_boundary.py`: `benchmark boundary: OK`.
2. `uv run python scripts/scan_release.py --terms <private terms file>` over the
   working tree, every blob of all 83 commits on every ref (`main`,
   `origin/main`, `origin/feat/deletion-marker`), and every commit message and
   author identity.
   - Built-in classes: e-mail addresses (not `example.*` or GitHub noreply),
     Tailscale addresses (the 100.64/10 block), and private paths (macOS and
     Linux home directories, the owner's ops folder).
   - Private terms: the surnames, first names, and business domain of the
     keyers and reviewers; the owner's surname and domain; the review host;
     the tailnet host names and MagicDNS suffix. The terms file stays outside
     the repository, and the script prints labels only, so this report names
     nobody.
3. Manual review of the B3 file list (see "Manual review").

## Hits

"Commits" counts the commits whose tree contains the hit. Every hit was also
present at the start of the branch (`ec54b30`), so no hit exists only in
history.

| Class (label) | File | Commits (first–last) | Fix on `release-v1` |
|---|---|---|---|
| Tailscale address | `configs/engines.yml` (2 lines) | 81 (`a55c7f3`–`ec54b30`) | `http://localhost:8080/v1`, as for the other VLM engines (A1) |
| Tailscale address | `deploy/evo-vlm/README.md` (4 lines) | 81 (`a55c7f3`–`ec54b30`) | `<user>@<evo-host>` and `http://<evo-host>:8080/v1` (A1) |
| Tailscale address | `scripts/dev_ablations.py` (1 line) | 39 (`4fb93da`–`ec54b30`) | default `--base-url http://localhost:8080/v1` (A1) |
| E-mail address, owner surname | `hosting/pilot-review/src/worker.js` (1 line) | 54 (`78880b0`–`ec54b30`) | contact line now asks the reviewer to reply to the invitation e-mail (A1) |
| Owner domain, review host | `hosting/pilot-review/wrangler.jsonc` | 54 (`78880b0`–`ec54b30`) | placeholder route `review.example.org`; the deployed route moves to the untracked `wrangler.local.jsonc` (A1) |
| Owner domain, review host | `hosting/pilot-review/README.md` (7 lines) | 54 (`78880b0`–`ec54b30`) | `<review-host>`, `<team>` (A1) |
| Owner domain, review host | `docs/FABRICATION_PILOT.md` (3 lines) | 54 (`78880b0`–`ec54b30`) | `<review-host>`; "the owner's address" (A1) |
| Keyer 1 surname | `BENCHMARK_PROTOCOL.md` (3 lines) | 81 (`a55c7f3`–`ec54b30`) | role "keyer 1" (A2, O6) |
| Keyer 1 business domain | `BENCHMARK_PROTOCOL.md` (1 line) | 71 (`93d6ce3`–`ec54b30`) | role "keyer 1" (A2, O6) |
| Keyer 2 surname | `BENCHMARK_PROTOCOL.md` (5 lines) | 81 (`a55c7f3`–`ec54b30`) | role "keyer 2" (A2, O6) |
| Keyer 1 first name and surname | `docs/FABRICATION_PILOT.md` (9 lines) | 12 (`afa2fd0`–`ec54b30`) | role "reviewer 1" (A2, O6) |
| Keyer 2 first name and surname | `docs/FABRICATION_PILOT.md` (4 lines) | 12 (`afa2fd0`–`ec54b30`) | role "reviewer 2" (A2, O6) |
| Review host in a commit message | message of `78880b0` | 1 | history only; cannot change without a rewrite |

Reviewed and kept:

- `deploy/evo-vlm/README.md`: "GMKtec EVO-X2" is the hardware product name, not
  a host name. The term was narrowed to the two tailnet host names; no hit.
- `hosting/pilot-review/test/worker.test.mjs`: `pruefung.example.com` is a test
  hostname on a reserved example domain.
- `hosting/pilot-review/wrangler.jsonc`: the KV namespace ID stays. It is an
  account resource ID, not a credential.
- `BENCHMARK_PROTOCOL.md` §10, 2026-07-28: the keying budget figures stay. They
  are an amendment's cost reasoning, not an invoice or an agreement.
- Commit identities: one author and committer, a GitHub noreply address.
- `configs/prompts/vendor/deepseek_ocr_free.txt` is the only path that exists in
  history but not in the working tree. It is a vendor prompt that `f671034`
  dropped from the base-model screen. No private content.
- No keyer 3 or keyer 4 surname, no tailnet host name, no MagicDNS suffix, and no
  private home path appears in any commit.

## Manual review (B3 file list)

| File | Result |
|---|---|
| `BENCHMARK_PROTOCOL.md` §2, §10, §11 | keyer names replaced by roles (A2) |
| `configs/engines.yml`, `scripts/dev_ablations.py`, `deploy/evo-vlm/README.md` | Tailscale addresses replaced (A1) |
| `scripts/mail_packet.py` | builds a mail-sized packet copy from a private pilot directory; no names, addresses, or packet data |
| `scripts/prepare_fabrication_pilot.py` | reads private run dirs; default pages are silver dev pages, not gold |
| `scripts/pilot_site.py` | builds worker assets and reads the KV store through wrangler; no addresses |
| `hosting/pilot-review/` | contact address and deployed host removed (A1); `assets/`, `.dev.vars`, and `wrangler.local.jsonc` are gitignored |
| `harness/pilot_*.html`, `harness/pilot_*.js` | no names or addresses |

## Owner organization made public (O7)

On 2026-11-06 the owner chose the Hugging Face organization `13fragments` (O7),
so the organization name now appears in public files on purpose. The private
terms file no longer lists the owner domain. The review host and every e-mail
address are still scanned. The submission address `kurrent-pages@13fragments.com` (owner
decision, 2026-11-06) is the one allowed address: the terms file lists it on an
`allow` line, and `scan_release.py` removes allowed text before it matches.

## Rescan after A1 and A2

After A2, `scripts/scan_release.py --working-tree-only` reports
`working tree: 0 (label, file) hits`, and `check_boundary.py` reports OK.

## Recommendation

The fixes clean the working tree only. Every commit before `release-v1` still
holds the Tailscale address, the keyer names, the owner's contact address, and
the review host. Making the current repository public as it is would publish
all of them.

Recommended: publish a fresh single-commit export of `release-v1` to a new
public repository (or to the existing repository after its history is
replaced), and keep the current repository private as the working history.
`OWNER_STEPS.md` gives the commands. A history rewrite of the existing
repository (for example with `git filter-repo`) is the alternative.

Both options break the commit hashes that §10 and the decision records cite
(for example `da5ec8c`, the scoring code of the gold runs). The private
repository keeps them resolvable. The public export cites its release tag
`v1.0.0`, and the §10 entries keep their private hashes as provenance.

**Owner decision (2026-11-06):** fresh single-commit export to a new public
repository, `13fragments/kurrent-pages`.
