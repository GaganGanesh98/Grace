from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core import errors
from axiom.models.policy import Policy
from axiom.services import audit as audit_service
from axiom.services.embeddings import embed_query, embed_texts

logger = structlog.get_logger(__name__)


def policy_embedding_text(name: str, description: str | None, rules: list[object]) -> str:
    """Compose the text embedded for semantic matching: policy name, description,
    and each rule's human description (the semantically meaningful parts)."""
    parts: list[str] = [name]
    if description:
        parts.append(description)
    for rule in rules or []:
        if isinstance(rule, dict):
            rule_description = rule.get("description")
            if isinstance(rule_description, str) and rule_description.strip():
                parts.append(rule_description.strip())
    return "\n".join(part for part in parts if part and str(part).strip())


async def _embed_policy_best_effort(policy: Policy) -> None:
    """Populate ``policy.embedding`` in place. Fail-soft: an embedding failure is
    logged and leaves the column NULL — it must never block policy writes or
    governance. (Runs before flush so the vector lands in the same INSERT.)"""
    text = policy_embedding_text(policy.name, policy.description, list(policy.rules))
    if not text.strip():
        return
    try:
        vectors = await embed_texts([text])
        policy.embedding = vectors[0]
    except Exception as exc:  # noqa: BLE001 — embeddings must never block a write
        logger.warning("policy.embed_failed", policy_slug=policy.slug, error=str(exc))


async def list_policies(
    session: AsyncSession, *, project_id: UUID, offset: int, limit: int
) -> tuple[list[Policy], int]:
    cond = (Policy.project_id == project_id, Policy.deleted_at.is_(None))
    total = int(await session.scalar(select(func.count()).select_from(Policy).where(*cond)) or 0)
    rows = await session.scalars(
        select(Policy)
        .where(*cond)
        .order_by(Policy.slug.asc(), Policy.version.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows), total


async def create_policy(
    session: AsyncSession,
    *,
    project_id: UUID,
    slug: str,
    name: str,
    description: str | None,
    pack: str,
    rules: list[object],
    created_by_user_id: UUID,
) -> Policy:
    policy = Policy(
        project_id=project_id,
        slug=slug,
        name=name,
        description=description,
        pack=pack,
        version=1,
        rules=rules,
        created_by_user_id=created_by_user_id,
    )
    await _embed_policy_best_effort(policy)
    session.add(policy)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise errors.ConflictError("Policy slug and version conflict.") from exc
    await audit_service.record_event(
        session,
        event_type="policy.created",
        actor_user_id=created_by_user_id,
        project_id=project_id,
        target_type="policy",
        target_id=policy.id,
        metadata={"slug": slug, "version": 1},
    )
    return policy


async def get_policy(session: AsyncSession, *, project_id: UUID, policy_id: UUID) -> Policy:
    policy = await session.scalar(
        select(Policy).where(
            Policy.id == policy_id,
            Policy.project_id == project_id,
            Policy.deleted_at.is_(None),
        )
    )
    if policy is None:
        raise errors.PolicyNotFoundError("Policy not found.")
    return policy


async def update_policy_new_version(
    session: AsyncSession,
    policy: Policy,
    *,
    name: str | None,
    description: str | None,
    pack: str | None,
    rules: list[object] | None,
    is_active: bool | None,
    created_by_user_id: UUID,
) -> Policy:
    next_version = (
        int(
            await session.scalar(
                select(func.max(Policy.version)).where(
                    Policy.project_id == policy.project_id,
                    Policy.slug == policy.slug,
                )
            )
            or 0
        )
        + 1
    )
    policy.deleted_at = datetime.now(UTC)
    new_policy = Policy(
        project_id=policy.project_id,
        slug=policy.slug,
        name=name if name is not None else policy.name,
        description=description if description is not None else policy.description,
        pack=pack if pack is not None else policy.pack,
        version=next_version,
        rules=list(rules) if rules is not None else list(policy.rules),
        is_active=is_active if is_active is not None else policy.is_active,
        created_by_user_id=created_by_user_id,
    )
    await _embed_policy_best_effort(new_policy)
    session.add(new_policy)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise errors.ConflictError("Could not create new policy version.") from exc
    await audit_service.record_event(
        session,
        event_type="policy.versioned",
        actor_user_id=created_by_user_id,
        project_id=policy.project_id,
        target_type="policy",
        target_id=new_policy.id,
        metadata={"slug": policy.slug, "version": next_version},
    )
    return new_policy


async def soft_delete_policy(session: AsyncSession, policy: Policy) -> None:
    policy.deleted_at = datetime.now(UTC)


# Max results any single semantic search may return (guards against abuse).
_MAX_SEARCH_K = 50

# Action fields (in priority order) that best describe intent for semantic search.
_ACTION_TEXT_KEYS = ("description", "summary", "intent", "action", "tool", "name", "type")


def action_query_text(action: dict[str, object]) -> str:
    """Derive a free-text query from an agent action dict for semantic matching.

    Prefers a human-meaningful field (description/summary/intent/…); otherwise
    joins the action's top-level scalar values. Returns "" if nothing usable.
    """
    if not isinstance(action, dict):
        return ""
    for key in _ACTION_TEXT_KEYS:
        value = action.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    scalars = [str(v) for v in action.values() if isinstance(v, str | int | float | bool)]
    return " ".join(scalars)[:2000]


async def search_policies(
    session: AsyncSession,
    *,
    project_id: UUID,
    query_text: str,
    k: int = 5,
) -> list[tuple[Policy, float]]:
    """Semantically match ``query_text`` (e.g. an agent action description) against
    active policies in the project via pgvector cosine similarity.

    Returns ``(policy, similarity)`` pairs ordered most-similar first, where
    similarity = 1 - cosine distance (1.0 = identical). Policies without an
    embedding are skipped. Returns ``[]`` for a blank query.
    """
    query = (query_text or "").strip()
    if not query:
        return []

    query_vector = await embed_query(query)
    distance = Policy.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(Policy, distance)
        .where(
            Policy.project_id == project_id,
            Policy.deleted_at.is_(None),
            Policy.is_active.is_(True),
            Policy.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(max(1, min(k, _MAX_SEARCH_K)))
    )
    rows = (await session.execute(stmt)).all()
    return [(policy, 1.0 - float(dist)) for policy, dist in rows]
