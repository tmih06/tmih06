"""
Pytest configuration and shared fixtures for testing the GitHub profile generator.
"""

import os
import pytest
import responses

# Set default environment variables for testing
os.environ.setdefault("ACCESS_TOKEN", "test_token_for_testing")
os.environ.setdefault("USER_NAME", "tmih06")


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("ACCESS_TOKEN", "test_token_12345")
    monkeypatch.setenv("USER_NAME", "tmih06")


@pytest.fixture
def sample_user_response():
    """Sample GitHub GraphQL response for user query."""
    return {
        "data": {
            "user": {"id": "MDQ6VXNlcjEyMzQ1Njc4", "createdAt": "2020-01-15T10:30:00Z"}
        }
    }


@pytest.fixture
def sample_follower_response():
    """Sample GitHub GraphQL response for follower query."""
    return {"data": {"user": {"followers": {"totalCount": 42}}}}


@pytest.fixture
def sample_commits_response():
    """Sample GitHub GraphQL response for commits query."""
    return {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {"totalContributions": 365}
                }
            }
        }
    }


@pytest.fixture
def sample_repos_response():
    """Sample GitHub GraphQL response for repos/stars query."""
    return {
        "data": {
            "user": {
                "repositories": {
                    "totalCount": 25,
                    "edges": [
                        {
                            "node": {
                                "nameWithOwner": "tmih06/repo1",
                                "stargazers": {"totalCount": 10},
                            }
                        },
                        {
                            "node": {
                                "nameWithOwner": "tmih06/repo2",
                                "stargazers": {"totalCount": 5},
                            }
                        },
                    ],
                    "pageInfo": {"endCursor": None, "hasNextPage": False},
                }
            }
        }
    }


@pytest.fixture
def mocked_responses():
    """Activate responses mock for HTTP requests."""
    with responses.RequestsMock() as rsps:
        yield rsps
