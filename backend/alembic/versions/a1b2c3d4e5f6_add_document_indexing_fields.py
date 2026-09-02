"""add document indexing fields

Revision ID: a1b2c3d4e5f6
Revises: 034e07cc2579
Create Date: 2026-07-12 13:00:00.000000

Adds index_status, chunk_count, and chunks_total to the documents table
to support progress tracking, resume-from-checkpoint, and UI status display.
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "034e07cc2579"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "index_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "documents",
        sa.Column("chunk_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("chunks_total", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "chunks_total")
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "index_status")
