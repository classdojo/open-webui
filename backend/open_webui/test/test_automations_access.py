from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from open_webui.models.access_grants import AccessGrants
from open_webui.routers.automations import check_automation_manage, check_automation_view


@pytest.mark.asyncio
async def test_shared_automation_access_contract(monkeypatch):
    grants = set()

    async def has_access(user_id, resource_type, resource_id, permission, db=None):
        return (user_id, permission) in grants

    monkeypatch.setattr(AccessGrants, 'has_access', has_access)
    automation = SimpleNamespace(id='automation', user_id='owner')
    user = SimpleNamespace(id='shared', role='user')

    with pytest.raises(HTTPException):
        await check_automation_view(automation, user, None)

    grants.add(('shared', 'read'))
    await check_automation_view(automation, user, None)
    with pytest.raises(HTTPException):
        await check_automation_manage(automation, user, None)

    grants.add(('shared', 'write'))
    await check_automation_manage(automation, user, None)
