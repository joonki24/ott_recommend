import os
import re
import psycopg
from psycopg import sql
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

from openai import OpenAI

load_dotenv()

pw = os.environ["PGPASSWORD"]

DB_NAME = "ott_recommend"

embedding_model = "text-embedding-3-small"
embedding_dimensions = 1024

admin_conn = psycopg.connect(
    host="localhost",
    port=15432,
    dbname="postgres",
    user="postgres",
    password=pw,
    autocommit=True
)

with admin_conn.cursor() as cur:

    cur.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (DB_NAME,)
    )

    exists = cur.fetchone()

    if exists is None:
        cur.execute(
            sql.SQL("CREATE DATABASE {}")
            .format(sql.Identifier(DB_NAME))
        )
        print(f"{DB_NAME} 데이터베이스 생성 완료")
    else:
        print(f"{DB_NAME} 데이터베이스가 이미 존재합니다.")

admin_conn.close()

conn = psycopg.connect(
    host="localhost",
    port=15432,
    dbname=DB_NAME,
    user="postgres",
    password=pw
)

with conn.cursor() as cur:
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")


register_vector(conn)


with conn.cursor() as cur:

    cur.execute("""
        DROP TABLE IF EXISTS
            content_person_role,
            content_embedding,
            content_tag_map,
            content_genre,
            content_tag,
            person,
            genre,
            content;
    """)

with conn.cursor() as cur:

    # CONTENT
    cur.execute("""
        CREATE TABLE content (
            content_id BIGINT PRIMARY KEY,
            tmdb_id BIGINT UNIQUE,
            title VARCHAR(255),
            content_type VARCHAR(255),
            country_code VARCHAR(255),
            runtime_minutes INT,
            episode_count INT,
            overview TEXT
        );
    """)

    # CONTENT_TAG
    cur.execute("""
        CREATE TABLE content_tag (
            tag_id BIGINT PRIMARY KEY,
            source_keyword_id BIGINT UNIQUE,
            tag_name VARCHAR(255),
            source_name VARCHAR(255)
        );
    """)

    # PERSON
    cur.execute("""
        CREATE TABLE person (
            person_id BIGINT PRIMARY KEY,
            tmdb_person_id BIGINT UNIQUE,
            person_name VARCHAR(255)
        );
    """)

    # GENRE
    cur.execute("""
        CREATE TABLE genre (
            genre_id INT PRIMARY KEY,
            genre_name VARCHAR(255)
        );
    """)

    # CONTENT_PERSON_ROLE
    cur.execute("""
        CREATE TABLE content_person_role (
            content_id BIGINT REFERENCES content(content_id),
            person_id BIGINT REFERENCES person(person_id),
            role_type VARCHAR(255),

            PRIMARY KEY (content_id, person_id, role_type)
        );
    """)

    # CONTENT_EMBEDDING
    cur.execute(f"""
        CREATE TABLE content_embedding (
            content_id BIGINT PRIMARY KEY
                REFERENCES content(content_id),

            embedding_text TEXT,
            embedding VECTOR({embedding_dimensions})
        );
    """)

    # CONTENT_TAG_MAP
    cur.execute("""
        CREATE TABLE content_tag_map (
            content_id BIGINT REFERENCES content(content_id),
            tag_id BIGINT REFERENCES content_tag(tag_id),

            PRIMARY KEY (content_id, tag_id)
        );
    """)

    # CONTENT_GENRE
    cur.execute("""
        CREATE TABLE content_genre (
            content_id BIGINT REFERENCES content(content_id),
            genre_id INT REFERENCES genre(genre_id),

            PRIMARY KEY (content_id, genre_id)
        );
    """)

