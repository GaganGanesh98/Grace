"""MCP tool behaviour: governance round trip, tenancy, and dry-run semantics."""

from __future__ import annotations

import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from axiom.db import session_scope
from axiom.mcp import schemas
from axiom.mcp.auth import SCOPE_READ, SCOPE_WRITE, resolve_principal
from axiom.mcp.tools import (
    ToolError,
    _payload_hash_matches,
    check_policy,
    get_receipt,
    govern_action,
    list_policies,
    verify_receipt,
)
from axiom.models.receipt import Receipt
from axiom.services.policy.evaluator import Verdict
from tests.fixtures.governance import bootstrap_project_with_api_key

MCP_SCOPES = [SCOPE_READ, SCOPE_WRITE]

_ALLOW_CHAT = [
    {"id": "allow_chat", "description": "Allow chat", "when": {"type": "chat"}, "then": "approve"}
]
_DENY_EMAIL = [
    {
        "id": "block_email",
        "description": "Block outbound email",
        "when": {"type": "send_email"},
        "then": "deny",
    }
]


async def _principal(fx: dict[str, str]):  # type: ignore[no-untyped-def]
    async with session_scope() as db:
        return await resolve_principal(db, fx["api_key_full"])


@pytest.mark.asyncio
async def test_govern_then_verify_round_trip(client: AsyncClient) -> None:
    """The headline contract: govern an action, then verify its receipt.

    Runs through the real pipeline and the real crypto — no mocks. If this
    passes, the MCP surface is producing first-class entries in the same
    Merkle chain as POST /v1/govern.
    """

    fx = await bootstrap_project_with_api_key(client, policy_rules=_ALLOW_CHAT, scopes=MCP_SCOPES)
    principal = await _principal(fx)

    async with session_scope() as db:
        governed = await govern_action(
            db,
            principal,
            schemas.GovernActionInput.model_validate(
                {"action": {"type": "chat", "body": "hi"}, "agent_id": fx["agent_id"]}
            ),
        )

    assert governed.verdict is Verdict.APPROVE
    assert governed.allowed is True
    assert governed.receipt_id.startswith("rcpt_")
    assert governed.decision.startswith("ALLOWED")
    assert governed.verify_url.endswith(f"/v1/verify/{governed.receipt_id}")

    async with session_scope() as db:
        verified = await verify_receipt(
            db, principal, schemas.VerifyReceiptInput(receipt_id=governed.receipt_id)
        )

    assert verified.verified is True, verified.summary
    assert verified.checks.ed25519_signature_valid is True
    assert verified.checks.ml_dsa_signature_valid is True
    assert verified.checks.merkle_inclusion_valid is True
    assert verified.checks.payload_hash_matches is True
    assert verified.summary.startswith("VERIFIED")


@pytest.mark.asyncio
async def test_deny_verdict_states_obligation_in_prose(client: AsyncClient) -> None:
    """ADR-027: the decision sentence must be unmissable, not just structured."""

    fx = await bootstrap_project_with_api_key(client, policy_rules=_DENY_EMAIL, scopes=MCP_SCOPES)
    principal = await _principal(fx)

    async with session_scope() as db:
        result = await govern_action(
            db,
            principal,
            schemas.GovernActionInput.model_validate(
                {"action": {"type": "send_email", "to": "x"}, "agent_id": fx["agent_id"]}
            ),
        )

    assert result.verdict is Verdict.DENY
    assert result.allowed is False
    assert result.decision.startswith("DENIED")
    assert "must NOT" in result.decision
    assert result.dispatched is False


@pytest.mark.asyncio
async def test_shadow_mode_says_so_in_the_decision(client: AsyncClient) -> None:
    """A non-blocking verdict must never read as a plain allow."""

    fx = await bootstrap_project_with_api_key(client, policy_rules=_DENY_EMAIL, scopes=MCP_SCOPES)
    principal = await _principal(fx)

    async with session_scope() as db:
        result = await govern_action(
            db,
            principal,
            schemas.GovernActionInput.model_validate(
                {
                    "action": {"type": "send_email", "to": "x"},
                    "agent_id": fx["agent_id"],
                    "mode": "shadow",
                }
            ),
        )

    assert "SHADOW MODE" in result.decision
    assert result.dispatched is False


