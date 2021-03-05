import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import pandas as pd
import numpy as np
import time
import json
import logging
import datetime
import requests
import sys
from decimal import Decimal
from stockstats import StockDataFrame


class Candles:

    def __init__(self, client):
        with open('../prod/key.json', 'r') as f:
            key = json.load(f)
        token = key['prod_token']
        self.client = client
        self.log = logging.getLogger()

    def fetch_ohlc(self, symbol, granularity, count=500, t_from=None, t_to=None, align_tz='UTC',
                   includeFirst=True):
        params = {
            "granularity": granularity,
            "count": count,
            "alignmentTimezone": align_tz
        }

        if t_from is not None:
            params["from"] = t_from
            params["includeFirst"] = includeFirst
        if t_to is not None:
            params["to"] = t_to

        data = {}
        try:
            r = instruments.InstrumentsCandles(symbol, params=params)
            data = self.client.request(r)
        except Exception as e:
            self.log.error("Unable to fetch candles for symbol {}:\n{}".format(symbol, e))

        if len(data) == 0:
            return data

        output = []
        for d in data['candles']:
            output.append({
                "datetime": d["time"],
                "volume": d["volume"],
                "open": d["mid"]["o"],
                "high": d["mid"]["h"],
                "low": d["mid"]["l"],
                "close": d["mid"]["c"]
            })

        return output

    @staticmethod
    def moving_average(dataframe, n_candles, source="close"):
        _df = StockDataFrame.retype(dataframe)
        _func = "{}_{}_sma".format(source, n_candles)
        _name = "sma_{}".format(n_candles)
        dataframe.append(_df.get(_func))
        dataframe.rename(columns={_func: _name}, inplace=True)
        return dataframe


if __name__ == "__main__":
    with open('../prod/key.json', 'r') as f:
        key = json.load(f)

    token = key['prod_token']
    client = oandapyV20.API(access_token=token, environment="live")
    m = Candles(client)
    _to = "{}Z".format(datetime.datetime.utcnow().isoformat())
    data = m.fetch_ohlc("EUR_USD", "M15", t_to="2021-03-05T06:45:00.00Z", count=1000)
    df = pd.DataFrame(data)
    last_time = df.iloc[-1]["datetime"]
    data = m.fetch_ohlc("EUR_USD", "M15", t_from=last_time, includeFirst=False)
    df2 = pd.DataFrame(data)
    df = pd.concat([df, df2])
    m.moving_average(df, 9)
    m.moving_average(df, 20)
    m.moving_average(df, 50)
    m.moving_average(df, 200)

    # Drop the first 200 rows as the average is not accurate
    df = df.iloc[200:]
    df["buy_signal"] = (df["sma_200"] > df["sma_50"].shift()) & (df["sma_200"] < df["sma_50"]) & (
                df["sma_50"] < df["sma_20"]) & (df["sma_20"] < df["sma_9"])
    df["trend_high"] = (df["sma_200"] < df["sma_50"]) & (df["sma_50"] < df["sma_20"])
    df["sell_signal"] = (df["sma_200"] < df["sma_50"].shift()) & (df["sma_200"] > df["sma_50"]) & (
                df["sma_50"] > df["sma_20"]) & (df["sma_20"] > df["sma_9"])
    df["trend_low"] = (df["sma_200"] > df["sma_50"]) & (df["sma_50"] > df["sma_20"])
    print(df)
