"""
content 테이블에 poster_path, backdrop_path, vote_average, release_date
컬럼을 추가하는 스크립트. DBeaver 대신 터미널에서 바로 실행.

사전 조건:
- .env에 PGHOST, PGPORT, PGUSER, PGPASSWORD 설정되어 있어야 함

실행:
    cd db
    python add_extra_columns.py
"""
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": "ott_recommend",
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ["PGPASSWORD"],
}

ALTER_SQL = """
ALTER TABLE content
  ADD COLUMN IF NOT EXISTS poster_path VARCHAR(255),
  ADD COLUMN IF NOT EXISTS backdrop_path VARCHAR(255),
  ADD COLUMN IF NOT EXISTS vote_average NUMERIC(3,1),
  ADD COLUMN IF NOT EXISTS release_date DATE;
"""

CHECK_SQL = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'content'
ORDER BY column_name;
"""


def main():
    print(f"DB 접속 시도: host={DB_CONFIG['host']} port={DB_CONFIG['port']} dbname={DB_CONFIG['dbname']}")

    try:
        conn = psycopg.connect(**DB_CONFIG)
    except Exception as e:
        print(f"\n[접속 실패] {e}")
        print("-> .env의 PGHOST/PGPORT/PGUSER/PGPASSWORD 값을 확인하세요.")
        return

    print("접속 성공. ALTER TABLE 실행 중...")

    try:
        with conn.cursor() as cur:
            cur.execute(ALTER_SQL)
        conn.commit()
        print("ALTER TABLE 성공 (또는 이미 존재해서 건너뜀).")
    except Exception as e:
        conn.rollback()
        print(f"\n[ALTER TABLE 실패] {e}")
        conn.close()
        return

    print("\n현재 content 테이블 컬럼 목록:")
    with conn.cursor() as cur:
        cur.execute(CHECK_SQL)
        rows = cur.fetchall()
        for name, dtype in rows:
            print(f"  - {name}: {dtype}")

    target_cols = {"poster_path", "backdrop_path", "vote_average", "release_date"}
    found_cols = {name for name, _ in rows}

    if target_cols.issubset(found_cols):
        print("\n[확인 완료] 4개 컬럼이 모두 정상적으로 존재합니다.")
    else:
        missing = target_cols - found_cols
        print(f"\n[경고] 아직 없는 컬럼: {missing}")

    conn.close()


if __name__ == "__main__":
    main()
