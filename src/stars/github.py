import asyncio
from functools import cached_property, wraps
from typing import TYPE_CHECKING, Final, override

from githubkit import GitHub
from pydantic import BaseModel, ConfigDict, Field

from .model import Source, Starred

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from githubkit.auth.token import TokenAuthStrategy
    from githubkit.graphql.paginator import Paginator

API_URL: Final = "https://api.github.com/graphql"

STARRED_QUERY: Final = """\
query($username: String!, $cursor: String) {
  user(login: $username) {
    starredRepositories(first: 100, after: $cursor, orderBy: {direction: DESC, field: STARRED_AT}) {
      nodes {
        nameWithOwner
        url
        isPrivate
        languages(first: 1, orderBy: {direction: DESC, field: SIZE}) {
          nodes {
            name
          }
        }
        repositoryTopics(first: 100) {
          nodes {
            topic {
              name
            }
          }
        }
      }
      pageInfo {
        endCursor
        hasNextPage
      }
    }
  }
}
"""


def sync[T, **P](function: Callable[P, Awaitable[T]]) -> Callable[P, T]:
    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return asyncio.run(function(*args, **kwargs))

    return wrapper


class _Wire(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


class _Language(_Wire):
    name: str


class _Topic(_Wire):
    name: str


class _TopicNode(_Wire):
    topic: _Topic | None


class _Connection[T](_Wire):
    nodes: list[T]


class _Repository(_Wire):
    name_with_owner: str = Field(validation_alias="nameWithOwner")
    url: str
    is_private: bool = Field(validation_alias="isPrivate")
    languages: _Connection[_Language]
    repository_topics: _Connection[_TopicNode] = Field(
        validation_alias="repositoryTopics"
    )


class _User[T](_Wire):
    starred_repositories: _Connection[T] = Field(validation_alias="starredRepositories")


class _Envelope[T](_Wire):
    user: _User[T]


def _starred(node: _Repository) -> Starred:
    return Starred(
        name=node.name_with_owner,
        url=node.url,
        is_private=node.is_private,
        language=node.languages.nodes[0].name if node.languages.nodes else "",
        topics=tuple(
            topic.name
            for topic_node in node.repository_topics.nodes
            if (topic := topic_node.topic)
        ),
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

    async def iter_starred(self, username: str) -> AsyncIterator[Starred]:
        pages: Paginator = self.client.graphql.paginate(
            STARRED_QUERY,
            variables={"username": username},
        )
        async for page in pages:
            response = _Envelope[_Repository].model_validate(page)
            for node in response.user.starred_repositories.nodes:
                yield _starred(node)

    @override
    @sync
    async def get_starred(self, username: str) -> list[Starred]:
        return [starred async for starred in self.iter_starred(username)]
