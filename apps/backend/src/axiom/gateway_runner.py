"""Entry point for the governance gateway (port 8001)."""

from __future__ import annotations

import uvicorn

from axiom.config import get_settings


def main() -> None:
    port = get_settings().gateway_port
    uvicorn.run(
        "axiom.gateway.app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
