#!/usr/bin/env python3
"""Generate safe local secrets for Ristorante AI."""

from __future__ import annotations

import base64
import os
import secrets


def fernet_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")


def main() -> None:
    print(f"JWT_SECRET={secrets.token_urlsafe(48)}")
    print(f"PII_ENCRYPTION_KEY={fernet_key()}")
    print(f"TOOL_SECRET={secrets.token_urlsafe(32)}")


if __name__ == "__main__":
    main()
