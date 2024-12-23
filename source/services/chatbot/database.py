from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Boolean, Integer, create_engine
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from source.config.env_config import DATABASE_URL
from pgvector.sqlalchemy import Vector
import structlog
import json


"""
### Cấu hình database
"""
engine = create_engine(DATABASE_URL, json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


"""
### Hàm tiện ích
"""
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
### Cấu hình logging
"""

def encode_unicode(logger, method_name, event_dict):
    """
    Encode unicode values in event_dict
    """
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = value.encode('utf-8', errors='replace').decode('utf-8')
    return event_dict


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        encode_unicode,
        structlog.processors.JSONRenderer(ensure_ascii=False),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()


"""
### Định nghĩa các bảng
"""
class Embedding(Base):
    __tablename__ = "embeddings"
    chunk_id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(String(255), ForeignKey("documents.doc_id"))
    embedding = Column(Vector(1024))
    embedding_enrichment = Column(Vector(1024))
    page_content = Column(Text)
    enriched_content = Column(Text, nullable=True)
    language = Column(Text, nullable=True) # Thêm cột mới
    text = Column(Text)
    url = Column(String(255))
    archived = Column(Boolean, default=False)
    customer_id = Column(String(255), default="getfly")
    language = Column(String(255), nullable=True)
    document = relationship("Document", back_populates="embeddings")


class Document(Base):
    __tablename__ = "documents"
    doc_id = Column(String(255), primary_key=True)
    url = Column(String(255), nullable=True)
    url_id = Column(String(255), nullable=True)
    title = Column(Text)
    text = Column(Text)
    context = Column(JSON)  # Chứa các title của parent doc id dưới dạng JSON
    parent_doc_id = Column(String(255), nullable=True)
    collection_id = Column(String(255), ForeignKey("collections.collection_id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)
    archived = Column(Boolean, default=False)
    bots = relationship("BotDocument", back_populates="document")
    embeddings = relationship("Embedding", back_populates="document")

    
class Collection(Base):
    __tablename__ = "collections"
    collection_id = Column(String(255), primary_key=True)
    url = Column(String)
    url_id = Column(String)
    name = Column(String)
    bots = relationship("BotCollection", back_populates="collection")

class Bot(Base):
    __tablename__ = "bots"
    bot_id = Column(String(255), primary_key=True)
    name = Column(String(255), unique=True)
    description = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    collections = relationship("BotCollection", back_populates="bot")
    documents = relationship("BotDocument", back_populates="bot")

class BotCollection(Base):
    __tablename__ = "bot_collections"
    bot_id = Column(String(255), ForeignKey("bots.bot_id"), primary_key=True)
    collection_id = Column(String(255), ForeignKey("collections.collection_id"), primary_key=True)
    created_at = Column(DateTime)
    bot = relationship("Bot", back_populates="collections")
    collection = relationship("Collection", back_populates="bots")

class BotDocument(Base):
    __tablename__ = "bot_documents"
    doc_id = Column(String(255), ForeignKey("documents.doc_id"), primary_key=True)
    bot_id = Column(String(255), ForeignKey("bots.bot_id"), primary_key=True)
    is_removed_from_bot = Column(Boolean, default=False)
    created_at = Column(DateTime)
    removed_at = Column(DateTime(timezone=True))
    document = relationship("Document", back_populates="bots")
    bot = relationship("Bot", back_populates="documents")



"""
### Tạo các bảng
"""
Base.metadata.create_all(bind=engine)

