from pydantic import BaseModel, ConfigDict, Field


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    full_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=2000)


class UserPasswordUpdate(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8, max_length=128)
