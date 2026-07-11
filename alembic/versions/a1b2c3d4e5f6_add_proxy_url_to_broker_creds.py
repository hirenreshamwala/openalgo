"""add proxy_url to user_broker_credentials

Revision ID: a1b2c3d4e5f6
Revises: 6288abd1a363
Create Date: 2026-07-11 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6288abd1a363'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Per-user outbound proxy URL (Fernet-encrypted). Nullable so existing rows
    # and single-tenant deployments are unaffected.
    with op.batch_alter_table('user_broker_credentials') as batch_op:
        batch_op.add_column(sa.Column('proxy_url_enc', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('user_broker_credentials') as batch_op:
        batch_op.drop_column('proxy_url_enc')
