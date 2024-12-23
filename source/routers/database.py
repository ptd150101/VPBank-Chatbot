# database.py
from sqlalchemy import (
    JSON, create_engine,
    Column, Integer, String,
    ForeignKey, MetaData, DateTime, Text
)


from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
DATABASE_URL = "sqlite:///./history.db"

# Tạo engine và session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Khởi tạo Base và metadata
Base = declarative_base()
metadata = MetaData()

# Tạo bảng User
class User(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, index=True, unique=True)
    display_name = Column(String)

# Tạo bảng Thread với thread_id auto increment
class Thread(Base):
    __tablename__ = "threads"
    thread_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey('users.user_id'))
    user = relationship("User")
    current_context = Column(String)
    communi_thread_id = Column(String)

class Bot(Base):
    __tablename__ = "bots"
    bot_id = Column(String, primary_key=True, index=True, unique=True)
    bot_name = Column(String)
    bot_token = Column(String)

# Tạo bảng ChatHistory để lưu trữ lịch sử chat
class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey('threads.thread_id'))
    user_id = Column(String, ForeignKey('users.user_id'))
    display_name = Column(String)  # Add display_name column
    conversation = Column(Text)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

# Khởi tạo bảng trong cơ sở dữ liệu
Base.metadata.create_all(bind=engine)
