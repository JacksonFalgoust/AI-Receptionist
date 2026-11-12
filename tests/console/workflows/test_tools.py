import json
import re
from pathlib import Path

import pytest

from app.console.workflows.tools import WORKFLOW_TOOLS

ROOT = Path(__file__).resolve().parents[3]


def test_workflow_tools_match_the_guide_tool_schemas():
    ids = set()
    for path in (ROOT / "guide-demo" / "tools").glob("*.json"):
        spec = json.loads(path.read_text())
        for operations in spec.get("paths", {}).values():
            for op in operations.values():
                if isinstance(op, dict) and "operationId" in op:
                    ids.add(op["operationId"])
    assert set(WORKFLOW_TOOLS) == ids
    assert len(WORKFLOW_TOOLS) == len(set(WORKFLOW_TOOLS))


@pytest.mark.xfail(strict=True, reason="frontend list added in Task 5")
def test_frontend_tool_list_matches_backend():
    text = (ROOT / "frontend" / "src" / "types" / "workflow.ts").read_text()
    block = re.search(r"WORKFLOW_TOOLS\s*=\s*\[(.*?)\]\s*as const", text, re.S).group(1)
    assert tuple(re.findall(r"""["']([^"']+)["']""", block)) == WORKFLOW_TOOLS


def test_workflow_tools_exact_order():
    assert WORKFLOW_TOOLS == (
        "listCatalog",
        "checkAvailability",
        "findReservations",
        "listCustomers",
        "createCustomer",
        "createReservation",
        "cancelReservation",
        "sendPaymentLink",
        "get_caller_phone_number",
        "endCall",
    )
