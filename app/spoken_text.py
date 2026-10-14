"""Keep protected phrases (the business name) whole in the text stream sent
to Twilio's TTS.

GuideAnts streams sub-word tokens ("Pe", "acht", "ree", " Ped", "als"), and
each one goes to Twilio as its own frame. ElevenLabs then voiced the
fragments oddly ("Ped-allies", "P. had less") on real calls. PhraseJoiner
holds back a tail that could be the start of a protected phrase until the
phrase is complete (or clearly isn't coming), so the name always reaches
TTS in one frame.
"""

from __future__ import annotations


class PhraseJoiner:
    def __init__(self, phrases) -> None:
        self._phrases = [p.lower() for p in phrases if p and len(p) >= 3]
        self._held = ""

    def _hold_len(self, text: str) -> int:
        """Length of the longest suffix of `text` that is a proper prefix of
        a protected phrase (so more of the phrase may still be coming)."""
        low = text.lower()
        best = 0
        for phrase in self._phrases:
            for n in range(min(len(phrase) - 1, len(low)), 0, -1):
                if n <= best:
                    break
                if phrase.startswith(low[-n:]):
                    # Only hold from a word start, never mid-word noise.
                    start = len(low) - n
                    if start == 0 or not low[start - 1].isalnum():
                        best = n
                    break
        return best

    def feed(self, token: str) -> str:
        """Text that is safe to send now; the rest stays held."""
        if not self._phrases:
            return token
        text = self._held + token
        n = self._hold_len(text)
        self._held = text[len(text) - n:] if n else ""
        return text[: len(text) - n] if n else text

    def flush(self) -> str:
        out, self._held = self._held, ""
        return out


def canned_goodbye_text(template: str | None = None, name: str | None = None) -> str:
    """The ready-made goodbye with the business name filled in, spoken form
    ("Peach tree Pedals"). Sent as one text frame, so the name is never split
    into sub-word tokens. Without a name, " {business}" is dropped."""
    from . import config

    template = config.CANNED_GOODBYE_TEXT if template is None else template
    if "{business}" not in template:
        return template
    if name is None:
        try:
            from . import business_hours

            name = business_hours.business_name()
        except Exception:  # noqa: BLE001
            name = ""
    if name:
        from .guide_publish.render import spoken_name

        return template.replace("{business}", spoken_name(name))
    return template.replace(" {business}", "").replace("{business}", "")
