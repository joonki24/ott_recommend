import base64
from pathlib import Path
from textwrap import dedent

import streamlit as st

from recommendation import recommend


# ==================================================
# 1. PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="Netflix Recommendation",
    page_icon="▶",
    layout="centered"
)


# ==================================================
# 2. SESSION STATE
# ==================================================

# 현재 브라우저 세션에서만 대화 기록을 유지
if "messages" not in st.session_state:
    st.session_state.messages = []


# messages가 비어 있으면 첫 접속 화면
is_new_chat = len(st.session_state.messages) == 0


# ==================================================
# 3. 화면 표시용 데이터
# ==================================================

type_map = {
    "movie": "영화",
    "drama": "드라마",
    "variety": "예능"
}


# ==================================================
# 4. LANDING 배경 이미지 함수
# ==================================================

def get_base64_image(image_path):
    """
    로컬 이미지를 CSS background에서 사용할 수 있도록
    base64 문자열로 변환합니다.

    이미지가 없으면 빈 문자열을 반환합니다.
    """

    path = Path(image_path)

    if not path.exists():
        return ""

    return base64.b64encode(
        path.read_bytes()
    ).decode()


# 프로젝트 폴더 아래에 이 파일이 있으면 첫 화면 배경으로 사용
# 없더라도 앱은 정상 실행됨
bg_base64 = get_base64_image(
    "netflix_bg.png"
)


# 이미지가 있으면 이미지 배경
if bg_base64:

    landing_background = f"""
        linear-gradient(
            to bottom,
            rgba(0, 0, 0, 0.45) 0%,
            rgba(0, 0, 0, 0.35) 45%,
            rgba(0, 0, 0, 0.80) 100%
        ),
        url("data:image/png;base64,{bg_base64}")
    """

# 이미지가 없으면 임시 검정 배경
else:

    landing_background = """
        radial-gradient(
            circle at 50% 20%,
            #272727 0%,
            #111111 35%,
            #000000 75%
        )
    """


# ==================================================
# 5. CSS
# ==================================================

