"""Parse the install, clone and skill-fetch commands a coding agent runs.

Each command becomes a list of Declaration objects, one per thing the command
would fetch and run. Anything the parser cannot read (for example a
requirements file, whose contents it does not open) is returned in
ParseResult.unparsed rather than dropped, so a checkpoint never silently
passes over it.

Skill fetches assume the `skills add <source>` convention (optionally run
through npx). Adjust SKILL_COMMANDS once the real skill installer is fixed.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


class Ecosystem(str, Enum):
    PYPI = "pypi"
    NPM = "npm"
    GIT = "git"
    SKILL = "skill"


@dataclass(frozen=True)
class Declaration:
    ecosystem: Ecosystem
    name: str
    specifier: str = ""
    source: str = ""

    @property
    def version(self) -> str | None:
        """The exact version when the specifier pins one, else None."""
        if self.specifier.startswith("=="):
            return self.specifier[2:].strip()
        if self.ecosystem is Ecosystem.NPM and self.specifier and self.specifier[0].isdigit():
            return self.specifier
        return None


@dataclass
class ParseResult:
    declarations: list[Declaration] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)


SEPARATORS = {"&&", "||", ";", "|", "&"}
WRAPPERS = {"sudo", "time", "env"}

PIP_VALUE_OPTIONS = {
    "-r", "--requirement", "-c", "--constraint", "-i", "--index-url",
    "--extra-index-url", "-f", "--find-links", "-t", "--target", "--prefix",
    "--root", "-e", "--editable", "--python-version", "--platform",
    "--implementation", "--abi", "--src", "--trusted-host", "--cache-dir",
    "--progress-bar", "--log", "--proxy", "--timeout", "--retries",
}

GIT_CLONE_VALUE_OPTIONS = {
    "--depth", "-b", "--branch", "-o", "--origin", "-c", "--config",
    "--reference", "--filter", "--separate-git-dir", "--template", "-u",
    "--upload-pack", "--jobs", "-j",
}

NPM_INSTALL_VERBS = {"install", "i", "add", "in", "isntall"}
NPM_TOOLS = {"npm", "pnpm", "yarn", "bun"}

REQ_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?\s*(?P<spec>.*)$"
)
SHORTHAND_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
# A bare redirection operator such as >, >>, <, >&, 2>, 2>&. Quoted text that
# merely contains > (like a version specifier) does not match.
REDIRECT_RE = re.compile(r"\d*[<>][<>&|]*")


def parse_command(command: str) -> ParseResult:
    """Parse a shell command line into declarations.

    Chained commands (&&, ||, ;, |) are parsed one by one.
    """
    result = ParseResult()
    for argv in _split_commands(command):
        _parse_argv(argv, " ".join(argv), result)
    return result


def _split_commands(command: str) -> list[list[str]]:
    """Split on command separators and drop redirections such as 2>&1 or > log.txt."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars="&|;<>")
    lexer.whitespace_split = True
    commands: list[list[str]] = [[]]
    skip_target = False
    for token in lexer:
        if skip_target:
            skip_target = False
            continue
        if token in SEPARATORS:
            commands.append([])
        elif REDIRECT_RE.fullmatch(token):
            # A bare fd number right before the operator (the "2" in 2>&1) is not an argument.
            if commands[-1] and commands[-1][-1].isdigit():
                commands[-1].pop()
            skip_target = True
        else:
            commands[-1].append(token)
    return [c for c in commands if c]


def _parse_argv(argv: list[str], source: str, result: ParseResult) -> None:
    while argv and argv[0] in WRAPPERS:
        argv = argv[1:]
    if not argv:
        return

    head = argv[0]
    if head in ("pip", "pip3"):
        _pip(argv[1:], source, result)
    elif head in ("python", "python3") and argv[1:3] == ["-m", "pip"]:
        _pip(argv[3:], source, result)
    elif head == "uv" and argv[1:2] == ["pip"]:
        _pip(argv[2:], source, result)
    elif head == "uv" and argv[1:2] == ["add"]:
        _pip(["install", *argv[2:]], source, result)
    elif head in NPM_TOOLS:
        _npm(argv[1:], source, result)
    elif head == "git" and argv[1:2] == ["clone"]:
        _git_clone(argv[2:], source, result)
    elif head == "gh" and argv[1:3] == ["repo", "clone"]:
        _gh_clone(argv[3:], source, result)
    elif head == "npx" and argv[1:2] == ["skills"]:
        _skills(argv[2:], source, result)
    elif head == "skills":
        _skills(argv[1:], source, result)


