"""Loop guard: cut runaway VLM outputs before scoring (protocol §10, 2026-10-16).

A VLM output that stops at the engine's token limit is a runaway generation. On the
dev pages every such output was a repetition loop, and the loop text counted as
both character errors and fabrication. The guard scores such an output without its
trailing loop. It never changes the stored raw output, and outputs below the token
limit are never changed.

Two rules each estimate where the loop starts; the earlier cut wins, because a loop
often begins with inexact repeats before it becomes exactly periodic:
- periodic: the output ends in an exact repetition of a block of at most
  PERIOD_MAX characters, at least three copies and MIN_LOOP_CHARS long. The
  repeated tail is removed; one copy of the block remains.
- line: some line (stripped, with at least one letter or digit) occurs a third
  time. The output is cut at that line's second occurrence, so one copy of the
  repeated lines remains. Lines without a letter or digit (table rules such as `|`
  or `---`, ditto marks) repeat on real pages and do not count (§10, 2026-10-18);
  a runaway of them is cut by the periodic rule.
"""

from __future__ import annotations

PERIOD_MAX = 2000
MIN_LOOP_CHARS = 200
VLM_DEFAULT_MAX_TOKENS = 4096  # VlmOpenAiEngine default when max_tokens is unset


def token_limited(record: dict, engine_description: dict) -> bool:
    """Whether a stored output used all of its engine's completion tokens."""
    usage = (record.get("meta") or {}).get("usage") or {}
    used = usage.get("completion_tokens")
    config = engine_description.get("config") or {}
    limit = config.get("max_tokens")
    if limit is None and engine_description.get("type") == "vlm_openai":
        limit = VLM_DEFAULT_MAX_TOKENS
    return isinstance(used, int) and isinstance(limit, int) and used >= limit


def cut_loop(text: str) -> tuple[str, str | None]:
    """Return (text without its trailing loop, rule name) or (text, None)."""
    cuts = [(cut, rule) for cut, rule in ((_cut_periodic(text), "periodic"), (_cut_line_repeat(text), "line"))
            if cut is not None]
    if not cuts:
        return text, None
    return min(cuts, key=lambda item: len(item[0]))


def _cut_periodic(text: str) -> str | None:
    n = len(text)
    for period in range(1, min(PERIOD_MAX, n // 3) + 1):
        run = 0  # length of the suffix where text[i] == text[i - period]
        while run < n - period and text[n - 1 - run] == text[n - 1 - run - period]:
            run += 1
        if run >= 2 * period and run + period >= MIN_LOOP_CHARS:
            return text[: n - run].rstrip()
    return None


def _cut_line_repeat(text: str) -> str | None:
    lines = text.split("\n")
    seen: dict[str, list[int]] = {}
    for index, line in enumerate(lines):
        key = line.strip()
        if not any(char.isalnum() for char in key):
            continue
        positions = seen.setdefault(key, [])
        positions.append(index)
        if len(positions) == 3:
            return "\n".join(lines[: positions[1]]).rstrip()
    return None
