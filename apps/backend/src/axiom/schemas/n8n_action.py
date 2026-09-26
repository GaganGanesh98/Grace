"""Request/response for POST /webhooks/n8n/govern-action (Phase 9.1).

The wire contract for external orchestrators. Deliberately flat and
string-typed: the caller is an n8n Code node, not a typed SDK client.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

#: What the orchestrator may ask for. `advise` maps onto the engine's `shadow`
#: mode: the action is evaluated and a receipt is written, but the response
#: always reads `allow` so the workflow proceeds. Use it to observe what a
#: policy *would* do before switching a workflow to `enforce`.
ActionMode = Literal["enforce", "advise"]


class N8nGovernActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(
        ..., min_length=1, max_length=255, description="n8n workflow identifier."
    )
    workflow_run_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description=(
            "n8n execution id. Used as the idempotency key — replaying the same "
            "(workflow_id, workflow_run_id) returns the original receipt rather "
            "than governing the action twice."
        ),
    )
    project_id: UUID = Field(..., description="Project whose policy governs this action.")
    agent_id: str = Field(..., min_length=1, max_length=255)
    action_type: str = Field(..., min_length=1, max_length=255)
    target: str = Field(..., min_length=1, max_length=1024)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk: Literal["low", "medium", "high"] = "medium"
    mode: ActionMode = "enforce"


class N8nGovernActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    verdict: str = Field(
        ...,
        description=(
            "Policy outcome: `allow`, `deny`, or `hold`. A `correct` verdict is "
            "reserved for policies that rewrite parameters; the current YAML "
            "engine does not emit one."
        ),
    )
    reason: str | None = Field(None, description="Why, when the policy supplied a reason.")
    verify_url: str = Field(..., description="Public URL that independently verifies the receipt.")
    corrected_parameters: dict[str, Any] | None = Field(
        None,
        description=(
            "Parameters the workflow should use instead of the ones it sent. "
            "Populated only by a `correct` verdict; always null today."
        ),
    )
    replayed: bool = Field(
        default=False,
        description=(
            "True when this response was served from the idempotency record "
            "rather than by governing the action again."
        ),
    )
