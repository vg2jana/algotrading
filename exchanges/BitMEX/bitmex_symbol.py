import sqlite3
import pandas as pd
import logging
import re
from indicator.base_symbol import Symbol
from time import sleep
from datetime import datetime, timedelta
from strategies.res_brkout import ResistanceBreakoutBackTest
from exchanges.BitMEX.rest_client import RestClient


class BitMEXSymbol(Symbol):
    def __init__(self, *args, **kwargs):
        self.client = kwargs.pop('client')
        self.logger = logging.getLogger()
        super(BitMEXSymbol, self).__init__(*args, **kwargs)

    def data_to_df(self, data):
        if data is None or len(data) == 0:
            return
        dataframe = pd.DataFrame(data)
        df1 = dataframe.loc[:, ('timestamp', 'open', 'high', 'low', 'close', 'volume')]
        df1.rename(columns={"timestamp": "Datetime", "open": "Open", "high": "High", "low": "Low", "close": "Adj Close",
                            "volume": "Volume"}, inplace=True)
        df1.set_index('Datetime', inplace=True)
        self.logger.info("UPDATE CANDLE:\n{}".format(str(data)))
        return df1

    def fetch_data(self, start_time, end_time=None, count=1000, data=None, frequency=None):
        if type(start_time) is not str:
            start_time = start_time.strftime("%Y-%m-%d %H:%M")
        filter = '{"symbol": "%s", "startTime": "%s"}' % (self.symbol, start_time)
        if end_time is not None:
            if type(end_time) is not str:
                end_time = end_time.strftime("%Y-%m-%d %H:%M")
            filter = '{"symbol": "%s", "startTime": "%s", "endTime": "%s"}' % (self.symbol, start_time, end_time)

        if frequency is None:
            frequency = self.frequency
        bin_size = frequency
        match = re.match("(\d+)(\S)", bin_size)
        counter, period = match.groups()
        counter = int(counter)
        if period == 'm':
            if counter % 5 == 0:
                bin_size = '5m'
                counter = int(counter / 5)
            else:
                bin_size = '1m'
        elif period == 'h':
            bin_size = '1h'
        elif period == 'd':
            bin_size = '1d'

        attempts = 5
        if data is None:
            while attempts > 0:
                data = self.client.trade_bucket(binSize=bin_size, count=count, filter=filter)
                if data is not None and len(data) > 0:
                    break
                sleep(1)
                attempts -= 1
            else:
                return

        if frequency not in ('1m', '5m', '1h', '1d'):
            temp = []
            for i in range(0, len(data), counter):
                if i + counter > len(data):
                    break
                d = {
                    'timestamp': data[i]['timestamp'],
                    'open': data[i]['open'],
                    'close': data[i + counter - 1]['close'],
                    'high': max([x['high'] for x in data[i:i+counter]]),
                    'low': min([x['low'] for x in data[i:i+counter]]),
                    'volume': sum([x['volume'] for x in data[i:i+counter]])
                }
                temp.append(d)
            data = temp

        return self.data_to_df(data)


if __name__ == '__main__':
    def sample(key, secret):
        db = '/Users/jganesan/workspace/algotrading/symbols.sqlite3'
        conn = sqlite3.connect(db)
        key = "MjLgBPoZey_vp3rQ7uM0riqA"
        secret = "1AiC5B6cqs4hRSgBDPU_KyU3rSCyMiIrCoD1mkkT-LjP3ymJ"
        symbol = 'XBTUSD'
        frequency = '5m'
        client = client = RestClient(False, key, secret, symbol)
        xbt = BitMEXSymbol(symbol, conn=conn, client=client, frequency=frequency)
        df1 = xbt.fetch_data(datetime.utcnow() - timedelta(days=3), count=740)
        xbt.write_to_db(df1)

        conn.close()

        s = ResistanceBreakoutBackTest(df)
        s.weighted = False
        s.rolling_period = 10
        s.min_profit = 13.5
        s.min_loss = -20
        s.setup()
        s.run()

        sum = 0
        for r in s.returns:
            sum += r[-1] - 13.5


    key = "VvD5-fMBfiZ9dlMtXP2pffHj"
    secret = "jROi3UZ5q_hkVW2RnK3xbCQEnTzpLXcnbOdUCJTnQFrrdUgj"
    product = 'XBTUSD'
    frequency = '5m'
    client = RestClient(False, key, secret, product)
    symbol = BitMEXSymbol(product, client=client, frequency=frequency)
    # now = datetime.utcnow()
    # data = []
    # fp = open('XBTUSD_5m_100days.txt', 'w')
    # wanted_ones = ['open', 'close', 'low', 'high', 'volume', 'timestamp']
    # for i in range(0, 100, 3):
    #     temp = symbol.fetch_data(datetime.utcnow() - timedelta(days=100 - i), count=864)
    #     ohlc = []
    #     for t in temp:
    #         d = {k: t[k] for k in wanted_ones}
    #         ohlc.append(str(d))
    #     sleep(2)
    #     fp.write('\n'.join(ohlc))
    #     fp.write('\n')
    # fp.close()
    fp = open('XBTUSD_5m_100days.txt', 'r')
    data = [eval(d.replace('datetime.datetime', 'datetime')) for d in fp.readlines()]
    fp.close()
    df = symbol.data_to_df(data)
