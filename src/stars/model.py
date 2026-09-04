from typing import Protocol, overload

from pydantic import BaseModel, ConfigDict


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _Named(_Model):
    name: str
    is_private: bool


class Repository(_Named):
    url: str
    language: str = ""
    topics: tuple[str, ...] = ()


class Lists(_Named):
    description: str = ""
    repositories: tuple[Repository, ...] = ()


class Source(Protocol):
    @overload
    def get(self, entity: type[Repository], username: str) -> list[Repository]: ...

    @overload
    def get(self, entity: type[Lists], username: str) -> list[Lists]: ...
