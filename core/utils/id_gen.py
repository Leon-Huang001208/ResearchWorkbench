import uuid


def generate_id(prefix: str | None = None) -> str:
    if prefix:
        return f"{prefix}_{uuid.uuid4()}"
    return str(uuid.uuid4())
