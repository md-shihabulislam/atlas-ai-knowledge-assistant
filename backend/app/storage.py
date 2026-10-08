"""SQLite developer mode or PostgreSQL/pgvector storage via DATABASE_URL."""
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from . import config


def _tokens(text: str) -> set[str]:
    return {s.lower() for s in re.findall(r'[A-Za-z0-9]{2,}', text)}

def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    a = sum(x*y for x,y in zip(left, right))
    d = math.sqrt(sum(x*x for x in left) * sum(y*y for y in right))
    return a/d if d else 0.0

class SQLiteStorage:
    def __init__(self, path: str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page INTEGER NOT NULL, chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL, embedding TEXT);
              CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def add(self, filename, chunks, vectors):
        doc_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('INSERT INTO documents VALUES (?, ?, ?)', (doc_id, filename, now))
            db.executemany('INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)', [
                (str(uuid4()), doc_id, c['page'], c['index'], c['content'],
                 json.dumps(vectors[i]) if vectors else None)
                for i, c in enumerate(chunks)
            ])
        return {'id': doc_id, 'filename': filename, 'created_at': now, 'chunks': len(chunks)}

    def list(self):
        with self.connect() as db:
            rows = db.execute('''SELECT d.id, d.filename, d.created_at,
                              COUNT(c.id) AS chunks FROM documents d
                              LEFT JOIN chunks c ON c.document_id=d.id
                              GROUP BY d.id ORDER BY d.created_at DESC''').fetchall()
            return [dict(r) for r in rows]

    def delete(self, doc_id):
        with self.connect() as db:
            cur = db.execute('DELETE FROM documents WHERE id=?', (doc_id,))
            return cur.rowcount > 0

    def search(self, question, vector, limit=4):
        with self.connect() as db:
            rows = db.execute('''SELECT c.*, d.filename FROM chunks c
                                 JOIN documents d ON c.document_id=d.id''').fetchall()
        terms = _tokens(question)
        scored = []
        for r in rows:
            content = r['content']
            vec = json.loads(r['embedding']) if r['embedding'] else None
            if vector and vec:
                score = _cosine(vector, vec)
            else:
                words = _tokens(content)
                score = len(terms & words) / max(1, len(terms))
            if score > 0:
                scored.append({'filename':r['filename'], 'page':r['page'],
                               'content':content, 'score':round(score, 4),
                               'document_id':r['document_id']})
        scored.sort(key=lambda r:r['score'], reverse=True)
        return scored[:limit]

class PostgresStorage:
    def __init__(self, dsn: str):
        self.dsn = dsn
        with self.connect() as db:
            db.execute('CREATE EXTENSION IF NOT EXISTS vector')
            db.execute('''CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY, filename TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
            db.execute('''CREATE TABLE IF NOT EXISTS chunks (
                id UUID PRIMARY KEY, document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page INTEGER NOT NULL, chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL, embedding VECTOR(1536))''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_chunks_search ON chunks USING GIN(to_tsvector(\'english\', content))')

    @contextmanager
    def connect(self):
        import psycopg
        db = psycopg.connect(self.dsn)
        # Registration is required for adaptation of pgvector.Vector values.
        # Create extension first so register_vector can discover its PostgreSQL type.
        from pgvector.psycopg import register_vector
        db.execute('CREATE EXTENSION IF NOT EXISTS vector')
        register_vector(db)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def add(self, filename, chunks, vectors):
        doc_id = str(uuid4())
        from pgvector import Vector
        with self.connect() as db:
            db.execute('INSERT INTO documents(id,filename) VALUES (%s,%s)', (doc_id, filename))
            for i, c in enumerate(chunks):
                value = Vector(vectors[i]) if vectors else None
                db.execute('''INSERT INTO chunks (id, document_id, page, chunk_index, content, embedding)
                              VALUES (%s,%s,%s,%s,%s,%s)''',
                           (str(uuid4()), doc_id, c['page'], c['index'], c['content'], value))
            row = db.execute('SELECT created_at FROM documents WHERE id=%s', (doc_id,)).fetchone()
        return {'id':doc_id, 'filename':filename, 'created_at':row[0].isoformat(), 'chunks':len(chunks)}

    def list(self):
        with self.connect() as db:
            rows = db.execute('''SELECT d.id, d.filename, d.created_at, COUNT(c.id) FROM documents d
                                 LEFT JOIN chunks c ON d.id=c.document_id
                                 GROUP BY d.id ORDER BY d.created_at DESC''').fetchall()
        return [{'id':str(r[0]),'filename':r[1], 'created_at':r[2].isoformat(), 'chunks':r[3]} for r in rows]

    def delete(self, doc_id):
        with self.connect() as db:
            try:
                cur = db.execute('DELETE FROM documents WHERE id=%s', (doc_id,))
            except Exception:
                return False
            return cur.rowcount > 0

    def search(self, question, vector, limit=4):
        from pgvector import Vector
        with self.connect() as db:
            if vector:
                rows = db.execute('''SELECT d.id, d.filename, c.page, c.content,
                                     1-(c.embedding <=> %s) AS score
                                     FROM chunks c JOIN documents d ON d.id=c.document_id
                                     WHERE c.embedding IS NOT NULL
                                     ORDER BY c.embedding <=> %s LIMIT %s''',
                                  (Vector(vector), Vector(vector), limit)).fetchall()
            else:
                rows = db.execute('''SELECT d.id, d.filename, c.page, c.content,
                                     ts_rank(to_tsvector('english',c.content),
                                             plainto_tsquery('english',%s)) AS score
                                     FROM chunks c JOIN documents d ON d.id=c.document_id
                                     WHERE to_tsvector('english',c.content) @@ plainto_tsquery('english',%s)
                                     ORDER BY score DESC LIMIT %s''',
                                  (question, question, limit)).fetchall()
        return [{'document_id':str(r[0]), 'filename':r[1], 'page':r[2],
                 'content':r[3], 'score':round(float(r[4]),4)} for r in rows]


def get_storage():
    if config.DATABASE_URL:
        return PostgresStorage(config.DATABASE_URL)
    return SQLiteStorage(config.SQLITE_PATH)
