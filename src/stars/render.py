from collections import defaultdict
from collections.abc import Mapping
from enum import StrEnum
from functools import cache
from itertools import chain, starmap
from typing import TYPE_CHECKING, Final, assert_never, override

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from .model import Lists, Repository

FILENAME: Final = "README.rst"
CATEGORY: Final = "Others"


class Section(StrEnum):
    LANGUAGE = "language"
    TOPIC = "topic"
    LIST = "list"

    @property
    @override
    def title(self) -> str:
        return self.value.capitalize()

    @property
    def filename(self) -> str:
        return f"{self.value}.rst"


type Entry = tuple[str, str]
type Output = dict[str, str]
type Categories = Mapping[str, tuple[Entry, ...]]
type Pair = tuple[str, Entry]


@cache
def _rst(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", "``")


def _link(label: str, target: str) -> str:
    return f"* `{_rst(label)} <{target}>`_"


def _heading(title: str, underline: str) -> str:
    return f"{title}\n{underline * len(title)}"


def _document(parts: Iterable[str]) -> str:
    return "\n".join(parts)


def _group(pairs: Iterable[Pair]) -> Categories:
    grouped: defaultdict[str, list[Entry]] = defaultdict(list)
    for category, entry in pairs:
        grouped[category].append(entry)
    return {
        category: tuple(sorted(entries))
        for category, entries in sorted(grouped.items())
    }


def _values(repository: Repository, section: Section) -> Iterator[str]:
    match section:
        case Section.LANGUAGE:
            yield from ((repository.language,) if repository.language else (CATEGORY,))
        case Section.TOPIC:
            yield from repository.topics or (CATEGORY,)
        case Section.LIST:
            return
        case _:
            assert_never(section)


def _entry(repository: Repository) -> Entry:
    return (repository.name, repository.url)


def _public(repositories: Iterable[Repository]) -> Iterator[Repository]:
    return (repository for repository in repositories if not repository.is_private)


def _spread(labeled: Iterable[tuple[Iterable[str], Repository]]) -> Iterator[Pair]:
    return (
        (label, _entry(repository))
        for labels, repository in labeled
        for label in labels
    )


def _repository_pairs(
    repositories: Sequence[Repository], section: Section
) -> Iterator[Pair]:
    return _spread(
        (_values(repository, section), repository)
        for repository in _public(repositories)
    )


def _list_pairs(lists: Sequence[Lists]) -> Iterator[Pair]:
    return _spread(
        ((lists_item.name,), repository)
        for lists_item in lists
        if not lists_item.is_private
        for repository in _public(lists_item.repositories)
    )


def _readme(username: str) -> str:
    return _document([
        _heading("awesome-stars", "="),
        "",
        "reStructuredText lists from GitHub stars",
        "",
        _heading("Lists", "-"),
        "",
        *(_link(section.title, section.filename) for section in Section),
        "",
        _heading("Credits", "-"),
        "",
        f"{_link('maguowei/starred', 'https://github.com/maguowei/starred')} (MIT)",
        f"{_link('maguowei/awesome-stars', 'https://github.com/maguowei/awesome-stars')} (CC0-1.0)",
        "",
        _heading("License", "-"),
        "",
        f"See `COPYING <COPYING>`_. Generated for `{username} <https://github.com/{username}>`_.",
    ])


def _section(title: str, categories: Categories) -> str:
    return _document(
        chain(
            [_heading(title, "="), ""],
            chain.from_iterable(
                [_heading(category, "^"), "", *starmap(_link, items), ""]
                for category, items in categories.items()
            ),
        )
    )


def render(
    username: str,
    repositories: Sequence[Repository],
    lists: Sequence[Lists] | None = None,
) -> Output:
    outputs: Output = {
        FILENAME: _readme(username),
        **{
            section.filename: _section(
                section.title, _group(_repository_pairs(repositories, section))
            )
            for section in Section
            if section is not Section.LIST
        },
    }
    if lists:
        outputs[Section.LIST.filename] = _section(
            Section.LIST.title, _group(_list_pairs(lists))
        )
    return outputs