contents = [
    (
        1,
        10001,
        "한강 추격전",
        "movie",
        "KR",
        55,
        None,
        "경찰들이 범죄 조직을 추격하며 벌어지는 빠르고 유쾌한 이야기"
    ),
    (
        2,
        10002,
        "마지막 복수",
        "movie",
        "KR",
        110,
        None,
        "가족을 잃은 주인공이 범죄 조직을 상대로 복수를 시작하는 이야기"
    ),
    (
        3,
        10003,
        "우주 생존자",
        "movie",
        "US",
        105,
        None,
        "우주선 사고 이후 홀로 남겨진 대원이 지구로 돌아가기 위해 생존하는 이야기"
    ),
    (
        4,
        10004,
        "우리들의 교실",
        "drama",
        "KR",
        50,
        12,
        "학교에서 만난 친구들이 갈등을 해결하며 성장하는 이야기"
    ),
    (
        5,
        10005,
        "웃음 원정대",
        "variety",
        "KR",
        70,
        8,
        "출연진들이 여행을 떠나 다양한 미션을 수행하는 예능"
    ),
    (
        6,
        10006,
        "조용한 주말",
        "movie",
        "JP",
        95,
        None,
        "가족이 시골에서 함께 주말을 보내며 서로의 관계를 회복하는 이야기"
    )
]

with conn.cursor() as cur:

    cur.executemany("""
        INSERT INTO content (
            content_id,
            tmdb_id,
            title,
            content_type,
            country_code,
            runtime_minutes,
            episode_count,
            overview
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """, contents)

genres = [
    (1, "Action"),
    (2, "Comedy"),
    (3, "Thriller"),
    (4, "Science Fiction"),
    (5, "Drama")
]

with conn.cursor() as cur:

    cur.executemany("""
        INSERT INTO genre (
            genre_id,
            genre_name
        )
        VALUES (%s, %s);
    """, genres)

content_genres = [
    (1, 1),  # 한강 추격전 - Action
    (1, 2),  # 한강 추격전 - Comedy

    (2, 1),  # 마지막 복수 - Action
    (2, 3),  # 마지막 복수 - Thriller

    (3, 4),  # 우주 생존자 - Science Fiction
    (3, 3),  # 우주 생존자 - Thriller

    (4, 5),  # 우리들의 교실 - Drama

    (5, 2),  # 웃음 원정대 - Comedy

    (6, 5)   # 조용한 주말 - Drama
]

with conn.cursor() as cur:

    cur.executemany("""
        INSERT INTO content_genre (
            content_id,
            genre_id
        )
        VALUES (%s, %s);
    """, content_genres)

tags = [
    (1, 90001, "police", "demo"),
    (2, 90002, "chase", "demo"),
    (3, 90003, "revenge", "demo"),
    (4, 90004, "crime", "demo"),
    (5, 90005, "survival", "demo"),
    (6, 90006, "space", "demo"),
    (7, 90007, "school", "demo"),
    (8, 90008, "friendship", "demo"),
    (9, 90009, "travel", "demo"),
    (10, 90010, "mission", "demo"),
    (11, 90011, "family", "demo"),
    (12, 90012, "countryside", "demo")
]

with conn.cursor() as cur:

    cur.executemany("""
        INSERT INTO content_tag (
            tag_id,
            source_keyword_id,
            tag_name,
            source_name
        )
        VALUES (%s, %s, %s, %s);
    """, tags)

content_tags = [
    (1, 1),   # police
    (1, 2),   # chase

    (2, 3),   # revenge
    (2, 4),   # crime

    (3, 5),   # survival
    (3, 6),   # space

    (4, 7),   # school
    (4, 8),   # friendship

    (5, 8),   # friendship
    (5, 9),   # travel
    (5, 10),  # mission

    (6, 11),  # family
    (6, 12)   # countryside
]

with conn.cursor() as cur:

    cur.executemany("""
        INSERT INTO content_tag_map (
            content_id,
            tag_id
        )
        VALUES (%s, %s);
    """, content_tags)

