"""Added name field to endpoint model

Revision ID: 75edfd3f9daf
Revises: b43d478a902d
Create Date: 2025-03-22 13:30:55.401258

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '75edfd3f9daf'
down_revision = 'b43d478a902d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('endpoints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('name', sa.String(length=255), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('endpoints', schema=None) as batch_op:
        batch_op.drop_column('name')

    # ### end Alembic commands ###