st.markdown(
    f"""
    <style>

    /* =========================
    APP
    ========================= */

    .stApp {{
        background: #000000;
        color: #ffffff;
        font-family: Arial, "Noto Sans KR", sans-serif;
    }}

    .block-container {{
        position: relative;
        z-index: 1;

        max-width: 1200px;
        padding-top: 3.5rem;
        padding-bottom: 8rem;
    }}


    /* =========================
    LANDING BACKGROUND
    ========================= */

    .landing-background {{
        position: fixed;

        top: 0;
        left: 0;

        width: 100vw;
        height: 100vh;

        z-index: 0;

        background: {landing_background};
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;

        pointer-events: none;
    }}

    /* =========================
    LOGO
    ========================= */

    .netflix-logo {{
        color: #E50914;

        font-size: 42px;
        font-weight: 900;

        line-height: 1;
        letter-spacing: -2px;
    }}

    .netflix-logo-small {{
        color: #E50914;

        font-size: 28px;
        font-weight: 900;

        line-height: 1;
        letter-spacing: -1.4px;
    }}

    .ai-label {{
        color: #B3B3B3;

        font-size: 11px;
        font-weight: 600;

        letter-spacing: 0.12em;

        margin-top: 6px;
    }}


    /* =========================
    LANDING TOP
    ========================= */

    .landing-header {{
        display: flex;

        align-items: center;
        justify-content: space-between;

        margin-bottom: 90px;
    }}

    .landing-brand {{
        display: flex;

        flex-direction: column;

        align-items: flex-start;
    }}

    .fake-menu {{
        display: flex;

        gap: 10px;

        align-items: center;
    }}

    .fake-language {{
        color: #ffffff;

        background: rgba(20, 20, 20, 0.75);

        border: 1px solid rgba(255, 255, 255, 0.35);
        border-radius: 4px;

        padding: 7px 14px;

        font-size: 14px;
    }}

    .prototype-label {{
        color: #ffffff;

        background: #E50914;

        border-radius: 4px;

        padding: 8px 14px;

        font-size: 13px;
        font-weight: 700;
    }}


    /* =========================
    LANDING HERO
    ========================= */

    .hero-area {{
        max-width: 840px;

        margin: 80px auto 28px auto;

        text-align: center;
    }}

    .hero-title {{
        color: #ffffff;

        font-size: 56px;
        font-weight: 900;

        line-height: 1.1;
        letter-spacing: -0.035em;
    }}

    .hero-subtitle {{
        color: #ffffff;

        margin-top: 24px;

        font-size: 22px;
        font-weight: 600;

        line-height: 1.5;
    }}

    .hero-description {{
        color: #e5e5e5;

        margin-top: 22px;

        font-size: 16px;
        line-height: 1.65;
    }}


    /* =========================
    ACTIVE CHAT HEADER
    ========================= */

    .chat-brand {{
        display: flex;

        align-items: center;

        gap: 14px;

        min-height: 48px;
    }}

    .chat-divider {{
        height: 1px;

        background: #242424;

        margin-top: 15px;
        margin-bottom: 18px;
    }}


    /* =========================
    BUTTON
    ========================= */

    .stButton > button {{
        background: #E50914 !important;
        color: #ffffff !important;

        border: none !important;
        border-radius: 4px !important;

        font-weight: 700 !important;

        min-height: 42px;

        padding: 0.55rem 1rem !important;

        box-shadow: none !important;
    }}

    .stButton > button:hover {{
        background: #c11119 !important;

        color: #ffffff !important;

        border: none !important;
    }}


    /* =========================
    LANDING TEXT INPUT
    ========================= */

    .stTextInput input {{
        background: rgba(20, 20, 20, 0.85) !important;

        color: #ffffff !important;

        border: 1px solid #777777 !important;
        border-radius: 4px !important;

        min-height: 52px;

        font-size: 15px !important;
    }}

    .stTextInput input:focus {{
        border-color: #ffffff !important;

        box-shadow: none !important;
    }}

    .stTextInput input::placeholder {{
        color: #B3B3B3 !important;
    }}


    /* =========================
    CHAT MESSAGE
    ========================= */

    [data-testid="stChatMessage"] {{
        background: transparent !important;

        padding-top: 1.1rem !important;
        padding-bottom: 1.1rem !important;
    }}


    /* =========================
    RECOMMENDATION CARD
    ========================= */

    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: #141414 !important;

        border: 1px solid #2a2a2a !important;
        border-radius: 4px !important;

        box-shadow: none !important;

        margin-bottom: 10px !important;
    }}

    [data-testid="stVerticalBlockBorderWrapper"] h3 {{
        color: #ffffff !important;

        font-size: 20px !important;
        font-weight: 700 !important;

        margin-bottom: 4px !important;
    }}

    [data-testid="stVerticalBlockBorderWrapper"] p {{
        color: #e2e2e2 !important;

        font-size: 14px !important;
        line-height: 1.6 !important;
    }}


    /* =========================
    CAPTION / METADATA
    ========================= */

    [data-testid="stCaptionContainer"] {{
        color: #B3B3B3 !important;

        font-size: 12px !important;
    }}


    /* =========================
    CHAT INPUT
    ========================= */

    [data-testid="stChatInput"] {{
        background: #141414 !important;

        border: 1px solid #555555 !important;
        border-radius: 4px !important;

        box-shadow: none !important;
    }}

    [data-testid="stChatInput"]:focus-within {{
        border-color: #ffffff !important;
    }}

    [data-testid="stChatInput"] textarea {{
        color: #ffffff !important;
    }}

    [data-testid="stChatInput"] textarea::placeholder {{
        color: #B3B3B3 !important;
    }}


    /* =========================
    STREAMLIT CHROME
    ========================= */

    header[data-testid="stHeader"] {{
        background: rgba(0, 0, 0, 0.88) !important;
    }}

    #MainMenu {{
        visibility: hidden;
    }}

    footer {{
        visibility: hidden;
    }}


    /* =========================
    MOBILE
    ========================= */

    @media (max-width: 768px) {{

        .block-container {{
            padding-left: 1.2rem;
            padding-right: 1.2rem;
        }}

        .netflix-logo {{
            font-size: 32px;
        }}

        .hero-area {{
            margin-top: 50px;
        }}

        .hero-title {{
            font-size: 38px;
        }}

        .hero-subtitle {{
            font-size: 18px;
        }}

        .fake-language {{
            display: none;
        }}

    }}

    </style>
    """,
    unsafe_allow_html=True
)


# ==================================================
# 6. 추천 요청 처리 함수
# ==================================================

def handle_user_query(user_query):
    """
    첫 화면 입력과 채팅 화면 입력이
    동일한 추천 처리 과정을 사용하도록 만든 함수입니다.
    """

    # 사용자 질문 저장
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_query
        }
    )

    try:

        # 추천 파이프라인 실행
        results = recommend(
            user_query,
            top_n=3
        )

        # 검색 결과 없음
        if not results:

            assistant_message = {
                "role": "assistant",
                "content": "조건에 맞는 콘텐츠를 찾지 못했어요."
            }

        # 추천 결과 있음
        else:

            assistant_message = {
                "role": "assistant",
                "content": "이런 콘텐츠를 추천해요.",
                "results": results
            }

    except Exception as e:

        # 앱 전체가 종료되지 않도록
        # 오류도 assistant 메시지로 저장
        assistant_message = {
            "role": "assistant",
            "content": "추천을 처리하는 중 오류가 발생했어요."
        }

        # 개발 중에는 터미널에서 실제 오류를 확인
        print("recommend error:", e)

    # AI 답변 저장
    st.session_state.messages.append(
        assistant_message
    )

    # 첫 화면 → 채팅 화면 전환
    # 또는 새 메시지를 화면에 즉시 반영
    st.rerun()