@pytest.mark.asyncio
async def test_check_policy_creates_no_receipt(client: AsyncClient) -> None:
    """The dry-run must leave the audit log untouched."""

    fx = await bootstrap_project_with_api_key(client, policy_rules=_ALLOW_CHAT, scopes=MCP_SCOPES)
    principal = await _principal(fx)

    async with session_scope() as db:
        before = await db.scalar(select(func.count()).select_from(Receipt))

    async with session_scope() as db:
        result = await check_policy(
            db, principal, schemas.CheckPolicyInput(action={"type": "chat"})
        )

    async with session_scope() as db:
        after = await db.scalar(select(func.count()).select_from(Receipt))

    assert before == after, "check_policy must not write a receipt"
    assert result.is_audit_record is False
    assert result.verdict is Verdict.APPROVE
    assert "DRY RUN" in result.decision


@pytest.mark.asyncio
async def test_check_policy_predicts_the_real_verdict(client: AsyncClient) -> None:
    """A dry run that disagrees with the pipeline is worse than no dry run."""

    fx = await bootstrap_project_with_api_key(client, policy_rules=_DENY_EMAIL, scopes=MCP_SCOPES)
    principal = await _principal(fx)
    action = {"type": "send_email", "to": "someone"}

    async with session_scope() as db:
        predicted = await check_policy(db, principal, schemas.CheckPolicyInput(action=action))

    async with session_scope() as db:
        actual = await govern_action(
            db,
            principal,
            schemas.GovernActionInput.model_validate(
                {"action": action, "agent_id": fx["agent_id"]}
            ),
        )

    assert predicted.verdict == actual.verdict


@pytest.mark.asyncio
async def test_no_policy_fails_closed(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=[], scopes=MCP_SCOPES)
    principal = await _principal(fx)

    async with session_scope() as db:
        result = await check_policy(
            db, principal, schemas.CheckPolicyInput(action={"type": "anything"})
        )

    assert result.verdict is Verdict.DENY
    assert result.allowed is False


@pytest.mark.asyncio
async def test_cross_project_receipt_is_not_found(client: AsyncClient) -> None:
    """Tenancy: project B's receipt must be indistinguishable from a bad id.

    Asserts *not found* rather than *forbidden* — a caller must not be able to
    confirm that a receipt id exists in a tenant they cannot read.
    """

    fx_a = await bootstrap_project_with_api_key(client, policy_rules=_ALLOW_CHAT, scopes=MCP_SCOPES)
    fx_b = await bootstrap_project_with_api_key(client, policy_rules=_ALLOW_CHAT, scopes=MCP_SCOPES)
    principal_a = await _principal(fx_a)
    principal_b = await _principal(fx_b)

    async with session_scope() as db:
        governed_a = await govern_action(
            db,
            principal_a,
            schemas.GovernActionInput.model_validate(
                {"action": {"type": "chat"}, "agent_id": fx_a["agent_id"]}
            ),
        )

    async with session_scope() as db:
        with pytest.raises(ToolError, match="not found"):
            await get_receipt(
                db, principal_b, schemas.GetReceiptInput(receipt_id=governed_a.receipt_id)
            )
        with pytest.raises(ToolError, match="not found"):
            await verify_receipt(
                db, principal_b, schemas.VerifyReceiptInput(receipt_id=governed_a.receipt_id)
            )


@pytest.mark.asyncio
async def test_get_receipt_never_returns_evidence(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=_ALLOW_CHAT, scopes=MCP_SCOPES)
    principal = await _principal(fx)

    async with session_scope() as db:
        governed = await govern_action(
            db,
            principal,
            schemas.GovernActionInput.model_validate(
                {"action": {"type": "chat"}, "agent_id": fx["agent_id"]}
            ),
        )

    async with session_scope() as db:
        fetched = await get_receipt(
            db, principal, schemas.GetReceiptInput(receipt_id=governed.receipt_id)
        )

    dumped = fetched.model_dump()
    assert "evidence_ciphertext" not in dumped
    assert "evidence_nonce" not in dumped
    assert fetched.receipt_id == governed.receipt_id


