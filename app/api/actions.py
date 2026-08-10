from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Self, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..actions.errors import (
    ActionError,
    ActionExecutionError,
    ActionNotFoundError,
    ActionUnavailableError,
)
from ..actions.models import ActionDefinition, ActionExecution
from ..actions.service import ActionService
from ..auth import AuthorizedDevice
from .dependencies import require_authorized_device


router = APIRouter(prefix="/api/v1/actions", tags=["actions"])


class ActionResponse(BaseModel):
    """Safe public metadata for one server-defined action."""

    id: str
    label: str

    @classmethod
    def from_definition(cls, action: ActionDefinition) -> Self:
        """Project an internal definition onto its public metadata."""

        return cls(id=action.id, label=action.label)


class ActionListResponse(BaseModel):
    """Ordered public catalog of explicitly registered actions."""

    actions: list[ActionResponse]

    @classmethod
    def from_definitions(cls, actions: Iterable[ActionDefinition]) -> Self:
        """Preserve registry order while removing process details."""

        return cls(
            actions=[ActionResponse.from_definition(action) for action in actions]
        )


class ActionExecutionResponse(BaseModel):
    """Safe result indicating whether an action process was started."""

    action_id: str
    started: bool

    @classmethod
    def from_execution(cls, execution: ActionExecution) -> Self:
        """Project a domain execution result without host process metadata."""

        return cls(
            action_id=execution.action_id,
            started=execution.started,
        )


@router.get(
    "",
    response_model=ActionListResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"}},
)
def list_actions(
    request: Request,
    _device: Annotated[AuthorizedDevice, Depends(require_authorized_device)],
) -> ActionListResponse:
    """Return safe metadata for actions available to an authorized device."""

    service = cast(ActionService, request.app.state.action_service)
    return ActionListResponse.from_definitions(service.list_actions())


@router.post(
    "/{action_id}/execute",
    response_model=ActionExecutionResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_404_NOT_FOUND: {"description": "Action not found."},
        status.HTTP_409_CONFLICT: {"description": "Action is unavailable."},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Action execution failed."
        },
    },
)
def execute_action(
    action_id: str,
    request: Request,
    _device: Annotated[AuthorizedDevice, Depends(require_authorized_device)],
) -> ActionExecutionResponse:
    """Execute a preconfigured action selected only by its registered ID."""

    service = cast(ActionService, request.app.state.action_service)
    try:
        execution = service.execute(action_id)
    except ActionError as exc:
        raise _action_http_exception(exc) from exc
    return ActionExecutionResponse.from_execution(execution)


def _action_http_exception(error: ActionError) -> HTTPException:
    """Map Actions domain failures to sanitized public HTTP errors."""

    if isinstance(error, ActionNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found.",
        )
    if isinstance(error, ActionUnavailableError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Action is unavailable.",
        )
    if isinstance(error, ActionExecutionError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Action execution failed.",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Action execution failed.",
    )


__all__ = [
    "ActionExecutionResponse",
    "ActionListResponse",
    "ActionResponse",
    "router",
]
