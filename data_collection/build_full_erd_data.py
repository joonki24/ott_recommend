"""
ERD 7개 테이블용 데이터 전체 추출 스크립트
- 입력: netflix_kr_full.csv (collect_netflix_kr_full.py 결과물)
- 각 콘텐츠마다 TMDB API를 3종류 호출:
    1) 상세정보(detail) - overview, country_code, runtime, season_count, episode_count
       + TV는 created_by(제작진)도 이 응답에 포함 -> 별도 호출 불필요
    2) 키워드(keywords) - CONTENT_TAG / CONTENT_TAG_MAP용
    3) 출연진(credits) - CONTENT_PERSON_ROLE용 (배우 상위 5명 + 영화 감독)
- 출력: schema.sql의 7개 테이블에 맞춘 CSV 8개
    content.csv, genre.csv, content_genre.csv,
    content_tag.csv, content_tag_map.csv,
    person.csv, content_person_role.csv,
    content_embedding.csv (embedding_text만 채움, embedding은 PostgreSQL 단계에서 채움)

⚠️ 소요 시간: 1,874건 x 3회 호출 = 약 5,600회 API 호출, 0.2초 간격 기준 약 19분 예상

실행 전 준비: pip install requests pandas python-dotenv
             .env에 TMDB_API_KEY 필요
"""

import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.environ["TMDB_API_KEY"]
BASE_URL = "https://api.themoviedb.org/3"
SLEEP = 0.2

TOP_CAST_N = 5


def media_type_of(content_type: str) -> str:
    return "movie" if content_type == "영화" else "tv"


# ── 1. 장르 마스터 ────────────────────────────────────
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


# ── 2. 상세정보 (CONTENT 테이블용) ────────────────────
def fetch_detail(tmdb_id: int, content_type: str) -> dict:
    media_type = media_type_of(content_type)
    resp = requests.get(
        f"{BASE_URL}/{media_type}/{tmdb_id}",
        params={"api_key": TMDB_API_KEY, "language": "ko-KR"},
    )
    resp.raise_for_status()
    data = resp.json()

    countries = data.get("production_countries") or []
    country_code = countries[0]["iso_3166_1"] if countries else None

    if media_type == "movie":
        return {
            "overview": data.get("overview"),
            "country_code": country_code,
            "runtime_minutes": data.get("runtime"),
            "season_count": None,
            "episode_count": None,
            "created_by": [],  # 영화는 제작진 정보 없음 (감독은 credits에서 처리)
        }
    else:
        return {
            "overview": data.get("overview"),
            "country_code": country_code,
            "runtime_minutes": (data.get("episode_run_time") or [None])[0],
            "season_count": data.get("number_of_seasons"),
            "episode_count": data.get("number_of_episodes"),
            "created_by": data.get("created_by") or [],  # [{id, name}, ...]
        }


# ── 3. 키워드 (CONTENT_TAG용) ─────────────────────────
def fetch_keywords(tmdb_id: int, content_type: str) -> list[dict]:
    media_type = media_type_of(content_type)
    resp = requests.get(
        f"{BASE_URL}/{media_type}/{tmdb_id}/keywords",
        params={"api_key": TMDB_API_KEY},
    )
    resp.raise_for_status()
    data = resp.json()
    # 영화는 'keywords' 키, TV는 'results' 키를 사용 (TMDB API 스펙 차이)
    return data.get("keywords") or data.get("results") or []


# ── 4. 출연진 (CONTENT_PERSON_ROLE용) ─────────────────
def fetch_credits(tmdb_id: int, content_type: str) -> dict:
    media_type = media_type_of(content_type)
    resp = requests.get(
        f"{BASE_URL}/{media_type}/{tmdb_id}/credits",
        params={"api_key": TMDB_API_KEY, "language": "ko-KR"},
    )
    resp.raise_for_status()
    data = resp.json()

    cast = data.get("cast", [])[:TOP_CAST_N]
    crew = data.get("crew", [])
    directors = [c for c in crew if c.get("job") == "Director"]

    return {"cast": cast, "directors": directors}


