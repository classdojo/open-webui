import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.models.automations import (
    AutomationForm,
    AutomationListResponse,
    AutomationModel,
    AutomationResponse,
    AutomationRunModel,
    AutomationRuns,
    Automations,
)
from open_webui.models.chats import Chats
from open_webui.utils.access_control import has_access, has_permission
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.automations import (
    execute_automation,
    next_n_runs_ns,
    next_run_ns,
    rrule_interval_seconds,
    validate_rrule,
)
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

router = APIRouter()

PAGE_ITEM_COUNT = 30


############################
# Helpers
############################


async def check_automations_permission(request, user):
    if not request.app.state.config.ENABLE_AUTOMATIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.automations', request.app.state.config.USER_PERMISSIONS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )


def _ensure_found(automation):
    if not automation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


async def check_automation_view(automation, user, db):
    """View access: owner, admin, a co-owner, or anyone if the automation is public."""
    _ensure_found(automation)
    if user.role == 'admin' or user.id == automation.user_id:
        return
    grants = automation.access_grants or []
    if await has_access(user.id, 'read', grants, db=db) or await has_access(user.id, 'write', grants, db=db):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.UNAUTHORIZED,
    )


async def check_automation_manage(automation, user, db):
    """Manage access: owner, admin, or a co-owner (a per-user write grant)."""
    _ensure_found(automation)
    if user.role == 'admin' or user.id == automation.user_id:
        return
    grants = automation.access_grants or []
    if await has_access(user.id, 'write', grants, db=db):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=ERROR_MESSAGES.UNAUTHORIZED,
    )


async def check_automation_limits(request, user, rrule_str: str, db, is_create: bool = False):
    """Enforce global automation limits. Admins bypass all checks."""
    if user.role == 'admin':
        return

    # Max count (create only)
    if is_create:
        max_count = request.app.state.config.AUTOMATION_MAX_COUNT
        if max_count:
            max_count = int(max_count)
            if max_count > 0 and await Automations.count_by_user(user.id, db=db) >= max_count:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ERROR_MESSAGES.AUTOMATION_LIMIT_EXCEEDED(max_count),
                )

    # Min interval (create + update)
    min_interval = request.app.state.config.AUTOMATION_MIN_INTERVAL
    if min_interval:
        min_interval = int(min_interval)
        if min_interval > 0:
            interval = rrule_interval_seconds(rrule_str)
            if interval is not None and interval < min_interval:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.AUTOMATION_TOO_FREQUENT(min_interval),
                )


async def enrich_automation(automation: AutomationModel, db: AsyncSession, tz: str = None) -> AutomationResponse:
    """Full enrichment for single-item views (includes next_runs computation)."""
    last_run = await AutomationRuns.get_latest(automation.id, db=db)
    return AutomationResponse(
        **automation.model_dump(),
        last_run=last_run,
        next_runs=next_n_runs_ns(automation.data['rrule'], tz=tz),
    )


############################
# GetAutomationItems (paginated)
############################