people = [
    (1, 80001, "김민수"),
    (2, 80002, "박지훈"),
    (3, 80003, "이서준"),
    (4, 80004, "최유진"),
    (5, 80005, "John Smith"),
    (6, 80006, "이지영"),
    (7, 80007, "Yuki Sato")
]

with conn.cursor() as cur:

    cur.executemany("""
        INSERT INTO person (
            person_id,
            tmdb_person_id,
            person_name
        )
        VALUES (%s, %s, %s);
    """, people)

content_people = [
    (1, 1, "actor"),
    (1, 2, "director"),

    (2, 3, "actor"),
    (2, 4, "director"),

    (3, 5, "actor"),

    (4, 1, "actor"),

    (5, 6, "cast"),

    (6, 7, "actor")
]

with conn.cursor() as cur:

    cur.executemany("""
        INSERT INTO content_person_role (
            content_id,
            person_id,
            role_type
        )
        VALUES (%s, %s, %s);
    """, content_people)

# sample_data 삽입

embedding_rows = [
    (
        1,
        "Action Comedy police chase 경찰 범죄 조직 추격 빠르고 유쾌한 이야기",
        None
    ),
    (
        2,
        "Action Thriller revenge crime 가족을 잃은 주인공의 범죄 조직 복수 이야기",
        None
    ),
    (
        3,
        "Science Fiction Thriller survival space 우주선 사고 후 홀로 생존하는 이야기",
        None
    ),
    (
        4,
        "Drama school friendship 학교 친구들의 갈등과 성장 이야기",
        None
    ),
    (
        5,
        "Comedy friendship travel mission 출연진들이 여행하며 미션을 수행하는 예능",
        None
    ),
    (
        6,
        "Drama family countryside 가족이 시골에서 시간을 보내며 관계를 회복하는 이야기",
        None
    )
]

with conn.cursor() as cur:

    cur.executemany("""
        INSERT INTO content_embedding (
            content_id,
            embedding_text,
            embedding
        )
        VALUES (%s, %s, %s);
    """, embedding_rows)

conn.commit()

def run(sql_text, params=None):
    with conn.cursor() as cur:
        cur.execute(sql_text, params)
        rows = cur.fetchall()

    for row in rows:
        print(row)

    print(f"-> {len(rows)}행")

    return rows

#------------------------------------------------#
#---------데이터 추출 확인(단독)------------------#

# run("select title, content_type from content where content_type='movie'")

# run("select title, runtime_minutes from content where runtime_minutes <=60 ")

# run("select title from content where content_type='movie' and country_code='KR' and runtime_minutes <= 60")

#------------------------------------------------#
#---------데이터 추출 확인(join)------------------#

# run("""select c.title, g.genre_name 
# from content c join content_genre cg on c.content_id=cg.content_id
# join genre g on cg.genre_id=g.genre_id
# where g.genre_name='Action' and c.content_type='movie'
# """)

# run(""" select c.title, p.person_name
# from content c join content_person_role cpr on c.content_id=cpr.content_id
# join person p on cpr.person_id=p.person_id
# where p.person_name=%s and cpr.role_type=%s
# """,('김민수','actor'))

# 목표: 60분 이하 한국 action 영화
# run("""select title 
# from content c join content_genre cg on c.content_id=cg.content_id
# join genre g on cg.genre_id= g.genre_id
# where c.runtime_minutes<=60 and c.country_code=%s and g.genre_name=%s and c.content_type = %s


#""",('KR','Action','movie'))

# run("""select title 
# from content c join content_genre cg on c.content_id=cg.content_id
# join genre g on cg.genre_id= g.genre_id
# where c.runtime_minutes<=60 and c.country_code=%s and g.genre_name=%s and c.content_type = %s


# """,('US','Action','movie'))

