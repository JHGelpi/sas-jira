<%
""" 
This is a template for generating migration scripts using Alembic. 
"""
%>
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'your_revision_id'
down_revision = 'your_down_revision_id'
branch_labels = None
depends_on = None


def upgrade():
    # Commands to upgrade the database schema
    op.create_table(
        'project_completion_forecast',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('project_issue_id', sa.String(length=255), nullable=False),
        sa.Column('confidence_interval_80', sa.String(length=255), nullable=False),
        sa.Column('midpoint', sa.Float, nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())
    )


def downgrade():
    # Commands to downgrade the database schema
    op.drop_table('project_completion_forecast')