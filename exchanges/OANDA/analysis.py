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
import os
import requests
import sys
from decimal import Decimal
from stockstats import StockDataFrame


class MyOanda():

    def __init__(self):
        with open('key.json', 'r') as f:
            key = json.load(f)
        token = key['token']
        self.client = oandapyV20.API(access_token=token, environment="practice")
        self.account_id = "101-009-13015690-006"

    def fetch_ohlc(self, symbol):
        params = {
            "granularity": "D",
            "from": "2015-01-01",
            "to": "2020-02-28",
            "alignmentTimezone": "UTC"
        }
        r = instruments.InstrumentsCandles(symbol, params=params)
        data = self.client.request(r)
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
        with open("ohlc_eur_usd.json", "w") as f:
            json.dump(output, f)


class MyDF():

    def __init__(self, file_name):
        self.df = self.convert_to_dataframe(file_name)
        self.columns = ["side", "qty", "open", "close", "profit", "max_dd", "days", "margin"]
        self.trades_df = None
        self.fibonacci = (1, 2, 3, 5, 8, 13, 21, 34, 55)
        self.trades = []

    def convert_to_dataframe(self, file_name):
        df = pd.read_json(file_name)
        DF = StockDataFrame.retype(df)
        df['macd'] = DF.get('macd')
        return df

    def compute_average_entry_price(self, trade, params):
        side = trade["side"]
        start_price = trade["entry_price"]
        max_dd = trade["max_dd"]
        fib_iter = iter(self.fibonacci)
        qty = params["qty"]

        price = start_price
        _positions = [(price, qty)]
        while True:
            _positions.append((price, qty))
            qty *= 2
            if side == "sell":
                price += next(fib_iter) * params["step_size"]
                if price > max_dd:
                    break
            elif side == "buy":
                price -= next(fib_iter) * params["step_size"]
                if price < max_dd:
                    break

        trade["qty"] = _positions[-1][1]
        total_price = 0
        total_qty = 0
        for p, q in _positions:
            total_price += p * q
            total_qty += q

        trade["entry_price"] = total_price / total_qty

    def log_trade(self, trade, params):
        exit_price = trade["exit_price"]
        entry_price = trade["entry_price"]
        profit = abs(entry_price - exit_price)
        qty = trade["qty"]
        margin = qty * params["margin"]
        self.trades.append((trade["side"], qty, entry_price, exit_price, profit, abs(trade["max_dd"] - entry_price),
                            trade["end_index"] - trade["start_index"], margin))

    def macd_fibonacci_strategy(self, params):
        buy = {"open": False, "side": "buy"}
        sell = {"open": False, "side": "sell"}

        for index, row in self.df.iterrows():
            if buy["open"] is False:
                buy["entry_price"] = row["open"]
                buy["start_index"] = index
                buy["open"] = True

            if sell["open"] is False:
                sell["entry_price"] = row["open"]
                sell["start_index"] = index
                sell["open"] = True

            if index <= 1:
                continue

            prev1 = self.df.iloc[index - 1]
            prev2 = self.df.iloc[index - 2]

            # Compute entry price and qty
            buy["max_dd"] = self.df.iloc[buy["start_index"]:index]["low"].min()
            self.compute_average_entry_price(buy, params)

            sell["max_dd"] = self.df.iloc[sell["start_index"]:index]["high"].max()
            self.compute_average_entry_price(sell, params)

            # Buy closure
            if prev1["macdh"] < prev2["macdh"] and row["open"] - buy["entry_price"] > params["take_profit"]:
                # Log the trade
                buy["exit_price"] = row["open"]
                buy["end_index"] = index
                self.log_trade(buy, params)

                # Open position again
                buy["entry_price"] = row["open"]
                buy["start_index"] = index

            # Sell closure
            if prev1["macdh"] > prev2["macdh"] and sell["entry_price"] - row["open"] > params["take_profit"]:
                # Log the trade
                sell["exit_price"] = row["open"]
                sell["end_index"] = index
                self.log_trade(sell, params)

                # Open position again
                sell["entry_price"] = row["open"]
                sell["start_index"] = index

        self.trades_df = pd.DataFrame(self.trades, columns=self.columns)

# oanda = MyOanda()
# oanda.fetch_ohlc("EUR_USD")

my_df = MyDF("ohlc_eur_usd.json")
my_df.macd_fibonacci_strategy({"take_profit": 0.00150, "step_size": 0.00150, "qty": 120, "margin": 5})