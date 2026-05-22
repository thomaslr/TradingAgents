import sqlite3

def run():
    conn = sqlite3.connect('/app/data/tradingagents.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, tickers, dates, status, created_at FROM research_queue")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()

if __name__ == '__main__':
    run()
