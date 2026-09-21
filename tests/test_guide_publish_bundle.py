"""The invariants that stand between a console click and a broken phone line.

GuideAnts' import is a FULL DECLARATIVE REPLACEMENT: anything missing from
the bundle is deleted from the live guide. These tests exist so that a
malformed bundle is refused here, before any network call, rather than
silently lobotomizing the receptionist.
"""

import io
import json
import zipfile

import pytest

from app import config
from app.guide_publish import bundle, template

GOOD_INSTRUCTIONS = "You are the phone receptionist.\nDeclare victory.\n"


def _static():
    return template.load_static_files()


def _zip_names(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return sorted(archive.namelist())


def test_bundle_contains_every_required_file():
    data, _ = bundle.build_bundle(GOOD_INSTRUCTIONS, {}, _static())
    names = _zip_names(data)
    assert "manifest.json" in names
    assert "instructions.md" in names
    assert "OpenAPI/voice-receptionist.json" in names
    assert "OpenAPI/caller-phone.json" in names


def test_instructions_are_written_as_instructions_md_not_the_template_name():
    """GuideAnts' importer looks for instructions.md; a bundle carrying
    instructions.template.md would import an empty prompt."""
    data, _ = bundle.build_bundle(GOOD_INSTRUCTIONS, {}, _static())
    assert "instructions.template.md" not in _zip_names(data)


def test_knowledge_files_are_included():
    knowledge = {"VectorStores/default/k1.md": b"# Damage policy\n"}
    data, _ = bundle.build_bundle(GOOD_INSTRUCTIONS, knowledge, _static())
    assert "VectorStores/default/k1.md" in _zip_names(data)


def test_hash_is_stable_across_builds_and_sensitive_to_content():
    first, hash_a = bundle.build_bundle(GOOD_INSTRUCTIONS, {}, _static())
    second, hash_b = bundle.build_bundle(GOOD_INSTRUCTIONS, {}, _static())
    _, hash_c = bundle.build_bundle(GOOD_INSTRUCTIONS + "extra", {}, _static())
    assert hash_a == hash_b
    assert hash_a != hash_c


# --- invariant 1: the tool surface ---------------------------------------

def test_missing_findReservations_is_refused():
    """The regression guard for this repo's real, historical landmine: the
    old exported schema was missing findReservations, and importing it
    would have deleted the tool the cancellation flow depends on."""
    static = _static()
    schema = json.loads(static["OpenAPI/voice-receptionist.json"])
    schema["paths"] = {
        path: methods
        for path, methods in schema["paths"].items()
        if not any(
            op.get("operationId") == "findReservations" for op in methods.values()
        )
    }
    static["OpenAPI/voice-receptionist.json"] = json.dumps(schema).encode()

    with pytest.raises(bundle.BundleError, match="findReservations"):
        bundle.build_bundle(GOOD_INSTRUCTIONS, {}, static)


def test_missing_schema_file_is_refused():
    static = _static()
    del static["OpenAPI/caller-phone.json"]
    with pytest.raises(bundle.BundleError, match="caller-phone"):
        bundle.build_bundle(GOOD_INSTRUCTIONS, {}, static)


def test_unparseable_schema_is_refused():
    static = _static()
    static["OpenAPI/caller-phone.json"] = b"{not json"
    with pytest.raises(bundle.BundleError, match="parse"):
        bundle.build_bundle(GOOD_INSTRUCTIONS, {}, static)


# --- invariant 2: the manifest name --------------------------------------

def test_manifest_name_must_match_the_configured_guide_name():
    static = _static()
    static["manifest.json"] = json.dumps({"name": "Some Other Guide"}).encode()
    with pytest.raises(bundle.BundleError, match="manifest name"):
        bundle.build_bundle(GOOD_INSTRUCTIONS, {}, static)


def test_manifest_name_matches_config_by_default():
    manifest = json.loads(_static()["manifest.json"])
    assert manifest["name"] == config.GUIDEANTS_GUIDE_NAME


# --- invariant 3: the instructions ---------------------------------------

def test_empty_instructions_are_refused():
    with pytest.raises(bundle.BundleError, match="empty"):
        bundle.build_bundle("   ", {}, _static())


def test_instructions_missing_the_sentinel_are_refused():
    with pytest.raises(bundle.BundleError, match="sentinel"):
        bundle.build_bundle("You are a receptionist.", {}, _static())


def test_unfilled_slot_in_instructions_is_refused():
    with pytest.raises(bundle.BundleError, match="unfilled"):
        bundle.build_bundle(GOOD_INSTRUCTIONS + " {{business.name}}", {}, _static())


# --- The stale-schema landmine, pinned shut ------------------------------
# guide-demo/tools/*.json is the canonical location operators edit (CLAUDE.md
# says so); guide-demo/template/OpenAPI/*.json is what actually gets
# published. They are two independent file copies, and bundle.py's
# EXPECTED_OPERATION_IDS check only catches a missing or extra operationId --
# never a changed parameter, enum or description. This repo already lived
# through exactly that drift once: the original exported folder's
# voice-receptionist.json had lost `findReservations` entirely.
#
# These two tests are the pin. Edit one copy without the other and CI fails
# immediately, instead of the divergence reaching a live guide.

_SCHEMA_PAIRS = (
    ("OpenAPI/voice-receptionist.json", "reservations-client-tool.json"),
    ("OpenAPI/caller-phone.json", "caller-phone-client-tool.json"),
)


@pytest.mark.parametrize("published, canonical", _SCHEMA_PAIRS)
def test_published_tool_schema_matches_the_canonical_copy(published, canonical):
    published_bytes = (template.TEMPLATE_DIR / published).read_bytes()
    canonical_bytes = (
        template.TEMPLATE_DIR.parent / "tools" / canonical
    ).read_bytes()

    assert published_bytes == canonical_bytes, (
        f"guide-demo/template/{published} has drifted from the canonical "
        f"guide-demo/tools/{canonical}. Copy the canonical file over the "
        "template one -- the template copy is what a publish actually sends, "
        "and GuideAnts' import replaces the guide's tools wholesale."
    )
