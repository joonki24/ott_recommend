import os
import re

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

from google import genai
from google.genai import types


# --------------------------------------------------
# 환경 설정
# --------------------------------------------------

load_dotenv()

pw = os.environ["PGPASSWORD"]
gemini_api_key = os.environ["GEMINI_API_KEY"]

DB_NAME = "ott_recommend"

# 각자 Docker 포트가 다를 수 있으므로 .env 우선
DB_PORT = int(
    os.environ.get(
        "PGPORT",
        "5432"
    )
)

conn = psycopg.connect(
    host=os.getenv("PGHOST", "localhost"),
    port=DB_PORT,
    dbname=DB_NAME,
    user=os.getenv("PGUSER", "postgres"),
    password=pw
)

# Gemini Embedding 설정
embedding_model = "gemini-embedding-001"
embedding_dimensions = 1024

# --------------------------------------------------
# DB 연결
# --------------------------------------------------

conn = psycopg.connect(
    host=os.getenv("PGHOST", "localhost"),
    port=DB_PORT,
    dbname=DB_NAME,
    user=os.getenv("PGUSER", "postgres"),
    password=pw
)

register_vector(conn)


# --------------------------------------------------
# DB 기준 장르 / 인물 목록 가져오기
# --------------------------------------------------

def get_genre_list():

    rows = conn.execute(
        "SELECT genre_name FROM genre"
    ).fetchall()

    return [
        row[0]
        for row in rows
    ]


genre_list = get_genre_list()


def get_person_names():

    rows = conn.execute(
        "SELECT person_name FROM person"
    ).fetchall()

    return [
        row[0]
        for row in rows
    ]


person_names = get_person_names()


# --------------------------------------------------
# Gemini 연결
# --------------------------------------------------

client = genai.Client(
    api_key=gemini_api_key
)


# --------------------------------------------------
# 1. 자연어 질문 → SQL 조건 추출
# --------------------------------------------------

def extract_filters(
    user_query,
    genre_list,
    person_names
):

    filters = {
        "content_type": None,
        "country_code": None,
        "max_runtime": None,
        "genre": None,
        "person_name": None,
        "role_type": None
    }


    # 콘텐츠 유형
    if "영화" in user_query:
        filters["content_type"] = "영화"

    elif "드라마" in user_query:
        filters["content_type"] = "드라마"

    elif "예능" in user_query:
        filters["content_type"] = "예능"


    # 국가
    if "한국" in user_query:
        filters["country_code"] = "KR"

    elif "미국" in user_query:
        filters["country_code"] = "US"

    elif "일본" in user_query:
        filters["country_code"] = "JP"


    # 러닝타임
    runtime_match = re.search(
        r"(\d+)\s*분\s*이하",
        user_query
    )

    hour_match = re.search(
        r"(\d+)\s*시간\s*이하",
        user_query
    )


    if hour_match:

        hours = int(
            hour_match.group(1)
        )

        filters["max_runtime"] = (
            hours * 60
        )


    if runtime_match:

        filters["max_runtime"] = int(
            runtime_match.group(1)
        )


    # 장르
    for genre_name in genre_list:

        if genre_name in user_query:

            filters["genre"] = (
                genre_name
            )

            break


    # 인물
    for person_name in person_names:

        if person_name in user_query:

            filters["person_name"] = (
                person_name
            )

            break


    # 사람 이름만 있으면 기본 배우
    if filters["person_name"] is not None:

        filters["role_type"] = "배우"


        # 감독이라고 명시한 경우
        if "감독" in user_query:

            filters["role_type"] = (
                "감독"
            )


    return filters


# --------------------------------------------------
# 2. SQL 조건으로 후보 콘텐츠 검색
# --------------------------------------------------

