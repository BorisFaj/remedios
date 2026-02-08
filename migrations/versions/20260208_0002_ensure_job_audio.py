"""ensure job_audio exists

Revision ID: 20260208_0002
Revises: 20260129_0001
Create Date: 2026-02-08
"""
from alembic import op

revision = "20260208_0002"
down_revision = "20260129_0001"
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade():
    # Ensure job_audio table exists (idempotent).
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE TABLE REMEDIOS.job_audio (
            job_id      NUMBER PRIMARY KEY,
            provider    VARCHAR2(50) NOT NULL,
            bucket_name VARCHAR2(255) NOT NULL,
            namespace   VARCHAR2(255) NOT NULL,
            object_key  VARCHAR2(2000) NOT NULL,
            size_bytes  NUMBER,
            content_type VARCHAR2(255),
            etag        VARCHAR2(255),
            audio_id    VARCHAR2(200),
            created_at  TIMESTAMP DEFAULT SYSTIMESTAMP,
            CONSTRAINT fk_job_audio_job
                FOREIGN KEY (job_id)
                REFERENCES REMEDIOS.jobs(id) ON DELETE CASCADE
          )';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )


def downgrade():
    _exec("DROP TABLE REMEDIOS.job_audio CASCADE CONSTRAINTS")
