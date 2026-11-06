"""Entity recall against hypothesis text (protocol §5.5).

An entity is recalled if its normalized form (or any recorded variant) appears
in the normalized hypothesis within Levenshtein distance <= 1 per token; dates
match exactly after canonical day/month/year parsing.
"""

from __future__ import annotations

import re

from harness import normalization
from harness.alignment import levenshtein
from harness.gold import Entity

ENTITY_CANDIDATE_VERSION = "entity-risk-v01-draft"

_PUNCT_ONLY = re.compile(r"[^\w]+")
# A numeral month (7ber, 8bre, 9bris, Xber, 10br: the old Roman count, September to
# December) is one token, not its digit (§10 2026-10-17).
_DATE_TOKEN_RE = re.compile(
    r"(?:10|[789])b(?:e)?r(?:is|e)?(?![a-zäöüß])|\d+|[a-zäöüß]+", re.IGNORECASE
)
_AMOUNT_NUMBER = r"(?:\d{1,3}(?:[./]\d{1,3})+|\d+)(?:[.,]\d{1,2})?(?:,-)?"
_AMOUNT_CURRENCY = (
    r"(?:RM|DM|Mark|ℳ|Kr?|Fr|Cts|Taler|Thlr|Gulden|fl\.?|fs|Sgr|Pf(?:ennig)?)"
)
_AMOUNT_RE = re.compile(
    rf"(?<!\w)(?:{_AMOUNT_CURRENCY}\s*{_AMOUNT_NUMBER}|"
    rf"{_AMOUNT_NUMBER}\s*{_AMOUNT_CURRENCY})(?!\w)",
    re.IGNORECASE,
)
_IDENTIFIER_RE = re.compile(
    r"(?<!\w)(?:Nr|No|Az|Aktenzeichen|Feldpost|FP)\.?\s*"
    r"(?=[A-Za-zÄÖÜäöüß0-9./-]*\d)"
    r"[A-Za-zÄÖÜäöüß0-9]+(?:[./-][A-Za-zÄÖÜäöüß0-9]+)*(?!\w)",
    re.IGNORECASE,
)
_EDGE_PUNCTUATION = ".,;:!?()[]{}<>\"'„“‚‘»«"
_SENTENCE_END_RE = re.compile(r"[.!?][\"'»”’)]*$")
_NAME_LIST_END_RE = re.compile(r"[,;][\"'»”’)]*$")
_LOWERCASE_CONTEXT_RE = re.compile(
    r"\b(?i:von|aus|nach|bei|in|zu)\s+([a-zäöüß][a-zäöüß'’-]{1,})(?!\w)"
)
_NAME_ABBREVIATIONS = frozenset({"dr", "fr", "st", "xav"})
_CONTEXT_STOPWORDS = {
    "das",
    "dem",
    "den",
    "der",
    "des",
    "die",
    "diesem",
    "dieser",
    "einem",
    "einer",
    "ihm",
}
_MONTHS = {
    "jan": "01",
    "januar": "01",
    "january": "01",
    "jaenner": "01",
    "janner": "01",
    "feb": "02",
    "februar": "02",
    "february": "02",
    "maer": "03",
    "maerz": "03",
    "mar": "03",
    "marz": "03",
    "mrz": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "mai": "05",
    "may": "05",
    "jun": "06",
    "juni": "06",
    "june": "06",
    "jul": "07",
    "juli": "07",
    "julii": "07",
    "july": "07",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "september": "09",
    "okt": "10",
    "oct": "10",
    "oktober": "10",
    "october": "10",
    "nov": "11",
    "november": "11",
    "dez": "12",
    "dec": "12",
    "dezember": "12",
    "december": "12",
}
# Historical forms (§10 2026-10-17), from general knowledge of German letters and
# records of the 17th–20th centuries, not from benchmark pages: Latin forms (also -ij
# for -ii), contracted abbreviations (Septbr.), truncations (Septem), numeral months,
# and the Germanic names of some 20th-century letters.
_HISTORICAL_MONTHS = {
    "01": "januarii januarij januarius jenner janr hartung",
    "02": "febr februarii februarij februarius feber hornung",
    "03": "martii martij martius mart mertz merz lenzing",
    "04": "aprilis aprill aprl ostermond",
    "05": "maii maij majus maius wonnemond",
    "06": "junii junij junius juny brachet brachmond",
    "07": "julij julius heuert heumond",
    "08": "augusti augustus augst ernting",
    "09": "septr septb septbr septem septemb septembr septembris"
    " 7br 7ber 7bre 7bris scheiding",
    "10": "octr oktr octbr oktbr octob oktob octobr octobris"
    " 8br 8ber 8bre 8bris gilbhart gilbhard",
    "11": "novr novbr novem novemb novembr novembris 9br 9ber 9bre 9bris nebelung",
    "12": "decr dezr decbr dezbr decem decemb dezemb decembr decembris"
    " xbr xber xbre xbris 10br 10ber 10bre 10bris julmond christmond",
}
for _number, _forms in _HISTORICAL_MONTHS.items():
    for _form in _forms.split():
        _MONTHS.setdefault(_form, _number)
