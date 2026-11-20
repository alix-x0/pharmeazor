"""Text normalisation helpers (accent folding, etc.)."""
import re
import unicodedata

_TRAIL = re.compile(r"[\s ]+")


def strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def fold(s: str) -> str:
    """Lowercase + accent-stripped + whitespace-collapsed (for matching)."""
    if not s:
        return ""
    s = strip_accents(s).lower()
    s = s.replace("’", "'").replace("‘", "'")
    s = s.replace(" ", " ")
    s = _TRAIL.sub(" ", s)
    return s.strip()


def norm_key(s: str) -> str:
    """Uppercase accent-stripped key used for indexing/search."""
    return re.sub(r"[^A-Z0-9]+", " ", fold(s).upper()).strip()


def clean_ws(s: str) -> str:
    s = s.replace(" ", " ").replace("", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def normalize_text(s: str) -> str:
    """Light normalisation that keeps French typography but removes layout noise."""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace(" ", " ").replace(" ", " ").replace("", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
