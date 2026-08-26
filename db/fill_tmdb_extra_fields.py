"""
content 테이블의 poster_path, backdrop_path, vote_average, release_date를
TMDB API로 채우는 스크립트.

사전 조건:
- DB에 컬럼 4개가 이미 추가되어 있어야 함 (ALTER TABLE, DBeaver에서 먼저 실행)
- .env에 TMDB_API_KEY, PGHOST, PGPORT, PGUSER, PGPASSWORD 설정되어 있어야 함

실행:
    cd db
    python fill_tmdb_extra_fields.py
"""
import os
import time

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
TMDB_BASE = "https://api.themoviedb.org/3"

DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": "ott_recommend",
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ["PGPASSWORD"],
}

# content_type -> TMDB 엔드포인트 매핑
TYPE_TO_ENDPOINT = {
    "영화": "movie",
    "드라마": "tv",
    "예능": "tv",
}


def fetch_tmdb_detail(tmdb_id: int, endpoint: str) -> dict | None:
    """TMDB API에서 상세 정보 조회. 실패 시 None 반환."""
    url = f"{TMDB_BASE}/{endpoint}/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "language": "ko-KR"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"  [실패] tmdb_id={tmdb_id} ({endpoint}) status={resp.status_code}")
            return None
        return resp.json()
    except requests.RequestException as e:
        print(f"  [예외] tmdb_id={tmdb_id} ({endpoint}) {e}")
        return None


def extract_fields(data: dict, endpoint: str) -> dict:
    """엔드포인트별로 다른 필드명을 통일된 딕셔너리로 변환."""
    poster_path = data.get("poster_path")
    backdrop_path = data.get("backdrop_path")
    vote_average = data.get("vote_average")

    if endpoint == "movie":
        release_date = data.get("release_date") or None
    else:  # tv (드라마, 예능)
        release_date = data.get("first_air_date") or None

    # 빈 문자열은 NULL로 처리
    if release_date == "":
        release_date = None

    return {
        "poster_path": poster_path,
        "backdrop_path": backdrop_path,
        "vote_average": vote_average,
        "release_date": release_date,
    }


def main():
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT content_id, tmdb_id, content_type FROM content ORDER BY content_id")
    rows = cur.fetchall()
    print(f"총 {len(rows)}건 처리 시작")

    success_count = 0
    fail_count = 0
    skip_count = 0

    for i, (content_id, tmdb_id, content_type) in enumerate(rows, 1):
        endpoint = TYPE_TO_ENDPOINT.get(content_type)
        if endpoint is None or tmdb_id is None:
            print(f"[{i}/{len(rows)}] content_id={content_id} 건너뜀 "
                  f"(content_type={content_type}, tmdb_id={tmdb_id})")
            skip_count += 1
            continue

        data = fetch_tmdb_detail(tmdb_id, endpoint)
        if data is None:
            fail_count += 1
            time.sleep(0.05)
            continue

        fields = extract_fields(data, endpoint)

        cur.execute(
            """
            UPDATE content
            SET poster_path = %(poster_path)s,
                backdrop_path = %(backdrop_path)s,
                vote_average = %(vote_average)s,
                release_date = %(release_date)s
            WHERE content_id = %(content_id)s
            """,
            {**fields, "content_id": content_id},
        )
        success_count += 1

        if i % 50 == 0:
            conn.commit()
            print(f"[{i}/{len(rows)}] 진행 중... (성공 {success_count}, 실패 {fail_count})")

        # TMDB rate limit 여유 있게 대응 (초당 약 20건)
        time.sleep(0.05)

    conn.commit()
    cur.close()
    conn.close()

    print("\n===== 완료 =====")
    print(f"성공: {success_count}건")
    print(f"실패: {fail_count}건")
    print(f"건너뜀: {skip_count}건")


if __name__ == "__main__":
    main()
