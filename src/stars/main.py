import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

from dulwich.repo import Repo

from .github import Stars
from .render import FILENAME, render

if TYPE_CHECKING:
    from .model import Source

OWNER_RE: Final = re.compile(r"github\.com[:/]([^/]+)/[^/]+(?:\.git)?$")


def _owner() -> str:
    remote: bytes | None = (
        Repo
        .discover(start=".")
        .get_config()
        .get(section=(b"remote", b"origin"), name=b"url")
    )
    match = OWNER_RE.search(remote.decode("utf-8") if remote is not None else "")
    if match is None:
        raise RuntimeError
    owner = match.group(1)
    if not isinstance(owner, str):
        raise TypeError
    return owner


def generate(token: str, source: Source | None = None) -> str:
    username = _owner()
    outputs = render(username, (source or Stars(token)).get_starred(username))
    for filename, content in outputs.items():
        Path(filename).write_text(content, encoding="utf-8")
    return outputs[FILENAME]


def run() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if token is None:
        raise RuntimeError
    generate(token)
