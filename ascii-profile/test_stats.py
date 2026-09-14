#!/usr/bin/env python3
"""Focused tests for the public GitHub statistics updater."""

from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError


import update_stats


def repo(
    repo_id: int,
    *,
    stars: int = 0,
    fork: bool = False,
    private: bool = False,
    visibility: str = "public",
    owner: str = "Ranj101",
) -> dict:
    return {
        "id": repo_id,
        "stargazers_count": stars,
        "fork": fork,
        "private": private,
        "visibility": visibility,
        "owner": {"login": owner},
    }


class FakeResponse:
    def __init__(self, payload, status: int = 200):
        self.body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.status = status

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeGitHub:
    def __init__(self, public_repos: int, followers: int, pages: dict[int, object]):
        self.user = {"login": "Ranj101", "public_repos": public_repos, "followers": followers}
        self.pages = pages
        self.requests = []

    def __call__(self, request, timeout: int):
        self.requests.append((request, timeout))
        parsed = urlparse(request.full_url)
        if parsed.path == "/users/Ranj101":
            return FakeResponse(self.user)
        page = int(parse_qs(parsed.query)["page"][0])
        return FakeResponse(self.pages[page])


def profile_bytes(metrics=None, note="Statistics are not configured.") -> bytes:
    profile = {
        "name": "Ranj Rashid",
        "handle": "Ranj101",
        "tagline": "Keep this",
        "fields": [{"label": "role", "value": "Engineer"}],
        "metrics": metrics if metrics is not None else [],
        "note": note,
        "custom": {"must": "survive"},
    }
    return (json.dumps(profile, indent=2) + "\n").encode()


