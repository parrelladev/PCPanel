import ast
import base64
import inspect
from datetime import datetime, timezone
from uuid import uuid4

from app.auth import DEVICE_TOKEN_BYTES, PAIRING_CODE_DIGITS, TokenService
from app.auth import tokens as tokens_module


def test_generates_non_empty_device_token() -> None:
    token = TokenService.generate_device_token()

    assert isinstance(token, str)
    assert token


def test_device_token_emissions_are_different() -> None:
    assert TokenService.generate_device_token() != TokenService.generate_device_token()


def test_device_token_contains_at_least_256_bits_of_random_input() -> None:
    token = TokenService.generate_device_token()
    padding = "=" * (-len(token) % 4)
    decoded = base64.urlsafe_b64decode(token + padding)

    assert DEVICE_TOKEN_BYTES >= 32
    assert len(decoded) == DEVICE_TOKEN_BYTES


def test_device_token_is_opaque_and_contains_no_device_id_or_timestamp() -> None:
    device_id = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    token = TokenService.generate_device_token()

    assert device_id not in token
    assert timestamp not in token


def test_device_token_hash_is_deterministic() -> None:
    token = "opaque-device-secret"

    assert TokenService.hash_device_token(token) == TokenService.hash_device_token(token)


def test_correct_device_token_verifies() -> None:
    token = TokenService.generate_device_token()
    token_hash = TokenService.hash_device_token(token)

    assert TokenService.verify_device_token(token, token_hash)


def test_incorrect_device_token_does_not_verify() -> None:
    token_hash = TokenService.hash_device_token("correct-token")

    assert not TokenService.verify_device_token("incorrect-token", token_hash)


def test_pairing_code_has_exactly_six_digits() -> None:
    code = TokenService.generate_pairing_code()

    assert PAIRING_CODE_DIGITS == 6
    assert len(code) == PAIRING_CODE_DIGITS
    assert code.isascii()
    assert code.isdigit()


def test_pairing_code_preserves_leading_zeroes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(tokens_module.secrets, "randbelow", lambda upper: 4271)

    assert TokenService.generate_pairing_code() == "004271"


def test_pairing_code_hash_is_deterministic() -> None:
    assert TokenService.hash_pairing_code("004271") == TokenService.hash_pairing_code(
        "004271"
    )


def test_correct_pairing_code_verifies() -> None:
    code_hash = TokenService.hash_pairing_code("483921")

    assert TokenService.verify_pairing_code("483921", code_hash)


def test_incorrect_pairing_code_does_not_verify() -> None:
    code_hash = TokenService.hash_pairing_code("483921")

    assert not TokenService.verify_pairing_code("483922", code_hash)


def test_token_service_retains_no_plaintext_state() -> None:
    service = TokenService()
    token = service.generate_device_token()
    code = service.generate_pairing_code()

    assert not hasattr(service, "__dict__") or vars(service) == {}
    assert token not in repr(service)
    assert code not in repr(service)


def test_secret_generation_does_not_import_or_use_random_module() -> None:
    source = inspect.getsource(tokens_module)
    tree = ast.parse(source)

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }

    assert "random" not in imported_modules
    assert "random" not in imported_from

