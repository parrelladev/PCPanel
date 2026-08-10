from pathlib import Path

from app.actions import ActionDefinition, ActionExecution
from app.api import actions as actions_api
from app.api.actions import (
    ActionExecutionResponse,
    ActionListResponse,
    ActionResponse,
)


INTERNAL_FIELDS = {
    "executable",
    "arguments",
    "working_directory",
    "path",
    "argv",
    "cwd",
    "command",
    "shell",
    "process_id",
}


def make_action(action_id: str, label: str) -> ActionDefinition:
    return ActionDefinition(
        id=action_id,
        label=label,
        executable=Path(f"C:/server-owned/{action_id}.exe"),
        arguments=("--server-owned",),
        working_directory=Path("C:/server-owned"),
    )


def test_action_response_contains_only_safe_public_metadata() -> None:
    response = ActionResponse.from_definition(make_action("notepad", "Bloco de Notas"))

    assert response.model_dump() == {
        "id": "notepad",
        "label": "Bloco de Notas",
    }
    assert INTERNAL_FIELDS.isdisjoint(response.model_dump())


def test_action_list_response_preserves_service_order_without_definitions() -> None:
    definitions = (
        make_action("notepad", "Bloco de Notas"),
        make_action("calculator", "Calculadora"),
    )

    response = ActionListResponse.from_definitions(definitions)

    assert response.model_dump() == {
        "actions": [
            {"id": "notepad", "label": "Bloco de Notas"},
            {"id": "calculator", "label": "Calculadora"},
        ]
    }
    assert all(
        not isinstance(action, ActionDefinition) for action in response.actions
    )


def test_execution_response_omits_process_and_definition_details() -> None:
    response = ActionExecutionResponse.from_execution(
        ActionExecution(action_id="notepad", started=True, process_id=4321)
    )

    assert response.model_dump() == {"action_id": "notepad", "started": True}
    assert INTERNAL_FIELDS.isdisjoint(response.model_dump())


def test_actions_api_defines_no_process_parameter_request_schema() -> None:
    public_models = {
        name: value
        for name, value in vars(actions_api).items()
        if isinstance(value, type)
        and issubclass(value, ActionResponse.__bases__[0])
        and value is not ActionResponse.__bases__[0]
    }

    assert set(public_models) == {
        "ActionResponse",
        "ActionListResponse",
        "ActionExecutionResponse",
    }
    assert all(
        INTERNAL_FIELDS.isdisjoint(model.model_fields) for model in public_models.values()
    )
