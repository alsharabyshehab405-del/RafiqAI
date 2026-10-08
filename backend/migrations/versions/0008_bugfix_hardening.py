from alembic import op
import sqlalchemy as sa

revision='0008_bugfix_hardening'
down_revision='0007_automation_execution'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('agent_runs', sa.Column('worker_id', sa.String(120), nullable=True))
    op.add_column('agent_runs', sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('agent_runs', sa.Column('attempt_id', sa.String(80), nullable=True))
    op.add_column('agent_runs', sa.Column('tool_calls_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('agent_runs', sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('agent_runs', sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('agent_runs', sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('agent_steps', sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('agent_steps', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('agent_steps', sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('agent_steps', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('automation_executions', sa.Column('retry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('automation_executions', sa.Column('failure_reason', sa.Text(), nullable=False, server_default=''))
    op.create_index('ix_agent_runs_lease_until','agent_runs',['lease_until'])
    op.create_index('ix_agent_runs_worker_id','agent_runs',['worker_id'])
    op.create_index('ix_agent_steps_updated_at','agent_steps',['updated_at'])

def downgrade():
    op.drop_index('ix_agent_steps_updated_at', table_name='agent_steps')
    op.drop_index('ix_agent_runs_worker_id', table_name='agent_runs')
    op.drop_index('ix_agent_runs_lease_until', table_name='agent_runs')
    for table, col in [('automation_executions','failure_reason'),('automation_executions','retry_at'),('agent_steps','updated_at'),('agent_steps','finished_at'),('agent_steps','started_at'),('agent_steps','attempts'),('agent_runs','total_tokens'),('agent_runs','output_tokens'),('agent_runs','input_tokens'),('agent_runs','tool_calls_used'),('agent_runs','attempt_id'),('agent_runs','lease_until'),('agent_runs','worker_id')]:
        op.drop_column(table,col)
