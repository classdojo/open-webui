"""classdojo: add access_grants to automation

Revision ID: c1a55d0a7e10
Revises: 461111b60977
Create Date: 2026-06-29
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1a55d0a7e10'
down_revision: Union[str, None] = '461111b60977'
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name, column_name):
    return any(col['name'] == column_name for col in inspector.get_columns(table_name))


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'automation' in inspector.get_table_names() and not _column_exists(inspector, 'automation', 'access_grants'):
        # classdojo: ownership levels for an automation.
        #   None / []                                  -> private (owner only)
        #   [{principal_type:user, principal_id:'*', permission:read}]  -> public
        #   [{principal_type:user, principal_id:<id>, permission:write}] -> co-owner
        op.add_column('automation', sa.Column('access_grants', sa.JSON(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'automation' in inspector.get_table_names() and _column_exists(inspector, 'automation', 'access_grants'):
        op.drop_column('automation', 'access_grants')
