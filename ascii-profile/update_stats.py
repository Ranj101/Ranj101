#!/usr/bin/env python3
"""Refresh the profile's aggregate public GitHub statistics."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen


API_VERSION = "2026-03-10"
TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
USER_AGENT = "Ranj101-public-profile-stats/1.0"
HANDLE_PATTERN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\Z")
NOTE = "Public GitHub statistics only."


class StatsError(ValueError):
    """Raised when public statistics cannot be refreshed safely."""


@dataclass(frozen=True)
class PublicStats:
    repositories: int
    stars: int
    followers: int


def validate_handle(handle: Any) -> str:
    if not isinstance(handle, str) or not 1 <= len(handle) <= 39 or not HANDLE_PATTERN.fullmatch(handle):
        raise StatsError("Invalid GitHub handle.")
    return handle


def nonnegative_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StatsError(f"{field} must be a nonnegative integer.")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StatsError("GitHub returned duplicate JSON object keys.")
        result[key] = value
    return result


def _invalid_json_constant(_: str) -> None:
    raise StatsError("GitHub returned invalid JSON numeric data.")


def request_json(url: str, opener: Callable[..., Any]) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        },
    )
    with opener(request, timeout=TIMEOUT_SECONDS) as response:
        if getattr(response, "status", 200) != 200:
            raise StatsError("GitHub returned an unsuccessful response.")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise StatsError("GitHub response is too large.")
    try:
        return json.loads(
            body,
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StatsError("GitHub returned malformed JSON.") from error


def _user_counts(payload: Any, handle: str) -> tuple[int, int]:
    if not isinstance(payload, dict):
        raise StatsError("GitHub user response must be an object.")
    login = payload.get("login")
    if not isinstance(login, str) or login.casefold() != handle.casefold():
        raise StatsError("GitHub returned a different user.")
    return (
        nonnegative_integer(payload.get("public_repos"), "public_repos"),
        nonnegative_integer(payload.get("followers"), "followers"),
    )


def _repo_record(payload: Any) -> tuple[int, bool, bool, str, str, int]:
    if not isinstance(payload, dict):
        raise StatsError("GitHub repository entries must be objects.")
    repo_id = nonnegative_integer(payload.get("id"), "repository id")
    private = payload.get("private")
    fork = payload.get("fork")
    visibility = payload.get("visibility")
    owner = payload.get("owner")
    stars = nonnegative_integer(payload.get("stargazers_count"), "stargazers_count")
    if not isinstance(private, bool) or not isinstance(fork, bool):
        raise StatsError("GitHub repository flags must be booleans.")
    if not isinstance(visibility, str):
        raise StatsError("GitHub repository visibility must be a string.")
    if not isinstance(owner, dict) or not isinstance(owner.get("login"), str):
        raise StatsError("GitHub repository owner is malformed.")
    return repo_id, private, fork, visibility, owner["login"], stars


def fetch_public_stats(handle: str, opener: Callable[..., Any] = urlopen) -> PublicStats:
    handle = validate_handle(handle)
    user_url = f"https://api.github.com/users/{handle}"
    public_repos, followers = _user_counts(request_json(user_url, opener), handle)

    repositories: dict[int, tuple[bool, bool, str, str, int]] = {}
    page = 1
    while True:
        repo_url = (
            f"https://api.github.com/users/{handle}/repos?type=owner"
            f"&sort=full_name&direction=asc&per_page=100&page={page}"
        )
        payload = request_json(repo_url, opener)
        if not isinstance(payload, list):
            raise StatsError("GitHub repositories response must be an array.")
        if len(payload) > 100:
            raise StatsError("GitHub returned an oversized repository page.")

        added = 0
        for raw_repo in payload:
            repo_id, private, fork, visibility, owner, stars = _repo_record(raw_repo)
            record = private, fork, visibility, owner, stars
            previous = repositories.get(repo_id)
            if previous is not None:
                if previous != record:
                    raise StatsError("GitHub returned conflicting duplicate repositories.")
                continue
            repositories[repo_id] = record
            added += 1

        if len(payload) < 100:
            break
        if added == 0:
            raise StatsError("GitHub repository pagination did not advance.")
        page += 1
        if page > 1000:
            raise StatsError("GitHub repository pagination exceeded its safety limit.")

    owned_public = [
        (fork, stars)
        for private, fork, visibility, owner, stars in repositories.values()
        if not private and visibility == "public" and owner.casefold() == handle.casefold()
    ]
    if len(owned_public) != public_repos:
        raise StatsError("GitHub repository pagination was incomplete or changed during the fetch.")
    return PublicStats(
        repositories=len(owned_public),
        stars=sum(stars for fork, stars in owned_public if not fork),
        followers=followers,
    )


def desired_metrics(stats: PublicStats) -> list[dict[str, str]]:
    return [
        {"label": "public repos", "value": str(stats.repositories)},
        {"label": "stars received", "value": str(stats.stars)},
        {"label": "followers", "value": str(stats.followers)},
    ]


def _read_config(path: Path) -> tuple[bytes, os.stat_result, dict[str, Any]]:
    try:
        with path.open("rb") as source:
            raw = source.read()
            details = os.fstat(source.fileno())
        profile = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StatsError("Profile config could not be read.") from error
    if not isinstance(profile, dict):
        raise StatsError("Profile config must be an object.")
    validate_handle(profile.get("handle"))
    if not isinstance(profile.get("metrics"), list) or not isinstance(profile.get("note"), str):
        raise StatsError("Profile metrics or note is malformed.")
    return raw, details, profile


def _fingerprint(details: os.stat_result) -> tuple[int, int, int, int, int]:
    return details.st_dev, details.st_ino, details.st_mode, details.st_size, details.st_mtime_ns


def _atomic_replace(path: Path, expected: bytes, expected_details: os.stat_result, content: bytes) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as output:
            temporary_name = output.name
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_name, stat.S_IMODE(expected_details.st_mode))

        with path.open("rb") as current:
            current_bytes = current.read()
            current_details = os.fstat(current.fileno())
        if current_bytes != expected or _fingerprint(current_details) != _fingerprint(expected_details):
            raise StatsError("Profile config changed during the fetch.")
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def refresh(path: Path, check: bool = False, opener: Callable[..., Any] = urlopen) -> tuple[PublicStats, str, int]:
    raw, details, profile = _read_config(path)
    stats = fetch_public_stats(profile["handle"], opener)
    metrics = desired_metrics(stats)
    current = profile["metrics"] == metrics and profile["note"] == NOTE
    if check:
        return stats, "unchanged" if current else "outdated", 0 if current else 1
    if current:
        return stats, "unchanged", 0

    profile["metrics"] = metrics
    profile["note"] = NOTE
    content = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _atomic_replace(path, raw, details, content)
    return stats, "updated", 0


def main(argv: list[str] | None = None, opener: Callable[..., Any] = urlopen) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("profile.json"))
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        stats, status, exit_code = refresh(arguments.config, arguments.check, opener)
    except (OSError, HTTPException, StatsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(
        f"public repos={stats.repositories} stars received={stats.stars} "
        f"followers={stats.followers} status={status}"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
