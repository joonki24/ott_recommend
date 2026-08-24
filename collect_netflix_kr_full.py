"""
넷플릭스 한국 콘텐츠 전체 수집 스크립트 (상한 5000건)
- 기존 collect_netflix_kr.py는 '2021년 이후'와 '고전 상위 20편'으로 일부러 좁혀 뽑았지만,
  데이터 상한이 5000건이라면 연도·평점 제한 없이 넷플릭스에 있는 한국 콘텐츠 전체를 수집하는 게 낫다.
- with_origin_country=KR + with_watch_providers=8(넷플릭스) + watch_region=KR 조건은 그대로 유지
  (플랫폼·국가 기준은 그대로, 연도/평점 필터만 제거)

실행 전 준비: 이전과 동일 (.env에 TMDB_API_KEY 필요)
    pip install requests pandas python-dotenv
"""

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

required_variables = ["TMDB_API_KEY"]
missing_variables = [name for name in required_variables if not os.getenv(name)]
if missing_variables:
    raise RuntimeError(".env에 TMDB_API_KEY가 없습니다: " + ", ".join(missing_variables))

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
BASE_URL = "https://api.themoviedb.org/3"
NETFLIX_PROVIDER_ID = 8
WATCH_REGION = "KR"
VARIETY_GENRE_IDS = {10764, 10767}  # Reality, Talk -> 예능 판별용
MAX_TOTAL = 5000


def discover(media_type: str, extra_params: dict) -> list[dict]:
    """media_type: 'movie' or 'tv'. 연도/평점 제한 없이 전체 페이지를 순회한다."""
    results = []
    page = 1
    while True:
        params = {
            "api_key": TMDB_API_KEY,
            "with_origin_country": "KR",
            "with_watch_providers": NETFLIX_PROVIDER_ID,
            "watch_region": WATCH_REGION,
            "language": "ko-KR",
            "sort_by": "popularity.desc",
            "page": page,
            **extra_params,
        }
        resp = requests.get(f"{BASE_URL}/discover/{media_type}", params=params)
        resp.raise_for_status()
        data = resp.json()

        results.extend(data.get("results", []))
        total_pages = data.get("total_pages", 1)
        print(f"   {media_type} {page}/{min(total_pages, 500)} 페이지 ({len(results)}건 누적)")
        if page >= min(total_pages, 500):
            break
        page += 1
        time.sleep(0.2)

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


def collect_all() -> pd.DataFrame:
    """연도/평점 제한 없이 넷플릭스 한국 콘텐츠 전체를 수집한다."""
    print("영화 수집 중 (전체, 제한 없음)...")
    movies = discover("movie", {})
    movie_rows = [build_row(m, "영화") for m in movies]

    print("\nTV(드라마+예능) 수집 중 (전체, 제한 없음)...")
    tv_shows = discover("tv", {})
    tv_rows = [build_row(t, classify_tv(t)) for t in tv_shows]

    df = pd.DataFrame(movie_rows + tv_rows)
    df = df.drop_duplicates(subset="tmdb_id").reset_index(drop=True)
    return df


def cap_at_limit(df: pd.DataFrame, max_total: int) -> pd.DataFrame:
    """5000건을 넘으면 유형별 비율을 유지하면서 인기도(popularity) 순으로 자른다."""
    if len(df) <= max_total:
        return df

    ratio = max_total / len(df)
    parts = []
    for content_type, group in df.groupby("content_type"):
        n = max(1, int(len(group) * ratio))
        parts.append(group.sort_values("popularity", ascending=False).head(n))
    return pd.concat(parts, ignore_index=True)


def main():
    df = collect_all()
    print(f"\n원본 수집 총 {len(df)}건 (중복 제거 후)")
    print(df["content_type"].value_counts())

    if len(df) > MAX_TOTAL:
        print(f"\n상한({MAX_TOTAL}건) 초과 -> 유형별 비율 유지하며 인기도순으로 축소")
        df = cap_at_limit(df, MAX_TOTAL)

    df.to_csv("netflix_kr_full.csv", index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: netflix_kr_full.csv ({len(df)}건)")
    print(df["content_type"].value_counts())

    print("\n⚠️ 다음 단계:")
    print("- 이 결과는 genre_ids(코드)만 있고 runtime/episode_count가 없음")
    print("- enrich_netflix_content.py 로직(장르 매핑 + 상세 조회)을 이 파일에 맞춰 재실행 필요")
    print("- 건수가 많아 상세 조회(runtime/episode_count) API 호출에 시간이 오래 걸릴 수 있음")


if __name__ == "__main__":
    main()