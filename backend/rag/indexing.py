
from os import listdir
from os.path import isfile, join

from sqlalchemy import select

from api import db
from api.models import DocumentChunks

from parser import Parser
from chunker import chunk_text_by_tokens
from embedding import embed_texts
from . import config


class Indexer:
    def __init__(self):
        self.ifab_dir = config.IFAB_DIR

    def save(self):
        """Parse PDFs, generate embeddings, and save chunks to PostgreSQL."""
        try:
            for filename in listdir(self.ifab_dir):
                path = join(self.ifab_dir, filename)

                if not isfile(path) or not filename.lower().endswith(".pdf"):
                    continue

                parser = Parser(path)
                text, metadata = parser.parse()

                chunks = chunk_text_by_tokens(text)

                if not chunks:
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

                for chunk, embedding in zip(chunks, embeddings):
                    if len(embedding) != 1024:
                        raise ValueError(
                            f"Expected 1024 dimensions, got {len(embedding)}"
                        )

                    document_chunk = DocumentChunks(
                        content=chunk,
                        source=metadata["source"],
                        embedding=embedding,
                    )

                    db.session.add(document_chunk)

            db.session.commit()

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

        if len(query_embedding) != 1024:
            raise ValueError(
                f"Expected 1024 dimensions, got {len(query_embedding)}"
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
