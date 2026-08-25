import os
from dotenv import load_dotenv
load_dotenv()

import re
import hashlib
import numpy as np
import pandas as pd
import psycopg
import redis
import streamlit as st
from openai import OpenAI
from pgvector.psycopg import register_vector

st.set_page_config(page_title="넷플릭스 콘텐츠 추천 챗봇", layout="wide")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1024


# ============================================================
# 질문에 쓰이는 국가 표현 -> DB에 저장된 ISO 국가 코드
# ============================================================
COUNTRY_MAP = {
    "한국": "KR", "미국": "US", "일본": "JP",
    "영국": "GB", "프랑스": "FR", "중국": "CN",
}


# ============================================================
# 앱 준비 — cache_resource로 연결 1회
# ============================================================
@st.cache_resource
def get_conn():
    pw = os.environ.get("PGPASSWORD") or st.text_input("PostgreSQL 비밀번호", type="password")
    if not pw:
        st.stop()
    conn = psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname="ott_recommend",
        user=os.environ.get("PGUSER", "postgres"),
        password=pw,
        autocommit=True,
    )
    register_vector(conn)
    return conn


@st.cache_resource
def get_redis():
    return redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


@st.cache_resource
def get_openai_client():
    return OpenAI()


@st.cache_resource
def get_genre_list(_conn):
    """DB에 실제로 있는 장르 이름 목록을 미리 불러온다 (하드코딩 매핑 없이 실데이터 그대로 대조)"""
    rows = _conn.execute("SELECT genre_name FROM genre").fetchall()
    return [r[0] for r in rows]


conn = get_conn()
r = get_redis()
client = get_openai_client()
genre_list = get_genre_list(conn)


# ============================================================
# session_state 초기화
# ============================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "logs" not in st.session_state:
    st.session_state.logs = []


# ============================================================
# 조건 파악: extract_filters()
# ============================================================
def extract_filters(user_query: str) -> dict:
    """질문 문장에서 content_type·country_code·max_runtime·genre 조건을 뽑아낸다."""
    filters = {
        "content_type": None,
        "country_code": None,
        "max_runtime": None,
        "genre": None,
    }

    if "영화" in user_query:
        filters["content_type"] = "영화"
    elif "드라마" in user_query:
        filters["content_type"] = "드라마"
    elif "예능" in user_query:
        filters["content_type"] = "예능"

    for word, code in COUNTRY_MAP.items():
        if word in user_query:
            filters["country_code"] = code
            break


    # ============================================================
    # "1시간 반", "1시간", "90분", "60분 이하" 등 시간 표현 처리
    # ============================================================
    hour_match = re.search(r"(\d+)\s*시간\s*(반)?", user_query)
    minute_match = re.search(r"(\d+)\s*분", user_query)
    if hour_match:
        minutes = int(hour_match.group(1)) * 60
        if hour_match.group(2):  # "반" -> 30분 추가
            minutes += 30
        filters["max_runtime"] = minutes
    elif minute_match:
        filters["max_runtime"] = int(minute_match.group(1))


    # ============================================================
    # 장르: DB에 실제로 있는 장르명을 그대로 대조
    # ============================================================
    for genre_name in genre_list:
        if genre_name in user_query:
            filters["genre"] = genre_name
            break

    return filters


