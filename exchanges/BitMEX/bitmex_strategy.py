import json
import bitmex
import pandas as pd
from datetime import datetime, timedelta
from exchanges.BitMEX.bitmex_symbol import BitMEXSymbol
from strategies.res_brkout import ResistanceBreakout
from exchanges.BitMEX.mywebsocket import MyWebSocket


class ResistanceBreakOutBitMEX(ResistanceBreakout):
    def __init__(self, dataframe, symbol, websocket):
        self.symbol = symbol
        self.client = symbol.client
        self.ws = websocket
        super(ResistanceBreakOutBitMEX, self).__init__(dataframe, duration=self.symbol.frequency)

    def update_book(self):
        self.book['ltp'] = self.ws.ltp()

    def update_dataframe(self):
        last_updated = self.dataframe.index[-1]
        start_time = last_updated + timedelta(minutes=1)
        df = self.symbol.fetch_data(start_time)
        self.dataframe = pd.concat([self.dataframe, df])


if __name__ == '__main__':
    key = "UzlrFYMJJGo_A7QDihj3ZtY8"
    secret = "LuA5rSvqLGDghJ8A-6ZtDEgahvbIroqFPpRdKd-uI3DPSXQG"
    product = 'XBTUSD'
    frequency = '1m'
    test_env = True
    if test_env is True:
        endpoint = "https://testnet.bitmex.com/api/v1"
    else:
        endpoint = "https://www.bitmex.com/api/v1"

    client = bitmex.bitmex(api_key=key, api_secret=secret, test=test_env)
    websocket = MyWebSocket(endpoint, product, key, secret)
    websocket.connect_ws()
    symbol = BitMEXSymbol(product, client=client, frequency=frequency)
    dataframe = symbol.fetch_data(datetime.utcnow() - timedelta(hours=1), count=100)
    res_bro = ResistanceBreakOutBitMEX(dataframe, symbol, websocket)
    res_bro.time_bound_run(600)
