"""Shared HTTP helpers."""
import json
import re
import time
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

session = requests.Session()
session.headers.update({
    "User-Agent": UA,
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
})


def get(url, **kw):
    """GET with retries on transient network errors."""
    last = None
    for attempt in range(5):
        try:
            kw.setdefault("timeout", 60)
            return session.get(url, **kw)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def post(url, **kw):
    last = None
    for attempt in range(5):
        try:
            kw.setdefault("timeout", 60)
            return session.post(url, **kw)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last
