import sqlite3

# Connect to the database
conn = sqlite3.connect('songs.db')
cursor = conn.cursor()

# 1. Get the names of all tables in the database
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

if not tables:
    print("No tables found in the database.")
else:
    table_name = tables[0][0]
    print(f"Checking table: {table_name}\n")

    # 2. Fetch the column names (headers)
    cursor.execute(f"PRAGMA table_info({table_name})")
    headers = [info[1] for info in cursor.fetchall()]
    print(headers)

    # 3. Fetch the first 5 rows
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
    rows = cursor.fetchall()

    for row in rows:
        print(row)

conn.close()