_ROMAN_MONTHS = {
    "i": "01",
    "ii": "02",
    "iii": "03",
    "iv": "04",
    "v": "05",
    "vi": "06",
    "vii": "07",
    "viii": "08",
    "ix": "09",
    "x": "10",
    "xi": "11",
    "xii": "12",
}
_MONTH_FORMS = {*_MONTHS, *_ROMAN_MONTHS}
_MONTH_FORMS.update(
    form.replace("ae", "ä") for form in tuple(_MONTH_FORMS) if "ae" in form
)
_MONTH_PATTERN = "|".join(
    re.escape(form) for form in sorted(_MONTH_FORMS, key=len, reverse=True)
)
_FULL_DATE_RE = re.compile(
    rf"(?<!\w)\d{{1,4}}\s*[.,/-]\s*(?:\d{{1,2}}|{_MONTH_PATTERN})"
    rf"\s*[.,/-]\s*\d{{1,4}}(?!\w)",
    re.IGNORECASE,
)
_TEXT_DATE_RE = re.compile(
    rf"(?<!\w)\d{{1,2}}\.?\s+(?:{_MONTH_PATTERN})\.?(?:,?\s+\d{{2,4}})?(?!\w)",
    re.IGNORECASE,
)
_YEAR_RANGE_RE = re.compile(r"(?<!\w)(?:1[5-9]\d{2}|20\d{2})\s*[/–-]\s*\d{2,4}(?!\w)")
_STANDALONE_YEAR_RE = re.compile(r"(?<!\w)(?:1[5-9]\d{2}|20\d{2})(?!\w)")


def _tokens_match(entity_tokens: list[str], window: list[str]) -> bool:
    return all(levenshtein(et, ht) <= 1 for et, ht in zip(entity_tokens, window))


def _month_value(token: str) -> str | None:
    key = token.casefold().rstrip(".")
    key = key.replace("ä", "ae")
    return _MONTHS.get(key) or _ROMAN_MONTHS.get(key)


def _date_key(text: str) -> tuple[str, ...] | None:
    tokens = _DATE_TOKEN_RE.findall(text)
    values: list[tuple[str, str]] = []
    has_month = False
    for token in tokens:
        if token.isdigit():
            values.append(("num", token))
        else:
            month = _month_value(token)
            if month is not None:
                has_month = True
                values.append(("month", month))
    for start in range(max(0, len(values) - 2)):
        first, second, third = values[start : start + 3]
        if first[0] == "num" and second[0] in {"num", "month"} and third[0] == "num":
            if len(first[1]) == 4:  # ISO-ish: yyyy-mm-dd
                year, month, day = first[1], second[1], third[1]
            else:  # diplomatic/common: dd.mm.yyyy or dd. month yyyy
                day, month, year = first[1], second[1], third[1]
            if _valid_date_parts(day, month, year):
                return "full", year, month.zfill(2), day.zfill(2)
    if has_month:
        return None
    digits = normalization.digit_normalize(text)
    return ("digits", digits) if digits else None


def _valid_date_parts(day: str, month: str, year: str) -> bool:
    if not day.isdigit() or not month.isdigit() or not year.isdigit():
        return False
    return 1 <= int(day) <= 31 and 1 <= int(month) <= 12 and len(year) in {2, 4}


def _form_recalled(form: str, entity_type: str, hyp_tokens: list[str]) -> bool:
    if entity_type == "date":
        target = _date_key(form)
        if target is None:
            return False
        # Punctuation-only tokens ("18 . 12 . 1924") must not eat span slots.
        date_tokens = [t for t in hyp_tokens if not _PUNCT_ONLY.fullmatch(t)]
        # Contiguous token spans; a date never spans more than a handful of tokens.
        max_span = max(len(form.split()) + 2, 4)
        for start in range(len(date_tokens)):
            for end in range(start + 1, min(start + max_span, len(date_tokens)) + 1):
                if _date_key(" ".join(date_tokens[start:end])) == target:
                    return True
        return False
    entity_tokens = normalization.normalize(form).split()
    if not entity_tokens:
        return False
    k = len(entity_tokens)
    return any(
        _tokens_match(entity_tokens, hyp_tokens[i : i + k])
        for i in range(len(hyp_tokens) - k + 1)
    )


def entity_recalled(entity: Entity, hyp_tokens: list[str]) -> bool:
    return any(_form_recalled(form, entity.type, hyp_tokens) for form in entity.forms())


