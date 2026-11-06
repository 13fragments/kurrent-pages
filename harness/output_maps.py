"""Output maps: one engine's documented markup rewritten into the §3 conventions.

For dev comparisons only (model-track EXP-20261029-lighton-baseline). No scored run applies
a map: runner and scoring do not import this module, and a gold run with a map needs a §10
amendment. A map is written from the engine's published format before any of its output is
seen, never tuned on output.
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


OUTPUT_MAPS = {"lighton-marks": lighton_marks}
