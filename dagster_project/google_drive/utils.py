import hashlib

def compute_hash(content: bytes) -> str:
    """Compute a SHA-256 hash of the given content."""
    return hashlib.sha256(content).hexdigest() 