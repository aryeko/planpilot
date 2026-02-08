"""Tests for rendering component helper functions."""

from __future__ import annotations

from planpilot.models.plan import Scope, SpecRef
from planpilot.rendering.components import bullets, scope_block, spec_ref_block


def test_bullets_empty():
    """Test bullets() with empty list returns '* (none)'."""
    assert bullets([]) == "* (none)"


def test_bullets_single_item():
    """Test bullets() with single item."""
    assert bullets(["item1"]) == "* item1"


def test_bullets_multiple_items():
    """Test bullets() with multiple items."""
    result = bullets(["item1", "item2", "item3"])
    assert result == "* item1\n* item2\n* item3"


def test_scope_block_empty():
    """Test scope_block() with empty scope."""
    scope = Scope(in_scope=[], out_scope=[])
    result = scope_block(scope)
    expected = "In:\n\n* (none)\n\nOut:\n\n* (none)"
    assert result == expected


def test_scope_block_with_items():
    """Test scope_block() with in-scope and out-of-scope items."""
    scope = Scope(in_scope=["item1", "item2"], out_scope=["item3"])
    result = scope_block(scope)
    expected = "In:\n\n* item1\n* item2\n\nOut:\n\n* item3"
    assert result == expected


def test_spec_ref_block_string():
    """Test spec_ref_block() with string input."""
    assert spec_ref_block("path/to/spec.md") == "* path/to/spec.md"


def test_spec_ref_block_string_empty():
    """Test spec_ref_block() with empty string."""
    assert spec_ref_block("") == "* (none)"
    assert spec_ref_block("   ") == "* (none)"


def test_spec_ref_block_string_stripped():
    """Test spec_ref_block() strips whitespace from string."""
    assert spec_ref_block("  path/to/spec.md  ") == "* path/to/spec.md"


def test_spec_ref_block_specref_path_only():
    """Test spec_ref_block() with SpecRef containing only path."""
    spec_ref = SpecRef(path="path/to/spec.md")
    assert spec_ref_block(spec_ref) == "* path/to/spec.md"


def test_spec_ref_block_specref_path_and_anchor():
    """Test spec_ref_block() with SpecRef containing path and anchor."""
    spec_ref = SpecRef(path="path/to/spec.md", anchor="section-name")
    assert spec_ref_block(spec_ref) == "* path/to/spec.md#section-name"


def test_spec_ref_block_specref_with_section():
    """Test spec_ref_block() with SpecRef containing section."""
    spec_ref = SpecRef(path="path/to/spec.md", anchor="anchor", section="Section 2.1")
    result = spec_ref_block(spec_ref)
    expected = "* path/to/spec.md#anchor\n* Section: Section 2.1"
    assert result == expected


def test_spec_ref_block_specref_with_quote():
    """Test spec_ref_block() with SpecRef containing quote."""
    spec_ref = SpecRef(path="path/to/spec.md", quote="Important quote here")
    result = spec_ref_block(spec_ref)
    expected = "* path/to/spec.md\n* Quote: Important quote here"
    assert result == expected


def test_spec_ref_block_specref_full():
    """Test spec_ref_block() with SpecRef containing all fields."""
    spec_ref = SpecRef(path="path/to/spec.md", anchor="anchor", section="Section 2.1", quote="Important quote")
    result = spec_ref_block(spec_ref)
    expected = "* path/to/spec.md#anchor\n* Section: Section 2.1\n* Quote: Important quote"
    assert result == expected


def test_spec_ref_block_specref_empty_path():
    """Test spec_ref_block() with SpecRef containing empty path."""
    spec_ref = SpecRef(path="")
    assert spec_ref_block(spec_ref) == "* (none)"


def test_spec_ref_block_specref_whitespace_path():
    """Test spec_ref_block() with SpecRef containing whitespace-only path."""
    spec_ref = SpecRef(path="   ")
    assert spec_ref_block(spec_ref) == "* (none)"


def test_spec_ref_block_specref_strips_fields():
    """Test spec_ref_block() strips whitespace from SpecRef fields."""
    spec_ref = SpecRef(
        path="  path/to/spec.md  ", anchor="  anchor  ", section="  Section 2.1  ", quote="  Important quote  "
    )
    result = spec_ref_block(spec_ref)
    expected = "* path/to/spec.md#anchor\n* Section: Section 2.1\n* Quote: Important quote"
    assert result == expected


def test_spec_ref_block_none():
    """Test spec_ref_block() with None input."""
    assert spec_ref_block(None) == "* (none)"


def test_spec_ref_block_other_type():
    """Test spec_ref_block() with unsupported type returns '* (none)'."""
    assert spec_ref_block(123) == "* (none)"
    assert spec_ref_block({}) == "* (none)"
