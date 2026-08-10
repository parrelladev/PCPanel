"""Trusted local presentation of transient pairing codes."""

from __future__ import annotations

import sys
from typing import Protocol

from app.auth.models import PairingChallenge


class PairingCodePresenter(Protocol):
    """Presents a pairing challenge through a trusted local channel."""

    def present(self, challenge: PairingChallenge) -> None:
        """Present the challenge without retaining it."""
        ...


class ConsolePairingCodePresenter:
    """Writes a pairing code intentionally to the process's local console."""

    __slots__ = ()

    def present(self, challenge: PairingChallenge) -> None:
        message = "\n".join(
            (
                "PCPanel pairing request",
                "",
                f"Pairing ID: {challenge.pairing_id}",
                f"Pairing code: {challenge.code}",
                f"Expires at: {challenge.expires_at.isoformat()}",
            )
        )
        print(message, file=sys.stdout, flush=True)

