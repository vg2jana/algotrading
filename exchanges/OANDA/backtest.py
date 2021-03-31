import numpy as np
import pandas as pd
import copy
import sqlite3
import json
import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import matplotlib.pyplot as plt
import talib
import statsmodels.api as sm
from stockstats import StockDataFrame
from datetime import datetime, timezone


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
    symbol = "EUR_CAD"
    granularity = "D"
    while True:
        if len(data) == 0:
            t_from = "2017-03-01T00:00:00.00Z"
            d = fetch_ohlc(symbol, granularity, t_from=t_from, count=1000)
        else:
            t_from = data[-1]["datetime"]
            d = fetch_ohlc(symbol, granularity, t_from=t_from, count=1000, includeFirst=False)
        if len(d) == 0:
            break
        data.extend(d)

    with open("data/{}_4year_{}".format(symbol.lower(), granularity), "w") as f:
        json.dump(data, f, indent=4)


def moving_average(dataframe, n_candles, source="close"):
    DF = dataframe.copy()
    _func = "{}_{}_sma".format(source, n_candles)
    if _func in DF.columns:
        DF = DF.drop(columns=_func, axis=1)
    _df = StockDataFrame.retype(DF)
    _df.get(_func)
    dataframe[_func] = DF[_func]


def calculate_slope(ser, n):
    # function to calculate the slope of n consecutive points on a plot
    slopes = [i * 0 for i in range(n - 1)]
    for i in range(n, len(ser) + 1):
        y = ser[i - n:i]
        x = np.array(range(n))
        y_scaled = (y - y.min()) / (y.max() - y.min())
        x_scaled = (x - x.min()) / (x.max() - x.min())
        x_scaled = sm.add_constant(x_scaled)
        model = sm.OLS(y_scaled, x_scaled)
        results = model.fit()
        slopes.append(results.params[-1])
    slope_angle = (np.rad2deg(np.arctan(np.array(slopes))))
    return np.array(slope_angle)


def macd(dataframe, a=9, b=12, c=26, source="close", slope=False):
    _df = dataframe.copy()
    _df["MA_Fast"] = _df[source].ewm(span=b, min_periods=b).mean()
    _df["MA_Slow"] = _df[source].ewm(span=c, min_periods=c).mean()
    dataframe["macd"] = _df["MA_Fast"] - _df["MA_Slow"]
    dataframe["macd_sig"] = dataframe["macd"].ewm(span=a, min_periods=a).mean()
    dataframe["macdh"] = dataframe["macd"] - dataframe["macd_sig"]
    if slope is True:
        dataframe["macd_slope"] = calculate_slope(dataframe["macd"], 5)
        dataframe["macd_sig_slope"] = calculate_slope(dataframe["macd_sig"], 5)


