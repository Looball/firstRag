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
        SELECT u.id, u.username, u.password_hash
        FROM users AS u
        WHERE u.username = %s
        """
    username = 'monkey'

    res = exe_sql(sql_statement=sql, args_tuple=(username,))
    print(res[0]['username'])
    print(res[0]['password_hash'])


