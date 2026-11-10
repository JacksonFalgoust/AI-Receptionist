"""Server-side backup for ending a call when the guide forgets endCall.

Conservative on purpose: it fires only when the caller has clearly finished
AND the receptionist's reply is itself a goodbye with no question in it.
"""

import re

_NORMALIZE = re.compile(r"[^a-z' ]+")
_GOODBYE = re.compile(r"\b(good ?bye|bye|bye bye|see you|have a (good|great|nice) (one|day|night))\b")
_DONE_PHRASES = {
    "no", "nope", "nah", "no thanks", "no thank you", "no thank you very much",
    "that's it", "that's all", "that is it", "that is all", "no that's it",
    "no that's all", "no that's it thank you", "no that's all thank you",
    "i'm good", "i'm all set", "nothing else", "no i'm good", "no i'm all set",
    "thank you", "thanks", "thank you so much", "thanks so much", "no thanks bye",
    "that's everything", "no that's everything", "all good", "we're good",
    "thank you bye", "thanks bye", "no thank you bye", "that's all thanks",
    "that's it thanks", "no that's it thanks", "that will be all", "that'll be all",
    "i'm good thanks", "i'm good thank you", "all set", "i'm done", "we're done",
}
# Leading acknowledgments stripped before matching ("okay, thank you" -> "thank you").
_LEADING_ACKS = ("okay", "ok", "alright", "all right", "great", "perfect", "cool", "oh", "well", "um", "uh")
_ANYTHING_ELSE = re.compile(
    r"\b(anything else|any other questions?|anything more|something else i can|else i can help|"
    r"other questions|if you have any (other|more) questions)\b"
)
_REPLY_GOODBYE = re.compile(r"\b(good ?bye|bye|thanks for calling|thank you for calling|have a (great|good|wonderful|nice))\b")


def _norm(text: str) -> str:
    return " ".join(_NORMALIZE.sub(" ", (text or "").lower().replace("\u2019", "'")).split())


def asked_anything_else(agent_text: str) -> bool:
    return bool(_ANYTHING_ELSE.search(_norm(agent_text)))


def _strip_acks(text: str) -> str:
    words = text.split()
    changed = True
    while changed and words:
        changed = False
        for ack in _LEADING_ACKS:
            ack_words = ack.split()
            if words[: len(ack_words)] == ack_words and len(words) > len(ack_words):
                words = words[len(ack_words):]
                changed = True
    return " ".join(words)


def caller_said_goodbye(user_text: str) -> bool:
    return bool(_GOODBYE.search(_norm(user_text)))


def caller_done(user_text: str) -> bool:
    norm = _norm(user_text)
    return norm in _DONE_PHRASES or _strip_acks(norm) in _DONE_PHRASES or caller_said_goodbye(user_text)


def reply_is_goodbye(reply_text: str) -> bool:
    return "?" not in (reply_text or "") and bool(_REPLY_GOODBYE.search(_norm(reply_text)))


def should_end(previous_agent_text: str, user_text: str, reply_text: str) -> bool:
    if not reply_is_goodbye(reply_text):
        return False
    if caller_said_goodbye(user_text):
        return True
    return asked_anything_else(previous_agent_text) and caller_done(user_text)


_BARE_GREETINGS = {"hi", "hello", "hey", "hi there", "hello there", "hey there", "hiya", "howdy", "good morning", "good afternoon", "good evening"}


def is_bare_greeting(text: str) -> bool:
    """A lone greeting with no request ("Hi.", "Hello?")."""
    return _norm(text) in _BARE_GREETINGS
