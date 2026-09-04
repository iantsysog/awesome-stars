import asyncio
from dataclasses import dataclass
from functools import cached_property, wraps
from typing import TYPE_CHECKING, Final, overload, override

from githubkit import GitHub
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .model import Lists, Repository, Source

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from githubkit.auth.token import TokenAuthStrategy
    from githubkit.graphql.paginator import Paginator

API_URL: Final = "https://api.github.com/graphql"

_REPO_SLIM: Final = """\
nameWithOwner
url
isPrivate\
"""

_REPO_NODES: Final = f"""\
{_REPO_SLIM}
languages(first: 1, orderBy: {{direction: DESC, field: SIZE}}) {{
  nodes {{
    name
  }}
}}
repositoryTopics(first: 20) {{
  nodes {{
    topic {{
      name
    }}
  }}
}}\
"""

_PAGE: Final = "pageInfo { endCursor hasNextPage }"


def _indent(block: str, width: int = 8) -> str:
    pad = " " * width
    return "\n".join(pad + line if line else line for line in block.splitlines())


_LIST_NODES: Final = f"""\
name
description
isPrivate
items(first: 100) {{
  nodes {{
    ... on Repository {{
{_indent(_REPO_SLIM, 6)}
    }}
  }}
}}\
"""


def _query(field: str, args: str, nodes: str) -> str:
    return f"""\
query($username: String!, $cursor: String) {{
  user(login: $username) {{
    {field}({args}) {{
      nodes {{
{_indent(nodes)}
      }}
      {_PAGE}
    }}
  }}
}}
"""


REPOSITORY_QUERY: Final = _query(
    "starredRepositories",
    "first: 100, after: $cursor, orderBy: {direction: DESC, field: STARRED_AT}",
    _REPO_NODES,
)

LISTS_QUERY: Final = _query("lists", "first: 100, after: $cursor", _LIST_NODES)


def sync[T, **P](function: Callable[P, Awaitable[T]]) -> Callable[P, T]:
    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return asyncio.run(function(*args, **kwargs))

    return wrapper


class _Wire(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


class _Name(_Wire):
    name: str


class _Topic(_Wire):
    topic: _Name | None


class _Connection[T](_Wire):
    nodes: list[T]


class _Repository(_Wire):
    name_with_owner: str = Field(validation_alias="nameWithOwner")
    url: str
    is_private: bool = Field(validation_alias="isPrivate")
    languages: _Connection[_Name]
    repository_topics: _Connection[_Topic] = Field(validation_alias="repositoryTopics")


class _Slim(_Wire):
    name_with_owner: str = Field(validation_alias="nameWithOwner")
    url: str
    is_private: bool = Field(validation_alias="isPrivate")


class _List(_Wire):
    name: str
    description: str | None
    is_private: bool = Field(validation_alias="isPrivate")
    items: _Connection[_Slim | None]


class _User[N](_Wire):
    connection: _Connection[N] = Field(
        validation_alias=AliasChoices("starredRepositories", "lists")
    )


class _Envelope[T](_Wire):
    user: T


def _language(node: _Repository) -> str:
    return node.languages.nodes[0].name if node.languages.nodes else ""


def _topics(node: _Repository) -> tuple[str, ...]:
    return tuple(
        topic.name
        for topic_node in node.repository_topics.nodes
        if (topic := topic_node.topic)
    )


def _repository(node: _Repository) -> Repository:
    return Repository(
        name=node.name_with_owner,
        url=node.url,
        is_private=node.is_private,
        language=_language(node),
        topics=_topics(node),
    )


def _slim(node: _Slim) -> Repository:
    return Repository(
        name=node.name_with_owner,
        url=node.url,
        is_private=node.is_private,
    )


def _lists(node: _List) -> Lists:
    return Lists(
        name=node.name,
        description=node.description or "",
        is_private=node.is_private,
        repositories=tuple(
            _slim(repo) for repo in node.items.nodes if repo is not None
        ),
    )


async def _drain[T](stream: AsyncIterator[T]) -> list[T]:
    return [item async for item in stream]


@dataclass(frozen=True, slots=True)
class _Spec[N, M]:
    query: str
    envelope: type[_Envelope[_User[N]]]
    adapt: Callable[[N], M]


_REPOSITORY_SPEC: Final[_Spec[_Repository, Repository]] = _Spec(
    REPOSITORY_QUERY, _Envelope[_User[_Repository]], _repository
)

_LISTS_SPEC: Final[_Spec[_List, Lists]] = _Spec(
    LISTS_QUERY, _Envelope[_User[_List]], _lists
)


class Stars(Source):
    def __init__(
        self,
        token: str,
        *,
        api_url: str = API_URL,
        timeout: float = 30.0,
    ) -> None:
        self._token = token
        self._api_url = api_url.removesuffix("/graphql")
        self._timeout = timeout

    @cached_property
    def client(self) -> GitHub[TokenAuthStrategy]:
        return GitHub(
            auth=self._token,
            base_url=self._api_url,
            timeout=self._timeout,
            http_cache=True,
            auto_retry=True,
        )

    async def _select[N, M](self, spec: _Spec[N, M], username: str) -> AsyncIterator[M]:
        pages: Paginator = self.client.graphql.paginate(
            spec.query,
            variables={"username": username},
        )
        async for page in pages:
            for node in spec.envelope.model_validate(page).user.connection.nodes:
                yield spec.adapt(node)

    @overload
    def get(self, entity: type[Repository], username: str) -> list[Repository]: ...

    @overload
    def get(self, entity: type[Lists], username: str) -> list[Lists]: ...

    @override
    @sync
    async def get(
        self, entity: type[Repository | Lists], username: str
    ) -> list[Repository] | list[Lists]:
        if entity is Repository:
            repositories: list[Repository] = await _drain(
                self._select(_REPOSITORY_SPEC, username)
            )
            return repositories
        if entity is Lists:
            lists: list[Lists] = await _drain(self._select(_LISTS_SPEC, username))
            return lists
        raise RuntimeError
