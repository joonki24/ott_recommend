"""
HNSW 인덱스 생성 + 검색 동작 확인
- embedding 컬럼이 다 채워진 뒤에 실행 (generate_embeddings.py 완료 후)

실행 전 준비: pip install openai psycopg pgvector python-dotenv
             .env에 OPENAI_API_KEY, PostgreSQL 접속정보 필요
"""

import os

from dotenv import load_dotenv
from openai import OpenAI
import psycopg
from pgvector.psycopg import register_vector

load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1024

DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": "ott_recommend",
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.environ["PGPASSWORD"],
}

client = OpenAI()
conn = psycopg.connect(**DB_CONFIG)
register_vector(conn)
print("PostgreSQL 연결:", conn.info.dbname)


def embed_text(text: str) -> list[float]:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


# 1. HNSW 인덱스 생성
conn.execute("""
    CREATE INDEX IF NOT EXISTS content_embedding_hnsw
    ON content_embedding
    USING hnsw (embedding vector_cosine_ops)
""")
conn.commit()

indexes = conn.execute("""
    SELECT indexname FROM pg_indexes WHERE tablename = 'content_embedding'
""").fetchall()
print("생성된 인덱스:", [row[0] for row in indexes])


# 2. ILIKE(JOIN) 검색 테스트 — "코미디"
print("\nILIKE 검색 테스트 — '코미디'")
result = conn.execute("""
    SELECT DISTINCT c.title, c.content_type, g.genre_name
    FROM content c
    JOIN content_genre cg ON c.content_id = cg.content_id
    JOIN genre g ON cg.genre_id = g.genre_id
    WHERE g.genre_name ILIKE %s OR c.title ILIKE %s
    LIMIT 5
""", ("%코미디%", "%코미디%")).fetchall()

for title, content_type, genre_name in result:
    print(f"  [{content_type}] {title} ({genre_name})")


# 3. 벡터(시맨틱) 검색 테스트 — "웃긴 거 추천해줘"
print("\n벡터 검색 테스트 — '웃긴 거 추천해줘'")
query_vector = embed_text("웃긴 거 추천해줘")

result = conn.execute("""
    SELECT c.title, c.content_type, 1 - (ce.embedding <=> %s) AS similarity
    FROM content_embedding ce
    JOIN content c ON c.content_id = ce.content_id
    ORDER BY ce.embedding <=> %s
    LIMIT 5
""", (query_vector, query_vector)).fetchall()

for title, content_type, similarity in result:
    print(f"  [{content_type}] {title} (유사도 {similarity:.3f})")


# 4. ILIKE가 놓치는 케이스를 벡터 검색이 잡아내는지 비교
print("\nILIKE 실패 -> 벡터 검색 성공 비교")

print("  ILIKE로 '웃긴' 검색 (실패 예상):")
ilike_result = conn.execute("""
    SELECT DISTINCT c.title
    FROM content c
    JOIN content_genre cg ON c.content_id = cg.content_id
    JOIN genre g ON cg.genre_id = g.genre_id
    WHERE g.genre_name ILIKE %s OR c.title ILIKE %s
""", ("%웃긴%", "%웃긴%")).fetchall()
print(f"    결과 {len(ilike_result)}건")

print("  같은 의미를 벡터 검색으로 (성공 예상):")
query_vector = embed_text("웃긴 콘텐츠")
result = conn.execute("""
    SELECT c.title, c.content_type, 1 - (ce.embedding <=> %s) AS similarity
    FROM content_embedding ce
    JOIN content c ON c.content_id = ce.content_id
    ORDER BY ce.embedding <=> %s
    LIMIT 3
""", (query_vector, query_vector)).fetchall()

for title, content_type, similarity in result:
    print(f"    [{content_type}] {title} (유사도 {similarity:.3f})")

conn.close()
print("\n검증 완료")
