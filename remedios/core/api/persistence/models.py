from sqlalchemy import Column, Float, ForeignKey, Identity, Integer, String, Text, TIMESTAMP, text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, Identity(), primary_key=True)
    phone = Column(String(20), unique=True, nullable=False)
    name = Column(String(255))
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))

    sent_messages = relationship(
        "Message",
        back_populates="sender",
        foreign_keys="Message.sender_phone",
    )
    received_messages = relationship(
        "Message",
        back_populates="receiver",
        foreign_keys="Message.receiver_phone",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, Identity(), primary_key=True)
    sender_phone = Column(String(20), ForeignKey("users.phone"))
    receiver_phone = Column(String(20), ForeignKey("users.phone"))
    message = Column(Text, nullable=False)
    message_type = Column(String(50), nullable=False, default="text")
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))

    message_id = Column(String(200), unique=True)
    number_id = Column(String(200))

    sender = relationship("User", foreign_keys=[sender_phone], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_phone], back_populates="received_messages")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, Identity(), primary_key=True)
    job_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    source_message_id = Column(ForeignKey("messages.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"))
    error_message = Column(Text)
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))
    updated_at = Column(TIMESTAMP(timezone=False))

    message = relationship("Message")
    user = relationship("User")
    result = relationship("JobResult", uselist=False, back_populates="job")
    audio = relationship("JobAudio", uselist=False, back_populates="job")


class JobResult(Base):
    __tablename__ = "job_results"

    job_id = Column(Integer, ForeignKey("jobs.id"), primary_key=True)
    result_json = Column(Text)
    output_ref = Column(String(2000))
    duration_ms = Column(Integer)
    audio_duration_seconds = Column(Float)
    started_at = Column(TIMESTAMP(timezone=False))
    finished_at = Column(TIMESTAMP(timezone=False))
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))

    job = relationship("Job", back_populates="result")


class JobAudio(Base):
    __tablename__ = "job_audio"

    job_id = Column(Integer, ForeignKey("jobs.id"), primary_key=True)
    provider = Column(String(50), nullable=False)
    bucket_name = Column(String(255), nullable=False)
    namespace = Column(String(255), nullable=False)
    object_key = Column(String(2000), nullable=False)
    size_bytes = Column(Integer)
    content_type = Column(String(255))
    etag = Column(String(255))
    audio_id = Column(String(200))
    created_at = Column(TIMESTAMP(timezone=False), server_default=text("SYSTIMESTAMP"))

    job = relationship("Job", back_populates="audio")
