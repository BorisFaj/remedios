CREATE TABLE REMEDIOS.users (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    phone       VARCHAR2(20) UNIQUE NOT NULL,
    name        VARCHAR2(255),
    created_at  TIMESTAMP DEFAULT SYSTIMESTAMP
);

CREATE TABLE REMEDIOS.messages (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sender_phone    VARCHAR2(20),
    receiver_phone  VARCHAR2(20),
    message_id  VARCHAR2(200),
    number_id   VARCHAR2(200)
    message         CLOB NOT NULL,
    message_type    VARCHAR2(50) DEFAULT 'text' NOT NULL,
    created_at      TIMESTAMP DEFAULT SYSTIMESTAMP,

    CONSTRAINT fk_sender FOREIGN KEY (sender_phone)
        REFERENCES REMEDIOS.users(phone)
        ON DELETE SET NULL,

    CONSTRAINT fk_receiver FOREIGN KEY (receiver_phone)
        REFERENCES REMEDIOS.users(phone)
        ON DELETE SET NULL
);

CREATE TABLE REMEDIOS.jobs (
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
        REFERENCES REMEDIOS.messages(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_jobs_user
        FOREIGN KEY (user_id)
        REFERENCES REMEDIOS.users(id)
        ON DELETE SET NULL
);

CREATE TABLE REMEDIOS.job_results (
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
        REFERENCES REMEDIOS.jobs(id)
        ON DELETE CASCADE
);

CREATE INDEX REMEDIOS.idx_messages_sender   ON REMEDIOS.messages(sender_phone);
CREATE INDEX REMEDIOS.idx_messages_receiver ON REMEDIOS.messages(receiver_phone);

CREATE INDEX REMEDIOS.idx_jobs_user_id   ON REMEDIOS.jobs(user_id);
CREATE INDEX REMEDIOS.idx_jobs_status    ON REMEDIOS.jobs(status);
CREATE INDEX REMEDIOS.idx_jobs_message   ON REMEDIOS.jobs(source_message_id);

CREATE UNIQUE INDEX REMEDIOS.ux_messages_message_id ON REMEDIOS.messages(message_id);

CREATE INDEX REMEDIOS.idx_messages_number_id ON REMEDIOS.messages(number_id);
CREATE UNIQUE INDEX REMEDIOS.ux_jobs_msg_type ON REMEDIOS.jobs(source_message_id, job_type);
