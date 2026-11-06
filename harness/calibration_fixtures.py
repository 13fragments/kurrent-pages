"""Checked-in synthetic text and deterministic calibration case generation."""

from __future__ import annotations

from dataclasses import dataclass
import random

from harness import normalization


DEFAULT_SEED = 1729
DEFAULT_SPAN_SIZES = (3, 5, 10, 25)
DEFAULT_POSITIONS = ("start", "middle", "end")
REPLACEMENT_MODES = ("appended", "equal", "shorter", "longer")

# These are public synthetic development pages. They are long enough to
# exercise all span sizes and contain line-like prose rather than placeholder
# tokens. Synthetic references stay here; held-out gold remains private.
DEV_TEXTS: dict[str, str] = {
    "dev_letter": (
        "Im Frühjahr 1924 prüfte der Archivar Wilhelm Kramer die Briefe aus "
        "Bremen und ordnete jedes Blatt nach Datum, Absender und Inhalt. Die "
        "Mappe enthielt Notizen zur Reise, eine Liste der Empfänger sowie "
        "mehrere Quittungen für Papier und Porto. Am Abend verglich er die "
        "Einträge mit dem Register und legte die vollständige Abschrift in den "
        "Schrank. Der folgende Morgen brachte weitere Umschläge aus dem Rathaus."
    ),
    "dev_register": (
        "Im Register des Bezirksamts standen Vermerke zu Fuhrwerken, Zollscheinen "
        "und eingegangenen Paketen. Die Schreiberin Clara Vogt ergänzte jede "
        "Zeile mit Ort, Nummer und Randnotiz. Nach der Mittagspause kontrollierte "
        "sie die Summen, faltete die Belege und versah den Umschlag mit einem "
        "Siegel. Ein später Nachtrag verwies auf den Bestand im Nebenraum und die "
        "dort verwahrten Bücher."
    ),
    "dev_diary": (
        "Am Dienstag notierte der Reisende Paul Henning den Wasserstand und die "
        "Abfahrt des kleinen Dampfers. Hinter dem Bahnhof fand er eine "
        "verschlossene Kiste, deren Inhalt niemand aus dem Dorf kannte. Er fragte "
        "beim Wirt nach dem Weg zum Lager und schrieb die Antwort in sein Heft. "
        "Gegen Abend brachte ein Bote die fehlende Karte zurück und bat um eine "
        "kurze Empfangsbestätigung."
    ),
    "dev_invoice": (
        "Die Rechnung nannte Papier, Bindfaden, Umschläge und drei Pakete für die "
        "Kanzlei. Kaufmann Elise Brandt strich eine falsche Summe, setzte die "
        "richtige Zahl daneben und zeichnete den Beleg ab. Im Anhang folgte eine "
        "Liste der gelieferten Stücke mit Maß, Gewicht und Preis. Der Schreiber "
        "heftete alles zusammen und übergab die Akte dem zuständigen Beamten."
    ),
}

# Excerpts from other synthetic pages. They use ordinary German words and
# realistic shared function words; they are not artificial ``fremdwort01``
# markers. Each excerpt has at least 25 words.
FOREIGN_TEXTS: tuple[str, ...] = (
    "Nach dem langen Regen brachte der Bote einen versiegelten Bericht aus dem "
    "nördlichen Bezirk. Darin beschrieb die Kommission den beschädigten Steg, "
    "prüfte die Vorräte und vermerkte jede Auslage im neuen Protokoll. Ein "
    "unbekannter Zeuge nannte den Weg zum alten Speicher und bat um weitere "
    "Anweisungen für den Rückweg.",
    "Am folgenden Morgen öffnete die Aufsicht das verschlossene Fach und fand "
    "darin mehrere Karten, einen fremden Schlüssel sowie die Quittung des "
    "örtlichen Händlers. Der sachkundige Schreiber verglich die Zeichen mit dem "
    "Verzeichnis, strich eine unklare Zahl und legte den Umschlag zur späteren "
    "Prüfung beiseite.",
    "Die Reisenden erreichten am Abend den abgelegenen Hof, wo ein schweigsamer "
    "Wächter auf die fehlende Nachricht wartete. Nach kurzer Beratung notierte "
    "die Gruppe den Namen des Flusses, zeichnete den beschädigten Wagen und "
    "sandte den Bericht an die zuständige Stelle zurück.",
)


