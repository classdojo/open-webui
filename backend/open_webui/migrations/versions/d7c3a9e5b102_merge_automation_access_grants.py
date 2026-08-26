"""merge ClassDojo automation sharing with normalized access grants

Revision ID: d7c3a9e5b102
Revises: d4c1a8e37b62, c1a55d0a7e10
Create Date: 2026-08-26
"""

import json
import time
import uuid

import sqlalchemy as sa
from alembic import op

revision = 'd7c3a9e5b102'
down_revision = ('d4c1a8e37b62', 'c1a55d0a7e10')
branch_labels = None
depends_on = None


def _tables(conn):
    metadata = sa.MetaData()
    return (
        sa.Table('automation', metadata, autoload_with=conn),
        sa.Table('access_grant', metadata, autoload_with=conn),
    )


def _normalized(grants):
    if isinstance(grants, str):
        try:
            grants = json.loads(grants)
        except ValueError:
            return []
    if not isinstance(grants, list):
        return []

    normalized = set()
    for grant in grants:
        if not isinstance(grant, dict):
            continue
        principal_type = grant.get('principal_type')
        principal_id = grant.get('principal_id')
        permission = grant.get('permission')
        if principal_type not in {'user', 'group', 'anyone'} or not isinstance(principal_id, str):
            continue
        if permission not in {'read', 'write'}:
            continue
        normalized.add((principal_type, principal_id, permission))
        if permission == 'write':
            normalized.add((principal_type, principal_id, 'read'))
    return sorted(normalized)


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not {'automation', 'access_grant'}.issubset(inspector.get_table_names()):
        return
    if 'access_grants' not in {column['name'] for column in inspector.get_columns('automation')}:
        return

    automation, access_grant = _tables(conn)
    existing = set(
        conn.execute(
            sa.select(
                access_grant.c.resource_id,
                access_grant.c.principal_type,
                access_grant.c.principal_id,
                access_grant.c.permission,
            ).where(access_grant.c.resource_type == 'automation')
        ).all()
    )
    now = int(time.time())

    for automation_id, grants in conn.execute(
        sa.select(automation.c.id, automation.c.access_grants).where(automation.c.access_grants.is_not(None))
    ):
        for principal_type, principal_id, permission in _normalized(grants):
            key = (automation_id, principal_type, principal_id, permission)
            if key in existing:
                continue
            conn.execute(
                access_grant.insert().values(
                    id=str(uuid.uuid4()),
                    resource_type='automation',
                    resource_id=automation_id,
                    principal_type=principal_type,
                    principal_id=principal_id,
                    permission=permission,
                    created_at=now,
                )
            )
            existing.add(key)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not {'automation', 'access_grant'}.issubset(inspector.get_table_names()):
        return
    if 'access_grants' not in {column['name'] for column in inspector.get_columns('automation')}:
        return

    automation, access_grant = _tables(conn)
    grants_by_automation = {}
    rows = conn.execute(
        sa.select(
            access_grant.c.resource_id,
            access_grant.c.principal_type,
            access_grant.c.principal_id,
            access_grant.c.permission,
        ).where(access_grant.c.resource_type == 'automation')
    )
    for automation_id, principal_type, principal_id, permission in rows:
        grants_by_automation.setdefault(automation_id, []).append(
            {
                'principal_type': principal_type,
                'principal_id': principal_id,
                'permission': permission,
            }
        )

    for automation_id, grants in grants_by_automation.items():
        conn.execute(
            automation.update().where(automation.c.id == automation_id).values(access_grants=grants)
        )
    conn.execute(access_grant.delete().where(access_grant.c.resource_type == 'automation'))