@pytest.mark.asyncio
async def test_unknown_receipt_is_not_found(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, scopes=MCP_SCOPES)
    principal = await _principal(fx)
    async with session_scope() as db:
        with pytest.raises(ToolError, match="not found"):
            await get_receipt(db, principal, schemas.GetReceiptInput(receipt_id="rcpt_nope"))


@pytest.mark.asyncio
async def test_list_policies_scoped_to_project(client: AsyncClient) -> None:
    fx_a = await bootstrap_project_with_api_key(client, policy_rules=_ALLOW_CHAT, scopes=MCP_SCOPES)
    fx_b = await bootstrap_project_with_api_key(client, policy_rules=_DENY_EMAIL, scopes=MCP_SCOPES)
    principal_a = await _principal(fx_a)

    async with session_scope() as db:
        listed = await list_policies(db, principal_a, schemas.ListPoliciesInput())

    ids = {p.policy_id for p in listed.policies}
    assert fx_a["policy_id"] in ids
    assert fx_b["policy_id"] not in ids
    assert listed.policies[0].rules[0].id == "allow_chat"
    assert "first match wins" in listed.summary


class _FakeReceipt:
    """Minimal stand-in for a Receipt row — only the evidence envelope fields."""

    def __init__(
        self,
        nonce: bytes | None,
        ciphertext: bytes | None,
        key_id: str | None,
        payload_hash: bytes,
    ) -> None:
        self.evidence_nonce = nonce
        self.evidence_ciphertext = ciphertext
        self.evidence_key_id = key_id
        self.payload_hash = payload_hash


def _envelope_hash(nonce: bytes, ciphertext: bytes, key_id: str) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(nonce)
    hasher.update(ciphertext)
    hasher.update(key_id.encode("utf-8"))
    return hasher.digest()


def test_payload_hash_matches_accepts_intact_evidence() -> None:
    nonce, ct, kid = b"\x00" * 12, b"ciphertext-bytes", "key-1"
    receipt = _FakeReceipt(nonce, ct, kid, _envelope_hash(nonce, ct, kid))
    assert _payload_hash_matches(receipt) is True  # type: ignore[arg-type]


def test_payload_hash_matches_detects_tampered_ciphertext() -> None:
    """The whole point of the check: post-hoc evidence edits must be caught."""

    nonce, ct, kid = b"\x00" * 12, b"ciphertext-bytes", "key-1"
    good = _envelope_hash(nonce, ct, kid)
    tampered = _FakeReceipt(nonce, ct[:-1] + bytes([ct[-1] ^ 0xFF]), kid, good)
    assert _payload_hash_matches(tampered) is False  # type: ignore[arg-type]


def test_payload_hash_matches_detects_swapped_key_id() -> None:
    nonce, ct, kid = b"\x00" * 12, b"ciphertext-bytes", "key-1"
    good = _envelope_hash(nonce, ct, kid)
    swapped = _FakeReceipt(nonce, ct, "key-2", good)
    assert _payload_hash_matches(swapped) is False  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("nonce", "ciphertext", "key_id"),
    [(None, b"c", "k"), (b"n", None, "k"), (b"n", b"c", None), (b"n", b"c", "")],
)
def test_payload_hash_fails_closed_without_evidence(
    nonce: bytes | None, ciphertext: bytes | None, key_id: str | None
) -> None:
    """An unverifiable receipt is not a verified one."""

    receipt = _FakeReceipt(nonce, ciphertext, key_id, b"\x00" * 32)
    assert _payload_hash_matches(receipt) is False  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_oversized_action_rejected(client: AsyncClient) -> None:
    fx = await bootstrap_project_with_api_key(client, policy_rules=_ALLOW_CHAT, scopes=MCP_SCOPES)
    principal = await _principal(fx)
    huge = {"type": "chat", "body": "x" * (100 * 1024 + 64)}

    async with session_scope() as db:
        with pytest.raises(ToolError, match="100 KB"):
            await govern_action(
                db,
                principal,
                schemas.GovernActionInput.model_validate(
                    {"action": huge, "agent_id": fx["agent_id"]}
                ),
            )
