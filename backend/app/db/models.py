import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, Text, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user", lazy="select")
    preference_profile: Mapped["UserPreferenceProfile | None"] = relationship(
        back_populates="user", uselist=False, lazy="select"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    image_filename: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    status: Mapped[str] = mapped_column(String, default="active")  # active | finalized | abandoned
    round_number: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions", lazy="select")
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="session", lazy="select")
    feedback_events: Mapped[list["FeedbackEvent"]] = relationship(back_populates="session", lazy="select")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    round_number: Mapped[int] = mapped_column(Integer)
    generation_config: Mapped[dict] = mapped_column(JSON)
    rendered_prompt: Mapped[str] = mapped_column(Text, default="")
    image_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    generation_status: Mapped[str] = mapped_column(String, default="pending")  # pending|generating|done|error
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Image analysis columns — added for per-image dynamic feedback chips.
    # Dev: delete backend/data/workshop.db to recreate schema if upgrading existing DB.
    analysis_status: Mapped[str] = mapped_column(String, default="pending")  # pending|running|done|failed
    image_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"like_chips":[...], "dislike_chips":[...]}
    chip_dimension_map: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"chip_id": ["dim1", ...], ...}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship(back_populates="candidates", lazy="select")

    __table_args__ = (
        Index("ix_candidates_session_round", "session_id", "round_number"),
    )


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"))
    action: Mapped[str] = mapped_column(String)  # like | dislike | save | pairwise_implicit
    reason_tags: Mapped[list] = mapped_column(JSON, default=list)
    text_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reward: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship(back_populates="feedback_events", lazy="select")


class UserPreferenceProfile(Base):
    __tablename__ = "user_preference_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="preference_profile", lazy="select")
    dimensions: Mapped[list["UserPreferenceDimension"]] = relationship(
        back_populates="profile", lazy="select"
    )


class UserPreferenceDimension(Base):
    __tablename__ = "user_preference_dimensions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    profile_id: Mapped[str] = mapped_column(ForeignKey("user_preference_profiles.id"))
    dimension_name: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float, default=0.0)       # [-1.0, +1.0]
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # [0.0, 1.0]
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["UserPreferenceProfile"] = relationship(back_populates="dimensions", lazy="select")

    __table_args__ = (
        Index("ix_dim_profile_name", "profile_id", "dimension_name", unique=True),
    )
