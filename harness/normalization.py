"""Text layers of BENCHMARK_PROTOCOL.md: §3.3 marker stripping and the §4
normalization pipeline (derived, never hand-edited). Every rule here is
pre-registered; changes require a §10 protocol amendment.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata

ABSTENTION_MARK = "[unleserlich]"
# Operationalization of §5.6 "abstention marker / explicit 'illegible' statement".
ABSTENTION_RE = re.compile(
    r"unleserlich|unlesbar|nicht\s+lesbar|illegible|not\s+legible|cannot\s+(?:be\s+)?read",
    re.IGNORECASE,
)

# §4.1: residual ligature/variant codepoints unpacked in the normalized layer.
_LIGATURES = {
    "ſ": "s",  # ſ long s
    "ꝛ": "r",  # ꝛ rotunda r
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",  # ﬅ long-s t
    "ﬆ": "st",
}
_LIGATURE_TABLE = str.maketrans(_LIGATURES)

# GT authoring rule: M/S/D markers never span line breaks — a multi-line marginal
# note is written as multiple ⟪M⟫-prefixed lines (§3.2 rule 3), a multi-line
# deletion as per-line ⟪D: …⟫. Print regions use their own DOTALL matcher
# because pasted print can be a block.
_MARKER_KEYED = re.compile(r"⟪(?P<tag>[MSD]):[ \t]?(?P<body>[^\n⟫]*)⟫")
_MARKER_PREFIX = re.compile(r"⟪(?P<tag>[MSD])⟫[ \t]?")
_GRAPHIC = "⟪G⟫"
_PRINT_REGION = re.compile(r"⟪P:[ \t]?(?P<body>.*?)⟫", re.DOTALL)
# ⟪G⟫ graphic placeholder; ⟪Z⟫ closing/section-mark placeholder (§3.1/§3.2 rule 5,
# §10 2026-09-03). Both are bare, unscored tokens.
_MARKER_UNSCORED = re.compile(r"⟪[GZ]⟫")
_CLOSING_MARK = re.compile(r"⟪Z⟫")
_UNCERTAIN = re.compile(r"⟦(?P<body>[^\n⟧]*)⟧")  # ⟦best guess⟧, scored normally
# End-of-line strokes (§4 step 2): -, =, ⸗ directly before a line break never count. After a
# letter (also one carrying a combining mark) the stroke is a hyphen and joins the halves of
# the word; after anything else it is a filler or continuation stroke (§3.1, "1812.-"), so
# only the stroke goes and the words stay apart (§10 2026-10-17).
_HYPHEN_BREAK = re.compile(r"(?:(?<=[^\W\d_])|(?<=[\u0300-\u036f]))[-=⸗]\n")
_STROKE_BREAK = re.compile(r"[-=⸗]\n")


def strip_markers(text: str) -> str:
    """§3.3: remove region-marker glyphs, keep scored content, drop unscored regions.

    ⟪M: x⟫/⟪S: x⟫/⟪D: x⟫ -> x; ⟪M⟫/⟪S⟫/⟪D⟫ line prefixes removed; ⟪G⟫, ⟪Z⟫
    and ⟪P: …⟫ dropped entirely; ⟦x⟧ -> x. Applied symmetrically to gold and
    hypothesis before any metric. Lines left empty by marker removal are dropped.
    """
    text = _PRINT_REGION.sub("", text)
    text = _MARKER_UNSCORED.sub("", text)
    text = _MARKER_KEYED.sub(lambda m: m.group("body"), text)
    text = _MARKER_PREFIX.sub("", text)
    text = _UNCERTAIN.sub(lambda m: m.group("body"), text)
    lines = [_collapse_spaces(line) for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def strip_hyp_markers(text: str) -> str:
    """Strip hypothesis markup without letting it self-declare unscored print.

    GT-authored ``⟪P: ...⟫`` regions are unscored, but a hypothesis marker is
    just emitted text from an engine. Unwrap its body so fabricated text is
    still counted; drop only bare placeholders (a whole-line ⟪G⟫, an inline
    ⟪Z⟫ — neither carries a body that could hide text).
    """
    text = _PRINT_REGION.sub(lambda m: m.group("body"), text)
    text = _CLOSING_MARK.sub("", text)
    text = _MARKER_KEYED.sub(lambda m: m.group("body"), text)
    text = _MARKER_PREFIX.sub("", text)
    text = _UNCERTAIN.sub(lambda m: m.group("body"), text)
    lines = [_collapse_spaces(line) for line in text.split("\n")]
    return "\n".join(line for line in lines if line and line != _GRAPHIC)


def scoring_texts(gold_text: str, hyp_text: str) -> tuple[str, str]:
    """Return marker-stripped gold/hypothesis text for scoring.

    Unscored print is declared by gold. OCR output of that print is removed from
    the hypothesis only when anchored by the corresponding gold ``⟪P: ...⟫``.
    Hypothesis-side ``⟪P: ...⟫`` markers are unwrapped, never trusted.
    """
    gold_scored = strip_markers(gold_text)
    hyp_without_gold_print = drop_unscored_print_from_hyp(gold_text, hyp_text)
    return gold_scored, strip_hyp_markers(hyp_without_gold_print)


def drop_unscored_print_from_hyp(gold_text: str, hyp_text: str) -> str:
    """Remove GT-declared unscored print text when OCR emits it unmarked."""
    matches = list(_PRINT_REGION.finditer(gold_text))
    previous_end = 0
    cursor = 0
    for index, match in enumerate(matches):
        before = _context_anchor(gold_text[previous_end : match.start()], last=True)
        cursor, before_found = _advance_past_context(hyp_text, before, cursor)

        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(gold_text)
        after = _context_anchor(gold_text[match.end() : next_start], last=False)
        end, after_found = _context_end(hyp_text, after, cursor)
        target = _print_region_text(match)
        target_span = _find_flex(hyp_text, target, cursor)
        if after and target_span is not None and end is not None and end <= target_span[0]:
            end, after_found = _context_end(hyp_text, after, target_span[1])
        if not after:
            end = len(hyp_text)
        allow_interval = before_found and after_found and (
            bool(after) or not _is_print_placeholder(target)
        )
        if before_found and after_found:
            hyp_text = _drop_between(
                hyp_text,
                target,
                cursor,
                end,
                allow_interval=allow_interval,
            )
        previous_end = match.end()
    return hyp_text


def _context_anchor(text: str, *, last: bool) -> str:
    lines = [line.strip() for line in strip_markers(text).splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1] if last else lines[0]


def _find_flex(
    text: str, target: str, start: int = 0, end: int | None = None
) -> tuple[int, int] | None:
    if not target:
        return None
    end = len(text) if end is None else end
    pos = text.find(target, start, end)
    if pos != -1:
        return pos, pos + len(target)
    parts = target.split()
    if not parts:
        return None
    pattern = r"\s+".join(re.escape(part) for part in parts)
    match = re.search(pattern, text[start:end])
    if match is None:
        return None
    return start + match.start(), start + match.end()


def _drop_between(
    text: str, target: str, start: int, end: int | None, *, allow_interval: bool
) -> str:
    span = _find_flex(text, target, start, end)
    if span is not None:
        line_start = text.rfind("\n", 0, span[0]) + 1
        next_newline = text.find("\n", span[1])
        line_end = len(text) if next_newline == -1 else next_newline
        if not text[line_start : span[0]].strip() and not text[span[1] : line_end].strip():
            if next_newline != -1:
                return text[:line_start] + text[next_newline + 1 :]
            if line_start > 0:
                return text[: line_start - 1] + text[line_end:]
        return text[: span[0]] + text[span[1] :]
    if not allow_interval or end is None or end <= start:
        return text
    removed = text[start:end]
    if not (_similar_enough(removed, target) or _is_print_placeholder(target)):
        return text
    if "\n" in removed:
        replacement = "" if start == 0 or end == len(text) else "\n"
    else:
        replacement = " " if removed.strip() else ""
    return text[:start] + replacement + text[end:]


def _similar_enough(text: str, target: str) -> bool:
    text_key = " ".join(text.lower().split())
    target_key = " ".join(target.lower().split())
    if not text_key or not target_key:
        return False
    if len(text_key) > max(len(target_key) * 3, len(target_key) + 20):
        return False
    return SequenceMatcher(None, text_key, target_key).ratio() >= 0.65


def _is_print_placeholder(target: str) -> bool:
    return " ".join(target.lower().split()) == "unscored"


def _print_region_text(match: re.Match[str]) -> str:
    return strip_hyp_markers(match.group("body")).strip()


def _advance_past_context(hyp_text: str, context: str, cursor: int) -> tuple[int, bool]:
    if not context:
        return cursor, True
    span = _find_flex(hyp_text, context, cursor)
    return (span[1], True) if span is not None else (cursor, False)


def _context_end(hyp_text: str, context: str, cursor: int) -> tuple[int | None, bool]:
    if not context:
        return None, True
    span = _find_flex(hyp_text, context, cursor)
    return (span[0], True) if span is not None else (None, False)


def diplomatic(text: str) -> str:
    """Diplomatic scoring layer: markers stripped, NFC, spacing tidied.

    Keeps ſ, ligature codepoints, end-of-line hyphenation, and line breaks —
    those ARE the convention being scored (§3).
    """
    return unicodedata.normalize("NFC", strip_markers(text))


def normalize(text: str, lowercase: bool = False) -> str:
    """§4 normalized layer, applied identically to gold and hypothesis.

    1. ſ -> s, unpack residual ligature codepoints.
    2. Dehyphenate line ends (a stroke after a letter joins; any other line-end
       stroke is dropped without joining), then line breaks -> space.
    3. Strip region markers (done first here; order-neutral because markers
       are single-line by GT authoring rule — see marker regexes above).
    4. Unicode NFC, collapse whitespace.
    5. Lowercase only when the cer_norm_lc variant asks for it.
    """
    text = strip_markers(text)
    text = text.translate(_LIGATURE_TABLE)
    text = _HYPHEN_BREAK.sub("", text)
    text = _STROKE_BREAK.sub("\n", text)
    text = text.replace("\n", " ")
    text = unicodedata.normalize("NFC", text)
    text = _collapse_spaces(text)
    if lowercase:
        text = text.lower()
    return text


def normalize_line(line: str) -> str:
    """Per-line normalization for the order-insensitive CER (§5.2): all §4
    character rules, but no dehyphenation/line-joining (lines stay lines)."""
    line = strip_markers(line)
    line = line.translate(_LIGATURE_TABLE)
    line = unicodedata.normalize("NFC", line)
    return _collapse_spaces(line)


def norm_lines(text: str) -> list[str]:
    """Non-empty normalized lines of a page, for Hungarian line matching."""
    lines = [normalize_line(line) for line in text.split("\n")]
    return [line for line in lines if line]


def tokens(text: str) -> list[str]:
    return text.split()


def digit_normalize(text: str) -> str:
    """§5.5 date matching: keep only digits, mapped to ASCII via NFKC."""
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if ch.isdigit())


def _collapse_spaces(text: str) -> str:
    return re.sub(r"[ \t ]+", " ", text).strip()
