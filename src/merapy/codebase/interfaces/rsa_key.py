from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RSAKey(Protocol):
    """RSA keypair holder for JWT / encryption."""

    def public_key_pem(self) -> bytes: ...
    def private_key_pem(self) -> bytes: ...