@dataclass(frozen=True)
class CalibrationConfig:
    """Reproducible fixture dimensions."""

    seed: int = DEFAULT_SEED
    span_sizes: tuple[int, ...] = DEFAULT_SPAN_SIZES
    positions: tuple[str, ...] = DEFAULT_POSITIONS
    pages: tuple[str, ...] = tuple(DEV_TEXTS)

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int):
            raise TypeError("calibration seed must be an integer")
        if not self.span_sizes or any(size < 1 for size in self.span_sizes):
            raise ValueError("span_sizes must contain positive word counts")
        if not self.positions:
            raise ValueError("positions must not be empty")
        if not self.pages:
            raise ValueError("pages must not be empty")
        unknown = set(self.positions) - set(DEFAULT_POSITIONS)
        if unknown:
            raise ValueError(f"unknown insertion positions: {sorted(unknown)}")
        unknown_pages = set(self.pages) - set(DEV_TEXTS)
        if unknown_pages:
            raise ValueError(f"unknown synthetic pages: {sorted(unknown_pages)}")


def build_fixture_cases(
    seed: int = DEFAULT_SEED, *, config: CalibrationConfig | None = None
) -> list[dict]:
    """Build deterministic injected-span, entity, and control cases."""

    if config is None:
        config = CalibrationConfig(seed=seed)
    elif seed != DEFAULT_SEED and seed != config.seed:
        raise ValueError("pass the seed either directly or through config, not both")
    cases: list[dict] = []
    case_number = 0
    page_ids = list(config.pages)
    for page_index, page_id in enumerate(page_ids):
        gold = DEV_TEXTS[page_id]
        gold_words = normalization.normalize(gold).split()
        for size in config.span_sizes:
            source_index = (page_index + 1) % len(FOREIGN_TEXTS)
            foreign_words = normalization.normalize(FOREIGN_TEXTS[source_index]).split()
            injected_words = _source_words(
                foreign_words, size, config.seed + page_index
            )
            for position in config.positions:
                for mode in REPLACEMENT_MODES:
                    if mode == "appended" and position != "end":
                        continue
                    case_seed = config.seed + case_number * 7919
                    common = size >= 10 and mode == "equal" and position == "middle"
                    words = (
                        _with_common_overlap(injected_words)
                        if common
                        else injected_words
                    )
                    cases.append(
                        _injection_case(
                            page_id,
                            gold,
                            gold_words,
                            words,
                            mode,
                            position,
                            size,
                            case_seed,
                            source_page=f"synthetic_source_{source_index + 1}",
                            common_overlap=common,
                        )
                    )
                    case_number += 1

    cases.extend(_entity_cases(config, page_ids))
    cases.extend(_control_cases(config, page_ids[0]))
    return cases


generate_fixture_cases = build_fixture_cases


def _source_words(words: list[str], size: int, seed: int) -> list[str]:
    """Take a deterministic contiguous excerpt, wrapping only if needed."""

    if size <= len(words):
        start = random.Random(seed).randrange(len(words) - size + 1)
        return words[start : start + size]
    repeats = (size + len(words) - 1) // len(words)
    return (words * repeats)[:size]


def _with_common_overlap(words: list[str]) -> list[str]:
    """Add two ordinary bridge words while retaining at least five novel words."""

    result = list(words)
    if len(result) >= 10:
        result[2] = "der"
        result[6] = "und"
    return result


