from alembic import op
import sqlalchemy as sa
revision = "0002_global_production"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("display_name", sa.String(120), nullable=False, server_default=""))
    op.add_column("users", sa.Column("locale", sa.String(20), nullable=False, server_default="ar"))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_users_updated_at", "users", ["updated_at"])
    op.add_column("tasks", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_tasks_due_at", "tasks", ["due_at"])

def downgrade():
    op.drop_index("ix_tasks_due_at", table_name="tasks")
    op.drop_column("tasks", "due_at")
    op.drop_index("ix_users_updated_at", table_name="users")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "locale")
    op.drop_column("users", "display_name")