# ----- Fixed -----
def backtest_eur_jpy_H1():
    df = pd.read_json("data/eur_jpy_2year_H1")
    df["day"] = (df["datetime"].dt.day_name())
    macd(df, a=9, b=12, c=26)
    df.dropna(inplace=True)
    point = "close"
    m = [20, 50]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    # _df = pd.DataFrame(df.iloc[m[-1]:])
    _df = pd.DataFrame(df.iloc[m[-1]:])
    start_hour = 7
    end_hour = 14
    _df["buy"] = (_df[ma[0]].shift() > _df[ma[1]].shift()) & (_df["macdh"].shift() <= 0) & (_df["macdh"] > 0) & (
            _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    # _df["trend_low"] = (_df["macdh"] < 0) & (_df["macdh"].shift() >= 0) & (
    #         _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    _df["sell"] = (_df[ma[0]].shift() < _df[ma[1]].shift()) & (_df["macdh"].shift() >= 0) & (_df["macdh"] < 0) & (
            _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    # _df["trend_high"] = (_df["macdh"] > 0) & (_df["macdh"].shift() <= 0) & (
    #         _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    df = _df

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    tp1 = 0.25
    tp2 = 0.75  # or 0.01
    sl = -0.75
    b_sl = None
    s_sl = None
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
            buy["open_time"] = df["datetime"][i]
            b_sl = sl
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i
            sell["open_time"] = df["datetime"][i]
            s_sl = sl

        if len(buy) != 0:
            if df["sell"][i - 1] == True:
                buy["exit_price"] = df["open"][i]
            elif df["low"][i] - buy["entry_price"] <= b_sl:
                buy["exit_price"] = buy["entry_price"] + b_sl
            elif df["high"][i] - buy["entry_price"] >= tp2:
                buy["exit_price"] = buy["entry_price"] + tp2
                b_sl = 0
            elif df["high"][i] - buy["entry_price"] >= tp1:
                b_sl = 0

            if "exit_price" in buy:
                if b_sl == 0:
                    buy["exit_price"] = (buy["exit_price"] + buy["entry_price"] + tp1) / 2
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                buy["close_time"] = df["datetime"][i]
                buy["day"] = df["day"][buy["entry_row"]]
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if df["buy"][i - 1] == True:
                sell["exit_price"] = df["open"][i]
            elif sell["entry_price"] - df["high"][i] <= s_sl:
                sell["exit_price"] = sell["entry_price"] - s_sl
            elif sell["entry_price"] - df["low"][i] >= tp2:
                sell["exit_price"] = sell["entry_price"] - tp2
                s_sl = 0
            elif sell["entry_price"] - df["low"][i] >= tp1:
                s_sl = 0

            if "exit_price" in sell:
                if s_sl == 0:
                    sell["exit_price"] = (sell["exit_price"] + sell["entry_price"] - tp1) / 2
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                sell["close_time"] = df["datetime"][i]
                sell["day"] = df["day"][sell["entry_row"]]
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"] - 0.00028))
    loss_trades = trades_df[trades_df["pnl"] < 0]
    print("Total trades: %d" % len(trades_df))
    print("Profit trades: %d" % len(trades_df[trades_df["pnl"] > 0]))
    print("Loss trades: %d" % len(loss_trades))


# ----- Fixed -----
# There is another for H1 below
def backtest_gbp_usd_d():
    df = pd.read_json("data/gbp_usd_4year_D")
    df["vratio"] = df["volume"] / df["volume"].shift()
    df.dropna(inplace=True)
    df["buy"] = (df["volume"] > 80000) & (df["close"] > df["open"])
    df["sell"] = (df["volume"] > 80000) & (df["open"] > df["close"])
    df["exit_buy"] = (df["close"] < df["open"]) & (df["close"].shift() < df["open"].shift())
    df["exit_sell"] = (df["close"] > df["open"]) & (df["close"].shift() > df["open"].shift())

    last_time = df.iloc[-1]["datetime"]
    diff = datetime.now(timezone.utc) - last_time.to_pydatetime()

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

        if len(buy) != 0 and (df["exit_buy"][i - 1] == True or df["sell"][i - 1] == True or df["close"][i - 1] - buy[
            "entry_price"] < sl):
            buy["exit_price"] = df["open"][i]
            buy["exit_row"] = i
            buy["pnl"] = buy["exit_price"] - buy["entry_price"]
            buy["period"] = buy["exit_row"] - buy["entry_row"]
            buy["side"] = "buy"
            trades.append(buy)
            buy = {}

        if len(sell) != 0 and (
                df["exit_sell"][i - 1] == True or df["buy"][i - 1] == True or sell["entry_price"] - df["close"][
            i - 1] < sl):
            sell["exit_price"] = df["open"][i]
            sell["exit_row"] = i
            sell["pnl"] = sell["entry_price"] - sell["exit_price"]
            sell["period"] = sell["exit_row"] - sell["entry_row"]
            sell["side"] = "sell"
            trades.append(sell)
            sell = {}

    trades_df = pd.DataFrame(trades)
    profit_trades = trades_df[trades_df["pnl"] > 0]
    loss_trades = trades_df[trades_df["pnl"] < 0]
    print(sum(trades_df["pnl"] - 0.00026))
    print("Total trades: %d" % len(trades_df))
    print("Profit trades: %d" % len(trades_df[trades_df["pnl"] > 0]))
    print("Loss trades: %d" % len(trades_df[trades_df["pnl"] < 0]))


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
    print(sum(trades_df["pnl"] - 0.00016))
    print("Total trades: %d" % len(trades_df))
    print("Profit trades: %d" % len(trades_df[trades_df["pnl"] > 0]))
    print("Loss trades: %d" % len(trades_df[trades_df["pnl"] < 0]))


# ----- Fixed -----
def backtest_aud_usd_H1():
    df = pd.read_json("data/aud_usd_2year_H1")
    # df["vratio"] = df["volume"] / df["volume"].shift()
    macd(df, a=9, b=12, c=26)
    df.dropna(inplace=True)
    point = "close"
    m = [20, 50]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    _df = pd.DataFrame(df.iloc[m[-1]:])
    _df["buy"] = (_df[ma[0]].shift() > _df[ma[1]].shift()) & (_df["macdh"].shift() <= 0) & (_df["macdh"] > 0)
    # _df["exit_buy"] = (_df["macdh"].shift() >= 0) & (_df["macdh"] < 0)
    _df["sell"] = (_df[ma[0]].shift() < _df[ma[1]].shift()) & (_df["macdh"].shift() >= 0) & (_df["macdh"] < 0)
    # _df["exit_sell"] = (_df["macdh"].shift() <= 0) & (_df["macdh"] > 0)
    df = _df

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    # TODO: TP1 at 0.075 and TP2 at 0.015
    tp1 = 0.0075
    tp2 = 0.01  # or 0.01
    sl = -0.01
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
            buy["open_time"] = df["datetime"][i]
            b_sl = sl
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i
            sell["open_time"] = df["datetime"][i]
            s_sl = sl

        if len(buy) != 0:
            if i != buy["entry_row"] and df["sell"][i - 1] == True:
                buy["exit_price"] = df["open"][i]
            elif df["close"][i - 1] - buy["entry_price"] <= b_sl:
                buy["exit_price"] = df["open"][i]
            elif df["high"][i] - buy["entry_price"] >= tp2:
                buy["exit_price"] = buy["entry_price"] + tp2
                b_sl = 0
            elif df["high"][i] - buy["entry_price"] >= tp1:
                b_sl = 0

            if "exit_price" in buy:
                if b_sl == 0:
                    buy["exit_price"] = (buy["exit_price"] + buy["entry_price"] + tp1) / 2
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                buy["close_time"] = df["datetime"][i]
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if i != sell["entry_row"] and df["buy"][i - 1] == True:
                sell["exit_price"] = df["open"][i]
            elif sell["entry_price"] - df["close"][i - 1] <= s_sl:
                sell["exit_price"] = df["open"][i]
            elif sell["entry_price"] - df["low"][i] >= tp2:
                sell["exit_price"] = sell["entry_price"] - tp2
                s_sl = 0
            elif sell["entry_price"] - df["low"][i] >= tp1:
                s_sl = 0

            if "exit_price" in sell:
                if s_sl == 0:
                    sell["exit_price"] = (sell["exit_price"] + sell["entry_price"] - tp1) / 2
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                sell["close_time"] = df["datetime"][i]
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"] - 0.00028))
    loss_trades = trades_df[trades_df["pnl"] < 0]
    print("Total trades: %d" % len(trades_df))
    print("Profit trades: %d" % len(trades_df[trades_df["pnl"] > 0]))
    print("Loss trades: %d" % len(trades_df[trades_df["pnl"] < 0]))


def backtest_gbp_usd_H1():
    df = pd.read_json("data/gbp_usd_2year_H1")
    df["day"] = (df["datetime"].dt.day_name())
    macd(df, a=9, b=12, c=26)
    df.dropna(inplace=True)
    point = "close"
    m = [20, 50]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    _df = pd.DataFrame(df.iloc[m[-1]:])
    start_hour = 0
    end_hour = 24
    _df["buy"] = (_df[ma[0]].shift() > _df[ma[1]].shift()) & (_df["macdh"].shift() <= 0) & (_df["macdh"] > 0) & (
            (_df["datetime"].dt.hour >= start_hour) | (_df["datetime"].dt.hour <= end_hour))
    _df["sell"] = (_df[ma[0]].shift() < _df[ma[1]].shift()) & (_df["macdh"].shift() >= 0) & (_df["macdh"] < 0) & (
            (_df["datetime"].dt.hour >= start_hour) | (_df["datetime"].dt.hour <= end_hour))

    _df["trend_high"] = (_df["macdh"] > 0) & (_df["macdh"].shift() <= 0) & (
            _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    _df["trend_low"] = (_df["macdh"] < 0) & (_df["macdh"].shift() >= 0) & (
            _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)

    _df["mm"] = _df["macdh"] > 0

    df = _df
    df.reset_index(drop=True, inplace=True)

    buy = {}
    sell = {}
    trades = []
    tp1 = 0.005
    tp2 = 0.005  # or 0.01
    sl = -0.005
    b_sl = None
    s_sl = None
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
            buy["open_time"] = df["datetime"][i]
            b_sl = sl
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i
            sell["open_time"] = df["datetime"][i]
            s_sl = sl

        if len(buy) != 0:
            if i != buy["entry_row"] and df["sell"][i - 1] == True:
                buy["exit_price"] = df["open"][i]
            elif (df[buy["entry_row"]:i]["mm"].values.sum() < (~df[buy["entry_row"]:i]["mm"]).values.sum()) or (
                    df["trend_low"][i - 1] == True and i - buy["entry_row"] <= 5):
                buy["exit_price"] = df["open"][i]
            elif df["low"][i] - buy["entry_price"] <= b_sl:
                if b_sl != sl:
                    buy["exit_price"] = (buy["entry_price"] + tp1 + buy["entry_price"]) / 2
                else:
                    buy["exit_price"] = buy["entry_price"] + b_sl
            elif df["high"][i] - buy["entry_price"] >= tp2:
                buy["exit_price"] = (buy["entry_price"] + tp1 + buy["entry_price"] + tp2) / 2
            elif df["high"][i] - buy["entry_price"] >= tp1:
                b_sl = 0

            if "exit_price" in buy:
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                buy["close_time"] = df["datetime"][i]
                buy["day"] = df["day"][buy["entry_row"]]
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if i != sell["entry_row"] and df["buy"][i - 1] == True:
                sell["exit_price"] = df["open"][i]
            elif (df[sell["entry_row"]:i]["mm"].values.sum() > (~df[sell["entry_row"]:i]["mm"]).values.sum()) or (
                    df["trend_high"][i - 1] == True and i - sell["entry_row"] <= 5):
                sell["exit_price"] = df["open"][i]
            elif sell["entry_price"] - df["high"][i] <= s_sl:
                if s_sl != sl:
                    sell["exit_price"] = (sell["entry_price"] - tp1 + sell["entry_price"]) / 2
                else:
                    sell["exit_price"] = sell["entry_price"] - s_sl
            elif sell["entry_price"] - df["low"][i] >= tp2:
                sell["exit_price"] = (sell["entry_price"] - tp1 + sell["entry_price"] - tp2) / 2
            elif sell["entry_price"] - df["low"][i] >= tp1:
                s_sl = 0

            if "exit_price" in sell:
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                sell["close_time"] = df["datetime"][i]
                sell["day"] = df["day"][sell["entry_row"]]
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"] - 0.00026))
    loss_trades = trades_df[trades_df["pnl"] < 0]
    print("Total trades: %d" % len(trades_df))
    print("Profit trades: %d" % len(trades_df[trades_df["pnl"] > 0]))
    print("Loss trades: %d" % len(loss_trades))


# ----- Fixed -----
def backtest_usd_jpy_H1():
    df = pd.read_json("data/usd_jpy_2year_H1")
    macd(df, a=10, b=20, c=50)
    df.dropna(inplace=True)
    point = "close"
    m = [20, 50]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    _df = pd.DataFrame(df.iloc[m[-1]:])
    _df["buy"] = (_df["macdh"].shift() <= 0) & (_df["macdh"] >= 0.0001) & (_df[ma[0]].shift() > _df[ma[1]].shift())
    _df["sell"] = (_df["macdh"].shift() >= 0) & (_df["macdh"] <= -0.0001) & (_df[ma[0]].shift() < _df[ma[1]].shift())
    df = _df

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    tp1 = 0.3
    tp2 = 0.75
    sl = -0.75
    b_sl = None
    s_sl = None
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
            buy["open_time"] = df["datetime"][i]
            b_sl = sl
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i
            sell["open_time"] = df["datetime"][i]
            s_sl = sl

        if len(buy) != 0:
            if df["low"][i] - buy["entry_price"] <= b_sl:
                if b_sl != sl:
                    buy["exit_price"] = (buy["entry_price"] + tp1 + buy["entry_price"]) / 2
                else:
                    buy["exit_price"] = buy["entry_price"] + b_sl
            elif df["sell"][i - 1] == True:
                buy["exit_price"] = df["open"][i]
            elif df["high"][i] - buy["entry_price"] >= tp2:
                buy["exit_price"] = (buy["entry_price"] + tp1 + buy["entry_price"] + tp2) / 2
            elif df["high"][i] - buy["entry_price"] >= tp1:
                b_sl = 0

            if "exit_price" in buy:
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                buy["close_time"] = df["datetime"][i]
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if sell["entry_price"] - df["high"][i] <= s_sl:
                if s_sl != sl:
                    sell["exit_price"] = (sell["entry_price"] - tp1 + sell["entry_price"]) / 2
                else:
                    sell["exit_price"] = sell["entry_price"] - s_sl
            elif df["buy"][i - 1] == True:
                sell["exit_price"] = df["open"][i]
            elif sell["entry_price"] - df["low"][i] >= tp2:
                sell["exit_price"] = (sell["entry_price"] - tp1 + sell["entry_price"] - tp2) / 2
            elif sell["entry_price"] - df["low"][i] >= tp1:
                s_sl = 0

            if "exit_price" in sell:
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                sell["close_time"] = df["datetime"][i]
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"] - 0.016))
    loss_trades = trades_df[trades_df["pnl"] < 0]
    print("Total trades: %d" % len(trades_df))
    print("Profit trades: %d" % len(trades_df[trades_df["pnl"] > 0]))
    print("Loss trades: %d" % len(loss_trades))


def test():
    df = pd.read_json("data/eur_usd_2year_H1")
    df["day"] = (df["datetime"].dt.day_name())
    macd(df, a=9, b=12, c=26)
    df.dropna(inplace=True)
    point = "close"
    m = [20, 50]
    for _t in m:
        moving_average(df, _t, source=point)
    ma = ["%s_%s_sma" % (point, _m) for _m in m]

    # _df = pd.DataFrame(df.iloc[m[-1]:])
    _df = pd.DataFrame(df.iloc[m[-1]:])
    start_hour = 7
    end_hour = 14
    _df["buy"] = (_df[ma[0]].shift() > _df[ma[1]].shift()) & (_df["macdh"].shift() <= 0) & (_df["macdh"] > 0) & (
            _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    # _df["trend_low"] = (_df["macdh"] < 0) & (_df["macdh"].shift() >= 0) & (
    #         _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    _df["sell"] = (_df[ma[0]].shift() < _df[ma[1]].shift()) & (_df["macdh"].shift() >= 0) & (_df["macdh"] < 0) & (
            _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    # _df["trend_high"] = (_df["macdh"] > 0) & (_df["macdh"].shift() <= 0) & (
    #         _df["datetime"].dt.hour >= start_hour) & (_df["datetime"].dt.hour <= end_hour)
    df = _df

    buy = {}
    sell = {}
    trades = []
    df.reset_index(drop=True, inplace=True)
    tp1 = 0.005
    tp2 = 0.01  # or 0.01
    sl = -0.01
    b_sl = None
    s_sl = None
    for i in range(1, len(df)):
        if len(buy) == 0 and df["buy"][i - 1] == True:
            buy["entry_price"] = df["open"][i]
            buy["entry_row"] = i
            buy["open_time"] = df["datetime"][i]
            b_sl = sl
        if len(sell) == 0 and df["sell"][i - 1] == True:
            sell["entry_price"] = df["open"][i]
            sell["entry_row"] = i
            sell["open_time"] = df["datetime"][i]
            s_sl = sl

        if len(buy) != 0:
            if df["sell"][i - 1] == True:
                buy["exit_price"] = df["open"][i]
            elif df["low"][i] - buy["entry_price"] <= b_sl:
                buy["exit_price"] = buy["entry_price"] + b_sl
            elif df["high"][i] - buy["entry_price"] >= tp2:
                buy["exit_price"] = buy["entry_price"] + tp2
                b_sl = 0
            elif df["high"][i] - buy["entry_price"] >= tp1:
                b_sl = 0

            if "exit_price" in buy:
                if b_sl == 0:
                    buy["exit_price"] = (buy["exit_price"] + buy["entry_price"] + tp1) / 2
                buy["exit_row"] = i
                buy["pnl"] = buy["exit_price"] - buy["entry_price"]
                buy["period"] = buy["exit_row"] - buy["entry_row"]
                buy["side"] = "buy"
                buy["close_time"] = df["datetime"][i]
                buy["day"] = df["day"][buy["entry_row"]]
                trades.append(buy)
                buy = {}

        if len(sell) != 0:
            if df["buy"][i - 1] == True:
                sell["exit_price"] = df["open"][i]
            elif sell["entry_price"] - df["high"][i] <= s_sl:
                sell["exit_price"] = sell["entry_price"] - s_sl
            elif sell["entry_price"] - df["low"][i] >= tp2:
                sell["exit_price"] = sell["entry_price"] - tp2
                s_sl = 0
            elif sell["entry_price"] - df["low"][i] >= tp1:
                s_sl = 0

            if "exit_price" in sell:
                if s_sl == 0:
                    sell["exit_price"] = (sell["exit_price"] + sell["entry_price"] - tp1) / 2
                sell["exit_row"] = i
                sell["pnl"] = sell["entry_price"] - sell["exit_price"]
                sell["period"] = sell["exit_row"] - sell["entry_row"]
                sell["side"] = "sell"
                sell["close_time"] = df["datetime"][i]
                sell["day"] = df["day"][sell["entry_row"]]
                trades.append(sell)
                sell = {}

    trades_df = pd.DataFrame(trades)
    print(sum(trades_df["pnl"] - 0.00028))
    loss_trades = trades_df[trades_df["pnl"] < 0]
    print("Total trades: %d" % len(trades_df))
    print("Profit trades: %d" % len(trades_df[trades_df["pnl"] > 0]))
    print("Loss trades: %d" % len(loss_trades))


if __name__ == "__main__":
    # with open('prod/key.json', 'r') as f:
    #     key = json.load(f)
    #
    # token = key['prod_token']
    # client = oandapyV20.API(access_token=token, environment="live")
    # dump_to_json_file()

    # backtest_eur_jpy_H1()
    # backtest_usd_jpy_H1()
    backtest_aud_usd_H1()
    # test()
    # backtest_eur_usd_M15()
