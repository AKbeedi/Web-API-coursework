from datetime import date
from sqlalchemy import String, Integer, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)

    observations: Mapped[list["Observation"]] = relationship(
        back_populates="city",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("name", "country", name="uq_city_name_country"),
    )


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    city_id: Mapped[int] = mapped_column(
        ForeignKey("cities.id", ondelete="CASCADE"),
        index=True,
    )
    obs_date: Mapped[date] = mapped_column(Date, index=True)
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm25: Mapped[float | None] = mapped_column(Float, nullable=True)

    city: Mapped["City"] = relationship(back_populates="observations")

    __table_args__ = (
        UniqueConstraint("city_id", "obs_date", name="uq_city_date"),
    )