class PublicStatsTests(unittest.TestCase):
    def test_fetches_multiple_pages_and_excludes_fork_stars(self):
        first_page = [repo(number, stars=1) for number in range(1, 100)]
        first_page.append(repo(100, stars=500, fork=True))
        github = FakeGitHub(102, 26, {1: first_page, 2: [repo(101, stars=2), repo(102, stars=3)]})

        stats = update_stats.fetch_public_stats("Ranj101", github)

        self.assertEqual(stats, update_stats.PublicStats(repositories=102, stars=104, followers=26))
        repo_requests = [request for request, _ in github.requests if request.full_url.endswith("page=1")]
        self.assertEqual(len(repo_requests), 1)
        query = parse_qs(urlparse(repo_requests[0].full_url).query)
        self.assertEqual(query, {
            "type": ["owner"],
            "sort": ["full_name"],
            "direction": ["asc"],
            "per_page": ["100"],
            "page": ["1"],
        })

    def test_excludes_private_internal_and_foreign_owner_rows(self):
        github = FakeGitHub(1, 4, {1: [
            repo(1, stars=7),
            repo(2, stars=100, private=True),
            repo(3, stars=100, visibility="internal"),
            repo(4, stars=100, owner="someone-else"),
        ]})

        self.assertEqual(
            update_stats.fetch_public_stats("Ranj101", github),
            update_stats.PublicStats(1, 7, 4),
        )

    def test_requests_are_anonymous_even_when_token_variables_exist(self):
        github = FakeGitHub(0, 0, {1: []})
        with patch.dict(os.environ, {"GH_TOKEN": "secret-one", "GITHUB_TOKEN": "secret-two"}):
            update_stats.fetch_public_stats("Ranj101", github)

        for request, timeout in github.requests:
            parsed = urlparse(request.full_url)
            self.assertEqual((parsed.scheme, parsed.netloc), ("https", "api.github.com"))
            self.assertIn(parsed.path, ("/users/Ranj101", "/users/Ranj101/repos"))
            headers = {key.casefold(): value for key, value in request.header_items()}
            self.assertNotIn("authorization", headers)
            self.assertNotIn("cookie", headers)
            self.assertEqual(headers["accept"], "application/vnd.github+json")
            self.assertEqual(headers["x-github-api-version"], "2026-03-10")
            self.assertIn("public-profile-stats", headers["user-agent"])
            self.assertEqual(timeout, 15)

    def test_rejects_bad_handles_counts_and_response_shapes(self):
        for handle in ("", "-bad", "bad-", "two--hyphens", "a" * 40, "slash/name"):
            with self.subTest(handle=handle), self.assertRaises(update_stats.StatsError):
                update_stats.validate_handle(handle)

        cases = [
            ({"login": "Ranj101", "public_repos": True, "followers": 0}, []),
            ({"login": "Ranj101", "public_repos": 0, "followers": -1}, []),
            ({"login": "other", "public_repos": 0, "followers": 0}, []),
            ([], []),
            ({"login": "Ranj101", "public_repos": 0, "followers": 0}, {}),
        ]
        for user, repos in cases:
            with self.subTest(user=user, repos=repos):
                github = FakeGitHub(0, 0, {1: repos})
                github.user = user
                with self.assertRaises(update_stats.StatsError):
                    update_stats.fetch_public_stats("Ranj101", github)

        github = FakeGitHub(1, 0, {1: [repo(1, stars=-1)]})
        with self.assertRaises(update_stats.StatsError):
            update_stats.fetch_public_stats("Ranj101", github)

    def test_deduplicates_identical_repositories_and_rejects_conflicts(self):
        duplicate = repo(1, stars=2)
        github = FakeGitHub(1, 0, {1: [duplicate, duplicate.copy()]})
        self.assertEqual(update_stats.fetch_public_stats("Ranj101", github).stars, 2)

        github = FakeGitHub(1, 0, {1: [duplicate, repo(1, stars=3)]})
        with self.assertRaises(update_stats.StatsError):
            update_stats.fetch_public_stats("Ranj101", github)

    def test_incomplete_fetch_and_network_failure_leave_profile_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "profile.json")
            original = profile_bytes()
            config.write_bytes(original)
            incomplete = FakeGitHub(2, 0, {1: [repo(1)]})
            with self.assertRaises(update_stats.StatsError):
                update_stats.refresh(config, opener=incomplete)
            self.assertEqual(config.read_bytes(), original)

            def failure(request, timeout):
                if request.full_url.endswith("/users/Ranj101"):
                    return FakeResponse({"login": "Ranj101", "public_repos": 0, "followers": 0})
                raise OSError("offline")

            with self.assertRaises(OSError):
                update_stats.refresh(config, opener=failure)
            self.assertEqual(config.read_bytes(), original)

            def malformed(request, timeout):
                if request.full_url.endswith("/users/Ranj101"):
                    return FakeResponse(b"{not json")
                raise AssertionError("Repository request should not occur")

            with self.assertRaises(update_stats.StatsError):
                update_stats.refresh(config, opener=malformed)
            self.assertEqual(config.read_bytes(), original)

    def test_does_not_overwrite_config_changed_during_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "profile.json")
            config.write_bytes(profile_bytes())
            changed = profile_bytes(note="Edited while the request was running.")

            def edit_during_fetch(request, timeout):
                if request.full_url.endswith("/users/Ranj101"):
                    return FakeResponse({"login": "Ranj101", "public_repos": 0, "followers": 0})
                config.write_bytes(changed)
                return FakeResponse([])

            with self.assertRaises(update_stats.StatsError):
                update_stats.refresh(config, opener=edit_during_fetch)
            self.assertEqual(config.read_bytes(), changed)

    def test_check_is_read_only_and_reports_difference(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "profile.json")
            original = profile_bytes()
            config.write_bytes(original)
            before = config.stat().st_mtime_ns

            stats, status, exit_code = update_stats.refresh(
                config, check=True, opener=FakeGitHub(1, 26, {1: [repo(1, stars=1)]})
            )

            self.assertEqual(stats, update_stats.PublicStats(1, 1, 26))
            self.assertEqual((status, exit_code), ("outdated", 1))
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(config.stat().st_mtime_ns, before)

    def test_check_cli_prints_only_aggregate_result(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "profile.json")
            config.write_bytes(profile_bytes())
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = update_stats.main(
                    ["--config", str(config), "--check"],
                    opener=FakeGitHub(1, 26, {1: [repo(1, stars=1)]}),
                )

            self.assertEqual(exit_code, 1)
            self.assertEqual(
                output.getvalue(),
                "public repos=1 stars received=1 followers=26 status=outdated\n",
            )

    def test_cli_network_errors_do_not_write_counts(self):
        failures = [
            HTTPError("https://api.github.com/users/Ranj101", 403, "Forbidden", {}, None),
            IncompleteRead(b"partial response", 100),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as directory:
                config = Path(directory, "profile.json")
                original = profile_bytes()
                config.write_bytes(original)
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = update_stats.main(
                        ["--config", str(config)],
                        opener=Mock(side_effect=failure),
                    )
                self.assertEqual(exit_code, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertTrue(stderr.getvalue().startswith("error: "))
                self.assertEqual(config.read_bytes(), original)

    def test_rejects_invalid_json_constants_and_duplicate_keys(self):
        for body in (b'{"followers": NaN}', b'{"followers": 1, "followers": 2}'):
            with self.subTest(body=body), self.assertRaises(update_stats.StatsError):
                update_stats.request_json(
                    "https://api.github.com/users/Ranj101",
                    lambda request, timeout: FakeResponse(body),
                )

    def test_failed_atomic_replace_keeps_previous_profile_and_removes_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "profile.json")
            original = profile_bytes()
            config.write_bytes(original)
            github = FakeGitHub(0, 26, {1: []})
            with patch.object(update_stats.os, "replace", side_effect=OSError("Write failed")):
                with self.assertRaises(OSError):
                    update_stats.refresh(config, opener=github)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [config])

    def test_refresh_preserves_fields_and_repeated_run_is_exact_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory, "profile.json")
            original = profile_bytes()
            config.write_bytes(original)
            github = FakeGitHub(5, 26, {1: [repo(1, stars=1), repo(2), repo(3), repo(4), repo(5)]})

            stats, status, exit_code = update_stats.refresh(config, opener=github)

            self.assertEqual(stats, update_stats.PublicStats(5, 1, 26))
            self.assertEqual((status, exit_code), ("updated", 0))
            updated = config.read_bytes()
            updated_profile = json.loads(updated)
            original_profile = json.loads(original)
            for key in ("name", "handle", "tagline", "fields", "custom"):
                self.assertEqual(updated_profile[key], original_profile[key])
            self.assertEqual(updated_profile["metrics"], [
                {"label": "public repos", "value": "5"},
                {"label": "stars received", "value": "1"},
                {"label": "followers", "value": "26"},
            ])
            self.assertEqual(updated_profile["note"], "Public GitHub statistics only.")

            time.sleep(0.002)
            before_second = config.stat().st_mtime_ns
            result = update_stats.refresh(
                config,
                opener=FakeGitHub(5, 26, {1: [repo(1, stars=1), repo(2), repo(3), repo(4), repo(5)]}),
            )
            self.assertEqual(result[1:], ("unchanged", 0))
            self.assertEqual(config.read_bytes(), updated)
            self.assertEqual(config.stat().st_mtime_ns, before_second)


if __name__ == "__main__":
    unittest.main()
