"""init schema

Revision ID: 20260129_0001
Revises: 
Create Date: 2026-01-29
"""
from alembic import op


revision = "20260129_0001"
down_revision = None
branch_labels = None
depends_on = None


def _exec(sql: str) -> None:
    op.execute(sql)


def upgrade():
    # Users
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE TABLE REMEDIOS.users (
            id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            phone       VARCHAR2(20) UNIQUE NOT NULL,
            name        VARCHAR2(255),
            created_at  TIMESTAMP DEFAULT SYSTIMESTAMP
          )';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )

    # Messages
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE TABLE REMEDIOS.messages (
            id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            sender_phone    VARCHAR2(20),
            receiver_phone  VARCHAR2(20),
            message_id      VARCHAR2(200),
            number_id       VARCHAR2(200),
            message         CLOB NOT NULL,
            message_type    VARCHAR2(50) DEFAULT ''text'' NOT NULL,
            created_at      TIMESTAMP DEFAULT SYSTIMESTAMP,
            CONSTRAINT fk_sender FOREIGN KEY (sender_phone)
                REFERENCES REMEDIOS.users(phone) ON DELETE SET NULL,
            CONSTRAINT fk_receiver FOREIGN KEY (receiver_phone)
                REFERENCES REMEDIOS.users(phone) ON DELETE SET NULL
          )';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )

    # Jobs
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE TABLE REMEDIOS.jobs (
            id                  NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            job_type            VARCHAR2(50) NOT NULL,
            status              VARCHAR2(20) NOT NULL,
            source_message_id   NUMBER NOT NULL,
            user_id             NUMBER,
            error_message       CLOB,
            created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
            updated_at          TIMESTAMP,
            CONSTRAINT fk_jobs_message
                FOREIGN KEY (source_message_id)
                REFERENCES REMEDIOS.messages(id) ON DELETE CASCADE,
            CONSTRAINT fk_jobs_user
                FOREIGN KEY (user_id)
                REFERENCES REMEDIOS.users(id) ON DELETE SET NULL
          )';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )

    # Job results
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE TABLE REMEDIOS.job_results (
            job_id        NUMBER PRIMARY KEY,
            result_json   CLOB CHECK (result_json IS JSON),
            output_ref    VARCHAR2(2000),
            duration_ms   NUMBER,
            audio_duration_seconds NUMBER,
            started_at    TIMESTAMP,
            finished_at   TIMESTAMP,
            created_at    TIMESTAMP DEFAULT SYSTIMESTAMP,
            CONSTRAINT fk_job_results_job
                FOREIGN KEY (job_id)
                REFERENCES REMEDIOS.jobs(id) ON DELETE CASCADE
          )';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )

    # Job audio (1:1)
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

    # Indexes
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE INDEX REMEDIOS.idx_messages_sender ON REMEDIOS.messages(sender_phone)';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE INDEX REMEDIOS.idx_messages_receiver ON REMEDIOS.messages(receiver_phone)';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE INDEX REMEDIOS.idx_jobs_user_id ON REMEDIOS.jobs(user_id)';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE INDEX REMEDIOS.idx_jobs_status ON REMEDIOS.jobs(status)';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE INDEX REMEDIOS.idx_jobs_message ON REMEDIOS.jobs(source_message_id)';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE UNIQUE INDEX REMEDIOS.ux_messages_message_id ON REMEDIOS.messages(message_id)';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE INDEX REMEDIOS.idx_messages_number_id ON REMEDIOS.messages(number_id)';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )
    _exec(
        """
        BEGIN
          EXECUTE IMMEDIATE 'CREATE UNIQUE INDEX REMEDIOS.ux_jobs_msg_type ON REMEDIOS.jobs(source_message_id, job_type)';
        EXCEPTION
          WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """
    )


def downgrade():
    _exec("DROP TABLE REMEDIOS.job_audio CASCADE CONSTRAINTS")
    _exec("DROP TABLE REMEDIOS.job_results CASCADE CONSTRAINTS")
    _exec("DROP TABLE REMEDIOS.jobs CASCADE CONSTRAINTS")
    _exec("DROP TABLE REMEDIOS.messages CASCADE CONSTRAINTS")
    _exec("DROP TABLE REMEDIOS.users CASCADE CONSTRAINTS")
