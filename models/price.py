from sqlalchemy import ForeignKey, Numeric, Text, String
from sqlalchemy.orm import Mapped, mapped_column
from models.product import Base


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id")
    )

    website: Mapped[str] = mapped_column(String(50))

    price: Mapped[float] = mapped_column(Numeric(10, 2))

    product_url: Mapped[str] = mapped_column(Text)