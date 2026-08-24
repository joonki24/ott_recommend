-- ott_recommend 프로젝트 ERD 기준 DDL
-- pgvector 확장 필요 (CONTENT_EMBEDDING.embedding)

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. CONTENT: 콘텐츠 기본 정보
CREATE TABLE content (
    content_id      BIGSERIAL PRIMARY KEY,
    tmdb_id         BIGINT UNIQUE NOT NULL,
    title           VARCHAR NOT NULL,
    content_type    VARCHAR NOT NULL,       -- '영화' | '드라마' | '예능'
    country_code    VARCHAR,                -- 대표 제작 국가 (ISO 코드, 예: 'KR')
    runtime_minutes INT,                    -- 1편/1회 재생시간(분)
    season_count    INT,                    -- 시즌 수 (영화는 NULL)
    episode_count   INT,                    -- 총 회차 수 (영화는 NULL)
    overview        TEXT                    -- 작품 줄거리/소개
);

-- 2. GENRE: 장르 마스터
CREATE TABLE genre (
    genre_id    INT PRIMARY KEY,   -- TMDB 장르 ID를 그대로 사용
    genre_name  VARCHAR NOT NULL
);

-- 3. CONTENT_GENRE: 콘텐츠-장르 연결 (N:M)
CREATE TABLE content_genre (
    content_id  BIGINT NOT NULL REFERENCES content(content_id),
    genre_id    INT NOT NULL REFERENCES genre(genre_id),
    PRIMARY KEY (content_id, genre_id)
);

-- 4. CONTENT_TAG: TMDB 키워드 마스터
CREATE TABLE content_tag (
    tag_id            BIGSERIAL PRIMARY KEY,
    source_keyword_id BIGINT UNIQUE NOT NULL,   -- TMDB Keyword ID
    tag_name          VARCHAR NOT NULL,          -- 작품 주제/상황 태그명
    source_name       VARCHAR DEFAULT 'tmdb_keyword'  -- 태그 출처
);

-- 5. CONTENT_TAG_MAP: 콘텐츠-태그 연결 (N:M)
CREATE TABLE content_tag_map (
    content_id  BIGINT NOT NULL REFERENCES content(content_id),
    tag_id      BIGINT NOT NULL REFERENCES content_tag(tag_id),
    PRIMARY KEY (content_id, tag_id)
);

-- 6. PERSON: 인물 마스터 (배우/감독/PD)
CREATE TABLE person (
    person_id       BIGSERIAL PRIMARY KEY,
    tmdb_person_id  BIGINT UNIQUE NOT NULL,   -- TMDB 인물 ID
    person_name     VARCHAR NOT NULL          -- 배우/감독/PD 이름
);

-- 7. CONTENT_PERSON_ROLE: 콘텐츠-인물 연결 + 역할 (N:M)
CREATE TABLE content_person_role (
    content_id  BIGINT NOT NULL REFERENCES content(content_id),
    person_id   BIGINT NOT NULL REFERENCES person(person_id),
    role_type   VARCHAR NOT NULL,   -- '배우' | '감독' | 'PD'
    PRIMARY KEY (content_id, person_id, role_type)
);

-- 8. CONTENT_EMBEDDING: 콘텐츠 의미 벡터 (시맨틱 검색용)
CREATE TABLE content_embedding (
    content_id      BIGINT PRIMARY KEY REFERENCES content(content_id),
    embedding_text  TEXT,           -- 임베딩에 사용한 검색용 문장
    embedding       vector(1024)    -- 콘텐츠 의미 벡터
);

-- HNSW 인덱스는 embedding 컬럼에 실제 값이 채워진 뒤 생성 (강의 실습과 동일한 순서)
-- CREATE INDEX content_embedding_hnsw ON content_embedding
--     USING hnsw (embedding vector_cosine_ops);
