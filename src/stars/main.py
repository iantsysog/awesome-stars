import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

from dulwich.repo import Repo

from .github import Stars
from .model import Lists, Repository
from .render import FILENAME, render

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .model import Source

OWNER_RE: Final = re.compile(r"github\.com[:/]([^/]+)/[^/]+?(?:\.git)?/?$")


def _remote() -> str:
    url: bytes | None = (
        Repo
        .discover(start=".")
        .get_config()
        .get(section=(b"remote", b"origin"), name=b"url")
    )
    return url.decode("utf-8") if url is not None else ""


def _parse(url: str) -> str | None:
    match = OWNER_RE.search(url)
    return str(match.group(1)) if match else None


def _owner() -> str:
    owner = _parse(_remote())
    if owner is None:
        raise RuntimeError
    return owner


def _write(outputs: Mapping[str, str]) -> None:
    for filename, content in outputs.items():
        Path(filename).write_text(content, encoding="utf-8")


def generate(token: str, source: Source | None = None) -> str:
    username = _owner()
    active = source if source is not None else Stars(token)
    outputs = render(
        username, active.get(Repository, username), active.get(Lists, username)
    )
    _write(outputs)
    return outputs[FILENAME]


def run() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if token is None:
        raise RuntimeError
    generate(token)
