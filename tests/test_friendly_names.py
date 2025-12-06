"""Tests for friendly session name generation."""

from claude_notify.tracker.friendly_names import generate_friendly_name


def test_generates_adjective_noun_format():
    """Name should be adjective-noun format."""
    name = generate_friendly_name("73b5e210-ec1a-4294-96e4-c2aecb2e1063")
    parts = name.split("-")
    assert len(parts) == 2
    assert len(parts[0]) > 0  # adjective
    assert len(parts[1]) > 0  # noun


def test_deterministic_for_same_uuid():
    """Same UUID should always produce same name."""
    uuid = "73b5e210-ec1a-4294-96e4-c2aecb2e1063"
    name1 = generate_friendly_name(uuid)
    name2 = generate_friendly_name(uuid)
    assert name1 == name2


def test_different_uuids_likely_different_names():
    """Different UUIDs should produce different names (with high probability)."""
    name1 = generate_friendly_name("73b5e210-ec1a-4294-96e4-c2aecb2e1063")
    name2 = generate_friendly_name("550e8400-e29b-41d4-a716-446655440000")
    assert name1 != name2
