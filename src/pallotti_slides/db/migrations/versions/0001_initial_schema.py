"""initial schema (songs, aliases, masses, mass_songs)

Revision ID: 0001
Revises:
Create Date: 2026-10-24 22:53:57.210180
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "masses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "season",
            sa.Enum(
                "advent",
                "christmas",
                "lent",
                "paschal_triduum",
                "easter",
                "ordinary_time",
                name="liturgicalseason",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "eucharistic_prayer",
            sa.Enum("I", "II", "III", "IV", name="eucharisticprayer", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("pptx_path", sa.String(length=500), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("masses", schema=None) as batch_op:
        batch_op.create_index("ix_masses_date", ["date"], unique=False)

    op.create_table(
        "songs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("title_search", sa.String(length=200), nullable=False),
        sa.Column("first_line_search", sa.String(length=300), nullable=False),
        sa.Column("artist", sa.String(length=200), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "letras_mus",
                "cifra_club",
                "manual",
                "other",
                name="songsource",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("original_lyrics", sa.Text(), nullable=False),
        sa.Column("structure", sa.JSON(), nullable=False),
        sa.Column("usual_moments", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("reviewed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url"),
    )
    with op.batch_alter_table("songs", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_songs_first_line_search"), ["first_line_search"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_songs_title_search"), ["title_search"], unique=False)

    op.create_table(
        "mass_songs",
        sa.Column("mass_id", sa.Integer(), nullable=False),
        sa.Column(
            "moment",
            sa.Enum(
                "mantra",
                "entrance",
                "penitential_act",
                "gloria",
                "acclamation",
                "offertory",
                "communion",
                "post_communion",
                "recessional",
                name="songmoment",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("song_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["mass_id"], ["masses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("mass_id", "moment"),
    )
    op.create_table(
        "song_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("song_id", sa.Integer(), nullable=False),
        sa.Column("alias_search", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["song_id"], ["songs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alias_search"),
    )


def downgrade() -> None:
    op.drop_table("song_aliases")
    op.drop_table("mass_songs")
    with op.batch_alter_table("songs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_songs_title_search"))
        batch_op.drop_index(batch_op.f("ix_songs_first_line_search"))

    op.drop_table("songs")
    with op.batch_alter_table("masses", schema=None) as batch_op:
        batch_op.drop_index("ix_masses_date")

    op.drop_table("masses")
