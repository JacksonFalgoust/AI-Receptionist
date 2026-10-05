"""GuideAnts connection: the AsyncOpenAI client for the published guide's
OpenAI-compatible Responses endpoint, plus helpers that read a response's
conversation id and recognize the error codes meaning a conversation can't
be continued."""

import openai
from openai import AsyncOpenAI

from app import config

_client: AsyncOpenAI | None = None

_LOST_CONVERSATION_CODES = {"conversation_not_found", "invalid_conversation_id"}

# GuideAnts rejects a function_call_output whose turn is no longer "streaming"
# (it completed, or -- the case we hit -- was cancelled server-side when a
# mid-stream disconnect aborted the request that carried it). See
# GuideAnts' WireToolResultContinuation.cs. Treated like a lost conversation:
# the turn is unresumable, so recover by starting fresh rather than crashing.
_STALE_TOOL_RESULT_CODE = "tool_results_not_pending"


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not config.GUIDEANTS_PUB_ID:
            raise RuntimeError(
                "GUIDEANTS_PUB_ID is not set. Copy .env.example to .env and fill it in."
            )
        _client = AsyncOpenAI(
            base_url=f"{config.GUIDEANTS_BASE_URL}/api/published/openai/{config.GUIDEANTS_PUB_ID}/v1",
            api_key=config.GUIDEANTS_API_KEY or "anonymous",
            timeout=config.GUIDEANTS_TIMEOUT_SECONDS,
            max_retries=1,
        )
    return _client


def extract_conversation_id(response) -> str | None:
    # GuideAnts returns conversation as the plain string "conv_...". The
    # openai SDK's type annotation models it as an object with `.id`; handle
    # both shapes in case the SDK ever starts constructing that object.
    conv = getattr(response, "conversation", None)
    if isinstance(conv, str):
        return conv or None
    conv_id = getattr(conv, "id", None)
    return conv_id or None


def is_lost_conversation(err: "openai.BadRequestError") -> bool:
    code = getattr(err, "code", None)
    return code in _LOST_CONVERSATION_CODES


def is_stale_tool_result(err: "openai.BadRequestError") -> bool:
    return getattr(err, "code", None) == _STALE_TOOL_RESULT_CODE
