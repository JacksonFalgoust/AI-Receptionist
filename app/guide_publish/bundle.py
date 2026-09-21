"""Assembles the guide bundle and refuses to build an unsafe one.

GuideAnts' import wipes and replaces every dependent collection on the
guide -- tools, OpenAPI schemas, context options, vector-store files -- and
then re-adds whatever the zip contains. Anything omitted is DELETED from
the live guide.

That makes omission the dangerous failure mode, and it is a silent one: a
guide stripped of its tools still answers the phone perfectly fluently and
simply cannot do anything. Every check here runs before any network call,
so the failure is a refused publish rather than a damaged receptionist.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

from .. import config

# The guide's entire tool surface, matching what app/guide_client.py
# dispatches. Pinned as a constant so a truncated or stale schema fails
# loudly instead of quietly removing a capability.
EXPECTED_OPERATION_IDS = frozenset(
    {
        "listCatalog",
        "checkAvailability",
        "findReservations",
        "listCustomers",
        "createCustomer",
        "createReservation",
        "cancelReservation",
        "sendPaymentLink",
        "get_caller_phone_number",
    }
)

SCHEMA_FILES = ("OpenAPI/voice-receptionist.json", "OpenAPI/caller-phone.json")

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


class BundleError(ValueError):
    """A bundle failed an invariant and must not be published."""


def _operation_ids(static: dict[str, bytes]) -> set[str]:
    found: set[str] = set()
    for name in SCHEMA_FILES:
        if name not in static:
            raise BundleError(f"tool schema missing from bundle: {name}")
        try:
            document = json.loads(static[name])
        except (ValueError, UnicodeDecodeError) as exc:
            raise BundleError(f"could not parse tool schema {name}: {exc}") from exc
        for methods in document.get("paths", {}).values():
            for method, operation in methods.items():
                if method.lower() in _HTTP_METHODS and "operationId" in operation:
                    found.add(operation["operationId"])
    return found


def _check_tools(static: dict[str, bytes]) -> None:
    found = _operation_ids(static)
    missing = EXPECTED_OPERATION_IDS - found
    if missing:
        raise BundleError(
            "bundle would delete live tools -- missing operation(s): "
            + ", ".join(sorted(missing))
        )
    unexpected = found - EXPECTED_OPERATION_IDS
    if unexpected:
        raise BundleError(
            "bundle declares unknown tool(s) this app cannot answer: "
            + ", ".join(sorted(unexpected))
        )


def _check_manifest(static: dict[str, bytes]) -> None:
    if "manifest.json" not in static:
        raise BundleError("manifest.json missing from bundle")
    try:
        manifest = json.loads(static["manifest.json"])
    except (ValueError, UnicodeDecodeError) as exc:
        raise BundleError(f"could not parse manifest.json: {exc}") from exc
    name = manifest.get("name")
    if name != config.GUIDEANTS_GUIDE_NAME:
        raise BundleError(
            f"manifest name {name!r} does not match GUIDEANTS_GUIDE_NAME "
            f"{config.GUIDEANTS_GUIDE_NAME!r} -- importing it would create a "
            "second guide instead of updating the live one"
        )


def _check_instructions(instructions: str) -> None:
    if not instructions.strip():
        raise BundleError("rendered instructions are empty")
    if "{{" in instructions:
        raise BundleError("rendered instructions contain an unfilled slot")
    sentinel = config.FINAL_ANSWER_SENTINEL
    if sentinel and sentinel.lower() not in instructions.lower():
        raise BundleError(
            f"rendered instructions do not contain the final-answer sentinel "
            f"{sentinel!r} -- the app would never speak the guide's replies"
        )


def build_bundle(
    instructions: str, knowledge: dict[str, bytes], static: dict[str, bytes]
) -> tuple[bytes, str]:
    """Returns (zip_bytes, content_hash). Raises BundleError if any
    invariant fails -- always before the caller reaches the network."""
    _check_instructions(instructions)
    _check_manifest(static)
    _check_tools(static)

    files: dict[str, bytes] = dict(static)
    files["instructions.md"] = instructions.encode("utf-8")
    files.update(knowledge)

    # Fixed timestamps and sorted order so identical content always produces
    # an identical archive -- the no-op check compares hashes.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name])

    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8"))
        digest.update(files[name])
    return buffer.getvalue(), digest.hexdigest()
