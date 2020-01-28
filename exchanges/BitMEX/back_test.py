import pandas as pd
import sys
import json
from dateutil.tz import tzutc
from datetime import datetime, timedelta
from exchanges.BitMEX.bitmex_symbol import BitMEXSymbol
from strategies.res_brkout import ResistanceBreakoutBackTest
from strategies.renko_macd import RenkoMACDBackTest
from exchanges.BitMEX.rest_client import RestClient


def renkomacd_backtest(key, secret, product, frequency):
    def import_data():
        fp = open('5m_xbtusd_100days.txt', 'r')
        data = [eval(d.replace('datetime.datetime', 'datetime')) for d in fp.readlines()]
        fp.close()
        df = symbol.data_to_df(data)
        return df
    client = RestClient(False, key, secret, product)
    symbol = BitMEXSymbol(product, client=client, frequency=frequency)
    # dataframe = pd.DataFrame(symbol.fetch_data(datetime.utcnow() - timedelta(days=3)))
    dataframe = import_data()
    backtest = RenkoMACDBackTest(dataframe)
    backtest.atr_period = 60
    backtest.slope_period = 3
    backtest.macd_array = (6, 15, 6)
    backtest.setup()
    backtest.run()

    sum = 0
    for r in backtest.returns:
        sum += r[-1] - 13.5

    print(sum)
    return backtest

def resbrk_backtest(key, secret, product, frequency):
    client = RestClient(False, key, secret, product)
    symbol = BitMEXSymbol(product, client=client, frequency=frequency)
    dataframe = pd.DataFrame(symbol.fetch_data(datetime.utcnow() - timedelta(days=3)))
    res_bro = ResistanceBreakoutBackTest(dataframe)
    res_bro.weighted = False
    res_bro.rolling_period = 15
    res_bro.min_profit = 13.5
    res_bro.min_loss = 0
    res_bro.setup()
    res_bro.run()

    sum = 0
    trades = []
    time_series = res_bro.dataframe.index.tolist()
    for r in res_bro.returns:
        sum += r[2] - 13.5
        open_frame = res_bro.dataframe.iloc[r[0]]
        close_frame = res_bro.dataframe.iloc[r[1]]
        trades.append((time_series[r[0]], open_frame['Open'], time_series[r[1]], close_frame['Adj Close']))

    print(sum)
    return res_bro


def combo():
    atr_range = (20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120)
    combo = []
    fp = open('combo.txt', 'w')
    for atr in atr_range:
        for slow_ma in range(2, 27):
            for fast_ma in range(1, int(slow_ma / 2)):
                for avg in range(fast_ma, int(slow_ma / 2)):
                    for slope in range(2, avg):
                        macd_array = (fast_ma, slow_ma, avg)
                        combo.append((atr, slope, macd_array))
                        fp.write("%s\n" % str(combo[-1]))
    fp.close()
    sys.exit(0)


if __name__ == '__main__':
    with open("config.json", 'r') as f:
        data = json.load(f)

    params = data['prod']
    key = params['key']
    secret = params['secret']
    product = params['symbol']
    frequency = '5m'
    btc = renkomacd_backtest(key, secret, product, frequency)
