"""Hook wire protocol for communication between hook and daemon."""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

PROTOCOL_VERSION = 1


@dataclass
class HookMessage:
    """Decoded hook message."""
    version: int
    timestamp: float
    env: Dict[str, str]
    claude_size: int
    claude_data: Optional[Dict[str, Any]]
    claude_raw: str


def encode_hook_message(
    claude_data: Dict[str, Any],
    env_data: Dict[str, str],
) -> str:
    """
    Encode a hook message for transmission to daemon.

    Args:
        claude_data: Raw JSON data from Claude (passed through)
        env_data: Environment variables to include

    Returns:
        Two newline-separated JSON blobs
    """
    # Encode Claude data first to get its size
    claude_blob = json.dumps(claude_data, separators=(",", ":"))
    claude_size = len(claude_blob.encode("utf-8"))

    # Build custom blob
    custom_blob = json.dumps({
        "version": PROTOCOL_VERSION,
        "timestamp": time.time(),
        "env": env_data,
        "claude_size": claude_size,
    }, separators=(",", ":"))

    return f"{custom_blob}\n{claude_blob}\n"


def decode_hook_message(data: str) -> HookMessage:
    """
    Decode a hook message from the wire format.

    Args:
        data: Two newline-separated JSON blobs

    Returns:
        HookMessage with parsed data (claude_data may be None if malformed)
    """
    lines = data.strip().split("\n", 1)

    # Parse custom blob (should always succeed)
    custom = json.loads(lines[0])

    # Try to parse Claude blob
    claude_raw = lines[1] if len(lines) > 1 else ""
    claude_data = None

    try:
        if claude_raw:
            claude_data = json.loads(claude_raw)
    except json.JSONDecodeError:
        pass  # Keep claude_data as None, preserve raw

    return HookMessage(
        version=custom["version"],
        timestamp=custom["timestamp"],
        env=custom.get("env", {}),
        claude_size=custom["claude_size"],
        claude_data=claude_data,
        claude_raw=claude_raw,
    )
