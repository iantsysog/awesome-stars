from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from itertools import starmap
from typing import TYPE_CHECKING, Final, assert_never, override

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from .model import Starred

FILENAME: Final = "README.rst"
CATEGORY: Final = "Others"


class Section(StrEnum):
    LANGUAGE = "language"
    TOPICS = "topics"


@dataclass(frozen=True, slots=True)
class Spec:
    title: str
    prefix: str
    section: Section

    @property
    def filename(self) -> str:
        return f"{self.prefix}.rst"


SPECS: Final = (
    Spec("Language", "language", Section.LANGUAGE),
    Spec("Topic", "topic", Section.TOPICS),
)

type Entry = tuple[str, str]
type Output = dict[str, str]


class Categories(Mapping[str, list[Entry]]):
    def __init__(self, groups: Mapping[str, Sequence[Entry]]) -> None:
        self._groups: dict[str, list[Entry]] = {
            category: sorted(items) for category, items in sorted(groups.items())
        }

    @override
    def __getitem__(self, category: str) -> list[Entry]:
        return self._groups[category]

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._groups)

    @override
    def __len__(self) -> int:
        return len(self._groups)


@cache
def _rst(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", "``")


def _link(label: str, target: str) -> str:
    return f"* `{_rst(label)} <{target}>`_"


def _heading(title: str, underline: str) -> str:
    return f"{title}\n{underline * len(title)}"


def _values(repository: Starred, section: Section) -> Iterator[str]:
    match section:
        case Section.LANGUAGE:
            yield from ((repository.language,) if repository.language else (CATEGORY,))
        case Section.TOPICS:
            yield from repository.topics or (CATEGORY,)
        case _:
            assert_never(section)


def _categorize(repositories: Sequence[Starred], section: Section) -> Categories:
    grouped: defaultdict[str, list[Entry]] = defaultdict(list)
    for repository in repositories:
        if repository.is_private:
            continue
        for category in _values(repository, section):
            grouped[category].append((repository.name, repository.url))
    return Categories(grouped)


def _readme(username: str) -> str:
    return "\n".join([
        _heading("awesome-stars", "="),
        "",
        "reStructuredText lists from GitHub stars",
        "",
        _heading("Lists", "-"),
        "",
        *(_link(spec.title, spec.filename) for spec in SPECS),
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
    lines: list[str] = [_heading(title, "="), ""]
    for category, items in categories.items():
        lines += [_heading(category, "^"), ""]
        lines += list(starmap(_link, items))
        lines.append("")
    return "\n".join(lines)


def render(username: str, repositories: Sequence[Starred]) -> Output:
    return {
        FILENAME: _readme(username),
        **{
            spec.filename: _section(spec.title, _categorize(repositories, spec.section))
            for spec in SPECS
        },
    }