#----------------------------------0---------------#
#--- filters를 가지고 sql을 통해 db 조회하는 함수 ---#
def search_contents(filters):
    conditions=[]
    params=[]
    joins=[] # genre를 뽑기 위함


    if filters['content_type'] is not None:
        conditions.append('c.content_type=%s')
        params.append(filters['content_type'])

    if filters['country_code'] is not None:
        conditions.append('c.country_code=%s')
        params.append(filters['country_code'])

    if filters['max_runtime'] is not None:
        conditions.append('c.runtime_minutes<=%s')
        params.append(filters['max_runtime'])

    if filters['genre'] is not None:
        joins.append(
            'join content_genre cg on c.content_id=cg.content_id'
        )
        joins.append(
            'join genre g on cg.genre_id=g.genre_id'
        )
        conditions.append('g.genre_name=%s')
        params.append(filters['genre'])

    if filters['person_name'] is not None:
        joins.append(
            'join content_person_role cpr on c.content_id=cpr.content_id'
        )
        joins.append(
            'join person p on cpr.person_id=p.person_id'
        )
        conditions.append('p.person_name=%s')
        params.append(filters['person_name'])

    if filters['role_type'] is not None:
        conditions.append('cpr.role_type=%s')
        params.append(filters['role_type'])

    # joins와 coditions를 하나의 sql 문장으로 합치는 단계
    join_sql=' '.join(joins)
    if conditions:
        where_sql='where '+' AND '.join(conditions)
    else:
        where_sql=''

    # 한 줄로 합쳐짐.

    sql=f'''
        select c.content_id, c.title, c.content_type, c.runtime_minutes, c.overview
        from content c
        {join_sql}
        {where_sql}
    '''
    # print(joins)
    # print(conditions)
    # print(params)
    # print(sql)

    # postgresql에 전달
    with conn.cursor() as cur:
        cur.execute(sql,params)
        rows=cur.fetchall()
        return rows

person_names = [
        "김민수",
        "박지훈",
        "이서준",
        "최유진",
        "이지영"
    ]

# input 값 매칭 함수
def extract_filters(user_query):
    filters = {
        "content_type": None,
        "country_code": None,
        "max_runtime": None,
        "genre": None,
        "person_name": None,
        "role_type": None
    }

    if '영화' in user_query:
        filters['content_type']='movie'
    elif '드라마' in user_query:
        filters['content_type']='drama'
    elif '예능' in user_query:
        filters['content_type']='variety'

    if '한국' in user_query:
        filters['country_code']='KR'
    elif '미국' in user_query:
        filters['country_code']='US'
    elif '일본' in user_query:
        filters['country_code']='JP'

    # runtime 관련(숫자를 자연어에서 뽑는 부분)
    runtime_match=re.search(r'(\d+)\s*분\s*이하',user_query)
    hour_match=re.search(r'(\d+)\s*시간\s*이하',user_query)

    if hour_match:
        hours=int(hour_match.group(1))
        filters['max_runtime']=hours * 60

    if runtime_match:
        filters['max_runtime']=int(runtime_match.group(1))

    # genre

    genre_map = {
    "액션": "Action",
    "코미디": "Comedy",
    "스릴러": "Thriller",
    "SF": "Science Fiction"
}
    
    for keyword, genre_name in genre_map.items():
        if keyword in user_query:
            filters['genre']=genre_name
            break

    # person 관련

    for person_name in person_names:
        if person_name in user_query:
            filters["person_name"] = person_name
            break

    if filters['person_name'] is not None:
        filters['role_type']='actor'

        if '감독' in user_query:
            filters['role_type']='director'

    return filters

# llm 연결

client=OpenAI()

def create_embedding(text):
    response=client.embeddings.create(
        model=embedding_model,
        input=text,
        dimensions=embedding_dimensions
    )
    return response.data[0].embedding

# db에서 정보 가지고 오기

with conn.cursor() as cur:
    cur.execute("""
        SELECT content_id, embedding_text
        FROM content_embedding
    """)

    rows = cur.fetchall()

