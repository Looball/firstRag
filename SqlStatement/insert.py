import psycopg
from psycopg.rows import dict_row

def exe_sql(*,sql_statement:str,args_tuple:tuple):
    conn = psycopg.connect(
        "postgresql://bing@localhost:5432/first_rag",
        row_factory=dict_row,
    )

    with conn:
        with conn.cursor() as cur:
            cur.execute(sql_statement, args_tuple)
            rows = cur.fetchall()


        return rows

if __name__ == "__main__":
    sql = f"""
        INSERT INTO conversations (user_id, title)
        VALUES (%s, %s)
        RETURNING id, user_id, title, created_at, updated_at;
        """
    user_id = 3
    title = '新会话'

    res = exe_sql(sql_statement=sql,args_tuple=(user_id,title))
    print(res[0])