@router.get('/list')
async def get_automation_items(
    request: Request,
    query: Optional[str] = None,
    status: Optional[str] = None,
    page: Optional[int] = 1,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await check_automations_permission(request, user)
    limit = PAGE_ITEM_COUNT
    page = max(1, page)
    skip = (page - 1) * limit

    result = await Automations.search_automations(
        user_id=user.id,
        query=query,
        status=status,
        skip=skip,
        limit=limit,
        db=db,
    )

    # Batch-fetch latest runs in a single query instead of N+1
    ids = [item.id for item in result.items]
    latest_runs = await AutomationRuns.get_latest_batch(ids, db=db) if ids else {}

    return {
        'items': [
            AutomationResponse(
                **item.model_dump(),
                last_run=latest_runs.get(item.id),
            )
            for item in result.items
        ],
        'total': result.total,
    }


############################
# CreateNewAutomation
############################


@router.post('/create', response_model=AutomationResponse)
async def create_new_automation(
    request: Request,
    form_data: AutomationForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await check_automations_permission(request, user)
    try:
        validate_rrule(form_data.data.rrule, tz=user.timezone)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await check_automation_limits(request, user, form_data.data.rrule, db, is_create=True)

    tz = user.timezone
    automation = await Automations.insert(user.id, form_data, next_run_ns(form_data.data.rrule, tz=tz), db=db)
    return await enrich_automation(automation, db, tz=tz)


############################
# GetAutomationById
############################


@router.get('/{id}', response_model=AutomationResponse)
async def get_automation_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await check_automations_permission(request, user)
    automation = await Automations.get_by_id(id, db=db)
    await check_automation_view(automation, user, db)
    return await enrich_automation(automation, db, tz=user.timezone)


############################
# UpdateAutomationById
############################


@router.post('/{id}/update', response_model=AutomationResponse)
async def update_automation_by_id(
    request: Request,
    id: str,
    form_data: AutomationForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await check_automations_permission(request, user)
    automation = await Automations.get_by_id(id, db=db)
    await check_automation_manage(automation, user, db)

    try:
        validate_rrule(form_data.data.rrule, tz=user.timezone)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    await check_automation_limits(request, user, form_data.data.rrule, db, is_create=False)

    tz = user.timezone
    updated = await Automations.update_by_id(id, form_data, next_run_ns(form_data.data.rrule, tz=tz), db=db)
    return await enrich_automation(updated, db, tz=tz)


############################
# ToggleAutomationById
############################


@router.post('/{id}/toggle', response_model=AutomationResponse)
async def toggle_automation_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await check_automations_permission(request, user)
    automation = await Automations.get_by_id(id, db=db)
    await check_automation_manage(automation, user, db)
    toggled = await Automations.toggle(id, next_run_ns(automation.data['rrule'], tz=user.timezone), db=db)
    return await enrich_automation(toggled, db, tz=user.timezone)


############################
# RunAutomationById
############################


@router.post('/{id}/run')
async def run_automation_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await check_automations_permission(request, user)
    automation = await Automations.get_by_id(id, db=db)
    await check_automation_manage(automation, user, db)
    # classdojo: a manual "Run now" executes as the triggering user (owner or
    # co-owner) with their own OIDC; scheduled runs use the owner (see
    # execute_automation / scheduler_worker_loop).
    asyncio.create_task(execute_automation(request.app, automation, run_as_user_id=user.id))
    return await enrich_automation(automation, db, tz=user.timezone)


############################
# DeleteAutomationById
############################


@router.delete('/{id}/delete')
async def delete_automation_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await check_automations_permission(request, user)
    automation = await Automations.get_by_id(id, db=db)
    await check_automation_manage(automation, user, db)
    await AutomationRuns.delete_by_automation(id, db=db)
    return await Automations.delete(id, db=db)


############################
# GetAutomationRuns
############################


@router.get('/{id}/runs', response_model=list[AutomationRunModel])
async def get_automation_runs(
    request: Request,
    id: str,
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await check_automations_permission(request, user)
    automation = await Automations.get_by_id(id, db=db)
    await check_automation_view(automation, user, db)
    return await AutomationRuns.get_by_automation(id, skip=skip, limit=limit, db=db)


############################
# GetAutomationChat (view-through-automation)
############################


@router.get('/{id}/chat')
async def get_automation_chat(
    request: Request,
    id: str,
    chat_id: Optional[str] = None,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Return one of the automation's generated chats (a specific run's chat when
    chat_id is given, otherwise the latest) to anyone who can view the automation.
    The chat is owned by whoever ran it and has no access control of its own, so
    co-owners (and viewers of public automations) reach it through the
    automation's permissions rather than chat ownership. Read-only for the UI."""
    await check_automations_permission(request, user)
    automation = await Automations.get_by_id(id, db=db)
    await check_automation_view(automation, user, db)

    if chat_id:
        # Only chats produced by a run of *this* automation are viewable here.
        run = await AutomationRuns.get_by_chat_id(id, chat_id, db=db)
        target_chat_id = run.chat_id if run else None
    else:
        latest = await AutomationRuns.get_latest(id, db=db)
        target_chat_id = latest.chat_id if latest else None

    if not target_chat_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    chat = await Chats.get_chat_by_id(target_chat_id, db=db)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return chat
