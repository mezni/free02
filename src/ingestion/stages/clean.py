"""Clean stage: normalize raw text before chunking.

Kept intentionally conservative so chunk counts and offsets are stable.
"""


def clean_text(text: str) -> str:
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
