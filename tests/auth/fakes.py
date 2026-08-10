from app.auth import PairingChallenge


class FakePairingCodePresenter:
    """Test-only presenter that records challenges for later assertions."""

    def __init__(self) -> None:
        self.presented: list[PairingChallenge] = []

    def present(self, challenge: PairingChallenge) -> None:
        self.presented.append(challenge)