# ── 5. 전체 처리 ───────────────────────────────────────
def main():
    print("① 장르 매핑 테이블 로드...")
    genre_map = load_genre_map()

    print("② netflix_kr_full.csv 로드...")
    source_df = pd.read_csv("netflix_kr_full.csv")
    print(f"   -> {len(source_df)}건")

    content_rows = []
    content_genre_rows = []
    content_embedding_rows = []

    tag_dict = {}   # tmdb_keyword_id -> {tag_id, tag_name}
    tag_map_rows = []

    person_dict = {}  # tmdb_person_id -> {person_id, person_name}
    person_role_rows = []

    next_tag_id = 1
    next_person_id = 1

    total = len(source_df)
    for i, row in source_df.iterrows():
        content_id = i + 1  # 1부터 순차 부여 (BIGSERIAL과 맞춤)
        tmdb_id = int(row["tmdb_id"])
        content_type = row["content_type"]

        if (i + 1) % 50 == 0 or i == 0:
            print(f"   진행 {i + 1}/{total}: {row['title']}")

        # -- 상세정보 --
        try:
            detail = fetch_detail(tmdb_id, content_type)
        except requests.HTTPError:
            detail = {
                "overview": None, "country_code": None, "runtime_minutes": None,
                "season_count": None, "episode_count": None, "created_by": [],
            }
        time.sleep(SLEEP)

        content_rows.append({
            "content_id": content_id,
            "tmdb_id": tmdb_id,
            "title": row["title"],
            "content_type": content_type,
            "country_code": detail["country_code"],
            "runtime_minutes": detail["runtime_minutes"],
            "season_count": detail["season_count"],
            "episode_count": detail["episode_count"],
            "overview": detail["overview"],
        })

        # -- 장르 연결 (genre_ids는 CSV에 "[35, 80, 53]" 형태 문자열) --
        try:
            genre_ids = eval(row["genre_ids"]) if isinstance(row["genre_ids"], str) else row["genre_ids"]
        except Exception:
            genre_ids = []
        for gid in genre_ids:
            if gid in genre_map:
                content_genre_rows.append({"content_id": content_id, "genre_id": gid})

        # -- 임베딩용 텍스트 (embedding 값 자체는 PostgreSQL 단계에서 채움) --
        genre_text = ", ".join([genre_map.get(g, "") for g in genre_ids])
        embedding_text = f"{row['title']} {content_type} {genre_text} {detail['overview'] or ''}".strip()
        content_embedding_rows.append({
            "content_id": content_id,
            "embedding_text": embedding_text,
        })

        # -- 키워드(태그) --
        try:
            keywords = fetch_keywords(tmdb_id, content_type)
        except requests.HTTPError:
            keywords = []
        time.sleep(SLEEP)

        for kw in keywords:
            kw_id, kw_name = kw.get("id"), kw.get("name")
            if kw_id is None:
                continue
            if kw_id not in tag_dict:
                tag_dict[kw_id] = {"tag_id": next_tag_id, "tag_name": kw_name}
                next_tag_id += 1
            tag_map_rows.append({"content_id": content_id, "tag_id": tag_dict[kw_id]["tag_id"]})

        # -- 출연진/감독/제작진 --
        try:
            credits = fetch_credits(tmdb_id, content_type)
        except requests.HTTPError:
            credits = {"cast": [], "directors": []}
        time.sleep(SLEEP)

        def register_person(tmdb_person_id, name):
            nonlocal next_person_id
            if tmdb_person_id not in person_dict:
                person_dict[tmdb_person_id] = {"person_id": next_person_id, "person_name": name}
                next_person_id += 1
            return person_dict[tmdb_person_id]["person_id"]

        for actor in credits["cast"]:
            pid = register_person(actor["id"], actor["name"])
            person_role_rows.append({"content_id": content_id, "person_id": pid, "role_type": "배우"})

        for director in credits["directors"]:
            pid = register_person(director["id"], director["name"])
            person_role_rows.append({"content_id": content_id, "person_id": pid, "role_type": "감독"})

        for creator in detail["created_by"]:
            pid = register_person(creator["id"], creator["name"])
            person_role_rows.append({"content_id": content_id, "person_id": pid, "role_type": "PD"})

    # ── 저장 ────────────────────────────────────────────
    pd.DataFrame(content_rows).to_csv("content.csv", index=False, encoding="utf-8-sig")

    genre_rows = [{"genre_id": gid, "genre_name": name} for gid, name in genre_map.items()]
    pd.DataFrame(genre_rows).to_csv("genre.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(content_genre_rows).drop_duplicates().to_csv("content_genre.csv", index=False, encoding="utf-8-sig")

    tag_rows = [
        {"tag_id": v["tag_id"], "source_keyword_id": kw_id, "tag_name": v["tag_name"], "source_name": "tmdb_keyword"}
        for kw_id, v in tag_dict.items()
    ]
    pd.DataFrame(tag_rows).to_csv("content_tag.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(tag_map_rows).drop_duplicates().to_csv("content_tag_map.csv", index=False, encoding="utf-8-sig")

    person_rows = [
        {"person_id": v["person_id"], "tmdb_person_id": pid, "person_name": v["person_name"]}
        for pid, v in person_dict.items()
    ]
    pd.DataFrame(person_rows).to_csv("person.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(person_role_rows).drop_duplicates().to_csv("content_person_role.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(content_embedding_rows).to_csv("content_embedding.csv", index=False, encoding="utf-8-sig")

    print("\n저장 완료:")
    print(f"  content.csv            {len(content_rows)}건")
    print(f"  genre.csv               {len(genre_rows)}건")
    print(f"  content_genre.csv       {len(content_genre_rows)}건")
    print(f"  content_tag.csv         {len(tag_rows)}건")
    print(f"  content_tag_map.csv     {len(tag_map_rows)}건")
    print(f"  person.csv              {len(person_rows)}건")
    print(f"  content_person_role.csv {len(person_role_rows)}건")
    print(f"  content_embedding.csv   {len(content_embedding_rows)}건 (embedding 컬럼은 비어있음)")


if __name__ == "__main__":
    main()
