# ott_recommend

넷플릭스 한국 콘텐츠(영화/드라마/예능) 추천 챗봇 — TMDB 데이터 수집 + PostgreSQL/pgvector 검색

## 폴더 구조

```
ott_recommend/
├── data_collection/          # TMDB API 데이터 수집 (AI 도구 활용)
│   ├── collect_netflix_kr_full.py
│   └── build_full_erd_data.py
├── db/                       # PostgreSQL/pgvector 구축 (강의 자료 패턴 기반)
│   ├── schema.sql
│   ├── load_to_postgres.py
│   ├── generate_embeddings.py
│   └── setup_index_and_test.py
├── data/                     # 수집된 CSV 8종
│   ├── content.csv
│   ├── genre.csv
│   ├── content_genre.csv
│   ├── content_tag.csv
│   ├── content_tag_map.csv
│   ├── person.csv
│   ├── content_person_role.csv
│   └── content_embedding.csv
├── ERD.png
├── .env.example
└── .gitignore
```

## 코드 출처 안내

- **`data_collection/`**: TMDB API로 넷플릭스 한국 콘텐츠를 수집하는 부분. 강의 범위(PostgreSQL/NoSQL/pgvector/Streamlit) 밖의 작업이라 AI 도구의 도움을 받아 작성함.
- **`db/`**: PostgreSQL 연결, pgvector 임베딩 저장, HNSW 인덱스 생성 부분. 강의 pgvector 실습 노트북의 패턴(`load_dotenv`, `DB_CONFIG`, `register_vector`, `embed_many`)을 그대로 따라 작성함.

## 실행 순서

1. `.env.example`을 `.env`로 복사하고 값 채우기 (`TMDB_API_KEY`, `OPENAI_API_KEY`, `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`)
2. Docker로 PostgreSQL(pgvector) 컨테이너 실행
   ```
   docker run -d --name db-pg -e POSTGRES_PASSWORD=본인비밀번호 -p 5432:5432 pgvector/pgvector:pg16
   ```
3. DBeaver 등으로 `ott_recommend` 데이터베이스 생성 후 `db/schema.sql` 실행 (테이블 8개 생성)
4. 데이터 적재 및 임베딩 생성
   ```
   cd db
   python load_to_postgres.py
   python generate_embeddings.py
   python setup_index_and_test.py
   ```

(데이터를 새로 수집하고 싶다면 `data_collection/` 스크립트를 먼저 실행하여 `data/`의 CSV를 갱신)

## 데이터 개요

| 테이블 | 건수 | 설명 |
|---|---|---|
| content | 1,874 | 콘텐츠 기본 정보 |
| genre | 27 | 장르 마스터 |
| content_genre | 3,755 | 콘텐츠-장르 연결 |
| content_tag | 2,694 | TMDB 키워드 |
| content_tag_map | 7,710 | 콘텐츠-키워드 연결 |
| person | 3,720 | 배우/감독/PD |
| content_person_role | 10,055 | 콘텐츠-인물 연결 |
| content_embedding | 1,874 | 시맨틱 검색용 벡터 |
