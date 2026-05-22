import sqlite3

def run():
    conn = sqlite3.connect('/app/data/tradingagents.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticker, trade_date, status, provider, quick_model, deep_model, depth FROM runs WHERE ticker='NVDA'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()

if __name__ == '__main__':
    run()
