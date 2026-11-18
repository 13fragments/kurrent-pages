"""Output maps: one engine's documented markup rewritten into the §3 conventions.

Written for dev comparisons (model-track EXP-20261029-lighton-baseline). Since §10 2026-11-15 a scored run applies
the map that an engine entry names (`output_map`) to the stored text before scoring; engines without the key are
unchanged. A map is written from the engine's published format or code before any of its output is seen, never
tuned on output.
"""

from __future__ import annotations

import re

# b-straub/LightOnOCR-3-1B-Historic-German-Handwriting, model card "Output format" (revision
# 47931fbe): ⟦struck⟧ ⟨inserted⟩ 〔underlined〕 ⌈superscript⌉ ⌊subscript⌋, ⌈+⌉ the writer's
# reference sign, ▨ an illegible spot, TAB between table cells, ↵ a line break, a blank line
# between blocks, U+0305 nasal bar, ſ as some training editions wrote it.
_LIGHTON_REFERENCE_SIGN = "⌈+⌉"
_LIGHTON_BRACKETS = str.maketrans("", "", "⟦⟧⟨⟩〔〕⌈⌉⌊⌋")
_SPACES = re.compile(r"[ \t]+")


def lighton_marks(text: str) -> str:
    """LightOnOCR markup -> §3: struck, inserted, underlined, super- and subscript text kept
    on the line without its marks (§3.1, §3.3: struck content is scored); reference signs
    dropped (§3.2 item 3: not encoded); ▨ -> `[unleserlich]` (§3.4); TAB -> ` | ` (§3.2 item 2);
    ↵ -> line break; nasal bar U+0305 -> macron U+0304 (§3.1); ſ -> s (handwriting, §3.1);
    no blank lines (§3.1). Reading order is not changed."""
    text = text.replace(_LIGHTON_REFERENCE_SIGN, "").translate(_LIGHTON_BRACKETS)
    text = text.replace("▨", " [unleserlich] ").replace("\t", " | ").replace("↵", "\n")
    text = text.replace("\u0305", "\u0304").replace("ſ", "s")
    lines = (_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


# stanford-oval/churro at 23c3ac6 (Apache-2.0): its benchmark strips the <output> wrapper
# (src/churro_ocr/prompts/ocr.py strip_ocr_output_tag) and flattens its HistoricalDocument XML to the text of each
# Page's Header, Body, and Footer, without Description, Deletion, Illegible, and Gap elements
# (tooling/evaluation/xml_utils.py extract_actual_text_from_xml), before it scores a reply.
_CHURRO_OUTER = re.compile(r"^\s*<output>\s*(.*?)\s*</output>\s*$", flags=re.DOTALL)
_CHURRO_STRAY = re.compile(r"</?output\b[^>]*>", flags=re.IGNORECASE)


def _churro_local(tag: str) -> str:
    return tag.rsplit("}", 1)[1] if "}" in tag else tag


def churro_xml(text: str) -> str:
    """CHURRO 3B reply -> plain page text, as CHURRO's own benchmark reads it."""
    import xml.etree.ElementTree as ET

    match = _CHURRO_OUTER.match(text)
    text = match.group(1).strip() if match else _CHURRO_STRAY.sub("", text).strip()
    if "HistoricalDocument" not in text:
        return text
    for tag in ("Description", "Deletion", "Illegible", "Gap"):
        if f"<{tag}" in text:
            text = re.sub(rf"<{tag}\b[^>]*/>", "", re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", text, flags=re.DOTALL))
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return ""
    pages = []
    for page in root.iter():
        if _churro_local(page.tag) != "Page":
            continue
        sections = []
        for child in page.iter():
            if _churro_local(child.tag) in {"Header", "Body", "Footer"}:
                lines = [line.strip() for line in child.itertext() if line.strip()]
                if lines:
                    sections.append("\n".join(lines))
        if sections:
            pages.append("\n".join(sections))
    return "\n\n".join(pages).strip()


OUTPUT_MAPS = {"lighton-marks": lighton_marks, "churro-xml": churro_xml}
