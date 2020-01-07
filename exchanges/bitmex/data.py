import bitmex
import sqlite3
import time
from datetime import datetime, timedelta
from indicator.symbol import Symbol
import pandas as pd
from strategies.res_brkout import ResistanceBreakout

class BitMEXSymbol(Symbol):
    def __init__(self, *args, **kwargs):
        super(BitMEXSymbol, self).__init__(*args, **kwargs)

    def fetch_data(self):
        key = "2sdiDv2-DLkSZfC9A5PRExAN"
        secret = "_Llp9SQBfq46WWnXY8VqZ-vI31gIpn6NlNKdLsGG9LpNFsZR"
        symbol = 'XBTUSD'

        client = bitmex.bitmex(api_key=key, api_secret=secret, test=False)
        result = client.Trade.Trade_getBucketed(binSize='5m', count=1000, filter='{"symbol": "XBTUSD", "startTime": "2019-12-03 00:00"}').result()
        dataframe = pd.DataFrame(result[0])
        df1 = dataframe[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df1.rename(columns={"timestamp": "Datetime", "open": "Open", "high": "High", "low": "Low", "close": "Adj Close", "volume": "Volume"}, inplace=True)
        df1.set_index('Datetime', inplace=True)
        return df1


if __name__ == '__main__':
    db = '/Users/jganesan/workspace/algotrading/symbols.sqlite3'
    conn = sqlite3.connect(db)
    xbt = BitMEXSymbol(conn, 'XBTUSD', frequency='5m')
    # df = xbt.fetch_data()
    # xbt.write_to_db(df)
    df = xbt.read_from_db()
    conn.close()

    s = ResistanceBreakout(df)
    s.weighted = False
    s.rolling_period = 30
    s.setup()
    s.run()

    sum = 0
    for r in s.returns:
        sum += r[-1] - 13.5
