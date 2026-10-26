"""Permitir recomendaciones trazables a un escenario sin crear ingestas vigentes."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recommendations") as batch:
        batch.alter_column("data_run_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("scenario", sa.JSON(none_as_null=True)))
        batch.create_check_constraint(
            "ck_recommendations_data_origin",
            "(data_run_id IS NOT NULL AND scenario IS NULL) OR "
            "(data_run_id IS NULL AND scenario IS NOT NULL)",
        )


def downgrade() -> None:
    count = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM recommendations WHERE data_run_id IS NULL"))
        .scalar_one()
    )
    if count:
        raise ValueError("No se puede volver a 0001: hay recomendaciones de escenarios")
    with op.batch_alter_table("recommendations") as batch:
        batch.drop_constraint("ck_recommendations_data_origin", type_="check")
        batch.drop_column("scenario")
        batch.alter_column("data_run_id", existing_type=sa.Integer(), nullable=False)
