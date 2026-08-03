#!/usr/bin/env python3
"""End-to-end client for the Phase 2.5 governance engine.

Auth notes (see axiom.deps.require_api_key and routers/govern.py):
  - POST /v1/govern (legacy ReceiptService) and POST /v1/governance/govern (Phase 2.5)
    both use **API keys only**: Authorization: Bearer axm_<...> or X-Api-Key.
  - JWT (Bearer access token from /api/v1/auth) is used for /api/v1/projects, etc.,
    not for these /v1/govern* routes.

This script signs up a user (JWT), creates a project + API key, then calls the
governance engine under **/v1/governance/** (not the legacy /v1/govern body shape).

Usage (from apps/backend, API running on AXIOM_BASE_URL):
  uv run python scripts/test_governance.py

Env:
  AXIOM_BASE_URL   default http://127.0.0.1:8000
  DATABASE_URL     optional; must match the API process if using DB for /verify payload
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import uuid
from typing import Any
from uuid import UUID

import httpx

# Repo imports (package installed editable from apps/backend)
from axiom.db import session_scope
from axiom.models.governance import GovernanceIntent, GovernanceReceipt, GovernanceVerdict
from axiom.models.project import Project
from axiom.services.crypto.canonical_json import canonicalize
from axiom.services.governance.receipt import approval_dict_from_receipt, unsigned_receipt_for_sealing


def _j(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)


async def _ensure_project_policy(project_id: UUID, profile: str) -> None:
    async with session_scope() as session:
        project = await session.get(Project, project_id)
        if project is None:
            print("ERROR: project not found for policy update", file=sys.stderr)
            return
        settings = dict(project.settings)
        settings["governance_policy"] = profile
        project.settings = settings


async def main() -> int:  # noqa: PLR0915
    base = os.environ.get("AXIOM_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    email = f"gov-e2e-{uuid.uuid4().hex[:12]}@example.com"
    password = os.environ.get("AXIOM_E2E_PASSWORD", "password1a")

    print("=== AXIOM governance E2E (Phase 2.5: /v1/governance/*) ===\n")
    print(
        "Auth: /v1/governance/* uses API key (govern:write), same mechanism as legacy /v1/govern.\n"
        "JWT is only used here to create project + mint the API key via /api/v1/*.\n"
    )

    async with httpx.AsyncClient(base_url=base, timeout=120.0) as client:
        # 1) Signup (JWT issued)
        su = await client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": password, "full_name": "E2E Gov"},
        )
        if su.status_code != 201:
            print("signup failed:", su.status_code, su.text, file=sys.stderr)
            return 1
        tokens = su.json()["data"]
        access = tokens["access_token"]
        h = {"Authorization": f"Bearer {access}"}
        # Allow get_db to commit the new user before the next HTTP call (yielded session).
        await asyncio.sleep(0.2)

        # 2) Project
        slug = f"gov-e2e-{uuid.uuid4().hex[:8]}"
        pr = await client.post(
            "/api/v1/projects",
            headers=h,
            json={"name": "Governance E2E", "slug": slug},
        )
        if pr.status_code != 201:
            print("project create failed:", pr.status_code, pr.text, file=sys.stderr)
            return 1
        project_id = pr.json()["data"]["id"]
        print("Created project:", project_id)

        await asyncio.sleep(0.2)
        await _ensure_project_policy(UUID(project_id), "starter-safe")

        # 3) API key (govern:write) — this is what /v1/governance/govern expects
        kr = await client.post(
            f"/api/v1/projects/{project_id}/api-keys",
            headers=h,
            json={"name": "e2e-governance", "scopes": ["govern:write"]},
        )
        if kr.status_code != 201:
            print("api key create failed:", kr.status_code, kr.text, file=sys.stderr)
            return 1
        api_key_full = kr.json()["data"]["full_key"]
        api_hdr = {"Authorization": f"Bearer {api_key_full}"}
        # get_db commits after the handler returns; the next request can run before the
        # api_keys row is visible without a short pause.
        await asyncio.sleep(0.2)

        # 4) POST /v1/governance/govern (Phase 2.5 GovernRequest)
        gov_body = {
            "agent_id": "e2e-agent-1",
            "action_type": "tool.http.get",
            "target": "https://api.example.com/resource",
            "parameters": {},
            "risk": "low",
            "mode": "enforce",
            "metadata": {},
        }
        gov = await client.post("/v1/governance/govern", headers=api_hdr, json=gov_body)
        print("\n--- POST /v1/governance/govern ---")
        print("status:", gov.status_code)
        if gov.status_code != 200:
            print(gov.text, file=sys.stderr)
            return 1
        gov_json = gov.json()
        print(_j(gov_json))

        receipt_id = gov_json["receipt_id"]
        verdict = gov_json["verdict"]

        # 5) POST /v1/governance/report (if allow)
        if verdict == "allow":
            rep_body = {
                "receipt_id": receipt_id,
                "outcome": {
                    "target": "https://api.example.com/resource",
                    "action_type": "tool.http.get",
                    "risk": "low",
                },
            }
            rep = await client.post("/v1/governance/report", headers=api_hdr, json=rep_body)
            print("\n--- POST /v1/governance/report ---")
            print("status:", rep.status_code)
            if rep.status_code != 200:
                print(rep.text, file=sys.stderr)
                return 1
            print(_j(rep.json()))
        else:
            print("\n(skipping report: verdict != allow)")

        # 6) GET /v1/governance/receipts/{id}
        gr = await client.get(
            f"/v1/governance/receipts/{receipt_id}",
            headers=api_hdr,
        )
        print("\n--- GET /v1/governance/receipts/{id} ---")
        print("status:", gr.status_code)
        if gr.status_code != 200:
            print(gr.text, file=sys.stderr)
            return 1
        receipt_view = gr.json()
        print(_j(receipt_view))

        # 7) POST /v1/governance/verify — build canonical payload via DB (same as server seal)
        receipt_json: str | None = None
        ed_sig_b64 = ""
        ml_sig_b64 = ""
        merkle_root_hex = ""
        path: list[str] = []
        leaf_index: int | None = None
        tree_size: int | None = None

        async with session_scope() as session:
            greceipt = await session.get(GovernanceReceipt, UUID(receipt_id))
            if greceipt is None or greceipt.status != "sealed":
                print(
                    "\n--- POST /v1/governance/verify ---\n"
                    "skip: receipt not sealed in DB "
                    "(report may have failed or verdict was not allow).",
                    file=sys.stderr,
                )
                return 0 if verdict != "allow" else 1
            intent = await session.get(GovernanceIntent, greceipt.intent_id)
            verdict_row = await session.get(GovernanceVerdict, greceipt.verdict_id)
            assert intent is not None and verdict_row is not None
            payload_obj = unsigned_receipt_for_sealing(
                receipt_id=str(greceipt.id),
                intent=intent,
                verdict=verdict_row,
                execution_data=greceipt.execution_data,
                verification_status=greceipt.verification or "",
                mismatches=list(greceipt.mismatches or []),
                executed_at=greceipt.executed_at,
                approval=approval_dict_from_receipt(greceipt),
            )
            receipt_json = canonicalize(payload_obj).decode("utf-8")
            if greceipt.ed25519_sig:
                ed_sig_b64 = base64.b64encode(greceipt.ed25519_sig).decode("ascii")
            if greceipt.ml_dsa_sig:
                ml_sig_b64 = base64.b64encode(greceipt.ml_dsa_sig).decode("ascii")
            if greceipt.merkle_root:
                merkle_root_hex = greceipt.merkle_root.hex()
            mp = greceipt.merkle_proof if isinstance(greceipt.merkle_proof, dict) else {}
            raw_path = mp.get("path") if isinstance(mp.get("path"), list) else []
            path = [str(x) for x in raw_path]
            leaf_index = int(mp["leaf_index"]) if mp.get("leaf_index") is not None else None
            tree_size = int(mp["tree_size"]) if mp.get("tree_size") is not None else None

        assert receipt_json is not None
        pub = receipt_view.get("signer_public") or {}
        ed_pub = str(pub.get("ed25519_public_pem") or "")
        ml_pub = str(pub.get("ml_dsa_public_b64") or "")
        if not ed_pub or not ml_pub:
            print(
                "\n--- POST /v1/governance/verify ---\n"
                "skip: GET receipt did not include signer_public (need sealed receipt).",
                file=sys.stderr,
            )
            return 1
        vbody = {
            "receipt_json": receipt_json,
            "ed25519_signature": ed_sig_b64,
            "ml_dsa_signature": ml_sig_b64,
            "merkle_proof": path,
            "merkle_root": merkle_root_hex,
            "ed25519_public_key": ed_pub,
            "ml_dsa_public_key": ml_pub,
            "leaf_index": leaf_index,
            "tree_size": tree_size,
        }
        vr = await client.post("/v1/governance/verify", json=vbody)
        print("\n--- POST /v1/governance/verify ---")
        print("status:", vr.status_code)
        if vr.status_code != 200:
            print(vr.text, file=sys.stderr)
            return 1
        print(_j(vr.json()))

    print("\n=== done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