# ============================================================
# 동적 검색: search_contents()
# ============================================================
def search_contents(filters: dict, limit: int = 3):
    """파악된 조건만큼만 JOIN·WHERE를 조립해서 검색한다."""
    conditions = []
    params = []
    joins = []

    if filters["content_type"] is not None:
        conditions.append("c.content_type = %s")
        params.append(filters["content_type"])

    if filters["country_code"] is not None:
        conditions.append("c.country_code = %s")
        params.append(filters["country_code"])

    if filters["max_runtime"] is not None:
        conditions.append("c.runtime_minutes <= %s")
        params.append(filters["max_runtime"])

    if filters["genre"] is not None:
        joins.append("JOIN content_genre cg ON c.content_id = cg.content_id")
        joins.append("JOIN genre g ON cg.genre_id = g.genre_id")
        conditions.append("g.genre_name = %s")
        params.append(filters["genre"])

    join_sql = " ".join(joins)
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT DISTINCT c.content_id, c.title, c.content_type, c.runtime_minutes
        FROM content c
        {join_sql}
        {where_sql}
        ORDER BY c.content_id
        LIMIT %s
    """
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return rows


def embed_text(text: str) -> np.ndarray:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL, input=text, dimensions=EMBEDDING_DIMENSIONS,
    )
    return np.asarray(response.data[0].embedding, dtype=np.float32)


def semantic_search(q: str, top_k: int = 1):
    """필터 조건을 하나도 못 뽑았거나, 뽑은 조건으로도 결과가 없을 때의 폴백"""
    query_vector = embed_text(q)
    rows = conn.execute(
        """
        SELECT c.content_id, c.title, c.content_type,
               1 - (ce.embedding <=> %s) AS similarity
        FROM content_embedding ce
        JOIN content c ON c.content_id = ce.content_id
        ORDER BY ce.embedding <=> %s
        LIMIT %s
        """,
        (query_vector, query_vector, top_k),
    ).fetchall()
    return rows


# ============================================================
# 캐시 + 응답 조합
# ============================================================
def cache_key(q: str) -> str:
    return "cache:" + hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]


def retrieve_and_answer(q: str) -> str:
    key = cache_key(q)
    cached = r.get(key)
    if cached is not None:
        st.session_state.logs.append(f"캐시 hit: {q}")
        return cached

    st.session_state.logs.append(f"캐시 miss: {q}")

    filters = extract_filters(q)
    st.session_state.logs.append(f"조건 파악: {filters}")

    has_filter = any(v is not None for v in filters.values())
    rows = search_contents(filters) if has_filter else []

    if rows:
        content_id, title, content_type, runtime = rows[0]
        st.session_state.logs.append(f"필터 검색 적중: {title} ({content_type})")
        ans = f"[추천봇] '{title}' 어떠세요? [{content_type}] 조건에 맞춰 골랐어요."
        r.set(key, ans, ex=3600)
        st.session_state.logs.append("캐시 저장")
        return ans


    # ============================================================
    # 필터 조건이 없었거나, 조건에 맞는 게 없으면 벡터 검색으로 폴백
    # ============================================================
    st.session_state.logs.append("필터 검색 실패 → 시맨틱 검색 시도")
    results = semantic_search(q)
    if results:
        content_id, title, content_type, similarity = results[0]
        st.session_state.logs.append(f"시맨틱 검색 적중: {title} (유사도 {similarity:.3f})")
        ans = f"[추천봇] 의미가 비슷한 '{title}'을(를) 찾았어요! [{content_type}] (유사도 {similarity:.2f})"
        r.set(key, ans, ex=3600)
        st.session_state.logs.append("캐시 저장")
        return ans

    st.session_state.logs.append("검색 실패: 조건에 맞는 콘텐츠 없음")
    ans = "[추천봇] 조건에 맞는 콘텐츠를 못 찾았어요. 다른 조건으로 물어봐 주세요."
    r.set(key, ans, ex=3600)
    st.session_state.logs.append("캐시 저장")
    return ans


# ============================================================
# 본문: 추천 챗
# ============================================================
st.title("🎬 넷플릭스 콘텐츠 추천 챗봇")
st.caption("넷플릭스 한국 영화·드라마·예능 · 필터 기반 검색 · LLM 미사용")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("어떤 콘텐츠를 찾으세요? (예: 60분 이하 한국 코미디 영화)")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    answer = retrieve_and_answer(prompt)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)


# ============================================================
# 사이드바: 로그 + 유형별 통계
# ============================================================
with st.sidebar:
    st.header("📋 검색 처리 로그")
    for line in st.session_state.logs:
        st.text(line)

    st.divider()
    st.subheader("📊 콘텐츠 유형별 분포")
    type_counts = conn.execute(
        "SELECT content_type, COUNT(*) FROM content GROUP BY content_type"
    ).fetchall()
    type_df = pd.DataFrame(type_counts, columns=["유형", "건수"]).set_index("유형")
    st.bar_chart(type_df)
