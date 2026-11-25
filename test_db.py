
from config import get_db_connection

try:
    conn = get_db_connection()
    print("MySQL Connected Successfully!")

    conn.close()

except Exception as e:
    print("Database Error:", e)
