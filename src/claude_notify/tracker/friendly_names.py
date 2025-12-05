"""Generate friendly session names from UUIDs."""

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

    # Use first 8 chars for adjective, next 8 for noun
    adj_seed = int(clean_id[:8], 16)
    noun_seed = int(clean_id[8:16], 16)

    adjective = ADJECTIVES[adj_seed % len(ADJECTIVES)]
    noun = NOUNS[noun_seed % len(NOUNS)]

    return f"{adjective}-{noun}"
