"""
content_embedding.embedding 컬럼 채우기 (OpenAI 임베딩)
- 강의 pgvector 실습과 동일한 패턴: text-embedding-3-small, 1024차원
- embedding_text를 50개씩 묶어서 embed_many로 변환 -> UPDATE

실행 전 준비: pip install openai psycopg pgvector python-dotenv
             .env에 OPENAI_API_KEY, PGHOST 등 PostgreSQL 접속정보 필요
"""

import os

from dotenv import load_dotenv
from openai import OpenAI
import psycopg
from pgvector.psycopg import register_vector

load_dotenv()

required_variables = ["OPENAI_API_KEY", "PGPASSWORD"]
missing_variables = [name for name in required_variables if not os.getenv(name)]
if missing_variables:
    raise RuntimeError(
        ".env 또는 환경변수에 필수 값이 없습니다: " + ", ".join(missing_variables)
    )

DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": "ott_recommend",
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.environ["PGPASSWORD"],
}

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1024
BATCH_SIZE = 50

client = OpenAI()
conn = psycopg.connect(**DB_CONFIG)
register_vector(conn)

print("PostgreSQL 연결:", conn.info.dbname)
print("임베딩 모델:", EMBEDDING_MODEL)
print("임베딩 차원:", EMBEDDING_DIMENSIONS)


def embed_many(values: list[str]) -> list[list[float]]:
    """여러 문장을 하나의 API 요청으로 임베딩한다."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=values,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    ordered_items = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered_items]


# content_embedding 테이블에서 임베딩할 대상 전체를 가져온다
rows = conn.execute(
    "SELECT content_id, embedding_text FROM content_embedding ORDER BY content_id"
).fetchall()
print("임베딩 대상:", len(rows), "건")

# BATCH_SIZE개씩 끊어서 처리
for start in range(0, len(rows), BATCH_SIZE):
    batch = rows[start:start + BATCH_SIZE]

    ids = [content_id for content_id, _ in batch]
    texts = [text if text else "" for _, text in batch]

    vectors = embed_many(texts)

    for content_id, vector in zip(ids, vectors):
        conn.execute(
            "UPDATE content_embedding SET embedding = %s WHERE content_id = %s",
            (vector, content_id),
        )
    conn.commit()

    print(f"진행 {start + len(batch)}/{len(rows)}")

print("\n임베딩 UPDATE 완료")

filled = conn.execute(
    "SELECT COUNT(*) FROM content_embedding WHERE embedding IS NOT NULL"
).fetchone()[0]
print("embedding 채워진 행:", filled, "건")

conn.close()
