from __future__ import annotations

import ctypes
import threading

from ..auth.models import PairingChallenge


MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040
MB_SETFOREGROUND = 0x00010000


class WindowsPairingCodePresenter:
    """Show a transient pairing code only on the Agent's local desktop."""

    __slots__ = ()

    def present(self, challenge: PairingChallenge) -> None:
        message = (
            "Um dispositivo quer conectar ao PCPanel.\n\n"
            f"Código: {challenge.code}\n\n"
            f"Expira em: {challenge.expires_at.astimezone().strftime('%H:%M:%S')}"
        )
        threading.Thread(
            target=_show_pairing_message,
            args=(message,),
            name="pcpanel-pairing-code",
            daemon=True,
        ).start()


def _show_pairing_message(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(
        None,
        message,
        "Código de conexão do PCPanel",
        MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND,
    )
