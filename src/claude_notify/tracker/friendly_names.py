"""Generate friendly session names from UUIDs."""

import hashlib

ADJECTIVES = [
    "bold", "swift", "cosmic", "bright", "calm", "eager", "fair", "gentle",
    "happy", "keen", "lively", "merry", "noble", "proud", "quick", "ready",
    "smart", "true", "vivid", "warm", "wise", "young", "zesty", "agile",
    "brave", "clear", "deft", "epic", "fresh", "grand", "humble", "ideal",
]

NOUNS = [
    "cat", "eagle", "dragon", "wolf", "bear", "hawk", "lion", "tiger",
    "fox", "owl", "raven", "shark", "whale", "deer", "horse", "falcon",
    "phoenix", "griffin", "panther", "cobra", "jaguar", "orca", "puma", "lynx",
    "badger", "otter", "crane", "heron", "swan", "viper", "raptor", "condor",
]


def generate_friendly_name(session_id: str) -> str:
    """
    Generate a deterministic friendly name from a session UUID.

    Args:
        session_id: UUID string (with or without dashes)

    Returns:
        Friendly name like "bold-cat" or "swift-eagle"
    """
    # Remove dashes and get clean hex string
    clean_id = session_id.replace("-", "")

    # If not hex, hash it to get a deterministic number
    try:
        # Try to parse as hex first (for real UUIDs)
        adj_seed = int(clean_id[:8], 16)
        noun_seed = int(clean_id[8:16], 16)
    except (ValueError, IndexError):
        # Fall back to deterministic hash for non-UUID strings (like test IDs)
        h = int(hashlib.sha256(session_id.encode()).hexdigest()[:16], 16)
        adj_seed = h & 0xFFFFFFFF
        noun_seed = (h >> 32) & 0xFFFFFFFF

    adjective = ADJECTIVES[adj_seed % len(ADJECTIVES)]
    noun = NOUNS[noun_seed % len(NOUNS)]

    return f"{adjective}-{noun}"
