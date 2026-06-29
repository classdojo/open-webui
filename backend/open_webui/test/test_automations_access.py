"""classdojo: access-control contract for shared automations.

Locks the grant semantics that routers/automations.py relies on:
  - check_automation_view  uses  has_access(read) OR has_access(write)
  - check_automation_manage uses has_access(write)
and the three ownership levels the UI produces:
  - private  -> [] / None                         (owner only)
  - public   -> '*' read grant                    (everyone can view, not manage)
  - co-owner -> per-user write grant              (view + manage)
  - viewer   -> per-user read grant               (view, not manage)

Pure unit tests over has_access; user_group_ids is passed explicitly so no DB
lookup is needed. Run inside the built image:
    python -m pytest open_webui/test/test_automations_access.py -q
"""

import asyncio

from open_webui.utils.access_control import has_access

NO_GROUPS: set = set()

PRIVATE: list = []
PUBLIC = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]


def _coowner(uid):
    return [{"principal_type": "user", "principal_id": uid, "permission": "write"}]


def _viewer(uid):
    return [{"principal_type": "user", "principal_id": uid, "permission": "read"}]


def _can_view(uid, grants):
    # mirrors check_automation_view (non-owner branch)
    return asyncio.run(has_access(uid, "read", grants, user_group_ids=NO_GROUPS)) or asyncio.run(
        has_access(uid, "write", grants, user_group_ids=NO_GROUPS)
    )


def _can_manage(uid, grants):
    # mirrors check_automation_manage (non-owner branch)
    return asyncio.run(has_access(uid, "write", grants, user_group_ids=NO_GROUPS))


def test_private_denies_non_owner():
    assert _can_view("u1", PRIVATE) is False
    assert _can_manage("u1", PRIVATE) is False


def test_private_none_grants_denies():
    assert _can_view("u1", None or []) is False


def test_public_is_view_only_for_everyone():
    assert _can_view("anyone", PUBLIC) is True
    assert _can_manage("anyone", PUBLIC) is False


def test_coowner_can_view_and_manage():
    g = _coowner("u2")
    assert _can_view("u2", g) is True
    assert _can_manage("u2", g) is True


def test_coowner_grant_does_not_leak_to_others():
    g = _coowner("u2")
    assert _can_view("u3", g) is False
    assert _can_manage("u3", g) is False


def test_viewer_can_view_but_not_manage():
    g = _viewer("u2")
    assert _can_view("u2", g) is True
    assert _can_manage("u2", g) is False


def test_public_plus_coowner_combination():
    grants = PUBLIC + _coowner("u2")
    # public viewer: view only
    assert _can_view("rando", grants) is True
    assert _can_manage("rando", grants) is False
    # co-owner: view + manage
    assert _can_view("u2", grants) is True
    assert _can_manage("u2", grants) is True