for content_id, embedding_text in rows:
    embedding = create_embedding(embedding_text)

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE content_embedding
            SET embedding = %s
            WHERE content_id = %s
        """, (embedding, content_id))

conn.commit()

# sql 후보 제한 + pgvector 의미 정렬
def search_by_embedding(candidate_ids, semantic_query):
    query_embedding = create_embedding(semantic_query)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                c.content_id,
                c.title,
                c.content_type,
                c.runtime_minutes,
                STRING_AGG(g.genre_name, ', ') AS genres,
                c.overview,
                ce.embedding <=> %s::vector AS distance

            FROM content_embedding ce

            JOIN content c
                ON ce.content_id = c.content_id

            LEFT JOIN content_genre cg
                ON c.content_id = cg.content_id

            LEFT JOIN genre g
                ON cg.genre_id = g.genre_id

            WHERE c.content_id = ANY(%s::bigint[])
            AND ce.embedding IS NOT NULL

            GROUP BY
                c.content_id,
                c.title,
                c.content_type,
                c.runtime_minutes,
                c.overview,
                ce.embedding

            ORDER BY distance ASC

        """, (query_embedding, candidate_ids))

        vector_results = cur.fetchall()

    return vector_results

def extract_semantic_query(user_query):
    semantic_query = user_query

    # SQL에서 처리할 명확한 키워드 제거
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

    for keyword in explicit_keywords:
        semantic_query = semantic_query.replace(keyword, "")

    for person_name in person_names:
        semantic_query = semantic_query.replace(person_name, "")

    # 러닝타임 조건 제거
    semantic_query = re.sub(r"\d+\s*분\s*이하", "", semantic_query)
    semantic_query = re.sub(r"\d+\s*시간\s*이하", "", semantic_query)

    # 추천 문장에서 불필요한 표현 제거
    semantic_query = semantic_query.replace("중에서", "")
    semantic_query = semantic_query.replace("추천해줘", "")

    # 역할 표현 제거
    semantic_query = semantic_query.replace("배우가", "")
    semantic_query = semantic_query.replace("배우", "")
    semantic_query = semantic_query.replace("감독이", "")
    semantic_query = semantic_query.replace("감독", "")
    semantic_query = semantic_query.replace("출연한", "")
    semantic_query = semantic_query.replace("출연", "")
    semantic_query = semantic_query.replace("나온", "")

    semantic_query = re.sub(r"\s+", " ", semantic_query)

    return semantic_query.strip()


# 추천
def recommend(user_query, top_n=3):

    filters = extract_filters(user_query)

    results = search_contents(filters)

    candidate_ids = [row[0] for row in results]

    if not candidate_ids:
        print("조건에 맞는 콘텐츠가 없습니다.")
        return []

    semantic_query = extract_semantic_query(user_query)

    if not semantic_query:
        final_results = get_content_details(candidate_ids)
        return final_results[:top_n]

    vector_results = search_by_embedding(
        candidate_ids,
        semantic_query
    )

    return vector_results[:top_n]

def get_content_details(candidate_ids):

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                c.content_id,
                c.title,
                c.content_type,
                c.runtime_minutes,
                STRING_AGG(g.genre_name, ', ') AS genres,
                c.overview,
                NULL::double precision AS distance

            FROM content c

            LEFT JOIN content_genre cg
                ON c.content_id = cg.content_id

            LEFT JOIN genre g
                ON cg.genre_id = g.genre_id

            WHERE c.content_id = ANY(%s::bigint[])

            GROUP BY
                c.content_id,
                c.title,
                c.content_type,
                c.runtime_minutes,
                c.overview

            ORDER BY c.content_id
        """, (candidate_ids,))

        detail_results = cur.fetchall()

    return detail_results



user_query = "편하게 볼 수 있는 거 추천해줘"

results = recommend(user_query, top_n=3)

for row in results:
    print(row)

conn.close()