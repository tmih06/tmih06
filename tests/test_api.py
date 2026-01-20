"""
Tests for GitHub API interactions with mocked responses.
"""

import sys
import os
import json

import pytest
import responses

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from today import (
    simple_request,
    user_getter,
    follower_getter,
    graph_commits,
    graph_repos_stars,
)


class TestSimpleRequest:
    """Tests for the simple_request function."""

    @responses.activate
    def test_successful_request(self):
        """Test a successful API request."""
        responses.add(
            responses.POST,
            "https://api.github.com/graphql",
            json={"data": {"test": "value"}},
            status=200,
        )

        result = simple_request("test_func", "query {}", {})
        assert result.status_code == 200
        assert result.json()["data"]["test"] == "value"

    @responses.activate
    def test_failed_request(self):
        """Test that failed requests raise exceptions."""
        responses.add(
            responses.POST,
            "https://api.github.com/graphql",
            json={"error": "Bad request"},
            status=400,
        )

        with pytest.raises(Exception):
            simple_request("test_func", "query {}", {})


class TestUserGetter:
    """Tests for the user_getter function."""

    @responses.activate
    def test_returns_user_data(self, sample_user_response):
        """Test that user_getter returns user ID and creation date."""
        responses.add(
            responses.POST,
            "https://api.github.com/graphql",
            json=sample_user_response,
            status=200,
        )

        owner_id, created_at = user_getter("tmih06")
        assert owner_id == {"id": "MDQ6VXNlcjEyMzQ1Njc4"}
        assert created_at == "2020-01-15T10:30:00Z"


class TestFollowerGetter:
    """Tests for the follower_getter function."""

    @responses.activate
    def test_returns_follower_count(self, sample_follower_response):
        """Test that follower_getter returns correct count."""
        responses.add(
            responses.POST,
            "https://api.github.com/graphql",
            json=sample_follower_response,
            status=200,
        )

        count = follower_getter("tmih06")
        assert count == 42
        assert isinstance(count, int)


class TestGraphCommits:
    """Tests for the graph_commits function."""

    @responses.activate
    def test_returns_commit_count(self, sample_commits_response):
        """Test that graph_commits returns correct contribution count."""
        responses.add(
            responses.POST,
            "https://api.github.com/graphql",
            json=sample_commits_response,
            status=200,
        )

        count = graph_commits("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z")
        assert count == 365
        assert isinstance(count, int)


class TestGraphReposStars:
    """Tests for the graph_repos_stars function."""

    @responses.activate
    def test_returns_repo_count(self, sample_repos_response):
        """Test that graph_repos_stars returns correct repo count."""
        responses.add(
            responses.POST,
            "https://api.github.com/graphql",
            json=sample_repos_response,
            status=200,
        )

        count = graph_repos_stars("repos", ["OWNER"])
        assert count == 25

    @responses.activate
    def test_returns_star_count(self, sample_repos_response):
        """Test that graph_repos_stars returns correct star count."""
        responses.add(
            responses.POST,
            "https://api.github.com/graphql",
            json=sample_repos_response,
            status=200,
        )

        count = graph_repos_stars("stars", ["OWNER"])
        assert count == 15  # 10 + 5 from the fixture
