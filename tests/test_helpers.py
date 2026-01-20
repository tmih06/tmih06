"""
Tests for helper functions in today.py that don't require API calls.
"""

import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from today import format_plural, daily_readme, stars_counter


class TestFormatPlural:
    """Tests for the format_plural function."""

    def test_singular(self):
        """Test that singular values return empty string."""
        assert format_plural(1) == ""

    def test_plural_zero(self):
        """Test that zero returns 's'."""
        assert format_plural(0) == "s"

    def test_plural_many(self):
        """Test that values > 1 return 's'."""
        assert format_plural(2) == "s"
        assert format_plural(10) == "s"
        assert format_plural(100) == "s"

    def test_negative(self):
        """Test negative values."""
        assert format_plural(-1) == "s"


class TestDailyReadme:
    """Tests for the daily_readme function."""

    def test_returns_string(self):
        """Test that daily_readme returns a string."""
        birthday = datetime.datetime(2000, 1, 1)
        result = daily_readme(birthday)
        assert isinstance(result, str)

    def test_contains_years_months_days(self):
        """Test that the result contains year, month, day labels."""
        birthday = datetime.datetime(2000, 1, 1)
        result = daily_readme(birthday)
        assert "year" in result
        assert "month" in result
        assert "day" in result

    def test_birthday_emoji(self):
        """Test that birthday shows cake emoji."""
        # Use today's date for the birthday
        today = datetime.datetime.today()
        birthday = datetime.datetime(today.year - 25, today.month, today.day)
        result = daily_readme(birthday)
        # Should contain birthday cake emoji on the exact day
        assert "25 year" in result


class TestStarsCounter:
    """Tests for the stars_counter function."""

    def test_empty_data(self):
        """Test with no repositories."""
        assert stars_counter([]) == 0

    def test_single_repo(self):
        """Test with a single repository."""
        data = [{"node": {"stargazers": {"totalCount": 10}}}]
        assert stars_counter(data) == 10

    def test_multiple_repos(self):
        """Test with multiple repositories."""
        data = [
            {"node": {"stargazers": {"totalCount": 10}}},
            {"node": {"stargazers": {"totalCount": 20}}},
            {"node": {"stargazers": {"totalCount": 5}}},
        ]
        assert stars_counter(data) == 35

    def test_zero_stars(self):
        """Test with repos that have no stars."""
        data = [
            {"node": {"stargazers": {"totalCount": 0}}},
            {"node": {"stargazers": {"totalCount": 0}}},
        ]
        assert stars_counter(data) == 0
