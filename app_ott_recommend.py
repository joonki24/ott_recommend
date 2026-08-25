import os
from dotenv import load_dotenv
load_dotenv()   # .env의 PGPASSWORD 등을 앱도 읽는다

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


# ===== [그룹 A] 앱 준비 — cache_resource로 연결 1회 =====
@st.cache_resource
def get_conn():
    # 앱은 stdin 없음 → PGPASSWORD env 우선, 없으면 화면 입력(하드코딩 금지)
    pw = os.environ.get("PGPASSWORD") or st.text_input("PostgreSQL 비밀번호", type="password")
    if not pw:
        st.stop()
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname="ott_recommend",
        user=os.environ.get("PGUSER", "postgres"),
        password=pw,
        autocommit=True,
    )


@st.cache_resource
def get_redis():
    return redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


@st.cache_resource
def get_openai_client():
    return OpenAI()


conn = get_conn()
register_vector(conn)
r = get_redis()
client = get_openai_client()


# ===== [그룹 B] session_state 초기화 =====
if "messages" not in st.session_state:
    st.session_state.messages = []
if "logs" not in st.session_state:
    st.session_state.logs = []
if "context" not in st.session_state:
    # [그룹 E] 직전 검색에서 뭘 찾아줬는지 기억해두는 자리 (LLM 없이 규칙으로 맥락 흉내)
    st.session_state.context = {"genre_keyword": None, "last_content_id": None}


# ===== [그룹 C] 캐시 키 + 검색(ILIKE JOIN → 실패 시 벡터) + 응답 조합 =====
def cache_key(q: str) -> str:
    return "cache:" + hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]


def keyword_search(q: str, genre_hint: str | None = None, exclude_id: int | None = None):
    """content + content_genre + genre 조인으로 ILIKE 검색 (장르명 또는 제목)
    genre_hint: [그룹 E] 새 질문에 장르 단어가 없으면 이전에 기억해둔 장르로 재시도할 때 씀
    exclude_id: "다른 거" 같은 후속 질문일 때 방금 보여준 콘텐츠는 다시 안 보여주려고 씀
    """
    words = [w.strip("?!.,") for w in q.split()]
    words = [w for w in words if len(w) >= 2]
    if genre_hint:
        words = words + [genre_hint]  # 새 질문 단어들 뒤에 기억해둔 장르를 추가로 시도

    for w in words:  # 앞 단어부터 차례로 시도
        row = conn.execute(
            """
            SELECT DISTINCT c.content_id, c.title, c.content_type, c.runtime_minutes
            FROM content c
            JOIN content_genre cg ON c.content_id = cg.content_id
            JOIN genre g ON cg.genre_id = g.genre_id
            WHERE (g.genre_name ILIKE %s OR c.title ILIKE %s)
              AND (%s::bigint IS NULL OR c.content_id != %s)
            LIMIT 1
            """,
            (f"%{w}%", f"%{w}%", exclude_id, exclude_id),
        ).fetchone()
        if row:
            return row, w
    return None, None  # 어느 단어도 안 걸리면 실패


def embed_text(text: str) -> np.ndarray:
    """pgvector 실습 노트북과 동일한 패턴"""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return np.asarray(response.data[0].embedding, dtype=np.float32)


def semantic_search(q: str, top_k: int = 3):
    """ILIKE가 못 찾을 때(글자는 안 겹치지만 뜻이 비슷한 경우)의 폴백"""
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


def retrieve_and_answer(q: str) -> str:
    key = cache_key(q)
    cached = r.get(key)
    if cached is not None:
        st.session_state.logs.append(f"캐시 hit: {q}")
        return cached

    st.session_state.logs.append(f"캐시 miss: {q}")

    ctx = st.session_state.context

    # 1차: 이번 질문 단어만으로 검색
    row, hit_word = keyword_search(q)

    # 2차: 실패했고 기억해둔 장르가 있으면, 그 장르를 더해서 재시도 [그룹 E]
    used_context = False
    if row is None and ctx["genre_keyword"]:
        st.session_state.logs.append(f"이번 질문만으론 실패 → 이전 맥락 '{ctx['genre_keyword']}' 적용해 재시도")
        row, hit_word = keyword_search(q, genre_hint=ctx["genre_keyword"], exclude_id=ctx["last_content_id"])
        used_context = row is not None

    if row is not None:
        content_id, title, content_type, runtime = row
        st.session_state.logs.append(
            f"ILIKE 검색 적중: {title} ({content_type}) 단어 '{hit_word}'"
            + (" (맥락 반영)" if used_context else "")
        )
        # [그룹 E] 다음 질문을 위해 이번에 찾은 장르·콘텐츠를 기억해둔다
        st.session_state.context = {"genre_keyword": hit_word, "last_content_id": content_id}

        ans = f"[추천봇] '{title}' 어떠세요? [{content_type}] 추천드려요 — '{hit_word}' 검색으로 찾았어요."
        r.set(key, ans, ex=3600)
        st.session_state.logs.append("캐시 저장")
        return ans

    # ILIKE 실패 → 벡터 검색 폴백
    st.session_state.logs.append("ILIKE 검색 실패 → 시맨틱 검색 시도")
    results = semantic_search(q, top_k=1)
    if results:
        content_id, title, content_type, similarity = results[0]
        st.session_state.logs.append(
            f"시맨틱 검색 적중: {title} ({content_type}) 유사도 {similarity:.3f}"
        )
        st.session_state.context = {"genre_keyword": None, "last_content_id": content_id}

        ans = f"[추천봇] 의미가 비슷한 '{title}'을(를) 찾았어요! [{content_type}] (유사도 {similarity:.2f})"
        r.set(key, ans, ex=3600)
        st.session_state.logs.append("캐시 저장")
        return ans

    st.session_state.logs.append("검색 실패: 조건에 맞는 콘텐츠 없음")
    ans = "[추천봇] 조건에 맞는 콘텐츠를 못 찾았어요. 다른 조건으로 물어봐 주세요."
    r.set(key, ans, ex=3600)
    st.session_state.logs.append("캐시 저장")
    return ans


# ===== 본문: 추천 챗 =====
st.title("🎬 넷플릭스 콘텐츠 추천 챗봇")
st.caption("넷플릭스 한국 영화·드라마·예능 · LLM 미사용(검색·표시까지)")

# 대화 이력 재렌더 루프 — 반드시 chat_input '위'에!
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("어떤 콘텐츠를 찾으세요? (예: 코미디 추천해줘)")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    answer = retrieve_and_answer(prompt)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)


# ===== [그룹 D] 사이드바: 로그 + 유형별 통계 =====
with st.sidebar:
    st.header("검색 처리 로그")
    for line in st.session_state.logs:
        st.text(line)

    st.divider()
    st.subheader("기억 중인 맥락")
    ctx = st.session_state.context
    if ctx["genre_keyword"]:
        st.text(f"최근 장르: {ctx['genre_keyword']}")
        st.text(f"최근 추천 content_id: {ctx['last_content_id']}")
    else:
        st.text("(아직 없음)")

    st.divider()
    st.subheader("콘텐츠 유형별 분포")
    type_counts = conn.execute(
        "SELECT content_type, COUNT(*) FROM content GROUP BY content_type"
    ).fetchall()
    type_df = pd.DataFrame(type_counts, columns=["유형", "건수"]).set_index("유형")
    st.bar_chart(type_df)
