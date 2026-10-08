from alembic import op
import sqlalchemy as sa
revision='0006_runtime_completion'; down_revision='0005_world_class'; branch_labels=None; depends_on=None

def upgrade():
    op.add_column('agent_runs',sa.Column('idempotency_key',sa.String(160),nullable=True))
    op.add_column('agent_runs',sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'))
    op.add_column('agent_runs',sa.Column('resume_requested',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('agent_runs',sa.Column('max_tokens',sa.Integer(),nullable=False,server_default='12000'))
    op.add_column('agent_runs',sa.Column('max_tool_calls',sa.Integer(),nullable=False,server_default='12'))
    op.add_column('agent_runs',sa.Column('max_seconds',sa.Integer(),nullable=False,server_default='90'))
    op.add_column('agent_runs',sa.Column('last_error',sa.Text(),nullable=False,server_default=''))
    op.create_index('ix_agent_runs_idempotency_key','agent_runs',['idempotency_key'],unique=True)
    op.add_column('research_runs',sa.Column('updated_at',sa.DateTime(timezone=True),nullable=True))

def downgrade():
    op.drop_column('research_runs','updated_at')
    op.drop_index('ix_agent_runs_idempotency_key',table_name='agent_runs')
    for c in ['last_error','max_seconds','max_tool_calls','max_tokens','resume_requested','attempts','idempotency_key']:
        op.drop_column('agent_runs',c)
