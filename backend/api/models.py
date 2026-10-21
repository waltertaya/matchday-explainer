from datetime import datetime, timezone
import uuid

from sqlalchemy import Text, Integer, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from . import db


class DocumentChunks(db.Model):
    __tablename__ = "document_chunks"

    id = db.Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    content = db.Column(Text, nullable=False)
    source = db.Column(Text)
    page_number = db.Column(Integer)
    embedding = db.Column(Vector(1024), nullable=False)

    created_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "page_number": self.page_number,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
