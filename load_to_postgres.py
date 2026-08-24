"""
CSV 8종 -> PostgreSQL(ott_recommend) 적재 스크립트
- 입력: build_full_erd_data.py가 만든 8개 CSV
    content.csv, genre.csv, content_genre.csv,
    content_tag.csv, content_tag_map.csv,
    person.csv, content_person_role.csv, content_embedding.csv
- 순서: FK 제약 때문에 부모 테이블부터 적재
    1) content, genre, person, content_tag  (독립 테이블)
    2) content_genre, content_tag_map, content_person_role, content_embedding  (연결 테이블)

실행 전 준비: .env에 ott_recommend DB 접속 정보 필요
    PGHOST, PGPORT, PGUSER, PGPASSWORD (PGDATABASE는 코드에서 ott_recommend로 고정)
    pip install psycopg pandas python-dotenv
"""

import os

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": "ott_recommend",
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.environ["PGPASSWORD"],
}


def load_csv_to_table(conn, csv_path: str, table: str, columns: list[str], int_columns: list[str] = None):
    df = pd.read_csv(csv_path)
    df = df[columns]  # 컬럼 순서를 테이블과 맞춤

    # 정수 컬럼에 결측치가 있으면 pandas가 float으로 읽어서 132.0 같은 값이 됨
    # -> PostgreSQL INT 컬럼에 float을 그대로 넣으면 타입 에러가 나므로 nullable Int64로 먼저 변환
    for col in (int_columns or []):
        if col in df.columns:
            df[col] = df[col].astype("Int64")

    df = df.astype(object).where(pd.notnull(df), None)  # NaN/pd.NA -> NULL

    placeholders = ", ".join(["%s"] * len(columns))
    col_list = ", ".join(columns)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    print(f"  {table}: {len(rows)}건 적재 완료")


def main():
    conn = psycopg.connect(**DB_CONFIG)
    print("ott_recommend 연결 성공\n")

    print("① 독립 테이블 적재 (content, genre, person, content_tag)")
    load_csv_to_table(conn, "content.csv", "content",
        ["content_id", "tmdb_id", "title", "content_type", "country_code",
         "runtime_minutes", "episode_count", "overview"],
        int_columns=["content_id", "tmdb_id", "runtime_minutes", "episode_count"])
    load_csv_to_table(conn, "genre.csv", "genre", ["genre_id", "genre_name"])
    load_csv_to_table(conn, "person.csv", "person", ["person_id", "tmdb_person_id", "person_name"])
    load_csv_to_table(conn, "content_tag.csv", "content_tag",
        ["tag_id", "source_keyword_id", "tag_name", "source_name"])

    print("\n② 연결 테이블 적재 (content_genre, content_tag_map, content_person_role, content_embedding)")
    load_csv_to_table(conn, "content_genre.csv", "content_genre", ["content_id", "genre_id"])
    load_csv_to_table(conn, "content_tag_map.csv", "content_tag_map", ["content_id", "tag_id"])
    load_csv_to_table(conn, "content_person_role.csv", "content_person_role",
        ["content_id", "person_id", "role_type"])
    load_csv_to_table(conn, "content_embedding.csv", "content_embedding",
        ["content_id", "embedding_text"])  # embedding 컬럼은 다음 단계에서 UPDATE

    print("\n③ 적재 결과 확인")
    with conn.cursor() as cur:
        for table in ["content", "genre", "content_genre", "content_tag",
                       "content_tag_map", "person", "content_person_role", "content_embedding"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"  {table}: {cur.fetchone()[0]}건")

    conn.close()
    print("\n적재 완료. 다음 단계: content_embedding.embedding 컬럼을 OpenAI 임베딩으로 채우기")


if __name__ == "__main__":
    main()