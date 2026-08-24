"""
넷플릭스 콘텐츠 보강 스크립트 (netflix_kr_full.csv 전용)
- 입력: netflix_kr_full.csv (collect_netflix_kr_full.py 결과물, 연도/평점 제한 없이 수집한 전체)
- 처리:
    1) genre_ids(숫자 코드) → genre(사람이 읽는 텍스트)로 매핑
    2) runtime(영화) / episode_count(드라마·예능) 상세 조회로 보강
    3) 설계서 3번 섹션 출력 스키마에 맞는 최종 CSV 생성
- 출력: netflix_kr_final.csv
  컬럼: title, content_type, genre, runtime, episode_count, release_year, tmdb_id

실행 전 준비: 이전 collect_netflix_kr_full.py와 동일 (.env에 TMDB_API_KEY 필요)
    pip install requests pandas python-dotenv

참고: 건수가 1,874건이라 상세 조회(4단계) API 호출이 1,874번 발생합니다.
      0.2초 간격으로 호출하므로 총 6~7분 정도 예상됩니다. 다른 작업과 병행하며 기다리세요.
"""

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.environ["TMDB_API_KEY"]
BASE_URL = "https://api.themoviedb.org/3"
NETFLIX_PROVIDER_ID = 8
WATCH_REGION = "KR"
VARIETY_GENRE_IDS = {10764, 10767}


# ── 1단계: 장르 코드 → 이름 매핑 테이블 준비 ────────────
def load_genre_map() -> dict[int, str]:
    genre_map = {}
    for media_type in ["movie", "tv"]:
        resp = requests.get(
            f"{BASE_URL}/genre/{media_type}/list",
            params={"api_key": TMDB_API_KEY, "language": "ko-KR"},
        )
        resp.raise_for_status()
        for g in resp.json()["genres"]:
            genre_map[g["id"]] = g["name"]
    return genre_map


def genre_ids_to_text(genre_ids, genre_map: dict[int, str]) -> str:
    if isinstance(genre_ids, str):  # CSV에서 읽으면 문자열 "[35, 80, 53]" 형태
        genre_ids = eval(genre_ids)  # 안전한 리스트 리터럴만 오므로 ast.literal_eval 권장
    names = [genre_map.get(gid, "") for gid in genre_ids]
    return ", ".join([n for n in names if n])


# ── 2단계: 상세 정보(러닝타임/회차) 조회 ────────────────
def fetch_detail(tmdb_id: int, content_type: str) -> dict:
    media_type = "movie" if content_type == "영화" else "tv"
    resp = requests.get(
        f"{BASE_URL}/{media_type}/{tmdb_id}",
        params={"api_key": TMDB_API_KEY, "language": "ko-KR"},
    )
    resp.raise_for_status()
    data = resp.json()
    if media_type == "movie":
        return {"runtime": data.get("runtime"), "episode_count": None}
    else:
        # TV는 에피소드 런타임 평균값과 총 에피소드 수를 함께 제공
        return {
            "runtime": (data.get("episode_run_time") or [None])[0],
            "episode_count": data.get("number_of_episodes"),
        }


def enrich_with_details(df: pd.DataFrame) -> pd.DataFrame:
    details = []
    for _, row in df.iterrows():
        try:
            d = fetch_detail(row["tmdb_id"], row["content_type"])
        except requests.HTTPError:
            d = {"runtime": None, "episode_count": None}
        details.append(d)
        time.sleep(0.2)
    detail_df = pd.DataFrame(details)
    return pd.concat([df.reset_index(drop=True), detail_df], axis=1)


# ── 3단계: 전체 실행 ────────────────────────────────────
def main():
    print("① 장르 매핑 테이블 로드 중...")
    genre_map = load_genre_map()

    print("② netflix_kr_full.csv 로드 중...")
    df = pd.read_csv("netflix_kr_full.csv")
    print(f"   -> {len(df)}건")
    print(df["content_type"].value_counts())

    print("\n③ 장르 코드 -> 텍스트 매핑 중...")
    df["genre"] = df["genre_ids"].apply(lambda ids: genre_ids_to_text(ids, genre_map))

    print("④ 러닝타임/회차 상세 조회 중 (1,874건 -> 약 6~7분 예상)...")
    df = enrich_with_details(df)

    df["release_year"] = pd.to_datetime(df["release_date"], errors="coerce").dt.year

    final = df[["title", "content_type", "genre", "runtime", "episode_count", "release_year", "tmdb_id"]]
    final.to_csv("netflix_kr_final.csv", index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: netflix_kr_final.csv ({len(final)}건)")
    print(final["content_type"].value_counts())
    print(f"\nrelease_year 결측치: {final['release_year'].isnull().sum()}건 (원본 release_date 누락분)")


if __name__ == "__main__":
    main()