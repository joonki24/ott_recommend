"""
HNSW 인덱스 생성 + 검색 동작 확인
- embedding 컬럼이 다 채워진 뒤에 실행 (generate_embeddings.py 완료 후)
- ① HNSW 인덱스 생성
- ② ILIKE(JOIN) 검색 테스트
- ③ 벡터(시맨틱) 검색 테스트
- ④ ILIKE가 놓치는 케이스에서 벡터 검색이 잡아내는지 비교 시연

실행 전 준비: .env에 OPENAI_API_KEY, PostgreSQL 접속정보 필요
    pip install openai psycopg pgvector python-dotenv
"""

import os

import numpy as np
import psycopg
from dotenv import load_dotenv
from openai import OpenAI
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


def embed_text(text: str) -> np.ndarray:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL, input=text, dimensions=EMBEDDING_DIMENSIONS,
    )
    return np.asarray(response.data[0].embedding, dtype=np.float32)


def create_hnsw_index(conn):
    print("① HNSW 인덱스 생성 중...")
    conn.execute("""
        CREATE INDEX IF NOT EXISTS content_embedding_hnsw
        ON content_embedding
        USING hnsw (embedding vector_cosine_ops)
    """)
    conn.commit()

    result = conn.execute("""
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'content_embedding'
    """).fetchall()
    print("  생성된 인덱스:", [r[0] for r in result])


def ilike_search(conn, keyword: str, limit: int = 5):
    """정규화 스키마 기준 JOIN 검색 (설계서 4번 섹션과 동일 로직)"""
    result = conn.execute("""
        SELECT DISTINCT c.title, c.content_type, g.genre_name
        FROM content c
        JOIN content_genre cg ON c.content_id = cg.content_id
        JOIN genre g ON cg.genre_id = g.genre_id
        WHERE g.genre_name ILIKE %s OR c.title ILIKE %s
        LIMIT %s
    """, (f"%{keyword}%", f"%{keyword}%", limit)).fetchall()
    return result


def semantic_search(conn, query: str, top_k: int = 5):
    query_vector = embed_text(query)
    result = conn.execute("""
        SELECT c.title, c.content_type, 1 - (ce.embedding <=> %s) AS similarity
        FROM content_embedding ce
        JOIN content c ON c.content_id = ce.content_id
        ORDER BY ce.embedding <=> %s
        LIMIT %s
    """, (query_vector, query_vector, top_k)).fetchall()
    return result


def main():
    conn = psycopg.connect(**DB_CONFIG)
    register_vector(conn)
    print("ott_recommend 연결 성공\n")

    create_hnsw_index(conn)

    print("\n② ILIKE(JOIN) 검색 테스트 — '코미디'")
    for title, ctype, genre in ilike_search(conn, "코미디"):
        print(f"  [{ctype}] {title} ({genre})")

    print("\n③ 벡터(시맨틱) 검색 테스트 — '웃긴 거 추천해줘'")
    for title, ctype, sim in semantic_search(conn, "웃긴 거 추천해줘"):
        print(f"  [{ctype}] {title} (유사도 {sim:.3f})")

    print("\n④ ILIKE 실패 -> 벡터 검색 성공 시연")
    print("  ILIKE로 '웃긴' 검색 (실패 예상):")
    ilike_fail = ilike_search(conn, "웃긴")
    print(f"    결과 {len(ilike_fail)}건")

    print("  같은 의미를 벡터 검색으로 (성공 예상):")
    for title, ctype, sim in semantic_search(conn, "웃긴 콘텐츠", top_k=3):
        print(f"    [{ctype}] {title} (유사도 {sim:.3f})")

    conn.close()
    print("\n검증 완료")


if __name__ == "__main__":
    main()