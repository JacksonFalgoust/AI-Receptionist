"""The guide's tool names a workflow step may reference. Must match the
operationIds in guide-demo/tools/*.json and the frontend's WORKFLOW_TOOLS
(frontend/src/types/workflow.ts); tests enforce both."""

WORKFLOW_TOOLS: tuple[str, ...] = (
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
