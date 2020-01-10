import sqlite3
from indicator.base_symbol import *
from indicator.candle_stick import three_candle_curve
from indicator.rsi import RSI
from strategies.res_brkout import ResistanceBreakoutBackTest

if __name__ == '__main__':
    db = '/Users/jganesan/workspace/algotrading/symbols.sqlite3'
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
    table_list = cursor.execute('SELECT NAME FROM sqlite_master WHERE TYPE = "table"').fetchall()
    cursor.close()

    strategy = {}
    for table in table_list:
        table = table[0]
        df = read_from_db(conn, table)
        strategy[table] = ResistanceBreakoutBackTest(df)
        strategy[table].setup()
        strategy[table].run()
