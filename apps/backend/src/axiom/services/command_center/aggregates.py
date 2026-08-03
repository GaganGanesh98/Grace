"""Command Center aggregate metrics (Phase 7.5.1)."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.config import get_settings
from axiom.models.agent_run import AgentRun, AgentRunStatus
from axiom.models.governance import GovernanceReceipt, GovernanceVerdict
from axiom.models.policy import Policy
from axiom.schemas.command_center import (
    CryptoHealthOut,
    PolicyBreakdownOut,
    PostureOut,
    TsaStatusOut,
)
from axiom.services import projects as projects_service
from axiom.services.governance.policy import describe_active_governance_policy

logger = structlog.get_logger(__name__)

_WINDOW_RE = re.compile(r"^\s*(\d+)\s*([hHdD])\s*$")


def parse_window_to_start(window: str) -> datetime:
    """Parse `24h`, `1h`, `7d` into a rolling window start in UTC (now - delta)."""
    s = (window or "").strip()
    m = _WINDOW_RE.match(s)
    if not m:
        msg = f"invalid window: {window!r}"
        raise ValueError(msg)
    n, unit = int(m.group(1)), m.group(2).lower()
    if unit == "d":
        delta = timedelta(days=n)
    else:
        delta = timedelta(hours=n)
    return datetime.now(UTC) - delta


def _next_rotation_days() -> int | None:
    raw = get_settings().axiom_key_rotation_date
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    try:
        rot = date.fromisoformat(str(raw).strip()[:10])
    except (ValueError, OSError) as e:
        logger.warning(
            "command_center.aggregates.key_rotation_date_invalid",
            value=raw,
            err=str(e),
        )
        return None
    today = datetime.now(UTC).date()
    return max(0, (rot - today).days)


def _signing_status(
    sealed_total: int,
    with_signature: int,
) -> str:
    """Status over sealed receipts only (Phase 7.5.4)."""
    if sealed_total <= 0:
        return "no_data"
    if with_signature <= 0:
        return "never_signed"
    if with_signature >= sealed_total:
        return "all_signed"
    return "partial"


def _merkle_status(
    total: int,
    with_merkle: int,
) -> str:
    if total <= 0 or with_merkle <= 0:
        return "no_data"
    return "healthy"


def _verdict_approved(v) -> "case":  # type: ignore[valid-type]
    return case(
        (
            func.lower(v).in_(("approve", "modify", "allow")),
            1,
        ),
        else_=0,
    )


def _verdict_escalated(v) -> "case":
    return case(
        (
            func.lower(v).in_(("escalate", "hold")),
            1,
        ),
        else_=0,
    )


def _verdict_denied(v) -> "case":
    return case(
        (
            func.lower(v) == "deny",
            1,
        ),
        else_=0,
    )


def _receipt_has_tsa() -> and_:
    tsa = GovernanceReceipt.execution_data["tsa"]  # JSONB path
    return and_(
        GovernanceReceipt.execution_data.isnot(None),
        tsa.is_not(None),
        or_(
            tsa["token"].isnot(None),
            tsa["timestamp"].isnot(None),
        ),
    )


async def project_has_active_db_policy(
    session: AsyncSession, project_id: UUID
) -> bool:
    n = await session.scalar(
        select(func.count())
        .select_from(Policy)
        .where(
            and_(
                Policy.project_id == project_id,
                Policy.is_active.is_(True),
                Policy.deleted_at.is_(None),
            )
        )
    )
    return (n or 0) > 0


class AggregatesService:
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def get_posture(
        self,
        project_id: UUID,
        *,
        window: str = "24h",
    ) -> PostureOut:
        try:
            start = parse_window_to_start(window)
        except ValueError:
            start = parse_window_to_start("24h")
        calls = await self._db.scalar(
            select(func.count())
            .select_from(GovernanceReceipt)
            .where(
                and_(
                    GovernanceReceipt.project_id == project_id,
                    GovernanceReceipt.created_at >= start,
                )
            )
        ) or 0
        completed = await self._db.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(
                and_(
                    AgentRun.project_id == project_id,
                    AgentRun.status == AgentRunStatus.SUCCEEDED.value,
                    or_(
                        and_(
                            AgentRun.completed_at.is_not(None),
                            AgentRun.completed_at >= start,
                        ),
                        and_(
                            AgentRun.completed_at.is_(None),
                            AgentRun.created_at >= start,
                        ),
                    ),
                )
            )
        ) or 0
        violations = await self._db.scalar(
            select(func.coalesce(func.sum(_verdict_denied(GovernanceVerdict.verdict)), 0))
            .select_from(GovernanceReceipt)
            .join(GovernanceVerdict, GovernanceVerdict.id == GovernanceReceipt.verdict_id)
            .where(
                and_(
                    GovernanceReceipt.project_id == project_id,
                    GovernanceReceipt.created_at >= start,
                )
            )
        ) or 0
        return PostureOut(
            calls_governed=int(calls),
            runs_completed=int(completed),
            violations=int(violations),
        )

    async def get_crypto_health(
        self,
        project_id: UUID,
    ) -> CryptoHealthOut:
        sealed_f = and_(
            GovernanceReceipt.project_id == project_id,
            GovernanceReceipt.status == "sealed",
        )
        t_sealed = int(
            await self._db.scalar(
                select(func.count()).select_from(GovernanceReceipt).where(sealed_f)
            )
            or 0
        )
        n_ed = int(
            await self._db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                (GovernanceReceipt.ed25519_sig.is_not(None), 1),
                                else_=0,
                            )
                        ),
                        0,
                    )
                )
                .select_from(GovernanceReceipt)
                .where(sealed_f)
            )
            or 0
        )
        n_ml = int(
            await self._db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                (GovernanceReceipt.ml_dsa_sig.is_not(None), 1),
                                else_=0,
                            )
                        ),
                        0,
                    )
                )
                .select_from(GovernanceReceipt)
                .where(sealed_f)
            )
            or 0
        )
        t_all = int(
            await self._db.scalar(
                select(func.count())
                .select_from(GovernanceReceipt)
                .where(GovernanceReceipt.project_id == project_id)
            )
            or 0
        )
        n_m = int(
            await self._db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            case(
                                (GovernanceReceipt.merkle_root.is_not(None), 1),
                                else_=0,
                            )
                        ),
                        0,
                    )
                )
                .select_from(GovernanceReceipt)
                .where(GovernanceReceipt.project_id == project_id)
            )
            or 0
        )
        return CryptoHealthOut(
            ed25519_status=_signing_status(t_sealed, n_ed),  # type: ignore[arg-type]
            mldsa65_status=_signing_status(t_sealed, n_ml),  # type: ignore[arg-type]
            merkle_status=_merkle_status(t_all, n_m),  # type: ignore[arg-type]
            next_rotation_days=_next_rotation_days(),
        )

    async def get_policy_breakdown(
        self,
        project_id: UUID,
        *,
        window: str = "24h",
    ) -> PolicyBreakdownOut:
        if not await project_has_active_db_policy(self._db, project_id):
            return PolicyBreakdownOut(
                policy_name=None,
                evaluated_count=0,
                approved_count=0,
                escalated_count=0,
                denied_count=0,
            )
        try:
            start = parse_window_to_start(window)
        except ValueError:
            start = parse_window_to_start("24h")
        project = await projects_service.get_project(self._db, project_id)
        settings = project.settings if isinstance(project.settings, dict) else {}
        meta = describe_active_governance_policy(settings)
        policy_name = str(meta.get("display_name") or meta.get("name") or "policy")
        v = GovernanceVerdict
        wh = and_(
            GovernanceReceipt.project_id == project_id,
            GovernanceReceipt.created_at >= start,
        )
        n_eval = int(
            await self._db.scalar(
                select(func.count())
                .select_from(GovernanceReceipt)
                .join(v, v.id == GovernanceReceipt.verdict_id)
                .where(wh)
            )
            or 0
        )
        n_app = int(
            await self._db.scalar(
                select(
                    func.coalesce(func.sum(_verdict_approved(v.verdict)), 0)
                )
                .select_from(GovernanceReceipt)
                .join(v, v.id == GovernanceReceipt.verdict_id)
                .where(wh)
            )
            or 0
        )
        n_esc = int(
            await self._db.scalar(
                select(
                    func.coalesce(func.sum(_verdict_escalated(v.verdict)), 0)
                )
                .select_from(GovernanceReceipt)
                .join(v, v.id == GovernanceReceipt.verdict_id)
                .where(wh)
            )
            or 0
        )
        n_deny = int(
            await self._db.scalar(
                select(
                    func.coalesce(func.sum(_verdict_denied(v.verdict)), 0)
                )
                .select_from(GovernanceReceipt)
                .join(v, v.id == GovernanceReceipt.verdict_id)
                .where(wh)
            )
            or 0
        )
        return PolicyBreakdownOut(
            policy_name=policy_name,
            evaluated_count=n_eval,
            approved_count=n_app,
            escalated_count=n_esc,
            denied_count=n_deny,
        )

    async def get_tsa_status(
        self,
        project_id: UUID,
    ) -> TsaStatusOut:
        tsa_f = and_(GovernanceReceipt.project_id == project_id, _receipt_has_tsa())
        max_at = await self._db.scalar(
            select(func.max(GovernanceReceipt.created_at)).where(tsa_f)
        )
        age: int | None
        if max_at is None:
            age = None
        else:
            if max_at.tzinfo is None:
                max_utc = max_at.replace(tzinfo=UTC)
            else:
                max_utc = max_at.astimezone(UTC)
            age = int((datetime.now(UTC) - max_utc).total_seconds())
        tsa_url = get_settings().axiom_tsa_authority_url
        if isinstance(tsa_url, str) and not tsa_url.strip():
            tsa_url = None
        return TsaStatusOut(
            last_anchor_age_seconds=age,
            tsa_authority_url=tsa_url,
        )
