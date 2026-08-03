"""Govern intent declaration and request validation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from axiom.db import session_scope
from axiom.models.governance import GovernanceIntent
from axiom.models.member import MemberRole, ProjectMember
from axiom.models.project import Project
from axiom.schemas.governance import GovernRequest
from axiom.services import auth as auth_service
from axiom.services.governance.intent import declare_intent


def test_govern_request_rejects_invalid_risk() -> None:
    with pytest.raises(ValidationError):
        GovernRequest(
            agent_id="a",
            action_type="t",
            target="https://x",
            risk="extreme",
        )


def test_govern_request_rejects_empty_agent_id() -> None:
    with pytest.raises(ValidationError):
        GovernRequest(
            agent_id="",
            action_type="t",
            target="https://x",
            risk="low",
        )


@pytest.mark.asyncio
async def test_declare_intent_persists_row() -> None:
    email = f"gov-intent-{uuid4().hex}@example.com"
    async with session_scope() as session:
        user, _, _ = await auth_service.signup(
            session,
            email=email,
            password="password1a",
            full_name="T",
        )
        project = await session.scalar(select(Project).where(Project.owner_user_id == user.id))
        if project is None:
            slug = f"gov-intent-{uuid4().hex}"
            project = Project(
                slug=slug,
                name="Test",
                description=None,
                owner_user_id=user.id,
            )
            session.add(project)
            await session.flush()
            session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=user.id,
                    role=MemberRole.OWNER.value,
                    invited_by_user_id=None,
                )
            )
            await session.flush()

        body = GovernRequest(
            agent_id="agent-1",
            action_type="tool.http.get",
            target="https://api.example.com/x",
            risk="low",
        )
        intent = await declare_intent(session, project.id, body)
        assert intent.id is not None
        assert intent.risk_declared == "low"

        loaded = await session.get(GovernanceIntent, intent.id)
        assert loaded is not None
        assert loaded.target == "https://api.example.com/x"