# ==================================================
# 7. 첫 접속 LANDING SCREEN
# ==================================================

if is_new_chat:

    # 화면 전체에 랜딩 배경 적용
    st.html('<div class="landing-background"></div>')

    # Netflix 스타일 상단
    st.html("""
    <div class="landing-header">
        <div class="landing-brand">
            <div class="netflix-logo">NETFLIX</div>
            <div class="ai-label">AI RECOMMENDATION</div>
        </div>
        <div class="fake-menu">
            <div class="fake-language">한국어</div>
            <div class="prototype-label">AI 추천</div>
        </div>
    </div>
    """)

    # 중앙 Hero
    st.html("""
    <div class="hero-area">
        <div class="hero-title">
            오늘은 어떤 이야기에<br>
            빠져보고 싶으세요?
        </div>
        <div class="hero-subtitle">
            영화, 드라마, 예능을 취향에 맞게 추천해드려요.
        </div>
        <div class="hero-description">
            장르, 배우, 러닝타임처럼 정확한 조건부터<br>
            통쾌한 작품, 편하게 볼 작품 같은 분위기까지 자연스럽게 입력해보세요.
        </div>
    </div>
    """)


    # --------------------------------------------------
    # 첫 질문 입력 영역
    # --------------------------------------------------

    # form을 사용하면 Enter 또는 버튼으로 제출 가능
    with st.form(
        "landing_search_form",
        clear_on_submit=False
    ):

        input_col, button_col = st.columns(
            [5, 1.7],
            vertical_alignment="bottom"
        )

        with input_col:

            landing_query = st.text_input(
                "첫 질문",
                placeholder="예: 한국 액션 영화 중에서 통쾌한 거 추천해줘",
                label_visibility="collapsed"
            )

        with button_col:

            landing_submit = st.form_submit_button(
                "추천 시작하기  ›",
                use_container_width=True
            )


    # 제출했을 때만 추천 실행
    if landing_submit:

        landing_query = landing_query.strip()

        if landing_query:

            handle_user_query(
                landing_query
            )

        else:

            st.warning(
                "보고 싶은 콘텐츠를 입력해주세요."
            )


# ==================================================
# 8. 대화 진행 중 CHAT SCREEN
# ==================================================

else:

    # --------------------------------------------------
    # 상단 Header
    # --------------------------------------------------

    header_left, header_right = st.columns(
        [5, 1.1],
        vertical_alignment="center"
    )

    with header_left:

        st.markdown(
            """
<div class="chat-brand">
    <div class="netflix-logo-small">NETFLIX</div>
    <div class="ai-label">AI RECOMMENDATION</div>
</div>
""",
            unsafe_allow_html=True
        )

    with header_right:

        if st.button(
            "새 대화",
            use_container_width=True
        ):

            st.session_state.messages = []

            st.rerun()


    st.markdown(
        '<div class="chat-divider"></div>',
        unsafe_allow_html=True
    )


    # ==================================================
    # 9. 이전 대화 출력
    # ==================================================

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            st.write(
                message["content"]
            )


            # Assistant 추천 결과가 있는 경우
            if "results" in message:

                for row in message["results"]:

                    (
                        content_id,
                        title,
                        content_type,
                        runtime,
                        genres,
                        overview,
                        poster_path,
                        vote_average,
                        release_date,
                        distance
                    ) = row


                    # DB 콘텐츠 유형 → 사용자 표시용 한글
                    display_type = type_map.get(
                        content_type,
                        content_type
                    )


                    # Action, Comedy
                    # →
                    # Action · Comedy
                    if genres:

                        display_genres = genres.replace(
                            ",",
                            " ·"
                        )

                    else:

                        display_genres = "장르 정보 없음"


                    # ----------------------------------
                    # 추천 콘텐츠 카드
                    # ----------------------------------

                    with st.container(
                        border=True
                    ):

                        poster_col, info_col = st.columns(
                            [1, 3],
                            vertical_alignment="top"
                        )

                        with poster_col:
                            if poster_path:
                                poster_url = (
                                    "https://image.tmdb.org/t/p/w500"
                                    + poster_path
                                )
                                st.image(
                                    poster_url,
                                    width="stretch"
                                )

                        with info_col:

                            rating_text = (
                                f"⭐ {vote_average}"
                                if vote_average else ""
                            )

                            st.subheader(
                                title
                            )

                            st.caption(
                                f"{display_type} · "
                                f"{runtime}분 · "
                                f"{display_genres}"
                                f" · {rating_text}"
                            )

                            st.write(
                                overview
                            )


    # ==================================================
    # 10. CHAT INPUT
    # ==================================================

    user_query = st.chat_input(
        "어떤 콘텐츠를 보고 싶으신가요?"
    )


    # 새 질문이 들어오면
    if user_query:

        user_query = user_query.strip()

        if user_query:

            handle_user_query(
                user_query
            )