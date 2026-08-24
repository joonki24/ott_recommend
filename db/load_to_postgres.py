"""
CSV 8종 -> PostgreSQL(ott_recommend) 적재
- 강의 노트북과 동일한 방식: load_dotenv로 환경변수 확인 -> DB_CONFIG로 접속 -> conn.execute 반복
- 순서: FK 제약 때문에 부모 테이블부터 넣는다
    1) content, genre, person, content_tag (독립 테이블)
    2) content_genre, content_tag_map, content_person_role, content_embedding (연결 테이블)

실행 전 준비: pip install psycopg pandas python-dotenv
             .env에 PGHOST, PGPORT, PGUSER, PGPASSWORD 필요
"""

import os

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

required_variables = ["PGPASSWORD"]
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

conn = psycopg.connect(**DB_CONFIG)
print("PostgreSQL 연결:", conn.info.dbname)


def to_sql_value(value):
    """CSV에서 읽은 빈 값(NaN)을 PostgreSQL이 이해하는 NULL(None)로 바꾼다."""
    if pd.isna(value):
        return None
    return value


def to_sql_int(value):
    """정수 컬럼용. NaN이면 None, 아니면 정수로 바꾼다.
    (CSV에 빈 값이 섞여 있으면 pandas가 132.0처럼 float으로 읽어서, 그대로 넣으면 오류가 남)"""
    if pd.isna(value):
        return None
    return int(value)


# 1. content 테이블
df = pd.read_csv("../data/content.csv")
for _, row in df.iterrows():
    conn.execute(
        """
        INSERT INTO content (content_id, tmdb_id, title, content_type, country_code,
                              runtime_minutes, episode_count, overview)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            int(row["content_id"]),
            int(row["tmdb_id"]),
            row["title"],
            row["content_type"],
            to_sql_value(row["country_code"]),
            to_sql_int(row["runtime_minutes"]),
            to_sql_int(row["episode_count"]),
            to_sql_value(row["overview"]),
        ),
    )
conn.commit()
print("content 적재 완료:", len(df), "건")

# 2. genre 테이블
df = pd.read_csv("../data/genre.csv")
for _, row in df.iterrows():
    conn.execute(
        "INSERT INTO genre (genre_id, genre_name) VALUES (%s, %s)",
        (int(row["genre_id"]), row["genre_name"]),
    )
conn.commit()
print("genre 적재 완료:", len(df), "건")

# 3. person 테이블
df = pd.read_csv("../data/person.csv")
for _, row in df.iterrows():
    conn.execute(
        "INSERT INTO person (person_id, tmdb_person_id, person_name) VALUES (%s, %s, %s)",
        (int(row["person_id"]), int(row["tmdb_person_id"]), row["person_name"]),
    )
conn.commit()
print("person 적재 완료:", len(df), "건")

# 4. content_tag 테이블
df = pd.read_csv("../data/content_tag.csv")
for _, row in df.iterrows():
    conn.execute(
        """
        INSERT INTO content_tag (tag_id, source_keyword_id, tag_name, source_name)
        VALUES (%s, %s, %s, %s)
        """,
        (
            int(row["tag_id"]),
            int(row["source_keyword_id"]),
            row["tag_name"],
            to_sql_value(row["source_name"]),
        ),
    )
conn.commit()
print("content_tag 적재 완료:", len(df), "건")

# 5. content_genre (연결 테이블)
df = pd.read_csv("../data/content_genre.csv")
for _, row in df.iterrows():
    conn.execute(
        "INSERT INTO content_genre (content_id, genre_id) VALUES (%s, %s)",
        (int(row["content_id"]), int(row["genre_id"])),
    )
conn.commit()
print("content_genre 적재 완료:", len(df), "건")

# 6. content_tag_map (연결 테이블)
df = pd.read_csv("../data/content_tag_map.csv")
for _, row in df.iterrows():
    conn.execute(
        "INSERT INTO content_tag_map (content_id, tag_id) VALUES (%s, %s)",
        (int(row["content_id"]), int(row["tag_id"])),
    )
conn.commit()
print("content_tag_map 적재 완료:", len(df), "건")

# 7. content_person_role (연결 테이블)
df = pd.read_csv("../data/content_person_role.csv")
for _, row in df.iterrows():
    conn.execute(
        """
        INSERT INTO content_person_role (content_id, person_id, role_type)
        VALUES (%s, %s, %s)
        """,
        (int(row["content_id"]), int(row["person_id"]), row["role_type"]),
    )
conn.commit()
print("content_person_role 적재 완료:", len(df), "건")

# 8. content_embedding (embedding_text만 우선 적재, 벡터값은 다음 스크립트에서 채움)
df = pd.read_csv("../data/content_embedding.csv")
for _, row in df.iterrows():
    conn.execute(
        "INSERT INTO content_embedding (content_id, embedding_text) VALUES (%s, %s)",
        (int(row["content_id"]), row["embedding_text"]),
    )
conn.commit()
print("content_embedding 적재 완료:", len(df), "건")

# 최종 확인
print("\n적재 결과 확인")
tables = [
    "content", "genre", "content_genre", "content_tag",
    "content_tag_map", "person", "content_person_role", "content_embedding",
]
for table in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: {count}건")

conn.close()
