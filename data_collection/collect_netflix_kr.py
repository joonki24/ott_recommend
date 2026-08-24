"""
넷플릭스 한국 콘텐츠 수집 스크립트 (TMDB API + .env)
- 강의 노트북(pgvector 실습)과 동일한 dotenv 패턴 사용
- 목적: '2021년 이후 최근작 전체' + '명작(고전) 큐레이션 20편 내외' 자동 수집
- TMDB의 with_watch_providers=8(넷플릭스) + watch_region=KR 필터로
  "지금 실제로 넷플릭스 한국에서 볼 수 있는 작품"만 걸러낸다.

── 실행 전 준비 ──────────────────────────────────────
1. pip install requests pandas python-dotenv
2. 이 파일과 같은 폴더에 .env 파일을 만들고 아래처럼 작성:
       TMDB_API_KEY=발급받은_API_키
   (.env.example 파일을 복사해서 .env로 이름만 바꾸고 키를 채워 넣어도 됩니다)
3. .env는 절대 GitHub에 올리지 않기 — .gitignore에 .env 추가 권장

── 실행 ──────────────────────────────────────────────
python collect_netflix_kr.py
"""

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

# ── 1단계: 환경 준비 ──────────────────────────────────
load_dotenv()

required_variables = ["TMDB_API_KEY"]
missing_variables = [name for name in required_variables if not os.getenv(name)]
if missing_variables:
    raise RuntimeError(
        ".env 또는 환경변수에 필수 값이 없습니다: " + ", ".join(missing_variables)
        + "\n-> .env 파일에 TMDB_API_KEY=발급받은키 를 추가하세요."
    )

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
BASE_URL = "https://api.themoviedb.org/3"
NETFLIX_PROVIDER_ID = 8  # TMDB 내부 고정 ID (넷플릭스)
WATCH_REGION = "KR"
VARIETY_GENRE_IDS = {10764, 10767}  # Reality, Talk -> 예능 판별용

print("TMDB API 키 확인 완료")
print("대상 지역:", WATCH_REGION, "/ 대상 플랫폼: 넷플릭스")


# ── 2단계: 공통 함수 정의 ─────────────────────────────
def discover(media_type: str, extra_params: dict) -> list[dict]:
    """media_type: 'movie' or 'tv'. 모든 페이지를 순회하며 결과를 모은다."""
    results = []
    page = 1
    while True:
        params = {
            "api_key": TMDB_API_KEY,
            "with_origin_country": "KR",
            "with_watch_providers": NETFLIX_PROVIDER_ID,
            "watch_region": WATCH_REGION,
            "language": "ko-KR",  # 한글 제목으로 수신
            "page": page,
            **extra_params,
        }
        resp = requests.get(f"{BASE_URL}/discover/{media_type}", params=params)
        resp.raise_for_status()
        data = resp.json()

        results.extend(data.get("results", []))
        total_pages = data.get("total_pages", 1)
        if page >= min(total_pages, 500):  # TMDB는 500페이지까지만 허용
            break
        page += 1
        time.sleep(0.25)  # API rate limit 배려

    return results


def classify_tv(item: dict) -> str:
    genre_ids = set(item.get("genre_ids", []))
    return "예능" if genre_ids & VARIETY_GENRE_IDS else "드라마"


def build_row(item: dict, content_type: str) -> dict:
    return {
        "title": item.get("title") or item.get("name"),
        "content_type": content_type,
        "genre_ids": item.get("genre_ids"),
        "release_date": item.get("release_date") or item.get("first_air_date"),
        "vote_average": item.get("vote_average"),
        "vote_count": item.get("vote_count"),
        "popularity": item.get("popularity"),
        "tmdb_id": item.get("id"),
    }


# ── 3단계: 최근작(2021년 이후) 수집 ────────────────────
def collect_recent(since_year: int = 2021) -> pd.DataFrame:
    rows = []

    movies = discover(
        "movie",
        {"primary_release_date.gte": f"{since_year}-01-01", "sort_by": "popularity.desc"},
    )
    rows += [build_row(m, "영화") for m in movies]

    tv_shows = discover(
        "tv",
        {"first_air_date.gte": f"{since_year}-01-01", "sort_by": "popularity.desc"},
    )
    rows += [build_row(t, classify_tv(t)) for t in tv_shows]

    return pd.DataFrame(rows)


# ── 4단계: 명작(고전) 큐레이션 후보 수집 ────────────────
def collect_classics(before_year: int = 2021, per_type: int = 20) -> pd.DataFrame:
    rows = []

    movies = discover(
        "movie",
        {
            "primary_release_date.lte": f"{before_year - 1}-12-31",
            "sort_by": "vote_average.desc",
            "vote_count.gte": 300,
        },
    )
    movie_df = pd.DataFrame([build_row(m, "영화") for m in movies])
    rows.append(movie_df.head(per_type))

    tv_shows = discover(
        "tv",
        {
            "first_air_date.lte": f"{before_year - 1}-12-31",
            "sort_by": "vote_average.desc",
            "vote_count.gte": 300,
        },
    )
    tv_df = pd.DataFrame([build_row(t, classify_tv(t)) for t in tv_shows])
    for content_type in ["드라마", "예능"]:
        rows.append(tv_df[tv_df["content_type"] == content_type].head(per_type))

    return pd.concat(rows, ignore_index=True)


# ── 5단계: 실행 및 저장 ────────────────────────────────
if __name__ == "__main__":
    print("\n① 최근작(2021년 이후) 수집 중...")
    recent = collect_recent(since_year=2021)
    print(f"   -> {len(recent)}건 수집")
    print(recent["content_type"].value_counts())
    recent.to_csv("netflix_kr_recent.csv", index=False, encoding="utf-8-sig")
    print("   저장 완료: netflix_kr_recent.csv")

    print("\n② 명작(고전) 큐레이션 후보 수집 중 (유형당 20편)...")
    classic = collect_classics(before_year=2021, per_type=20)
    print(f"   -> {len(classic)}건 수집")
    print(classic["content_type"].value_counts())
    classic.to_csv("netflix_kr_classic.csv", index=False, encoding="utf-8-sig")
    print("   저장 완료: netflix_kr_classic.csv")

    print("\n⚠️ 확인 필요:")
    print("- 예능(Reality/Talk 장르) 자동 분류는 TMDB 장르 태그 기준 → 검수 권장")
    print("- classic 결과는 vote_count>=300 기준 상위 평점작 후보 → 팀이 최종 선별 필요")
