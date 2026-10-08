from alembic import op
import sqlalchemy as sa
revision='0007_automation_execution'; down_revision='0006_runtime_completion'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('automation_executions',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('automation_id',sa.Integer(),sa.ForeignKey('automations.id',ondelete='CASCADE'),nullable=False),sa.Column('status',sa.String(30),nullable=False,server_default='queued'),sa.Column('idempotency_key',sa.String(180),nullable=False,unique=True),sa.Column('result_json',sa.Text(),nullable=False,server_default='{}'),sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('finished_at',sa.DateTime(timezone=True),nullable=True));op.create_index('ix_automation_executions_automation_id','automation_executions',['automation_id']);op.create_index('ix_automation_executions_status','automation_executions',['status'])
def downgrade(): op.drop_table('automation_executions')
