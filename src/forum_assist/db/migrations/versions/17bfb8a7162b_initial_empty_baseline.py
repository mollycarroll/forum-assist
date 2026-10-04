"""initial empty baseline

Revision ID: 17bfb8a7162b
Revises:
Create Date: 2026-10-04 05:42:29.213206

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "17bfb8a7162b"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
