from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class Starred(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str
    url: str
    is_private: bool
    language: str = ""
    topics: tuple[str, ...] = ()


class Source(ABC):
    @abstractmethod
    def get_starred(self, username: str) -> list[Starred]: ...
