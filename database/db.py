import dataclasses
import datetime
import enum

from adbutils import AdbDevice
from sqlalchemy import create_engine, ForeignKey, String, DateTime, \
    Integer, select, delete, Text, Date, Enum
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database


# db_url = f"postgresql+psycopg2://{conf.db.db_user}:{conf.db.db_password}@{conf.db.db_host}:{conf.db.db_port}/{conf.db.database}"
from config.bot_settings import BASE_DIR, logger

db_path = BASE_DIR / 'base.sqlite'
db_url = f"sqlite:///{db_path}"
engine = create_engine(db_url, echo=False)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    def set(self, key, value):
        _session = Session(expire_on_commit=False)
        with _session:
            if isinstance(value, str):
                value = value[:999]
            setattr(self, key, value)
            _session.add(self)
            _session.commit()
            # logger.debug(f'Изменено значение {key} на {value}')
            return self


class PhoneDB(Base):
    class PhoneStatus(enum.Enum):
        READY = 'Готов'
        IN_PROGRESS = 'В работе'
        WAIT_SMS = 'Жду смс'
        DONE = 'Закончил'
        ERROR = 'Ошибка'

    __tablename__ = 'phones'
    id: Mapped[int] = mapped_column(primary_key=True,
                                    autoincrement=True)
    serial: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[int] = mapped_column(Integer(), default=0)
    payment_id: Mapped[str] = mapped_column(String(50), nullable=True)
    current_status: Mapped[str] = mapped_column(Enum(PhoneStatus), nullable=True)
    amount: Mapped[int] = mapped_column(Integer(), nullable=True)
    card: Mapped[int] = mapped_column(Integer(), nullable=True)
    message: Mapped[str] = mapped_column(String(200), nullable=True)
    image: Mapped[str] = mapped_column(String(200), nullable=True)

    def __repr__(self):
        return f'Phone {self.name}. ({self.serial})'

    def __str__(self):
        return f'Phone {self.name}. ({self.serial})'


class PhoneDevice:
    def __init__(self, db, device):
        self.db = db
        self.device = device


if not database_exists(db_url):
    create_database(db_url)
Base.metadata.create_all(engine)