def search_contents(filters):

    conditions = []
    params = []
    joins = []


    # 콘텐츠 유형
    if filters["content_type"] is not None:

        conditions.append(
            "c.content_type = %s"
        )

        params.append(
            filters["content_type"]
        )


    # 국가
    if filters["country_code"] is not None:

        conditions.append(
            "c.country_code = %s"
        )

        params.append(
            filters["country_code"]
        )


    # 러닝타임
    if filters["max_runtime"] is not None:

        conditions.append(
            "c.runtime_minutes <= %s"
        )

        params.append(
            filters["max_runtime"]
        )


    # 장르
    if filters["genre"] is not None:

        joins.append(
            "JOIN content_genre cg "
            "ON c.content_id = cg.content_id"
        )

        joins.append(
            "JOIN genre g "
            "ON cg.genre_id = g.genre_id"
        )

        conditions.append(
            "g.genre_name = %s"
        )

        params.append(
            filters["genre"]
        )


    # 인물
    if filters["person_name"] is not None:

        joins.append(
            "JOIN content_person_role cpr "
            "ON c.content_id = cpr.content_id"
        )

        joins.append(
            "JOIN person p "
            "ON cpr.person_id = p.person_id"
        )

        conditions.append(
            "p.person_name = %s"
        )

        params.append(
            filters["person_name"]
        )


    # 역할
    if filters["role_type"] is not None:

        conditions.append(
            "cpr.role_type = %s"
        )

        params.append(
            filters["role_type"]
        )


    join_sql = " ".join(
        joins
    )


    if conditions:

        where_sql = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    else:

        where_sql = ""


    sql = f"""
        SELECT
            c.content_id,
            c.title,
            c.content_type,
            c.runtime_minutes,
            c.overview

        FROM content c

        {join_sql}

        {where_sql}
    """


    with conn.cursor() as cur:

        cur.execute(
            sql,
            params
        )

        rows = cur.fetchall()


    return rows


# --------------------------------------------------
# 3. Gemini Embedding 생성
# --------------------------------------------------

def create_embedding(text):

    response = (
        client.models.embed_content(
            model=embedding_model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=(
                    embedding_dimensions
                )
            )
        )
    )


    return (
        response
        .embeddings[0]
        .values
    )

def create_embeddings(texts):

    response = client.models.embed_content(
        model=embedding_model,
        contents=texts,
        config=types.EmbedContentConfig(
            output_dimensionality=(
                embedding_dimensions
            )
        )
    )

    return [
        embedding.values
        for embedding in response.embeddings
    ]

# --------------------------------------------------
# Cosine Similarity 계산
# --------------------------------------------------
def cosine_similarity(
    vector_a,
    vector_b
):

    dot_product = sum(
        a * b
        for a, b
        in zip(
            vector_a,
            vector_b
        )
    )

    norm_a = sum(
        a * a
        for a in vector_a
    ) ** 0.5

    norm_b = sum(
        b * b
        for b in vector_b
    ) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return (
        dot_product
        / (norm_a * norm_b)
    )

# --------------------------------------------------
# 4. SQL 조건 제거
#    → Embedding용 의미 문장 생성
# --------------------------------------------------

def extract_semantic_query(
    user_query,
    person_names
):

    semantic_query = (
        user_query
    )


    explicit_keywords = [
        "영화",
        "드라마",
        "예능",
        "한국",
        "미국",
        "일본",
        "액션",
        "코미디",
        "스릴러",
        "SF"
    ]


    # SQL 처리 명확 조건 제거
    for keyword in explicit_keywords:

        semantic_query = (
            semantic_query.replace(
                keyword,
                ""
            )
        )


    # 사람 이름 제거
    for person_name in person_names:

        semantic_query = (
            semantic_query.replace(
                person_name,
                ""
            )
        )


    # 러닝타임 표현 제거
    semantic_query = re.sub(
        r"\d+\s*분\s*이하",
        "",
        semantic_query
    )

    semantic_query = re.sub(
        r"\d+\s*시간\s*이하",
        "",
        semantic_query
    )


    # 추천 문장 표현 제거
    semantic_query = (
        semantic_query.replace(
            "중에서",
            ""
        )
    )

    semantic_query = (
        semantic_query.replace(
            "추천해줘",
            ""
        )
    )


    # 사람 역할 관련 표현 제거
    semantic_query = re.sub(
        r"(나오|출연|등장|연기|감독)"
        r"(하는|하신|한|했던|이)?",
        "",
        semantic_query
    )


    # 여러 공백 → 한 칸
    semantic_query = re.sub(
        r"\s+",
        " ",
        semantic_query
    )


    return (
        semantic_query.strip()
    )


# --------------------------------------------------
# 5. SQL 후보 내 pgvector 의미검색
# --------------------------------------------------

