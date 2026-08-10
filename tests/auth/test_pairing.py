from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from threading import Barrier, Lock

import pytest

from app.auth import (
    DeviceRegistry,
    PairingAlreadyConsumedError,
    PairingAttemptsExceededError,
    PairingCapacityError,
    PairingExpiredError,
    PairingInvalidCodeError,
    PairingService,
    PairingStatus,
)


NOW = datetime(2026, 8, 10, 16, 0, tzinfo=timezone.utc)


class MutableClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def service(
    *,
    clock: MutableClock | None = None,
    max_attempts: int = 5,
    max_pending_pairings: int = 10,
) -> tuple[PairingService, DeviceRegistry]:
    registry = DeviceRegistry(clock=clock or MutableClock())
    pairing = PairingService(
        registry,
        clock=clock or MutableClock(),
        max_attempts=max_attempts,
        max_pending_pairings=max_pending_pairings,
    )
    return pairing, registry


def test_start_creates_pending_session_with_only_code_hash() -> None:
    pairing, registry = service()

    challenge = pairing.start_pairing("  Galaxy S24  ")
    session = pairing.get_session(challenge.pairing_id)

    assert session.status is PairingStatus.PENDING
    assert session.device_name == "Galaxy S24"
    assert session.code_hash
    assert session.code_hash != challenge.code
    assert "code" not in {field.name for field in fields(session)}
    assert registry.list_devices() == ()


@pytest.mark.parametrize("name", ["", "   ", "Phone\nname"])
def test_start_rejects_invalid_device_name(name: str) -> None:
    pairing, _ = service()

    with pytest.raises(ValueError):
        pairing.start_pairing(name)


def test_correct_code_completes_and_only_then_creates_device() -> None:
    pairing, registry = service()
    challenge = pairing.start_pairing("Phone")
    assert registry.list_devices() == ()

    issued = pairing.complete_pairing(challenge.pairing_id, challenge.code)

    assert issued.token
    assert registry.authenticate(issued.token).id == issued.device_id
    assert len(registry.list_devices()) == 1
    assert pairing.get_session(challenge.pairing_id).status is PairingStatus.CONSUMED


def test_wrong_code_decrements_attempts_without_creating_device() -> None:
    pairing, registry = service(max_attempts=3)
    challenge = pairing.start_pairing("Phone")
    wrong_code = "000000" if challenge.code != "000000" else "000001"

    with pytest.raises(PairingInvalidCodeError):
        pairing.complete_pairing(challenge.pairing_id, wrong_code)

    session = pairing.get_session(challenge.pairing_id)
    assert session.attempts_remaining == 2
    assert session.status is PairingStatus.PENDING
    assert registry.list_devices() == ()


def test_last_wrong_attempt_locks_and_correct_code_cannot_recover() -> None:
    pairing, registry = service(max_attempts=1)
    challenge = pairing.start_pairing("Phone")
    wrong_code = "000000" if challenge.code != "000000" else "000001"

    with pytest.raises(PairingAttemptsExceededError):
        pairing.complete_pairing(challenge.pairing_id, wrong_code)

    session = pairing.get_session(challenge.pairing_id)
    assert session.attempts_remaining == 0
    assert session.status is PairingStatus.LOCKED
    with pytest.raises(PairingAttemptsExceededError):
        pairing.complete_pairing(challenge.pairing_id, challenge.code)
    assert registry.list_devices() == ()


def test_ttl_accepts_before_expiration_without_sleep() -> None:
    clock = MutableClock()
    registry = DeviceRegistry(clock=clock)
    pairing = PairingService(registry, ttl=timedelta(minutes=5), clock=clock)
    challenge = pairing.start_pairing("Phone")
    clock.now = challenge.expires_at - timedelta(microseconds=1)

    issued = pairing.complete_pairing(challenge.pairing_id, challenge.code)

    assert registry.authenticate(issued.token).id == issued.device_id


def test_expired_pairing_fails_without_creating_device_or_sleep() -> None:
    clock = MutableClock()
    registry = DeviceRegistry(clock=clock)
    pairing = PairingService(registry, ttl=timedelta(minutes=5), clock=clock)
    challenge = pairing.start_pairing("Phone")
    clock.now = challenge.expires_at

    with pytest.raises(PairingExpiredError):
        pairing.complete_pairing(challenge.pairing_id, challenge.code)

    assert registry.list_devices() == ()


def test_successful_pairing_is_single_use() -> None:
    pairing, registry = service()
    challenge = pairing.start_pairing("Phone")
    pairing.complete_pairing(challenge.pairing_id, challenge.code)

    with pytest.raises(PairingAlreadyConsumedError):
        pairing.complete_pairing(challenge.pairing_id, challenge.code)

    assert len(registry.list_devices()) == 1


def test_two_sessions_issue_independent_devices_and_tokens() -> None:
    pairing, registry = service()
    first = pairing.start_pairing("Phone")
    second = pairing.start_pairing("Tablet")

    first_issued = pairing.complete_pairing(first.pairing_id, first.code)
    second_issued = pairing.complete_pairing(second.pairing_id, second.code)

    assert first.pairing_id != second.pairing_id
    assert first_issued.device_id != second_issued.device_id
    assert first_issued.token != second_issued.token
    assert len(registry.list_devices()) == 2


def test_pending_pairing_capacity_is_enforced() -> None:
    pairing, _ = service(max_pending_pairings=2)
    pairing.start_pairing("Phone")
    pairing.start_pairing("Tablet")

    with pytest.raises(PairingCapacityError):
        pairing.start_pairing("Laptop")


def test_expired_sessions_release_capacity_lazily() -> None:
    clock = MutableClock()
    registry = DeviceRegistry(clock=clock)
    pairing = PairingService(
        registry,
        ttl=timedelta(minutes=5),
        max_pending_pairings=1,
        clock=clock,
    )
    first = pairing.start_pairing("Phone")
    clock.now = first.expires_at

    second = pairing.start_pairing("Tablet")

    assert second.pairing_id != first.pairing_id


def test_concurrent_starts_never_exceed_capacity() -> None:
    workers = 12
    capacity = 4
    barrier = Barrier(workers)
    pairing, _ = service(max_pending_pairings=capacity)

    def start(index: int) -> bool:
        barrier.wait()
        try:
            pairing.start_pairing(f"Phone {index}")
        except PairingCapacityError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(start, range(workers)))

    assert sum(results) == capacity


def test_concurrent_completion_issues_exactly_one_token_and_device() -> None:
    workers = 2
    barrier = Barrier(workers)
    pairing, registry = service()
    challenge = pairing.start_pairing("Phone")
    results: list[object] = []
    results_lock = Lock()

    def complete() -> None:
        barrier.wait()
        try:
            result: object = pairing.complete_pairing(
                challenge.pairing_id,
                challenge.code,
            )
        except PairingAlreadyConsumedError as error:
            result = error
        with results_lock:
            results.append(result)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(lambda _: complete(), range(workers)))

    successes = [result for result in results if not isinstance(result, Exception)]
    failures = [result for result in results if isinstance(result, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], PairingAlreadyConsumedError)
    assert len(registry.list_devices()) == 1
    assert successes[0].device_id == registry.list_devices()[0].id
    assert successes[0].token
