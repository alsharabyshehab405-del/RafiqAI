from alembic import op
import sqlalchemy as sa
revision="0003_global_commercial"
down_revision="0002_global_production"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("users",sa.Column("memory_enabled",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column("users",sa.Column("analytics_enabled",sa.Boolean(),nullable=False,server_default=sa.true()))
    op.add_column("users",sa.Column("is_admin",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column("users",sa.Column("disabled_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("refresh_tokens",sa.Column("device_name",sa.String(120),nullable=False,server_default="Android"))
    op.add_column("conversations",sa.Column("pinned",sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column("conversations",sa.Column("summary",sa.Text(),nullable=False,server_default=""))
    for n,t in [("input_tokens",sa.Integer()),("output_tokens",sa.Integer()),("model",sa.String(120))]: op.add_column("messages",sa.Column(n,t,nullable=False,server_default="0" if "tokens" in n else ""))
    op.add_column("tasks",sa.Column("priority",sa.String(20),nullable=False,server_default="normal"))
    op.add_column("tasks",sa.Column("recurrence",sa.String(100),nullable=True))
    op.add_column("tasks",sa.Column("reminded_at",sa.DateTime(timezone=True),nullable=True))
    op.create_table("memories",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("key",sa.String(120),nullable=False),sa.Column("value",sa.Text(),nullable=False),sa.Column("category",sa.String(40),nullable=False,server_default="preference"),sa.Column("source",sa.String(40),nullable=False,server_default="user"),sa.Column("sensitive",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")),sa.UniqueConstraint("user_id","key",name="uq_memory_user_key"))
    op.create_index("ix_memories_user_id","memories",["user_id"]);op.create_index("ix_memories_updated_at","memories",["updated_at"])
    op.create_table("subscriptions",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("product_id",sa.String(160),nullable=False),sa.Column("plan",sa.String(30),nullable=False,server_default="free"),sa.Column("purchase_token_hash",sa.String(64),nullable=False,unique=True),sa.Column("state",sa.String(50),nullable=False,server_default="pending"),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=True),sa.Column("auto_renew",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("grace_period",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")),sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"))
    op.create_index("ix_subscriptions_user_id","subscriptions",["user_id"]);op.create_index("ix_subscriptions_purchase_token_hash","subscriptions",["purchase_token_hash"]);op.create_index("ix_subscriptions_expires_at","subscriptions",["expires_at"])
    op.create_table("file_assets",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("conversation_id",sa.Integer(),sa.ForeignKey("conversations.id",ondelete="SET NULL"),nullable=True),sa.Column("object_key",sa.String(500),nullable=False,unique=True),sa.Column("filename",sa.String(255),nullable=False),sa.Column("content_type",sa.String(120),nullable=False),sa.Column("size_bytes",sa.BigInteger(),nullable=False),sa.Column("sha256",sa.String(64),nullable=False),sa.Column("extracted_text",sa.Text(),nullable=False,server_default=""),sa.Column("status",sa.String(30),nullable=False,server_default="uploaded"),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_file_assets_user_id","file_assets",["user_id"]);op.create_index("ix_file_assets_conversation_id","file_assets",["conversation_id"]);op.create_index("ix_file_assets_sha256","file_assets",["sha256"])
    op.create_table("device_tokens",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("token",sa.String(4096),nullable=False,unique=True),sa.Column("platform",sa.String(30),nullable=False,server_default="android"),sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_device_tokens_user_id","device_tokens",["user_id"])
    op.create_table("analytics_events",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL"),nullable=True),sa.Column("event_name",sa.String(100),nullable=False),sa.Column("properties_json",sa.Text(),nullable=False,server_default="{}"),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_analytics_events_user_id","analytics_events",["user_id"]);op.create_index("ix_analytics_events_event_name","analytics_events",["event_name"]);op.create_index("ix_analytics_events_created_at","analytics_events",["created_at"]);op.create_index("ix_events_name_created","analytics_events",["event_name","created_at"])
    op.create_table("audit_logs",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("actor_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL"),nullable=True),sa.Column("action",sa.String(120),nullable=False),sa.Column("target_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL"),nullable=True),sa.Column("metadata_json",sa.Text(),nullable=False,server_default="{}"),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_audit_logs_actor_user_id","audit_logs",["actor_user_id"]);op.create_index("ix_audit_logs_target_user_id","audit_logs",["target_user_id"]);op.create_index("ix_audit_logs_action","audit_logs",["action"]);op.create_index("ix_audit_logs_created_at","audit_logs",["created_at"])

def downgrade():
    for table in ["audit_logs","analytics_events","device_tokens","file_assets","subscriptions","memories"]: op.drop_table(table)
    for table,cols in [("tasks",["reminded_at","recurrence","priority"]),("messages",["model","output_tokens","input_tokens"]),("conversations",["summary","pinned"]),("refresh_tokens",["device_name"]),("users",["disabled_at","is_admin","analytics_enabled","memory_enabled"])]:
        for c in cols: op.drop_column(table,c)
