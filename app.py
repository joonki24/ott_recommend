import base64
import html
from pathlib import Path
from textwrap import dedent

import streamlit as st

# 사용 모델 선택
# open_ai 사용시는 아래 활성화
# from recommendation import recommend 

# gemini 사용시는 아래 활성화
# from gemini_recommendation import recommend


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
    "images/netflix_bg.png")
logo_base64 = get_base64_image(
    "images/netflix_logo.png")
symbol_base64 = get_base64_image(
    "images/netflix_symbol.png")

# 이미지가 있으면 이미지 배경
if bg_base64:

    landing_background = f"""
        linear-gradient(
            to right,
            rgba(0, 0, 0, 0.78) 0%,
            rgba(0, 0, 0, 0.48) 35%,
            rgba(0, 0, 0, 0.38) 65%,
            rgba(0, 0, 0, 0.62) 100%
        ),
        linear-gradient(
            to bottom,
            rgba(0, 0, 0, 0.18) 0%,
            rgba(0, 0, 0, 0.25) 55%,
            rgba(0, 0, 0, 0.82) 100%
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
        justify-content: flex-start;

        min-height: 70px;
        margin-bottom: 0;
    }}

    .landing-brand {{
        display: flex;
        align-items: center;
    }}

    .landing-logo-image {{
        width: 125px;
        height: auto;
        display: block;
    }}


    /* =========================
    LANDING HERO
    ========================= */

    .hero-area {{
        max-width: 900px;

        margin: 8.5rem auto 3.2rem auto;

        text-align: center;
    }}

    .hero-title {{
        color: #ffffff;

        font-size: 60px;
        font-weight: 900;

        line-height: 1.13;
        letter-spacing: -0.04em;

        text-shadow: 0 3px 18px rgba(0, 0, 0, 0.75);
    }}

    .hero-subtitle {{
        color: #d7d7d7;

        margin-top: 24px;

        font-size: 20px;
        font-weight: 400;

        line-height: 1.5;

        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.75);
    }}


    /* =========================
    LANDING SEARCH FORM
    ========================= */

    [data-testid="stForm"] {{
        max-width: 980px;

        margin-left: auto;
        margin-right: auto;

        padding: 12px;

        background: rgba(5, 5, 5, 0.62);

        border: 1px solid rgba(255, 255, 255, 0.24) !important;
        border-radius: 8px;

        backdrop-filter: blur(3px);
    }}

    [data-testid="stForm"] .stTextInput input {{
        min-height: 58px;

        background: rgba(35, 35, 35, 0.88) !important;

        color: #ffffff !important;

        border: 1px solid rgba(255, 255, 255, 0.18) !important;
        border-radius: 6px !important;

        font-size: 16px !important;

        padding-left: 18px;
    }}

    [data-testid="stForm"] .stTextInput input:focus {{
        border-color: rgba(255, 255, 255, 0.65) !important;
        box-shadow: none !important;
    }}

    [data-testid="stForm"] .stTextInput input::placeholder {{
        color: #b3b3b3 !important;
    }}

    [data-testid="stFormSubmitButton"] button {{
        min-height: 58px !important;

        background: #E50914 !important;
        color: #ffffff !important;

        border: none !important;
        border-radius: 6px !important;

        font-size: 17px !important;
        font-weight: 700 !important;
    }}

    [data-testid="stFormSubmitButton"] button:hover {{
        background: #f6121d !important;
    }}


    /* =========================
    ACTIVE CHAT HEADER
    ========================= */

    .chat-brand {{
        display: flex;
        align-items: center;
        gap: 22px;
        min-height: 52px;
    }}

    .chat-logo-image {{
        width: 120px;
        height: auto;
        display: block;
    }}

    .chat-ai-label {{
        color: #d5d5d5;
        font-size: 13px;
        font-weight: 500;
        letter-spacing: 0.12em;
    }}

    .chat-divider {{
        height: 1px;
        background: #242424;
        margin-top: 15px;
        margin-bottom: 28px;
    }}


    /* =========================
    NEW CHAT BUTTON
    ========================= */

    .stButton > button {{
        background: transparent !important;
        color: #ffffff !important;

        border: 1px solid #E50914 !important;
        border-radius: 6px !important;

        font-weight: 600 !important;

        min-height: 44px;

        padding: 0.55rem 1rem !important;

        box-shadow: none !important;
    }}

    .stButton > button:hover {{
        background: rgba(229, 9, 20, 0.12) !important;
        color: #ffffff !important;

        border-color: #ff1f2d !important;
    }}


    /* =========================
    CUSTOM CHAT
    ========================= */

    .user-row {{
        display: flex;
        justify-content: flex-end;
        align-items: center;

        gap: 14px;

        margin: 18px 0 30px 0;
    }}

    .user-bubble {{
        max-width: 620px;

        padding: 16px 22px;

        background:
            linear-gradient(
                135deg,
                #292929,
                #1b1b1b
            );

        color: #ffffff;

        border-radius: 16px 16px 4px 16px;

        font-size: 16px;
        line-height: 1.6;

        border: 1px solid #303030;
    }}

    .user-avatar {{
        width: 48px;
        height: 48px;

        flex: 0 0 48px;

        display: flex;
        align-items: center;
        justify-content: center;

        border-radius: 50%;

        background: #292929;
        border: 1px solid #3a3a3a;
    }}

    .user-avatar svg {{
        width: 25px;
        height: 25px;

        fill: #b3b3b3;
    }}


    .assistant-row {{
        display: flex;
        align-items: flex-start;

        gap: 16px;

        margin: 10px 0 22px 0;
    }}

    .assistant-avatar {{
        width: 52px;
        height: 52px;

        flex: 0 0 52px;

        display: flex;
        align-items: center;
        justify-content: center;

        overflow: hidden;

        background: #080808;

        border: 1px solid #3c3c3c;
        border-radius: 50%;
    }}

    .assistant-avatar img {{
        width: 32px;
        height: 42px;

        object-fit: contain;
    }}

    .assistant-bubble {{
        max-width: 650px;

        padding: 16px 22px;

        background:
            linear-gradient(
                135deg,
                #242424,
                #181818
            );

        color: #ffffff;

        border: 1px solid #2e2e2e;
        border-radius: 4px 16px 16px 16px;

        font-size: 16px;
        line-height: 1.6;
    }}


    /* =========================
    RECOMMENDATION GRID
    ========================= */

    .recommendation-card {{
        height: 100%;

        overflow: hidden;

        background:
            linear-gradient(
                to bottom,
                #171717,
                #101010
            );

        border: 1px solid #333333;
        border-radius: 6px;
    }}

    .recommendation-poster {{
        width: 100%;

        aspect-ratio: 2 / 3;

        display: block;

        object-fit: cover;

        background: #202020;
    }}

    .recommendation-info {{
        padding: 17px 17px 20px 17px;
    }}

    .recommendation-title-row {{
        display: flex;
        align-items: center;

        gap: 10px;

        margin-bottom: 9px;
    }}

    .rank-badge {{
        min-width: 28px;
        height: 28px;

        display: inline-flex;
        align-items: center;
        justify-content: center;

        color: #ffffff;

        border: 1px solid #E50914;
        border-radius: 4px;

        font-size: 13px;
        font-weight: 700;
    }}

    .recommendation-title {{
        color: #ffffff;

        font-size: 19px;
        font-weight: 700;

        line-height: 1.35;
    }}

    .recommendation-meta {{
        color: #b3b3b3;

        margin-bottom: 10px;

        font-size: 13px;
        line-height: 1.55;
    }}

    .recommendation-rating {{
        color: #e5e5e5;

        margin-bottom: 11px;

        font-size: 14px;
    }}

    .rating-star {{
        color: #E50914;

        margin-right: 4px;
    }}

    .recommendation-overview {{
        color: #cfcfcf;

        font-size: 13px;
        line-height: 1.6;
    }}

    .tmdb-note {{
        color: #777777;

        margin: 20px 0 15px 0;

        text-align: center;

        font-size: 12px;
    }}


    /* =========================
    CHAT INPUT
    ========================= */

    [data-testid="stChatInput"] {{
        background: #141414 !important;

        border: 1px solid #444444 !important;
        border-radius: 7px !important;

        box-shadow: none !important;
    }}

    [data-testid="stChatInput"]:focus-within {{
        border-color: #777777 !important;
    }}

    [data-testid="stChatInput"] textarea {{
        color: #ffffff !important;
    }}

    [data-testid="stChatInput"] textarea::placeholder {{
        color: #8c8c8c !important;
    }}

    [data-testid="stChatInput"] button {{
        background: #E50914 !important;
        color: #ffffff !important;

        border-radius: 5px !important;
    }}

    [data-testid="stChatInput"] button:hover {{
        background: #f6121d !important;
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

        .landing-logo-image {{
            width: 95px;
        }}

        .hero-area {{
            margin-top: 6rem;
        }}

        .hero-title {{
            font-size: 40px;
        }}

        .hero-subtitle {{
            font-size: 17px;
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

    # 공식 Netflix 로고
    if logo_base64:

        logo_html = f"""
            <img
                class="landing-logo-image"
                src="data:image/png;base64,{logo_base64}"
                alt="Netflix"
            >
        """

    else:

        logo_html = """
            <div style="
                color:#E50914;
                font-size:28px;
                font-weight:900;
            ">
                NETFLIX
            </div>
        """


    # 상단 로고
    st.html(
        f"""
        <div class="landing-header">
            <div class="landing-brand">
                {logo_html}
            </div>
        </div>
        """
    )


    # 중앙 Hero
    st.html(
        """
        <div class="hero-area">

            <div class="hero-title">
                오늘은 어떤 이야기에<br>
                빠져보고 싶으세요?
            </div>

            <div class="hero-subtitle">
                영화, 드라마, 예능을 취향에 맞게 추천해드려요
            </div>

        </div>
        """
    )


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

    # ==================================================
    # 두 번째 화면 전용 크기 조정
    # ==================================================

    st.markdown(
        """
        <style>

        /* 두 번째 화면 전체 폭/여백 */
        .block-container {
            max-width: 1100px;
            padding-top: 1.5rem;
            padding-bottom: 5rem;
        }


        /* 상단 로고 */
        .chat-logo-image {
            width: 100px;
        }

        .chat-brand {
            min-height: 40px;
        }

        .chat-divider {
            margin-top: 8px;
            margin-bottom: 12px;
        }


        /* 사용자 질문 */
        .user-row {
            margin-top: 8px;
            margin-bottom: 14px;
        }

        .user-bubble {
            padding: 10px 16px;
            font-size: 14px;
        }

        .user-avatar {
            width: 38px;
            height: 38px;
            flex-basis: 38px;
        }


        /* AI 답변 */
        .assistant-row {
            margin-top: 5px;
            margin-bottom: 12px;
        }

        .assistant-avatar {
            width: 40px;
            height: 40px;
            flex-basis: 40px;
        }

        .assistant-avatar img {
            width: 24px;
            height: 31px;
        }

        .assistant-bubble {
            padding: 10px 16px;
            font-size: 14px;
        }


        /* 추천 카드 */
        .recommendation-card {
            height: 100%;

            display: flex;
            flex-direction: column;
        }


        /* 포스터만 특히 작게 */
        .recommendation-poster {
            width: 62%;
            max-width: 210px;

            aspect-ratio: 2 / 3;

            margin: 12px auto 0 auto;

            object-fit: cover;
            border-radius: 4px;
        }


        /* 카드 정보 */
        .recommendation-info {
            flex: 1;

            padding: 10px 14px 14px 14px;
        }

        .recommendation-title {
            font-size: 16px;
        }

        .recommendation-meta {
            font-size: 11px;
            margin-bottom: 5px;
        }

        .recommendation-rating {
            font-size: 12px;
            margin-bottom: 6px;
        }

        .recommendation-overview {
            font-size: 11px;
            line-height: 1.45;
        }

        .tmdb-note {
            margin-top: 8px;
            font-size: 10px;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------
    # 상단 Header
    # --------------------------------------------------

    header_left, header_right = st.columns(
        [5, 1.35],
        vertical_alignment="center"
    )


    with header_left:

        if logo_base64:

            st.html(
                f"""
                <div class="chat-brand">

                    <img
                        class="chat-logo-image"
                        src="data:image/png;base64,{logo_base64}"
                        alt="Netflix"
                    >

                    <div class="chat-ai-label">
                        AI RECOMMENDATION
                    </div>

                </div>
                """
            )

        else:

            st.html(
                """
                <div class="chat-brand">

                    <div
                        style="
                            color:#E50914;
                            font-size:28px;
                            font-weight:900;
                        "
                    >
                        NETFLIX
                    </div>

                    <div class="chat-ai-label">
                        AI RECOMMENDATION
                    </div>

                </div>
                """
            )


    with header_right:

        if st.button(
            "＋ 새 대화 시작",
            use_container_width=True
        ):

            st.session_state.messages = []

            st.rerun()


    st.html(
        '<div class="chat-divider"></div>'
    )


    # ==================================================
    # 9. 이전 대화 출력
    # ==================================================

    for message in st.session_state.messages:

        role = message["role"]

        safe_content = html.escape(
            str(
                message["content"]
            )
        )


        # --------------------------------------------------
        # USER
        # --------------------------------------------------

        if role == "user":

            st.html(
                f"""
                <div class="user-row">

                    <div class="user-bubble">
                        {safe_content}
                    </div>

                    <div class="user-avatar">

                        <svg
                            viewBox="0 0 24 24"
                            aria-hidden="true"
                        >

                            <circle
                                cx="12"
                                cy="8"
                                r="4"
                            />

                            <path
                                d="
                                    M4 21
                                    C4 16.6 7.6 13 12 13
                                    C16.4 13 20 16.6 20 21
                                    Z
                                "
                            />

                        </svg>

                    </div>

                </div>
                """
            )


        # --------------------------------------------------
        # ASSISTANT
        # --------------------------------------------------

        else:

            if symbol_base64:

                assistant_avatar = f"""
                    <img
                        src="data:image/png;base64,{symbol_base64}"
                        alt="Netflix AI"
                    >
                """

            else:

                assistant_avatar = """
                    <span
                        style="
                            color:#E50914;
                            font-size:28px;
                            font-weight:900;
                        "
                    >
                        N
                    </span>
                """


            st.html(
                f"""
                <div class="assistant-row">

                    <div class="assistant-avatar">
                        {assistant_avatar}
                    </div>

                    <div class="assistant-bubble">
                        {safe_content}
                    </div>

                </div>
                """
            )


            # --------------------------------------------------
            # 추천 결과가 있는 Assistant 메시지
            # --------------------------------------------------

            if "results" in message:

                results = message["results"]

                # Top 3 → 가로 3열
                card_columns = st.columns(
                    len(results),
                    gap="medium"
                )


                for rank, (
                    column,
                    row
                ) in enumerate(
                    zip(
                        card_columns,
                        results
                    ),
                    start=1
                ):

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


                    # 콘텐츠 유형
                    display_type = type_map.get(
                        content_type,
                        content_type
                    )


                    # 장르
                    if genres:

                        display_genres = (
                            genres.replace(
                                ",",
                                " ·"
                            )
                        )

                    else:

                        display_genres = (
                            "장르 정보 없음"
                        )


                    # 공개연도
                    if release_date:

                        release_year = (
                            release_date.year
                        )

                    else:

                        release_year = "연도 정보 없음"


                    # 평점
                    if vote_average is not None:

                        rating_text = (
                            f"{float(vote_average):.1f}"
                        )

                    else:

                        rating_text = "-"


                    # 너무 긴 줄거리 때문에
                    # 카드 높이가 과도하게 달라지는 것 방지
                    if overview:

                        clean_overview = (
                            str(overview).strip()
                        )

                        if len(clean_overview) > 95:

                            clean_overview = (
                                clean_overview[:95]
                                + "..."
                            )

                    else:

                        clean_overview = (
                            "줄거리 정보가 없습니다."
                        )


                    # HTML 안전 처리
                    safe_title = html.escape(
                        str(title)
                    )

                    safe_type = html.escape(
                        str(display_type)
                    )

                    safe_genres = html.escape(
                        str(display_genres)
                    )

                    safe_overview = html.escape(
                        clean_overview
                    )


                    # TMDB 포스터
                    if poster_path:

                        poster_url = (
                            "https://image.tmdb.org/t/p/w500"
                            + poster_path
                        )

                    else:

                        poster_url = ""


                    with column:

                        if poster_url:

                            poster_html = f"""
                                <img
                                    class="recommendation-poster"
                                    src="{poster_url}"
                                    alt="{safe_title}"
                                >
                            """

                        else:

                            poster_html = """
                                <div
                                    class="recommendation-poster"
                                    style="
                                        display:flex;
                                        align-items:center;
                                        justify-content:center;
                                        color:#777777;
                                    "
                                >
                                    포스터 없음
                                </div>
                            """


                        st.html(
                            f"""
                            <div class="recommendation-card">

                                {poster_html}

                                <div class="recommendation-info">

                                    <div
                                        class="recommendation-title-row"
                                    >

                                        <span class="rank-badge">
                                            {rank}
                                        </span>

                                        <span
                                            class="recommendation-title"
                                        >
                                            {safe_title}
                                        </span>

                                    </div>


                                    <div
                                        class="recommendation-meta"
                                    >
                                        {release_year}
                                        ·
                                        {runtime}분
                                        ·
                                        {safe_type}
                                        ·
                                        {safe_genres}
                                    </div>


                                    <div
                                        class="recommendation-rating"
                                    >

                                        <span class="rating-star">
                                            ★
                                        </span>

                                        {rating_text}

                                    </div>


                                    <div
                                        class="recommendation-overview"
                                    >
                                        {safe_overview}
                                    </div>

                                </div>

                            </div>
                            """
                        )


                st.html(
                    """
                    <div class="tmdb-note">
                        ※ 평점은 TMDB 기준이며
                        변동될 수 있습니다.
                    </div>
                    """
                )


    # ==================================================
    # 10. CHAT INPUT
    # ==================================================

    user_query = st.chat_input(
        "어떤 콘텐츠를 보고 싶으신가요?"
    )


    if user_query:

        user_query = user_query.strip()

        if user_query:

            handle_user_query(
                user_query
            )