def _injection_case(
    page_id: str,
    gold: str,
    gold_words: list[str],
    injected_words: list[str],
    mode: str,
    position: str,
    size: int,
    seed: int,
    *,
    source_page: str,
    common_overlap: bool,
) -> dict:
    if mode == "equal":
        removed = size
    elif mode == "shorter":
        removed = size + 2
    elif mode == "longer":
        removed = max(1, size - 2)
    elif mode == "appended":
        removed = 0
    else:  # pragma: no cover - protected by REPLACEMENT_MODES
        raise ValueError(f"unknown replacement mode: {mode}")
    if removed > len(gold_words):
        raise ValueError(f"span size {size} is too large for page {page_id}")
    if mode == "appended":
        start_word = len(gold_words)
    elif position == "start":
        start_word = 0
    elif position == "middle":
        start_word = (len(gold_words) - removed) // 2
    else:
        start_word = len(gold_words) - removed
    hyp_words = (
        gold_words[:start_word] + injected_words + gold_words[start_word + removed :]
    )
    hyp = " ".join(hyp_words)
    injected = " ".join(injected_words)
    start = sum(len(word) + 1 for word in hyp_words[:start_word])
    end = start + len(injected)
    return {
        "id": f"inject_{page_id}_{mode}_{size}_{position}",
        "category": "injected_span",
        "page": page_id,
        "source_page": source_page,
        "seed": seed,
        "gold": gold,
        "hyp": hyp,
        "mode": mode,
        "position": position,
        "span_size": size,
        "removed_word_count": removed,
        "common_word_overlap": common_overlap,
        "offset_space": "normalized_hypothesis",
        "injected_span": {
            "text": injected,
            "start": start,
            "end": end,
            "word_count": len(injected_words),
        },
    }


def _entity_cases(config: CalibrationConfig, page_ids: list[str]) -> list[dict]:
    entities = (
        ("person", "Lorenz", "name_or_place"),
        ("place", "Waldkirch", "name_or_place"),
        ("date", "18.12.1924", "date"),
        ("amount", "25 RM", "amount"),
    )
    cases = []
    for index, (entity_type, text, candidate_kind) in enumerate(entities):
        page_id = page_ids[index % len(page_ids)]
        gold = DEV_TEXTS[page_id]
        words = normalization.normalize(gold).split()
        insertion = len(words) // 2
        hyp_words = words[:insertion] + text.split() + words[insertion:]
        hyp = " ".join(hyp_words)
        start = sum(len(word) + 1 for word in hyp_words[:insertion])
        end = start + len(text)
        cases.append(
            {
                "id": f"short_entity_{entity_type}",
                "category": "high_risk_entity",
                "page": page_id,
                "seed": config.seed + 50000 + index,
                "gold": gold,
                "hyp": hyp,
                "mode": "short_insertion",
                "position": "middle",
                "span_size": len(text.split()),
                "offset_space": "normalized_hypothesis",
                "expected_entities": [
                    {
                        "text": text,
                        "kind": candidate_kind,
                        "type": entity_type,
                        "start": start,
                        "end": end,
                    }
                ],
            }
        )
    return cases


def _control_cases(config: CalibrationConfig, page_id: str) -> list[dict]:
    gold = DEV_TEXTS[page_id]
    words = normalization.normalize(gold).split()
    wrapped_gold = "\n".join((" ".join(words[:15]), " ".join(words[15:])))
    reordered_gold = "\n".join((" ".join(words[:30]), " ".join(words[30:])))
    reordered_hyp = "\n".join((" ".join(words[30:]), " ".join(words[:30])))
    controls = [
        ("exact", gold, gold, True),
        ("one_character_typo", gold, gold.replace("Kramer", "Kramar", 1), True),
        ("line_wrapping", wrapped_gold, " ".join(words), True),
        (
            "compound_split",
            "Weihnachtsmannkostümverleih und Schluss",
            "Weih nachts mann kostüm ver leih und Schluss",
            True,
        ),
        ("truncation", gold, " ".join(words[:8]), True),
        ("crnn_noise", gold, "qzxv mptk rrrs nnnx vvvq llll zzzp kkkd", False),
        ("reordered_blocks", reordered_gold, reordered_hyp, False),
        (
            "repetition_loop",
            gold,
            gold + " rote blaue grüne gelbe rote blaue grüne gelbe",
            False,
        ),
    ]
    return [
        {
            "id": f"control_{name}",
            "category": "control",
            "control": name,
            "page": page_id,
            "seed": config.seed + 60000 + index,
            "gold": control_gold,
            "hyp": control_hyp,
            "expected_zero_candidates": zero,
            "offset_space": "normalized_hypothesis",
        }
        for index, (name, control_gold, control_hyp, zero) in enumerate(controls)
    ]