def _positionals(args: list[str], value_options: set[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Split args into positionals and (option, value) pairs."""
    positionals: list[str] = []
    values: list[tuple[str, str]] = []
    it = iter(args)
    for arg in it:
        if arg in value_options:
            values.append((arg, next(it, "")))
        elif arg.startswith("-"):
            continue
        else:
            positionals.append(arg)
    return positionals, values


def _pip(args: list[str], source: str, result: ParseResult) -> None:
    if not args or args[0] != "install":
        return
    it = iter(args[1:])
    for arg in it:
        if arg in PIP_VALUE_OPTIONS:
            value = next(it, "")
            if arg in ("-r", "--requirement", "-c", "--constraint"):
                result.unparsed.append(f"{arg} {value} (requirements file not read): {source}")
            elif arg in ("-e", "--editable") and value.startswith("git+"):
                result.declarations.append(
                    Declaration(Ecosystem.GIT, _git_name(value), source=source)
                )
            continue
        if arg.startswith("-"):
            continue
        decl = _pip_requirement(arg, source)
        if decl is None:
            result.unparsed.append(f"{arg}: {source}")
        else:
            result.declarations.append(decl)


def _pip_requirement(arg: str, source: str) -> Declaration | None:
    if "://" in arg:
        if arg.startswith("git+"):
            return Declaration(Ecosystem.GIT, _git_name(arg), source=source)
        return Declaration(Ecosystem.PYPI, arg, source=source)
    match = REQ_RE.match(arg)
    if not match:
        return None
    name = re.sub(r"[-_.]+", "-", match.group("name")).lower()
    return Declaration(Ecosystem.PYPI, name, specifier=match.group("spec").strip(), source=source)


def _npm(args: list[str], source: str, result: ParseResult) -> None:
    if not args or args[0] not in NPM_INSTALL_VERBS:
        return
    packages, _ = _positionals(args[1:], {"--prefix", "--registry", "--cwd", "-C"})
    for spec in packages:
        decl = _npm_spec(spec, source)
        if decl is None:
            result.unparsed.append(f"{spec}: {source}")
        else:
            result.declarations.append(decl)


def _npm_spec(spec: str, source: str) -> Declaration | None:
    if spec.startswith(("file:", "./", "../", "/")):
        return None
    if spec.startswith(("git", "github:", "gitlab:", "bitbucket:")) or "://" in spec:
        return Declaration(Ecosystem.GIT, _git_name(spec), source=source)
    if SHORTHAND_RE.match(spec):
        return Declaration(Ecosystem.GIT, f"github.com/{spec}", source=source)
    at = spec.find("@", 1)  # skip the leading @ of a scoped package
    if at == -1:
        name, specifier = spec, ""
    else:
        name, specifier = spec[:at], spec[at + 1:]
    if not name:
        return None
    return Declaration(Ecosystem.NPM, name.lower(), specifier=specifier, source=source)


def _git_clone(args: list[str], source: str, result: ParseResult) -> None:
    positionals, _ = _positionals(args, GIT_CLONE_VALUE_OPTIONS)
    if not positionals:
        return
    result.declarations.append(Declaration(Ecosystem.GIT, _git_name(positionals[0]), source=source))


def _gh_clone(args: list[str], source: str, result: ParseResult) -> None:
    positionals, _ = _positionals(args, set())
    if not positionals:
        return
    result.declarations.append(
        Declaration(Ecosystem.GIT, f"github.com/{positionals[0]}", source=source)
    )


def _skills(args: list[str], source: str, result: ParseResult) -> None:
    if not args or args[0] != "add":
        return
    positionals, _ = _positionals(args[1:], set())
    if not positionals:
        return
    result.declarations.append(Declaration(Ecosystem.SKILL, positionals[0], source=source))


def _git_name(url: str) -> str:
    """Normalise a git URL to host/path, without a git+ prefix or .git suffix."""
    url = url.strip().removeprefix("git+").rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.netloc.lower()}{parsed.path}"
    scp = re.match(r"^(?:[^@/]+@)?([^:/]+):(.+)$", url)
    if scp:
        return f"{scp.group(1).lower()}/{scp.group(2)}"
    return url
