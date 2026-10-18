"""Typo-squatting check: how close is a name to a popular package?

Attackers register near-miss names (for example "reqeusts" for "requests").
This module measures the optimal-string-alignment (restricted Damerau-
Levenshtein) distance from a name to a list of popular packages.

The popular-name list here is a seed. It should be replaced by a fuller list
per ecosystem before the evaluation harness runs.
"""

from __future__ import annotations

MAX_TYPO_DISTANCE = 2

POPULAR = {
    "pypi": [
        "requests", "numpy", "pandas", "flask", "django", "boto3", "urllib3",
        "setuptools", "pip", "pytest", "pyyaml", "click", "sqlalchemy", "fastapi",
        "pydantic", "httpx", "scipy", "matplotlib", "pillow", "beautifulsoup4",
        "selenium", "celery", "redis", "jinja2", "werkzeug", "tensorflow", "torch",
        "transformers", "openai", "anthropic", "langchain", "rich", "typer", "tqdm",
        "python-dateutil", "six", "cryptography", "paramiko", "lxml", "scikit-learn",
        "pytz", "certifi", "idna", "charset-normalizer", "attrs", "wheel", "uvicorn",
    ],
    "npm": [
        "react", "lodash", "express", "axios", "chalk", "commander", "typescript",
        "webpack", "vue", "moment", "debug", "uuid", "minimist", "yargs", "request",
        "async", "underscore", "jquery", "next", "eslint", "prettier", "jest",
        "mocha", "dotenv", "cors", "body-parser", "react-dom", "vite", "tailwindcss",
    ],
}


def osa_distance(a: str, b: str) -> int:
    """Optimal string alignment distance: insert, delete, substitute, or swap adjacent."""
    rows, cols = len(a) + 1, len(b) + 1
    d = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        d[i][0] = i
    for j in range(cols):
        d[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def closest_popular(name: str, ecosystem: str) -> tuple[str | None, int | None]:
    """Return (popular name, distance) for a near miss, else (None, None).

    A name that is itself popular is not a typo, so it returns (None, None).
    """
    lowered = name.lower()
    names = POPULAR.get(ecosystem, [])
    if lowered in names:
        return None, None
    best_name, best_distance = None, None
    for candidate in names:
        distance = osa_distance(lowered, candidate)
        if best_distance is None or distance < best_distance:
            best_name, best_distance = candidate, distance
    if best_distance is not None and best_distance <= MAX_TYPO_DISTANCE:
        return best_name, best_distance
    return None, None