def search_by_embedding(
    candidate_ids,
    semantic_query
):

    # --------------------------------------------------
    # 중요
    #
    # Gemini 질문 Embedding과 비교하려면
    # DB 콘텐츠 Embedding도 반드시
    # Gemini 모델로 생성된 벡터여야 함.
    # --------------------------------------------------

    # 사용자 질문 Gemini Embedding
    query_embedding = (
        create_embedding(
            semantic_query
        )
    )


    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT
                c.content_id,
                c.title,
                c.content_type,
                c.runtime_minutes,

                STRING_AGG(
                    g.genre_name,
                    ', '
                ) AS genres,

                c.overview,
                c.poster_path,
                c.vote_average,
                c.release_date,

                ce.embedding
                    <=> %s::vector
                    AS distance

            FROM content_embedding ce

            JOIN content c
                ON ce.content_id
                = c.content_id

            LEFT JOIN content_genre cg
                ON c.content_id
                = cg.content_id

            LEFT JOIN genre g
                ON cg.genre_id
                = g.genre_id

            WHERE
                c.content_id
                    = ANY(%s::bigint[])

                AND ce.embedding
                    IS NOT NULL

            GROUP BY
                c.content_id,
                c.title,
                c.content_type,
                c.runtime_minutes,
                c.overview,
                c.poster_path,
                c.vote_average,
                c.release_date,
                ce.embedding

            ORDER BY
                distance ASC

            """,
            (
                query_embedding,
                candidate_ids
            )
        )


        vector_results = (
            cur.fetchall()
        )


    return vector_results


# --------------------------------------------------
# 6. Embedding 검색을 하지 않는 경우
#    SQL 콘텐츠 상세정보 조회
# --------------------------------------------------

def get_content_details(
    candidate_ids
):

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT
                c.content_id,
                c.title,
                c.content_type,
                c.runtime_minutes,

                STRING_AGG(
                    g.genre_name,
                    ', '
                ) AS genres,

                c.overview,
                c.poster_path,
                c.vote_average,
                c.release_date,

                NULL::double precision
                    AS distance

            FROM content c

            LEFT JOIN content_genre cg
                ON c.content_id
                = cg.content_id

            LEFT JOIN genre g
                ON cg.genre_id
                = g.genre_id

            WHERE
                c.content_id
                    = ANY(%s::bigint[])

            GROUP BY
                c.content_id,
                c.title,
                c.content_type,
                c.runtime_minutes,
                c.overview,
                c.poster_path,
                c.vote_average,
                c.release_date

            ORDER BY
                c.content_id

            """,
            (
                candidate_ids,
            )
        )


        detail_results = (
            cur.fetchall()
        )


    return detail_results


# --------------------------------------------------
# 7. 최종 Gemini 추천 함수
# --------------------------------------------------

def recommend(
    user_query,
    top_n=3
):

    # SQL 조건 추출
    filters = extract_filters(
        user_query,
        genre_list,
        person_names
    )


    # SQL 후보 검색
    results = search_contents(
        filters
    )


    # 후보 ID 추출
    candidate_ids = [
        row[0]
        for row in results
    ]


    # 후보 없음
    if not candidate_ids:

        return []


    # Embedding용 의미 표현 추출
    semantic_query = (
        extract_semantic_query(
            user_query,
            person_names
        )
    )


    # --------------------------------------------------
    # 의미 표현이 없으면
    # Gemini Embedding 불필요
    # → SQL 결과만 반환
    # --------------------------------------------------

    if not semantic_query:

        final_results = (
            get_content_details(
                candidate_ids
            )
        )

        return (
            final_results[:top_n]
        )


    # --------------------------------------------------
    # 의미 표현이 있으면
    # Gemini + pgvector 의미검색
    # --------------------------------------------------

    vector_results = (
        search_by_embedding(
            candidate_ids,
            semantic_query
        )
    )


    return (
        vector_results[:top_n]
    )


print("DB 연결:", conn.info.dbname)
print(
    "content 수:",
    conn.execute(
        "SELECT COUNT(*) FROM content"
    ).fetchone()[0]
)

# # --------------------------------------------------
# # 직접 실행 테스트
# # --------------------------------------------------

if __name__ == "__main__":

    user_query = (
        "한국 액션 영화 중에서 "
        "통쾌한 거 추천해줘"
    )


    try:

        results = recommend(
            user_query,
            top_n=3
        )


        if not results:

            print(
                "조건에 맞는 "
                "콘텐츠가 없습니다."
            )


        else:

            for row in results:

                print(row)


    except Exception as e:

        print(
            "Gemini 추천 테스트 오류:"
        )

        print(e)


    finally:

        conn.close()