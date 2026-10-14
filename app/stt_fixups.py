"""Small, conservative fixes for known speech-to-text mishearings, applied
only in the context of the question the agent just asked."""

import re

# Clear mishearings of "text": treated as "Text." outright.
_TEXT_MISHEARINGS = {"tex", "texts", "techs", "text"}
# Unclear ones ("6", "next" ...): could be noise or a different word, so the
# guide is told to confirm once ("By text, right?") before sending anything.
_TEXT_UNCLEAR = {"6", "six", "next", "tax", "tech"}
UNCLEAR_TEXT_NOTE = (
    '[Note: the caller\'s reply was unclear (heard "{heard}"); it may mean text. Ask once, '
    '"By text, right?", and wait for their answer before sending anything.]'
)
_ASKED_TEXT_OR_EMAIL = re.compile(r"\btext\b.*\bemail\b|\bemail\b.*\btext\b", re.IGNORECASE)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split())


def fix_choice(last_agent_text: str, user_text: str) -> str:
    """If the agent just asked "text or email?" and the caller's whole reply
    was heard as "6"/"Tex"/"next" etc., treat it as "Text."."""
    if not _ASKED_TEXT_OR_EMAIL.search(last_agent_text or ""):
        return user_text
    words = _norm(user_text).split()
    if words and words[0] in ("by", "a", "uh", "um"):
        words = words[1:]
    if len(words) == 1 and words[0] in _TEXT_MISHEARINGS:
        return "Text."
    if len(words) == 1 and words[0] in _TEXT_UNCLEAR:
        return f"{UNCLEAR_TEXT_NOTE.format(heard=words[0])} {user_text}"
    return user_text
