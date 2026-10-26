
from os import listdir
from os.path import isfile, join

from sqlalchemy import delete, select

from api import db
from api.models import DocumentChunks

from .parser import Parser
from .chunker import chunk_text_by_tokens
from .embedding import embed_texts
from . import config


class Indexer:
    def __init__(self):
        self.ifab_dir = config.IFAB_DIR

    def save(self):
        """Parse PDFs, generate embeddings, and save chunks to PostgreSQL."""
        report = {"indexed": 0, "unchanged": 0, "chunks": 0}
        try:
            for filename in sorted(listdir(self.ifab_dir)):
                path = join(self.ifab_dir, filename)

                if not isfile(path) or not filename.lower().endswith(".pdf"):
                    continue

                parser = Parser(path)
                text, metadata = parser.parse()

                chunks = chunk_text_by_tokens(text)

                if not chunks:
                    continue

                # Re-indexing an unchanged file must not duplicate evidence or
                # pay for another embedding call. Changed sources are replaced
                # atomically in the same transaction, never appended blindly.
                source = metadata["source"]
                existing = db.session.execute(select(DocumentChunks.content).where(
                    DocumentChunks.source == source,
                )).scalars().all()
                if len(existing) == len(chunks) and sorted(existing) == sorted(chunks):
                    report["unchanged"] += 1
                    continue

                # generate document embeddings.
                embeddings = embed_texts(
                    chunks,
                    input_type="passage",
                )

                if len(chunks) != len(embeddings):
                    raise ValueError(
                        f"Chunk/embedding count mismatch: {filename}"
                    )

                if any(len(vector) != config.EMBEDDING_DIMENSIONS for vector in embeddings):
                    raise ValueError("Embedding dimensions do not match the configured index")
                db.session.execute(delete(DocumentChunks).where(DocumentChunks.source == source))

                for chunk, embedding in zip(chunks, embeddings):
                    document_chunk = DocumentChunks(
                        content=chunk,
                        source=metadata["source"],
                        embedding=embedding,
                    )

                    db.session.add(document_chunk)

                report["indexed"] += 1
                report["chunks"] += len(chunks)

            db.session.commit()
            return report

        except Exception:
            db.session.rollback()
            raise

    def search(self, query, limit=5, source=None):
        """
        Retrieve the most relevant chunks using cosine distance.

        Args:
            query: User's question.
            limit: Maximum number of chunks to return.
            source: Optional source filename filter.

        Returns:
            List of dictionaries containing chunk content and metadata.
        """
        if not query or not query.strip():
            return []

        if limit < 1:
            raise ValueError("limit must be at least 1")

        # embed the user's question using query mode.
        query_embedding = embed_texts(
            [query],
            input_type="query",
        )[0]

        if len(query_embedding) != config.EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Expected {config.EMBEDDING_DIMENSIONS} dimensions, got {len(query_embedding)}"
            )

        # pgvector's cosine distance operator: <=>.
        distance = DocumentChunks.embedding.cosine_distance(
            query_embedding.tolist()
        )

        statement = select(
            DocumentChunks,
            distance.label("distance"),
        )

        if source is not None:
            statement = statement.where(
                DocumentChunks.source == source
            )

        statement = statement.order_by(distance).limit(limit)

        rows = db.session.execute(statement).all()

        results = []

        for chunk, cosine_distance in rows:
            results.append({
                "id": chunk.id,
                "content": chunk.content,
                "source": chunk.source,
                "page_number": chunk.page_number,
                "distance": float(cosine_distance),
                "similarity": 1.0 - float(cosine_distance),
            })

        return results
