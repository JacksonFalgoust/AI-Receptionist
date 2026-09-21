"""Loads the authored guide template and fills its slots.

Substitution is deliberately dumb: a closed set of named slots and plain
replacement. No expression language, no loops, no conditionals. This
template governs what a live phone receptionist says, so anything
expressive enough to need a loop belongs in authored prose that a human
reviews in a pull request -- not in machine-generated text.

Both directions are errors: a slot in the template with no value, and a
value with no slot. Silence in either direction is how a prompt quietly
stops saying what someone intended.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app import config

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "guide-demo" / "template"
INSTRUCTIONS_PATH = TEMPLATE_DIR / "instructions.template.md"

# Everything in the template that is NOT instructions.template.md. Each is
# copied into the bundle verbatim. The OpenAPI files are the guide's entire
# tool surface -- see bundle.py's invariant, and note that GuideAnts' import
# deletes any tool absent from the bundle.
STATIC_FILES = (
    "manifest.json",
    "OpenAPI/voice-receptionist.json",
    "OpenAPI/caller-phone.json",
    "HostExtensions/UI/contextOptions.json",
)

_SLOT_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


class SlotError(ValueError):
    """A slot in the template had no value, or a value had no slot."""


def render_instructions(slots: dict[str, str]) -> str:
    text = INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    present = set(_SLOT_PATTERN.findall(text))

    unfilled = present - set(slots)
    if unfilled:
        raise SlotError(f"unfilled slot(s) in template: {', '.join(sorted(unfilled))}")
    unknown = set(slots) - present
    if unknown:
        raise SlotError(f"unknown slot(s) not in template: {', '.join(sorted(unknown))}")

    for name, value in slots.items():
        text = text.replace("{{" + name + "}}", value)
    return text


def load_static_files() -> dict[str, bytes]:
    files = {name: (TEMPLATE_DIR / name).read_bytes() for name in STATIC_FILES}
    # The manifest's name is the guide's identity, so it follows
    # GUIDEANTS_GUIDE_NAME rather than a copy checked into the template.
    manifest = json.loads(files["manifest.json"])
    manifest["name"] = config.GUIDEANTS_GUIDE_NAME
    files["manifest.json"] = json.dumps(manifest, indent=2).encode("utf-8")
    return files
