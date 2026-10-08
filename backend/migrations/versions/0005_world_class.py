from alembic import op
import sqlalchemy as sa
revision='0005_world_class';down_revision='0004_nextgen_platform';branch_labels=None;depends_on=None
def upgrade():
    op.add_column('agent_runs',sa.Column('checkpoint_json',sa.Text(),nullable=False,server_default='{}'))
    op.add_column('agent_runs',sa.Column('cancel_requested',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('research_runs',sa.Column('pipeline_json',sa.Text(),nullable=False,server_default='[]'))
    op.add_column('research_runs',sa.Column('confidence',sa.Float(),nullable=False,server_default='0'))
    op.add_column('vector_chunks',sa.Column('source_page',sa.Integer(),nullable=True))
    op.add_column('vector_chunks',sa.Column('source_section',sa.String(500),nullable=True))
def downgrade():
    for t,c in [('vector_chunks','source_section'),('vector_chunks','source_page'),('research_runs','confidence'),('research_runs','pipeline_json'),('agent_runs','cancel_requested'),('agent_runs','checkpoint_json')]: op.drop_column(t,c)
