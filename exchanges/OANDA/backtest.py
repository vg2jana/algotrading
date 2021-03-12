import numpy as np
import pandas as pd
import copy
import sqlite3
import datetime
import json
import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import matplotlib.pyplot as plt
from stockstats import StockDataFrame


def fetch_ohlc(symbol, granularity, count=500, t_from=None, t_to=None, align_tz='UTC',
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
        data = client.request(r)
    except Exception as e:
        print("Unable to fetch candles for symbol {}:\n{}".format(symbol, e))

    if len(data) == 0:
        return data

    output = []
    for d in data['candles']:
        output.append({
            "datetime": d["time"],
            "volume": int(d["volume"]),
            "open": float(d["mid"]["o"]),
            "high": float(d["mid"]["h"]),
            "low": float(d["mid"]["l"]),
            "close": float(d["mid"]["c"])
        })

    return output


def dump_to_json_file():
    data = []
    symbol = "EUR_JPY"
    granularity = "M15"
    while True:
        if len(data) == 0:
            t_from = "2020-03-01T00:00:00.00Z"
            d = fetch_ohlc(symbol, granularity, t_from=t_from, count=1000)
        else:
            t_from = data[-1]["datetime"]
            d = fetch_ohlc(symbol, granularity, t_from=t_from, count=1000, includeFirst=False)
        if len(d) == 0:
            break
        data.extend(d)

    with open("data/{}_1year_{}".format(symbol.lower(), granularity), "w") as f:
        json.dump(data, f, indent=4)


def moving_average(dataframe, n_candles, source="close"):
    DF = dataframe.copy()
    _func = "{}_{}_sma".format(source, n_candles)
    if _func in DF.columns:
        DF = DF.drop(columns=_func, axis=1)
    _df = StockDataFrame.retype(DF)
    _df.get(_func)
    dataframe[_func] = DF[_func]


# ----- Fixed -----
def backtest_gbp_usd_d():
    df = pd.read_json("data/gbp_usd_4year_D")
    df["vratio"] = df["volume"] / df["volume"].shift()
    df.dropna(inplace=True)
    df["buy"] = (df["volume"] > 80000) & (df["close"] > df["open"])
    df["sell"] = (df["volume"] > 80000) & (df["open"] > df["close"])
    df["exit_buy"] = (df["close"] < df["open"]) & (df["close"].shift() < df["open"].shift())
    df["exit_sell"] = (df["close"] > df["open"]) & (df["close"].shift() > df["open"].shift())

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    sl = -0.005
    # df = df.tail(365)
    # df.reset_index(drop=True, inplace=True)
    for i in range(1, len(df)):
        b = df["buy"][i - 1]
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i

        if len(buy) != 0 and (df["exit_buy"][i - 1] == True or df["sell"][i - 1] == True or df["close"][i - 1] - buy["entry_price"] < sl):
            buy["exit_price"] = df["open"][i]
            buy["exit_row"] = i
            buy["pnl"] = buy["exit_price"] - buy["entry_price"]
            buy["period"] = buy["exit_row"] - buy["entry_row"]
            buy["side"] = "buy"
            trades.append(buy)
            buy = {}

        if len(sell) != 0 and (df["exit_sell"][i - 1] == True or df["buy"][i - 1] == True or sell["entry_price"] - df["close"][i - 1] < sl):
            sell["exit_price"] = df["open"][i]
            sell["exit_row"] = i
            sell["pnl"] = sell["entry_price"] - sell["exit_price"]
            sell["period"] = sell["exit_row"] - sell["entry_row"]
            sell["side"] = "sell"
            trades.append(sell)
            sell = {}

    trades_df = pd.DataFrame(trades)
    print(trades_df)


# ----- Fixed -----
def backtest_eur_usd_M15():
    df = pd.read_json("data/eur_usd_1year_M15")
    point = "close"
    m = [9, 20, 50, 200]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    # Drop the first 200 rows as the average is not accurate
    _df = pd.DataFrame(df.iloc[m[-1]:])
    _df["buy"] = (_df[ma[-1]].shift() > _df[ma[-2]].shift()) & (
                _df[ma[-1]] < _df[ma[-2]]) & (
                                _df[ma[-2]] < _df[ma[-3]]) & (_df[ma[-3]] < _df[ma[-4]])
    _df["trend_high"] = (_df[ma[-1]] < _df[ma[-2]]) & (_df[ma[-2]] < _df[ma[-3]]) & (
            _df[ma[-2]] < _df[ma[-4]])
    _df["sell"] = (_df[ma[-1]].shift() < _df[ma[-2]].shift()) & (
                _df[ma[-1]] > _df[ma[-2]]) & (
                                 _df[ma[-2]] > _df[ma[-3]]) & (_df[ma[-3]] > _df[ma[-4]])
    _df["trend_low"] = (_df[ma[-1]] > _df[ma[-2]]) & (_df[ma[-2]] > _df[ma[-3]]) & (
            _df[ma[-2]] > _df[ma[-4]])

    df = _df

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    tp = 0.005
    sl = -0.005
    # df = df.tail(365)
    # df.reset_index(drop=True, inplace=True)
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i

        if len(buy) != 0:
            if df["trend_high"][i - 1] == True and df["high"][i] - buy["entry_price"] >= tp * 2:
                buy["exit_price"] = buy["entry_price"] + (tp * 2)
            elif df["trend_high"][i - 1] == False:
                if df["low"][i] - buy["entry_price"] <= sl:
                    buy["exit_price"] = buy["entry_price"] + sl
                elif df["high"][i] - buy["entry_price"] >= tp:
                    buy["exit_price"] = buy["entry_price"] + tp

            if "exit_price" in buy:
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if df["trend_low"][i - 1] == True and sell["entry_price"] - df["low"][i] >= tp * 2:
                sell["exit_price"] = sell["entry_price"] - (tp * 2)
            elif df["trend_low"][i - 1] == False:
                if sell["entry_price"] - df["high"][i] <= sl:
                    sell["exit_price"] = sell["entry_price"] - sl
                elif sell["entry_price"] - df["low"][i] >= tp:
                    sell["exit_price"] = sell["entry_price"] - tp

            if "exit_price" in sell:
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"]))
    print(len(trades_df))


# ----- Fixed -----
def backtest_aud_usd_M15():
    df = pd.read_json("data/aud_usd_1year_M15")
    point = "close"
    m = [9, 12, 18, 25]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    # Drop the first 200 rows as the average is not accurate
    _df = pd.DataFrame(df.iloc[m[-1]:])
    _df["buy"] = (_df[ma[-2]].shift() > _df[ma[-4]].shift()) & (_df[ma[-2]] < _df[ma[-4]])
    _df["exit_buy"] = (_df[ma[-2]].shift() > _df[ma[-1]].shift()) & (_df[ma[-2]] < _df[ma[-1]])

    _df["sell"] = (_df[ma[-2]].shift() < _df[ma[-4]].shift()) & (_df[ma[-2]] > _df[ma[-4]])
    _df["exit_sell"] = (_df[ma[-2]].shift() < _df[ma[-1]].shift()) & (_df[ma[-2]] > _df[ma[-1]])

    # _df["trend_high"] = (_df[ma[-1]] < _df[ma[-2]])
    #
    # _df["trend_low"] = (_df[ma[-1]] > _df[ma[-2]])

    df = _df

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    tp = 0.025
    sl = 0.5 # Not required
    # df = df.tail(365)
    # df.reset_index(drop=True, inplace=True)
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i

        if len(buy) != 0:
            if buy["entry_price"] - df["low"][i - 1] >= sl:
                buy["exit_price"] = buy["entry_price"] - sl
            elif df["high"][i] - buy["entry_price"] >= tp:
                buy["exit_price"] = buy["entry_price"] + tp
            elif df["exit_buy"][i - 1] == True:
                buy["exit_price"] = df["open"][i]

            if "exit_price" in buy:
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if df["high"][i - 1] - sell["entry_price"] >= sl:
                sell["exit_price"] = sell["entry_price"] + sl
            elif sell["entry_price"] - df["low"][i] >= tp:
                sell["exit_price"] = sell["entry_price"] - tp
            elif df["exit_sell"][i - 1] == True:
                sell["exit_price"] = df["open"][i]

            if "exit_price" in sell:
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"]))
    print(len(trades_df))


# ----- Fixed -----
def backtest_usd_jpy_M15():
    df = pd.read_json("data/usd_jpy_1year_M15")
    point = "close"
    m = [9, 12, 18, 25]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    # Drop the first 200 rows as the average is not accurate
    _df = pd.DataFrame(df.iloc[m[-1]:])
    _df["buy"] = (_df[ma[-2]].shift() > _df[ma[-4]].shift()) & (_df[ma[-2]] < _df[ma[-4]])
    _df["exit_buy"] = (_df[ma[-2]].shift() > _df[ma[-1]].shift()) & (_df[ma[-2]] < _df[ma[-1]])

    _df["sell"] = (_df[ma[-2]].shift() < _df[ma[-4]].shift()) & (_df[ma[-2]] > _df[ma[-4]])
    _df["exit_sell"] = (_df[ma[-2]].shift() < _df[ma[-1]].shift()) & (_df[ma[-2]] > _df[ma[-1]])

    # _df["trend_high"] = (_df[ma[-1]] < _df[ma[-2]])
    #
    # _df["trend_low"] = (_df[ma[-1]] > _df[ma[-2]])

    df = _df

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    tp = 3
    sl = 3 # Not required
    # df = df.tail(365)
    # df.reset_index(drop=True, inplace=True)
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i

        if len(buy) != 0:
            if buy["entry_price"] - df["low"][i - 1] >= sl:
                buy["exit_price"] = buy["entry_price"] - sl
            elif df["high"][i] - buy["entry_price"] >= tp:
                buy["exit_price"] = buy["entry_price"] + tp
            elif df["exit_buy"][i - 1] == True:
                buy["exit_price"] = df["open"][i]

            if "exit_price" in buy:
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if df["high"][i - 1] - sell["entry_price"] >= sl:
                sell["exit_price"] = sell["entry_price"] + sl
            elif sell["entry_price"] - df["low"][i] >= tp:
                sell["exit_price"] = sell["entry_price"] - tp
            elif df["exit_sell"][i - 1] == True:
                sell["exit_price"] = df["open"][i]

            if "exit_price" in sell:
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"]))
    print(len(trades_df))


# ----- Fixed -----
def backtest_eur_jpy_H1():
    df = pd.read_json("data/eur_jpy_2year_H1")
    point = "close"
    m = [9, 20, 50, 200]
    # m = [9, 12, 18, 25]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    # Drop the first 200 rows as the average is not accurate
    _df = pd.DataFrame(df.iloc[m[-1]:])
    _df["buy"] = (_df[ma[-2]].shift() > _df[ma[-4]].shift()) & (_df[ma[-2]] < _df[ma[-4]])
    _df["exit_buy"] = (_df[ma[-2]].shift() > _df[ma[-1]].shift()) & (_df[ma[-2]] < _df[ma[-1]])

    _df["sell"] = (_df[ma[-2]].shift() < _df[ma[-4]].shift()) & (_df[ma[-2]] > _df[ma[-4]])
    _df["exit_sell"] = (_df[ma[-2]].shift() < _df[ma[-1]].shift()) & (_df[ma[-2]] > _df[ma[-1]])

    # _df["trend_high"] = (_df[ma[-1]] < _df[ma[-2]])
    #
    # _df["trend_low"] = (_df[ma[-1]] > _df[ma[-2]])

    df = _df

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    tp = 1.5
    sl = 1.5 # Not required
    # df = df.tail(365)
    # df.reset_index(drop=True, inplace=True)
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i

        if len(buy) != 0:
            if buy["entry_price"] - df["low"][i - 1] >= sl:
                buy["exit_price"] = buy["entry_price"] - sl
            elif df["high"][i] - buy["entry_price"] >= tp:
                buy["exit_price"] = buy["entry_price"] + tp
            elif df["exit_buy"][i - 1] == True or df["sell"][i - 1] == True:
                buy["exit_price"] = df["open"][i]

            if "exit_price" in buy:
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if df["high"][i - 1] - sell["entry_price"] >= sl:
                sell["exit_price"] = sell["entry_price"] + sl
            elif sell["entry_price"] - df["low"][i] >= tp:
                sell["exit_price"] = sell["entry_price"] - tp
            elif df["exit_sell"][i - 1] == True or df["buy"][i - 1] == True:
                sell["exit_price"] = df["open"][i]

            if "exit_price" in sell:
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"]))
    print(len(trades_df))


if __name__ == "__main__":
    # with open('prod/key.json', 'r') as f:
    #     key = json.load(f)
    #
    # token = key['prod_token']
    # client = oandapyV20.API(access_token=token, environment="live")
    # dump_to_json_file()

    backtest_aud_usd_M15()

