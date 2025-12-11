CREATE TABLE users (
    id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    phone       VARCHAR2(20) UNIQUE NOT NULL,
    name        VARCHAR2(255),
    created_at  TIMESTAMP DEFAULT SYSTIMESTAMP
);

CREATE TABLE messages (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sender_phone    VARCHAR2(20),
    receiver_phone  VARCHAR2(20),
    message         CLOB NOT NULL,
    message_type    VARCHAR2(50) DEFAULT 'text' NOT NULL,
    created_at      TIMESTAMP DEFAULT SYSTIMESTAMP,

    CONSTRAINT fk_sender FOREIGN KEY (sender_phone)
        REFERENCES users(phone)
        ON DELETE SET NULL,

    CONSTRAINT fk_receiver FOREIGN KEY (receiver_phone)
        REFERENCES users(phone)
        ON DELETE SET NULL
);

CREATE TABLE jobs (
    id                  NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_type            VARCHAR2(50) NOT NULL,       -- transcription, answer, etc.
    status              VARCHAR2(20) NOT NULL,       -- queued, processing, done, error
    source_message_id   NUMBER NOT NULL,             -- FK a messages(id)
    user_id             NUMBER,                      -- FK opcional a users(id)
    error_message       CLOB,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP,

    CONSTRAINT fk_jobs_message
        FOREIGN KEY (source_message_id)
        REFERENCES messages(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_jobs_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
);

CREATE TABLE job_results (
    job_id        NUMBER PRIMARY KEY,
    result_json   CLOB CHECK (result_json IS JSON),  -- JSON almacenado en CLOB
    output_ref    VARCHAR2(2000),
    created_at    TIMESTAMP DEFAULT SYSTIMESTAMP,

    CONSTRAINT fk_job_results_job
        FOREIGN KEY (job_id)
        REFERENCES jobs(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_messages_sender ON messages(sender_phone);
CREATE INDEX idx_messages_receiver ON messages(receiver_phone);

CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_message ON jobs(source_message_id);
