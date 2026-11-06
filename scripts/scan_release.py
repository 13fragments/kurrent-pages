#!/usr/bin/env python3
"""Scan the working tree and the full git history for private material.

Built-in classes: e-mail addresses (except example and noreply domains),
Tailscale addresses (100.64.0.0/10), and private home paths. Private terms
(names, host names, domains) come from a file outside this repository:
one `label<TAB>regex` per line. Lines labelled `allow` name text that is public
on purpose (for example the submission address); it is removed from each line
before the other patterns run. The output names the term label, never the
matched text, so the report can be published.

  uv run python scripts/scan_release.py --terms ~/private/scan_terms.tsv

Exit 1 when the working tree has a hit. The working-tree scan skips files that
`git archive` leaves out (`export-ignore`), because a fresh export does not
publish them. History hits are reported only: removing them needs a history
rewrite or a fresh export.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = "scripts/scan_release.py"
BUILTIN = {
    "email": r"[A-Za-z0-9._%+-]+@(?!(?:[a-z0-9-]+\.)*example\.(?:org|com|net)\b)"
    r"(?!users\.noreply\.github\.com\b)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}",
    "tailscale-ip": r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b",
    "private-path": r"/Users/[A-Za-z]|/home/[a-z][a-z0-9_-]*/|~/ops\b",
}


ALLOW: list[re.Pattern] = []


def load_terms(path: Path | None) -> dict[str, re.Pattern]:
    global ALLOW
    terms = {label: re.compile(regex) for label, regex in BUILTIN.items()}
    if path is None:
        return terms
    allowed = []
    for line in path.expanduser().read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            label, regex = line.split("\t", 1)
            if label == "allow":
                allowed.append(regex)
            else:
                terms[label] = re.compile(regex)
    ALLOW = [re.compile(regex) for regex in allowed]
    return terms


def without_allowed(text: str) -> str:
    for pattern in ALLOW:
        text = pattern.sub("", text)
    return text


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode("utf-8", errors="replace")


def export_ignored(paths: list[str]) -> set[str]:
    """Paths that `git archive` leaves out (`export-ignore` in .gitattributes)."""
    out = subprocess.run(
        ["git", "check-attr", "-z", "--stdin", "export-ignore"], cwd=ROOT, check=True,
        capture_output=True, input="\0".join(paths).encode(),
    ).stdout.decode().split("\0")
    return {out[i] for i in range(0, len(out) - 2, 3) if out[i + 2] == "set"}


def tree_hits(ref: str, terms: dict[str, re.Pattern]) -> dict[tuple[str, str], int]:
    """(label, path) -> matching line count for one commit, or the exported tree for ''."""
    paths = git("ls-files", "-z") if not ref else git("ls-tree", "-r", "-z", "--name-only", ref)
    listed = list(filter(None, paths.split("\0")))
    skipped = export_ignored(listed) if not ref else set()
    hits: dict[tuple[str, str], int] = defaultdict(int)
    for path in listed:
        if path == SELF or path in skipped:
            continue  # the built-in patterns match their own source
        try:
            blob = (ROOT / path).read_bytes() if not ref else subprocess.run(
                ["git", "show", f"{ref}:{path}"], cwd=ROOT, check=True, capture_output=True
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            continue
        if b"\0" in blob[:8000]:
            continue  # binary
        for line in blob.decode("utf-8", errors="replace").splitlines():
            line = without_allowed(line)
            for label, pattern in terms.items():
                if pattern.search(line):
                    hits[(label, path)] += 1
    return hits


def message_hits(terms: dict[str, re.Pattern]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = defaultdict(list)
    for record in git("log", "--all", "--format=%h%x00%an <%ae>%x00%cn <%ce>%x00%B%x01").split("\x01"):
        if not record.strip():
            continue
        commit, *fields = record.strip().split("\0")
        text = without_allowed("\n".join(fields))
        for label, pattern in terms.items():
            if pattern.search(text):
                hits[label].append(commit)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terms", type=Path, help="private label<TAB>regex file")
    parser.add_argument(
        "--working-tree-only", action="store_true", help="skip the history scan"
    )
    args = parser.parse_args()
    terms = load_terms(args.terms)

    working = tree_hits("", terms)
    print(f"working tree: {len(working)} (label, file) hits")
    for (label, path), count in sorted(working.items()):
        print(f"  {label:18} {path} ({count} lines)")

    if args.working_tree_only:
        return 1 if working else 0
    commits = git("rev-list", "--all", "--reverse").split()
    history: dict[tuple[str, str], list[str]] = defaultdict(list)
    for commit in commits:
        for key in tree_hits(commit, terms):
            history[key].append(commit[:7])
    print(f"history: {len(commits)} commits, {len(history)} (label, file) hits")
    for (label, path), found in sorted(history.items()):
        state = "at HEAD" if (label, path) in working else "history only"
        print(
            f"  {label:18} {path}: {len(found)} commits, first {found[0]}, "
            f"last {found[-1]} ({state})"
        )

    messages = message_hits(terms)
    print(f"commit messages and identities: {sum(map(len, messages.values()))} hits")
    for label, found in sorted(messages.items()):
        print(f"  {label:18} {len(found)} commits: {' '.join(found)}")

    ever = set(filter(None, git("log", "--all", "--name-only", "--format=").splitlines()))
    current = set(filter(None, git("ls-files").splitlines()))
    removed = sorted(ever - current)
    print(f"paths in history but not in the working tree: {len(removed)}")
    for path in removed:
        print(f"  {path}")
    return 1 if working else 0


if __name__ == "__main__":
    raise SystemExit(main())
