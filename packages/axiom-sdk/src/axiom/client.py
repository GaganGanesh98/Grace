"""HTTP client for the AXIOM API (internal)."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .config import get_config, user_agent
from .exceptions import AxiomError, AuthError, GovernanceDenied, GovernanceHeld
from .models import ChainResult, GovernResult, ReceiptResult, ReportResult, VerifyResult

_LOG = logging.getLogger("axiom.sdk")


class AxiomClient:
    """Sync HTTP client using ``requests``."""

    def __init__(self) -> None:
        self._session = requests.Session()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        config = get_config()
        url = f"{config.base_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": user_agent(),
        }
        extra_headers = kwargs.pop("headers", None)
        if extra_headers:
            headers.update(extra_headers)

        if config.debug:
            _LOG.debug("%s %s", method, path)

        try:
            resp = self._session.request(
                method, url, headers=headers, timeout=config.timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise AxiomError(f"Network error calling {method} {path}: {exc}") from exc

        if resp.status_code == 401:
            raise AuthError("Invalid or revoked API key")

        if resp.status_code >= 400:
            body: Any = {}
            ct = resp.headers.get("content-type", "")
            if "application/json" in ct:
                try:
                    body = resp.json()
                except json.JSONDecodeError:
                    body = {}
            detail: Any = body.get("detail") if isinstance(body, dict) else None
            if detail is None:
                detail = resp.text or f"HTTP {resp.status_code}"
            raise AxiomError(f"API error {resp.status_code}: {detail}")

        if resp.status_code == 204 or not resp.content:
            return {}

        ct = resp.headers.get("content-type", "")
        if "application/json" not in ct:
            raise AxiomError(f"Unexpected response content-type for {path}: {ct or 'missing'}")
        try:
            out = resp.json()
        except json.JSONDecodeError as exc:
            raise AxiomError(f"Invalid JSON in response from {path}") from exc
        if not isinstance(out, dict):
            raise AxiomError(f"Expected JSON object from {path}")
        return out

    def govern(
        self,
        agent_id: str,
        action_type: str,
        target: str,
        risk: str = "low",
        parameters: dict[str, Any] | None = None,
        workflow: str | None = None,
        chain_id: str | None = None,
        enforce: bool = False,
    ) -> GovernResult:
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "action_type": action_type,
            "target": target,
            "risk": risk,
        }
        if parameters:
            payload["parameters"] = parameters
        if workflow:
            payload["workflow"] = workflow
        if chain_id:
            payload["chain_id"] = chain_id

        data = self._request("POST", "/v1/governance/govern", json=payload)

        result = GovernResult(
            verdict=data.get("verdict", "deny"),
            receipt_id=data.get("receipt_id", ""),
            chain_id=data.get("chain_id"),
            reason=data.get("reason"),
            policy_version=data.get("policy_version"),
            risk_assessed=data.get("risk_assessed"),
            raw=data,
        )

        if enforce:
            if result.verdict == "deny":
                raise GovernanceDenied(
                    verdict=result.verdict,
                    reason=result.reason,
                    receipt_id=result.receipt_id,
                )
            if result.verdict == "hold":
                raise GovernanceHeld(receipt_id=result.receipt_id)

        return result

    def report(self, receipt_id: str, outcome: dict[str, Any]) -> ReportResult:
        data = self._request(
            "POST",
            "/v1/governance/report",
            json={"receipt_id": receipt_id, "outcome": outcome},
        )
        return ReportResult(
            receipt_id=data.get("receipt_id", receipt_id),
            status=data.get("status", ""),
            verification=data.get("verification", "unverified"),
            signatures=data.get("signatures", {}),
            merkle=data.get("merkle", {}),
            raw=data,
        )

    def verify(self, receipt_id: str) -> VerifyResult:
        data = self._request(
            "POST",
            "/v1/governance/verify",
            json={"receipt_id": receipt_id},
        )
        return VerifyResult(
            valid=bool(data.get("valid", False)),
            checks=data.get("checks", {}),
            receipt_id=receipt_id,
            raw=data,
        )

    def get_receipt(self, receipt_id: str) -> ReceiptResult:
        data = self._request("GET", f"/v1/governance/receipts/{receipt_id}")
        vobj = data.get("verdict")
        verdict_str = ""
        reason: str | None = None
        if isinstance(vobj, dict):
            verdict_str = str(vobj.get("verdict", "") or "")
            r = vobj.get("reason")
            reason = r if isinstance(r, str) or r is None else None
        return ReceiptResult(
            receipt_id=receipt_id,
            verdict=verdict_str,
            approval_status=data.get("approval_status"),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            reason=reason,
            raw=data,
        )

    def close_chain(self, chain_id: str) -> ChainResult:
        data = self._request("POST", f"/v1/chains/{chain_id}/close", json={})
        cid = str(data.get("id", chain_id))
        return ChainResult(
            chain_id=cid,
            status=data.get("status", ""),
            total_actions=int(data.get("total_actions", 0)),
            authorized=int(data.get("authorized", 0)),
            held=int(data.get("held", 0)),
            denied=int(data.get("denied", 0)),
            chain_hash=_chain_hash_from_response(data),
            raw=data,
        )


def _chain_hash_from_response(data: dict[str, Any]) -> str | None:
    h = data.get("chain_hash")
    if isinstance(h, str) and h:
        return h
    sig = data.get("chain_signature")
    if isinstance(sig, dict):
        raw = sig.get("chain_hash_hex") or sig.get("hash")
        if isinstance(raw, str) and raw:
            return raw
    return None


_default_client = AxiomClient()


def default_client() -> AxiomClient:
    return _default_client
