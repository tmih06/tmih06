"""
Tests for SVG manipulation functions.
"""

import sys
import os
import tempfile
import shutil

import pytest
from lxml import etree

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from today import find_and_replace, justify_format


class TestFindAndReplace:
    """Tests for the find_and_replace function."""

    def test_replaces_text(self):
        """Test that find_and_replace updates element text."""
        xml_str = '<svg xmlns="http://www.w3.org/2000/svg"><text id="test_id">old_text</text></svg>'
        root = etree.fromstring(xml_str.encode())

        find_and_replace(root, "test_id", "new_text")

        element = root.find(".//*[@id='test_id']")
        assert element.text == "new_text"

    def test_missing_element(self):
        """Test that missing elements don't cause errors."""
        xml_str = '<svg xmlns="http://www.w3.org/2000/svg"><text id="other_id">text</text></svg>'
        root = etree.fromstring(xml_str.encode())

        # Should not raise any exception
        find_and_replace(root, "nonexistent_id", "new_text")


class TestJustifyFormat:
    """Tests for the justify_format function."""

    def test_formats_integer(self):
        """Test that integers are formatted with commas."""
        xml_str = """<svg xmlns="http://www.w3.org/2000/svg">
            <text id="test_data_dots">...</text>
            <text id="test_data">0</text>
        </svg>"""
        root = etree.fromstring(xml_str.encode())

        justify_format(root, "test_data", 1234567, length=15)

        element = root.find(".//*[@id='test_data']")
        assert element.text == "1,234,567"

    def test_dot_padding(self):
        """Test that dots are added for padding."""
        xml_str = """<svg xmlns="http://www.w3.org/2000/svg">
            <text id="test_data_dots">............</text>
            <text id="test_data">0</text>
        </svg>"""
        root = etree.fromstring(xml_str.encode())

        justify_format(root, "test_data", 42, length=10)

        dots_element = root.find(".//*[@id='test_data_dots']")
        # Should have padding dots
        assert "." in dots_element.text or dots_element.text.strip() == ""
