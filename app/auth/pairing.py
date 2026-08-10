"""Thread-safe orchestration of temporary device pairing sessions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable
from uuid import UUID, uuid4

from app.auth.errors import (
    PairingAlreadyConsumedError,
    PairingAttemptsExceededError,
    PairingCapacityError,
    PairingExpiredError,
    PairingInvalidCodeError,
    PairingNotFoundError,
)
from app.auth.models import (
    Device,
    DeviceStatus,
    IssuedDeviceToken,
    PairingChallenge,
    PairingSession,
    PairingStatus,
    _validated_device_name,
)
from app.auth.registry import DeviceRegistry
from app.auth.tokens import TokenService


DEFAULT_PAIRING_TTL = timedelta(minutes=5)
DEFAULT_MAX_PAIRING_ATTEMPTS = 5
DEFAULT_MAX_PENDING_PAIRINGS = 10


class PairingService:
    """Owns process-local pairing attempts and authorizes successful devices."""

    def __init__(
        self,
        registry: DeviceRegistry,
        token_service: TokenService | None = None,
        *,
        ttl: timedelta = DEFAULT_PAIRING_TTL,
        max_attempts: int = DEFAULT_MAX_PAIRING_ATTEMPTS,
        max_pending_pairings: int = DEFAULT_MAX_PENDING_PAIRINGS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl <= timedelta(0):
            raise ValueError("pairing TTL must be positive")
        if max_attempts <= 0:
            raise ValueError("max pairing attempts must be positive")
        if max_pending_pairings <= 0:
            raise ValueError("max pending pairings must be positive")

        self._registry = registry
        self._tokens = token_service or TokenService()
        self._ttl = ttl
        self._max_attempts = max_attempts
        self._max_pending_pairings = max_pending_pairings
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions: dict[UUID, PairingSession] = {}
        self._lock = Lock()

    def start_pairing(self, device_name: str) -> PairingChallenge:
        """Create a pending session and return its transient plaintext code."""
        normalized_name = _validated_device_name(device_name)
        now = self._now()

        with self._lock:
            self._remove_expired_sessions(now)
            pending_count = sum(
                session.status is PairingStatus.PENDING
                for session in self._sessions.values()
            )
            if pending_count >= self._max_pending_pairings:
                raise PairingCapacityError()

            pairing_id = uuid4()
            code = self._tokens.generate_pairing_code()
            expires_at = now + self._ttl
            session = PairingSession(
                pairing_id=pairing_id,
                device_name=normalized_name,
                code_hash=self._tokens.hash_pairing_code(code),
                created_at=now,
                expires_at=expires_at,
                attempts_remaining=self._max_attempts,
                status=PairingStatus.PENDING,
            )
            self._sessions[pairing_id] = session

        return PairingChallenge(
            pairing_id=pairing_id,
            code=code,
            expires_at=expires_at,
        )

    def complete_pairing(self, pairing_id: UUID, code: str) -> IssuedDeviceToken:
        """Consume a valid pairing exactly once and issue one device token."""
        now = self._now()

        with self._lock:
            session = self._sessions.get(pairing_id)
            if session is None:
                raise PairingNotFoundError(pairing_id)
            if session.is_expired(now):
                del self._sessions[pairing_id]
                raise PairingExpiredError(pairing_id)
            if session.status is PairingStatus.CONSUMED:
                raise PairingAlreadyConsumedError(pairing_id)
            if (
                session.status is PairingStatus.LOCKED
                or session.attempts_remaining == 0
            ):
                raise PairingAttemptsExceededError(pairing_id)

            if not self._tokens.verify_pairing_code(code, session.code_hash):
                attempts_remaining = session.attempts_remaining - 1
                status = (
                    PairingStatus.LOCKED
                    if attempts_remaining == 0
                    else PairingStatus.PENDING
                )
                self._sessions[pairing_id] = replace(
                    session,
                    attempts_remaining=attempts_remaining,
                    status=status,
                )
                if status is PairingStatus.LOCKED:
                    raise PairingAttemptsExceededError(pairing_id)
                raise PairingInvalidCodeError(pairing_id)

            device = Device(
                id=uuid4(),
                name=session.device_name,
                status=DeviceStatus.AUTHORIZED,
                created_at=now,
                authorized_at=now,
            )
            token = self._tokens.generate_device_token()
            self._sessions[pairing_id] = replace(
                session,
                status=PairingStatus.CONSUMED,
            )
            # A valid code is single-use even if durable registration fails.
            # The registry only returns after its store transaction commits.
            self._registry.register(device, token)
            return IssuedDeviceToken(device_id=device.id, token=token)

    def get_session(self, pairing_id: UUID) -> PairingSession:
        """Return an immutable session snapshot, or raise when absent."""
        with self._lock:
            session = self._sessions.get(pairing_id)
            if session is None:
                raise PairingNotFoundError(pairing_id)
            return session

    def revoke_device(self, device_id: UUID) -> Device:
        return self._registry.revoke(device_id)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("pairing clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)

    def _remove_expired_sessions(self, now: datetime) -> None:
        expired_ids = [
            pairing_id
            for pairing_id, session in self._sessions.items()
            if session.is_expired(now)
        ]
        for pairing_id in expired_ids:
            del self._sessions[pairing_id]
