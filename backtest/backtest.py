import numpy as np
import pandas as pd
from alpha_vantage.timeseries import TimeSeries
import copy


class Backtest:
    def __init__(self):
        self.returns = []

    def cagr(self, DF):
        "function to calculate the Cumulative Annual Growth Rate of a trading strategies"
        df = DF.copy()
        df["cum_return"] = (1 + df["ret"]).cumprod()
        n = len(df) / (252 * 78)
        CAGR = (df["cum_return"].tolist()[-1]) ** (1 / n) - 1
        return CAGR

    def volatility(self, DF):
        "function to calculate annualized volatility of a trading strategies"
        df = DF.copy()
        vol = df["ret"].std() * np.sqrt(252 * 78)
        return vol

    def sharpe(self, DF, rf):
        "function to calculate sharpe ratio ; rf is the risk free rate"
        df = DF.copy()
        sr = (self.cagr(df) - rf) / self.volatility(df)
        return sr

    def max_dd(self, DF):
        "function to calculate max drawdown"
        df = DF.copy()
        df["cum_return"] = (1 + df["ret"]).cumprod()
        df["cum_roll_max"] = df["cum_return"].cummax()
        df["drawdown"] = df["cum_roll_max"] - df["cum_return"]
        df["drawdown_pct"] = df["drawdown"] / df["cum_roll_max"]
        max_dd = df["drawdown_pct"].max()
        return max_dd
