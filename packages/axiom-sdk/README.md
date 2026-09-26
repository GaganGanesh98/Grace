# grace-sdk

Python SDK for Grace — cryptographic governance receipts for AI agent actions.

## Licence

This SDK is **MIT** ([LICENSE](LICENSE)), while the Grace platform in the rest of
this repository is **AGPL-3.0-only** ([../../LICENSE](../../LICENSE)). The split
is deliberate, not an oversight: an AGPL client library would place copyleft
obligations on every application that imports it, which would make the SDK
unusable for its intended purpose. Permissive client, copyleft server is the
standard shape for this. See [`docs/legal-posture.md`](../../docs/legal-posture.md) §5.

## Install

```bash
pip install grace-sdk
```

Runtime dependency: `requests` for HTTP.

## Quickstart

```python
import axiom

axiom.init(api_key="axm_live_...", base_url="http://127.0.0.1:8000")

r = axiom.govern(
    agent_id="billing-agent",
    action_type="tool.http.post",
    target="https://api.vendor.com/charge",
    risk="medium",
)
if r.verdict == "allow":
    axiom.report(
        r.receipt_id,
        outcome={
            "target": "https://api.vendor.com/charge",
            "action_type": "tool.http.post",
            "risk": "medium",
        },
    )
    v = axiom.verify(r.receipt_id)
    assert v.valid
```

## Hard enforcement

If you want the SDK to stop execution when governance does not allow the action, pass `enforce=True` to `govern`. A `deny` verdict raises `axiom.GovernanceDenied`; a `hold` verdict raises `axiom.GovernanceHeld`.

```python
import axiom

axiom.init(api_key="axm_live_...", base_url="http://127.0.0.1:8000")

try:
    axiom.govern(
        agent_id="a1",
        action_type="tool.exec",
        target="/bin/rm",
        risk="critical",
        enforce=True,
    )
except axiom.GovernanceDenied as exc:
    print(exc.verdict, exc.receipt_id)
```

### Hold → human approval

When policy returns `hold` and you use `enforce=True`, the SDK raises `GovernanceHeld`. Poll the receipt until a reviewer approves or rejects in the dashboard (or via the approval API):

```python
import axiom
from axiom import GovernanceHeld

axiom.init(api_key="axm_live_...", base_url="http://127.0.0.1:8000")

try:
    result = axiom.govern(
        agent_id="research-bot",
        action_type="tool.email.send",
        target="cfo@company.com",
        risk="high",
        enforce=True,
    )
    # ... allowed, proceed
except GovernanceHeld as held:
    final = axiom.wait_for_decision(held.receipt_id)
    if final.verdict == "allow":
        pass  # proceed
    else:
        pass  # denied, abort
```

## Chains / workflows

Pass `workflow` to start (or reuse) a named chain, or pass `chain_id` from a previous `govern` call to attach the next action. Close the chain when the workflow is finished:

```python
import axiom

axiom.init(api_key="axm_live_...", base_url="http://127.0.0.1:8000")

g1 = axiom.govern(
    agent_id="deploy-bot",
    action_type="ci.deploy",
    target="prod",
    workflow="release-42",
)
g2 = axiom.govern(
    agent_id="deploy-bot",
    action_type="ci.verify",
    target="prod",
    chain_id=g1.chain_id,
)
axiom.close_chain(g1.chain_id)
```

## API

| Function | Purpose |
| -------- | ------- |
| `init(api_key, base_url=..., timeout=...)` | Configure the SDK (no network I/O). |
| `govern(...)` | Request a governance verdict before acting; optional `enforce`, `workflow`, `chain_id`. |
| `report(receipt_id, outcome)` | Seal execution outcome for a receipt. |
| `verify(receipt_id)` | Cryptographically verify a sealed receipt via `POST /v1/governance/verify` with `receipt_id` (server-side). |
| `close_chain(chain_id)` | Close and seal a governance chain. |
| `set_debug(True)` | Enable debug logging for the `axiom` loggers (API keys are never logged). |

## Documentation

Full documentation: [https://docs.axiom.dev](https://docs.axiom.dev) (placeholder).

## Development

```bash
cd packages/axiom-sdk
pip install -e ".[dev]"
pytest tests/test_client.py -v
pytest tests/test_integration.py -v -m integration   # needs a running API
```
