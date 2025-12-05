"""Tests for hook wire protocol."""

import json
from claude_notify.hook.protocol import (
    encode_hook_message,
    decode_hook_message,
    HookMessage,
)


def test_encode_creates_two_blobs():
    """Encoding produces two newline-separated JSON blobs."""
    claude_data = {"hook_event_name": "Stop", "session_id": "test-123"}
    env_data = {"GNOME_TERMINAL_SCREEN": "/org/gnome/Terminal/screen/abc"}

    encoded = encode_hook_message(claude_data, env_data)
    lines = encoded.strip().split("\n")

    assert len(lines) == 2
    # First blob should be parseable
    custom = json.loads(lines[0])
    assert "version" in custom
    assert "timestamp" in custom
    assert "claude_size" in custom


def test_encode_claude_size_matches():
    """claude_size in custom blob matches actual Claude blob size."""
    claude_data = {"hook_event_name": "Stop", "session_id": "test-123"}
    env_data = {}

    encoded = encode_hook_message(claude_data, env_data)
    lines = encoded.strip().split("\n")

    custom = json.loads(lines[0])
    claude_blob = lines[1]

    assert custom["claude_size"] == len(claude_blob.encode("utf-8"))


def test_decode_valid_message():
    """Can decode a valid two-blob message."""
    claude_data = {"hook_event_name": "Stop", "session_id": "test-123"}
    env_data = {"GNOME_TERMINAL_SCREEN": "/org/gnome/Terminal/screen/abc"}

    encoded = encode_hook_message(claude_data, env_data)
    message = decode_hook_message(encoded)

    assert message.claude_data == claude_data
    assert message.env["GNOME_TERMINAL_SCREEN"] == "/org/gnome/Terminal/screen/abc"
    assert message.version == 1


def test_decode_malformed_claude_blob():
    """Decoding with malformed Claude blob still parses custom blob."""
    custom = json.dumps({
        "version": 1,
        "timestamp": 1234567890.0,
        "env": {"TERM": "xterm"},
        "claude_size": 50,
    })
    malformed_claude = "{ this is not valid json"
    encoded = f"{custom}\n{malformed_claude}\n"

    message = decode_hook_message(encoded)

    assert message.version == 1
    assert message.env["TERM"] == "xterm"
    assert message.claude_data is None
    assert message.claude_raw == malformed_claude
