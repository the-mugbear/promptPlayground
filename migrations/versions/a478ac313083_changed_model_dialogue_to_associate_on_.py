"""Changed model_Dialogue to associate on endpoint ID instead of name

Revision ID: a478ac313083
Revises: 8da6edba5a22
Create Date: 2025-04-06 00:08:40.448503

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a478ac313083'
down_revision = '8da6edba5a22'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dialogues', schema=None) as batch_op:
        batch_op.add_column(sa.Column('endpoint_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(None, 'endpoints', ['endpoint_id'], ['id'])
        batch_op.drop_column('target')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('dialogues', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target', sa.TEXT(), nullable=False))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('endpoint_id')

    # ### end Alembic commands ###
