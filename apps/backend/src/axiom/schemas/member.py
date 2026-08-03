from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from axiom.models.member import MemberRole


class MemberInvite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    role: MemberRole = MemberRole.MEMBER


class MemberRoleUpdate(BaseModel):
    role: MemberRole


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID
    role: str
    invited_by_user_id: UUID | None
    joined_at: datetime
    created_at: datetime
    updated_at: datetime


class MemberListItemOut(BaseModel):
    """Project member with user display fields (list endpoint)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID
    role: str
    invited_by_user_id: UUID | None
    joined_at: datetime
    created_at: datetime
    updated_at: datetime
    user_email: str
    full_name: str | None