def score_entities(entities: list[Entity], hyp_norm_text: str) -> dict:
    """Per-page gold-entity recall, overall and by type.

    Hypothesis-side precision is adjudicated independently from the versioned
    entity-risk candidates below; private gold targets are never serialized here.
    """
    hyp_tokens = hyp_norm_text.split()
    matched = 0
    by_type: dict[str, dict[str, int]] = {}
    for entity in entities:
        bucket = by_type.setdefault(entity.type, {"matched": 0, "total": 0})
        bucket["total"] += 1
        if entity_recalled(entity, hyp_tokens):
            bucket["matched"] += 1
            matched += 1
    total = len(entities)
    return {
        "entity_total": total,
        "entity_matched": matched,
        "entity_recall": (matched / total) if total else None,
        "entity_by_type": {
            t: {**counts, "recall": counts["matched"] / counts["total"]}
            for t, counts in by_type.items()
        },
    }


def extract_entity_risk_candidates(hyp_norm_text: str) -> dict:
    """Frozen, high-recall candidates for image-grounded entity review.

    German capitalization makes the name/place heuristic intentionally broad.
    These records are review inventory, never automatic unsupported claims.
    """
    candidates: dict[tuple[str, int, int], dict] = {}
    structured_ranges: list[tuple[int, int]] = []
    for kind, pattern in (
        ("amount", _AMOUNT_RE),
        ("identifier", _IDENTIFIER_RE),
    ):
        for match in pattern.finditer(hyp_norm_text):
            _add_candidate(candidates, hyp_norm_text, kind, match.start(), match.end())
            structured_ranges.append((match.start(), match.end()))
    for start, end in _date_candidate_ranges(hyp_norm_text):
        if not _overlaps(start, end, structured_ranges):
            _add_candidate(candidates, hyp_norm_text, "date", start, end)
            structured_ranges.append((start, end))

    run: list[tuple[str, int, int]] = []
    for match in re.finditer(r"\S+", hyp_norm_text):
        raw = match.group()
        leading = len(raw) - len(raw.lstrip(_EDGE_PUNCTUATION))
        cleaned = raw.strip(_EDGE_PUNCTUATION)
        start, end = match.start() + leading, match.start() + leading + len(cleaned)
        if (
            cleaned
            and _is_name_like(cleaned)
            and not _overlaps(start, end, structured_ranges)
        ):
            run.append((cleaned, start, end))
            if (
                (_SENTENCE_END_RE.search(raw) or _NAME_LIST_END_RE.search(raw))
                and not _is_initial(cleaned)
                and cleaned.casefold() not in _NAME_ABBREVIATIONS
            ):
                _flush_name_run(candidates, hyp_norm_text, run)
                run = []
            continue
        _flush_name_run(candidates, hyp_norm_text, run)
        run = []
    _flush_name_run(candidates, hyp_norm_text, run)
    for match in _LOWERCASE_CONTEXT_RE.finditer(hyp_norm_text):
        start, end = match.start(1), match.end(1)
        if match.group(1).casefold() not in _CONTEXT_STOPWORDS and not _overlaps(
            start, end, structured_ranges
        ):
            _add_candidate(candidates, hyp_norm_text, "name_or_place", start, end)

    return {
        "entity_candidate_version": ENTITY_CANDIDATE_VERSION,
        "entity_risk_candidates": sorted(
            candidates.values(),
            key=lambda item: (item["start"], item["end"], item["kind"]),
        ),
    }


def _add_candidate(
    candidates: dict[tuple[str, int, int], dict],
    text: str,
    kind: str,
    start: int,
    end: int,
) -> None:
    same_kind = [
        key
        for key in candidates
        if key[0] == kind and start <= key[1] and end >= key[2]
    ]
    if any(key[0] == kind and key[1] <= start and key[2] >= end for key in candidates):
        return
    for key in same_kind:
        del candidates[key]
    key = kind, start, end
    candidates[key] = {
        "id": f"{ENTITY_CANDIDATE_VERSION}:{kind}:{start}:{end}",
        "kind": kind,
        "start": start,
        "end": end,
        "text": text[start:end],
    }


def _flush_name_run(
    candidates: dict[tuple[str, int, int], dict],
    text: str,
    run: list[tuple[str, int, int]],
) -> None:
    if run:
        _add_candidate(candidates, text, "name_or_place", run[0][1], run[-1][2])


def _date_candidate_ranges(text: str) -> list[tuple[int, int]]:
    matches = {
        (match.start(), match.end())
        for pattern in (
            _FULL_DATE_RE,
            _TEXT_DATE_RE,
            _YEAR_RANGE_RE,
            _STANDALONE_YEAR_RE,
        )
        for match in pattern.finditer(text)
    }
    selected: list[tuple[int, int]] = []
    for start, end in sorted(matches, key=lambda item: (-(item[1] - item[0]), item[0])):
        if not _overlaps(start, end, selected):
            selected.append((start, end))
    return sorted(selected)


def _is_name_like(token: str) -> bool:
    parts = re.split(r"['’-]", token)
    return (
        bool(parts)
        and all(part.isalpha() for part in parts)
        and (token[0].isupper() or token.isupper())
    )


def _is_initial(token: str) -> bool:
    return len(token) == 1 and token.isalpha() and token.isupper()


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(
        start < other_end and end > other_start for other_start, other_end in ranges
    )
