"""
content_embedding.embedding 컬럼 채우기 (OpenAI 임베딩)
- 강의 pgvector 실습과 동일한 패턴: text-embedding-3-small, 1024차원
- content_embedding 테이블의 embedding_text를 배치로 임베딩 -> embedding 컬럼 UPDATE

실행 전 준비: .env에 OPENAI_API_KEY, PostgreSQL 접속정보(PGHOST 등) 필요
    pip install openai psycopg pgvector pandas python-dotenv

참고: 1,874건을 배치(기본 50개씩)로 처리 -> API 호출 약 38회, 수 분 내 완료 예상
     (기존 TMDB 수집처럼 항목당 1회 호출이 아니라 훨씬 빠름)
"""

import os
import time

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector

load_dotenv()

required_variables = ["OPENAI_API_KEY", "PGPASSWORD"]
missing_variables = [name for name in required_variables if not os.getenv(name)]
if missing_variables:
    raise RuntimeError(".env에 필수 값이 없습니다: " + ", ".join(missing_variables))

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1024
BATCH_SIZE = 50

DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": "ott_recommend",
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.environ["PGPASSWORD"],
}

client = OpenAI()


def embed_many(texts: list[str]) -> list[list[float]]:
    """여러 문장을 한 번의 API 요청으로 임베딩 (강의 실습과 동일 패턴)"""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    ordered_items = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered_items]


def main():
    conn = psycopg.connect(**DB_CONFIG)
    register_vector(conn)
    print("ott_recommend 연결 성공")

    with conn.cursor() as cur:
        cur.execute("SELECT content_id, embedding_text FROM content_embedding ORDER BY content_id")
        rows = cur.fetchall()
    print(f"임베딩 대상: {len(rows)}건\n")

    total = len(rows)
    done = 0
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        ids = [r[0] for r in batch]
        texts = [r[1] or "" for r in batch]  # None 방지

        vectors = embed_many(texts)

        with conn.cursor() as cur:
            for content_id, vector in zip(ids, vectors):
                cur.execute(
                    "UPDATE content_embedding SET embedding = %s WHERE content_id = %s",
                    (vector, content_id),
                )
        conn.commit()

        done += len(batch)
        print(f"진행 {done}/{total}")
        time.sleep(0.1)  # API rate limit 배려

    print("\n임베딩 UPDATE 완료")

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM content_embedding WHERE embedding IS NOT NULL")
        print(f"embedding 채워진 행: {cur.fetchone()[0]}건")

    conn.close()


if __name__ == "__main__":
    main()
