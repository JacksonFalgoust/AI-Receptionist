"""Console rows -> slot values and knowledge files. Pure: no network, no
database session, no filesystem writes -- it takes ORM rows and returns
strings and bytes, which is what makes it directly unit-testable in the
same way app/fillers.py is.
"""

from __future__ import annotations

import re
from datetime import date

from .. import models
from . import hours as hours_module

# Spoken aloud by TTS. instructions.md forbids markup in the guide's own
# replies for the same reason: a caller would hear the symbols.
_FORBIDDEN = re.compile(r"[*_#`•\[\]<>]|(?:^|\s)-\s")

_TONE_PROSE = {
    "professional": "professional and courteous",
    "friendly": "warm and friendly",
    "casual": "relaxed and casual",
    "formal": "formal and precise",
}


def _clean(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} must not be empty")
    if _FORBIDDEN.search(value):
        raise ValueError(
            f"{field} contains markup or symbols that a caller would hear read aloud"
        )
    return value


def _tone_prose(identity: dict) -> str:
    tone = identity.get("tone", "professional")
    if tone == "custom":
        return _clean(identity.get("customTone", ""), "identity.customTone")
    return _clean(_TONE_PROSE.get(tone, _TONE_PROSE["professional"]), "identity.tone_prose")


def _hours_prose(profile: dict, field: str) -> str:
    """hours.py raises its own ValueError (e.g. "business hours must cover
    all seven days") before _clean ever sees a value, so re-raise with the
    field name attached -- every other slot failure names its field, and a
    422 is only useful if it says which one to go fix."""
    try:
        return hours_module.hours_prose(profile.get("hours", []))
    except ValueError as exc:
        raise ValueError(f"{field}: {exc}") from exc


def build_slots(
    configuration: models.ConciergeConfiguration, knowledge_topics: list[str]
) -> dict[str, str]:
    """The complete slot set. Adding one here requires adding it to
    instructions.template.md too -- template.render_instructions() rejects
    any mismatch in either direction.

    `knowledge_topics` is the list from knowledge_topics(): exactly the
    titles of the items Publish sends, so the guide only searches for topics
    that exist. An empty list renders as the word "none", which the template
    tells the guide to read as "never search"."""
    profile = configuration.business_profile
    return {
        "business.name": _clean(profile.get("name", ""), "business.name"),
        "business.description": _clean(
            profile.get("description", ""), "business.description"
        ),
        "business.address": _clean(profile.get("address", ""), "business.address"),
        "business.hours_prose": _clean(
            _hours_prose(profile, "business.hours_prose"), "business.hours_prose"
        ),
        "identity.tone_prose": _tone_prose(configuration.identity),
        "knowledge.topics": "; ".join(knowledge_topics) if knowledge_topics else "none",
    }


def is_publishable(item: models.KnowledgeItem, today: date) -> bool:
    """Active, and today falls within its effective window (either bound
    optional). Anything else is absent from the rendered set -- and because
    Publish owns the guide's whole vector store, absent means removed from
    the live guide on the next publish, which is what an expired policy
    wants."""
    if item.status != "active":
        return False
    if item.effective_date and item.effective_date.date() > today:
        return False
    if item.expiration_date and item.expiration_date.date() < today:
        return False
    return True


def _item_markdown(item: models.KnowledgeItem) -> str:
    lines = [f"# {item.title}", ""]
    if item.category:
        lines += [f"Category: {item.category}", ""]
    if item.tags:
        lines += [f"Tags: {', '.join(item.tags)}", ""]
    lines.append(item.content or "")
    return "\n".join(lines).rstrip() + "\n"


def knowledge_files(
    items: list[models.KnowledgeItem], today: date
) -> dict[str, bytes]:
    """One file per publishable item, named by id so bundles hash stably
    across runs (a title-derived name would change the content hash on a
    rename and trigger a spurious republish)."""
    return {
        f"VectorStores/default/{item.id}.md": _item_markdown(item).encode("utf-8")
        for item in sorted(items, key=lambda i: i.id)
        if is_publishable(item, today)
    }


def knowledge_topics(items: list[models.KnowledgeItem], today: date) -> list[str]:
    """Titles of the publishable items, for the `{{knowledge.topics}}` slot.

    Titles are console-authored free text spoken aloud by the guide, so
    forbidden markup is replaced with a space rather than rejected -- one
    oddly-titled item must not block a publish the way a bad business name
    does. Exact duplicates collapse to one; the result is sorted
    case-insensitively so the prompt (and its hash) does not depend on
    row order."""
    seen: set[str] = set()
    topics: list[str] = []
    for item in items:
        if not is_publishable(item, today):
            continue
        title = " ".join(_FORBIDDEN.sub(" ", item.title or "").split())
        if title and title not in seen:
            seen.add(title)
            topics.append(title)
    return sorted(topics, key=lambda t: (t.lower(), t))
