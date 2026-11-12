from __future__ import annotations

ALLOWED_RECIPIENTS: tuple[str, ...] = (
    "human-resources@example.com",
    "help-desk@example.com",
    "it@example.com",
    "kadry@example.com",
    "other@example.com",
)

_ALIASES = {
    "human-resources": "human-resources@example.com",
    "humanresources": "human-resources@example.com",
    "hr": "human-resources@example.com",
    "help-desk": "help-desk@example.com",
    "helpdesk": "help-desk@example.com",
    "support": "help-desk@example.com",
    "it": "it@example.com",
    "kadry": "kadry@example.com",
    "other": "other@example.com",
    "inne": "other@example.com",
}


def normalize_recipient(value: str) -> str:
    """Zwraca adres z listy działów albo rzuca ValueError."""
    raw = " ".join(value.strip().lower().split())
    if raw in ALLOWED_RECIPIENTS:
        return raw

    local = raw.split("@", 1)[0].replace("_", "-").replace(" ", "-")
    if local in _ALIASES:
        return _ALIASES[local]

    allowed = ", ".join(ALLOWED_RECIPIENTS)
    raise ValueError(f"Niedozwolony adres {value!r}. Użyj dokładnie jednego z: {allowed}.")
