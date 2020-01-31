import logging
import statsmodels.api as sm

from datetime import datetime
from strategies.base_strategy import SinglePositionBackTest, SinglePosition


class RenkoMACDBackTest(SinglePositionBackTest):
    def __init__(self, dataframe):
        super(RenkoMACDBackTest, self).__init__(dataframe)
        self.atr_period = 120
        self.slope_period = 5
        self.macd_array = (12, 26, 9)
        self.min_profit = 0
        self.min_loss = 0

    def setup(self):
        # Merge renko bricks
        self.update_renko_bricks()

    def update_renko_bricks(self):
        renko = self.renko_bricks(self.atr_period)
        renko.columns = ["Date", "open", "high", "low", "close", "uptrend", "bar_num"]
        df = self.dataframe.copy()
        df["Date"] = df.index
        self.dataframe = df.merge(renko.loc[:, ["Date", "bar_num"]], how="outer", on="Date")
        self.dataframe["bar_num"].fillna(method='ffill', inplace=True)
        self.dataframe["macd"] = self.MACD(*self.macd_array)[0]
        self.dataframe["macd_sig"] = self.MACD(*self.macd_array)[1]
        self.dataframe["macd_slope"] = self.slope(self.dataframe["macd"], self.slope_period)
        self.dataframe["macd_sig_slope"] = self.slope(self.dataframe["macd_sig"], self.slope_period)

    def open_position(self):
        i = self.iter
        self.entry_price = self.dataframe["Adj Close"][self.iter]
        self.entry_index = i

    def close_position(self):
        i = self.iter
        multiplier = -1 if self.signal == 'Sell' else 1
        exit_price = self.dataframe["Adj Close"][i]
        net = (exit_price - self.entry_price) * multiplier
        if (net <= 0 and net <= self.min_loss) or (net > 0 and net >= self.min_profit):
            self.exit_price = self.dataframe["Adj Close"][i]
            self.exit_index = i
            self.returns.append((self.entry_index, self.exit_index, net, self.entry_price, exit_price, self.signal))
            return True

        return False

    def enter_buy(self):
        i = self.iter
        if self.dataframe["bar_num"][i] >= 2 and self.dataframe["macd"][i] > self.dataframe["macd_sig"][i] and \
                self.dataframe["macd_slope"][i] > self.dataframe["macd_sig_slope"][i]:
            return True

        return False

    def enter_sell(self):
        i = self.iter
        if self.dataframe["bar_num"][i] <= -2 and self.dataframe["macd"][i] < self.dataframe["macd_sig"][i] and \
                self.dataframe["macd_slope"][i] < self.dataframe["macd_sig_slope"][i]:
            return True

        return False

    def exit_buy(self):
        i = self.iter
        if self.dataframe["macd"][i] < self.dataframe["macd_sig"][i] and \
                self.dataframe["macd_slope"][i] < self.dataframe["macd_sig_slope"][i]:
            return True

        return False

    def exit_sell(self):
        i = self.iter
        if self.dataframe["macd"][i] > self.dataframe["macd_sig"][i] and \
                self.dataframe["macd_slope"][i] > self.dataframe["macd_sig_slope"][i]:
            return True

        return False


class RenkoMACD(SinglePosition):
    def __init__(self, dataframe, duration='5m'):
        super(RenkoMACD, self).__init__(dataframe)
        self.min_profit = 0
        self.min_loss = 0
        self.book = {'buy': None, 'sell': None, 'ltp': None}
        self.atr_period = 120
        self.slope_period = 5
        self.macd_array = (12, 26, 9)
        seconds = {
            '1m': 60,
            '3m': 60 * 3,
            '5m': 60 * 5,
            '15m': 60 * 15,
            '1h': 60 * 60 * 1,
            '4h': 60 * 60 * 4,
            '1d': 60 * 60 * 24
        }
        self.period = seconds[duration]
        self.logger = logging.getLogger()

    def setup(self):
        # Merge renko bricks
        self.update_renko_bricks()

    def update_renko_bricks(self):
        renko = self.renko_bricks(self.atr_period)
        renko.columns = ["Date", "open", "high", "low", "close", "uptrend", "bar_num"]
        df = self.dataframe.copy()
        df["Date"] = df.index
        self.dataframe = df.merge(renko.loc[:, ["Date", "bar_num"]], how="outer", on="Date")
        self.dataframe["bar_num"].fillna(method='ffill', inplace=True)
        (macd, macd_sig) = self.MACD(*self.macd_array)
        self.dataframe["macd"] = macd
        self.dataframe["macd_sig"] = macd_sig
        self.dataframe["macd_slope"] = self.slope(self.dataframe["macd"], self.slope_period)
        self.dataframe["macd_sig_slope"] = self.slope(self.dataframe["macd_sig"], self.slope_period)

    def update_book(self):
        # Override this method and update book info as per your exchange
        pass

    def update_dataframe(self):
        # Override this method and update ohlc dataframe info as per your exchange
        pass

    def before_run(self):
        # Update Buy/Sell/Ltp book
        self.update_book()

        last_updated = self.dataframe.index[-1]
        curr_time = datetime.now(last_updated.tz)
        seconds = curr_time - last_updated.to_pydatetime()
        if seconds.total_seconds() >= self.period:
            # Update candle
            self.update_dataframe()
            # Calculate renko bricks
            self.update_renko_bricks()

    def open_position(self):
        # Override this method to open a position. Use self.signal for Buy or Sell.
        # Also update self.position_index value
        print("Open position")

    def close_price_within_limits(self):
        multiplier = -1 if self.signal == 'Sell' else 1
        exit_price = self.book['ltp']
        net = (exit_price - self.entry_price) * multiplier
        if (net < 0 and net <= self.min_loss) or (net > 0 and net >= self.min_profit):
            self.logger.info("CLOSE SATISFIED:\nEntry at: {}, Exit at: {}, Net: {}".format(self.entry_price, exit_price, net))
            return True
        return False

    def close_position(self):
        # Override this method to close open position.
        # Use close_price_within_limits() to verify close price
        print("Close position")

    def enter_buy(self):
        if self.dataframe["bar_num"][-1] >= 2 and self.dataframe["macd"][-1] > self.dataframe["macd_sig"][-1] and \
                self.dataframe["macd_slope"][-1] > self.dataframe["macd_sig_slope"][-1]:
            self.logger.info("Enter BUY satisfied:\n%s" % self.dataframe.iloc[-2:])
            return True

        return False

    def enter_sell(self):
        if self.dataframe["bar_num"][-1] <= -2 and self.dataframe["macd"][-1] < self.dataframe["macd_sig"][-1] and \
                self.dataframe["macd_slope"][-1] < self.dataframe["macd_sig_slope"][-1]:
            self.logger.info("Enter SELL satisfied:\n%s" % self.dataframe.iloc[-2:])
            return True

        return False

    def exit_buy(self):
        if self.dataframe["macd"][-1] < self.dataframe["macd_sig"][-1] and \
                self.dataframe["macd_slope"][-1] < self.dataframe["macd_sig_slope"][-1]:
            self.logger.info("Exit BUY satisfied:\n%s" % self.dataframe.iloc[-2:])
            return True

        return False

    def exit_sell(self):
        if self.dataframe["macd"][-1] > self.dataframe["macd_sig"][-1] and \
                self.dataframe["macd_slope"][-1] > self.dataframe["macd_sig_slope"][-1]:
            self.logger.info("Exit SELL satisfied:\n%s" % self.dataframe.iloc[-2:])
            return True

        return False


def study():
    import numpy as np
    import pandas as pd
    from stocktrends import Renko

    from alpha_vantage.timeseries import TimeSeries
    import copy

    def MACD(DF,a,b,c):
        """function to calculate MACD
           typical values a = 12; b =26, c =9"""
        df = DF.copy()
        df["MA_Fast"]=df["Adj Close"].ewm(span=a,min_periods=a).mean()
        df["MA_Slow"]=df["Adj Close"].ewm(span=b,min_periods=b).mean()
        df["MACD"]=df["MA_Fast"]-df["MA_Slow"]
        df["Signal"]=df["MACD"].ewm(span=c,min_periods=c).mean()
        df.dropna(inplace=True)
        return (df["MACD"],df["Signal"])

    def ATR(DF,n):
        "function to calculate True Range and Average True Range"
        df = DF.copy()
        df['H-L']=abs(df['High']-df['Low'])
        df['H-PC']=abs(df['High']-df['Adj Close'].shift(1))
        df['L-PC']=abs(df['Low']-df['Adj Close'].shift(1))
        df['TR']=df[['H-L','H-PC','L-PC']].max(axis=1,skipna=False)
        df['ATR'] = df['TR'].rolling(n).mean()
        #df['ATR'] = df['TR'].ewm(span=n,adjust=False,min_periods=n).mean()
        df2 = df.drop(['H-L','H-PC','L-PC'],axis=1)
        return df2

    def slope(ser,n):
        "function to calculate the slope of n consecutive points on a plot"
        slopes = [i*0 for i in range(n-1)]
        for i in range(n,len(ser)+1):
            y = ser[i-n:i]
            x = np.array(range(n))
            y_scaled = (y - y.min())/(y.max() - y.min())
            x_scaled = (x - x.min())/(x.max() - x.min())
            x_scaled = sm.add_constant(x_scaled)
            model = sm.OLS(y_scaled,x_scaled)
            results = model.fit()
            slopes.append(results.params[-1])
        slope_angle = (np.rad2deg(np.arctan(np.array(slopes))))
        return np.array(slope_angle)

    def renko_DF(DF):
        "function to convert ohlc data into renko bricks"
        df = DF.copy()
        df.reset_index(inplace=True)
        df = df.iloc[:,[0,1,2,3,4,5]]
        df.columns = ["date","open","high","low","close","volume"]
        df2 = Renko(df)
        df2.brick_size = max(0.5,round(ATR(DF,120)["ATR"][-1],0))
        renko_df = df2.get_ohlc_data()
        renko_df["bar_num"] = np.where(renko_df["uptrend"]==True,1,np.where(renko_df["uptrend"]==False,-1,0))
        for i in range(1,len(renko_df["bar_num"])):
            if renko_df["bar_num"][i]>0 and renko_df["bar_num"][i-1]>0:
                renko_df["bar_num"][i]+=renko_df["bar_num"][i-1]
            elif renko_df["bar_num"][i]<0 and renko_df["bar_num"][i-1]<0:
                renko_df["bar_num"][i]+=renko_df["bar_num"][i-1]
        renko_df.drop_duplicates(subset="date",keep="last",inplace=True)
        return renko_df

    def CAGR(DF):
        "function to calculate the Cumulative Annual Growth Rate of a trading strategies"
        df = DF.copy()
        df["cum_return"] = (1 + df["ret"]).cumprod()
        n = len(df)/(252*78)
        CAGR = (df["cum_return"].tolist()[-1])**(1/n) - 1
        return CAGR

    def volatility(DF):
        "function to calculate annualized volatility of a trading strategies"
        df = DF.copy()
        vol = df["ret"].std() * np.sqrt(252*78)
        return vol

    def sharpe(DF,rf):
        "function to calculate sharpe ratio ; rf is the risk free rate"
        df = DF.copy()
        sr = (CAGR(df) - rf)/volatility(df)
        return sr


    def max_dd(DF):
        "function to calculate max drawdown"
        df = DF.copy()
        df["cum_return"] = (1 + df["ret"]).cumprod()
        df["cum_roll_max"] = df["cum_return"].cummax()
        df["drawdown"] = df["cum_roll_max"] - df["cum_return"]
        df["drawdown_pct"] = df["drawdown"]/df["cum_roll_max"]
        max_dd = df["drawdown_pct"].max()
        return max_dd

    # Download historical data for DJI constituent stocks

    tickers = ["MSFT","AAPL","FB","AMZN","INTC", "CSCO","VZ","IBM","QCOM","LYFT"]


    ohlc_intraday = {} # directory with ohlc value for each stock
    key_path = "D:\\Udemy\\Quantitative Investing Using Python\\1_Getting Data\\AlphaVantage\\key.txt"
    ts = TimeSeries(key=open(key_path,'r').read(), output_format='pandas')

    attempt = 0 # initializing passthrough variable
    drop = [] # initializing list to store tickers whose close price was successfully extracted
    while len(tickers) != 0 and attempt <=5:
        tickers = [j for j in tickers if j not in drop]
        for i in range(len(tickers)):
            try:
                ohlc_intraday[tickers[i]] = ts.get_intraday(symbol=tickers[i],interval='5min', outputsize='full')[0]
                ohlc_intraday[tickers[i]].columns = ["Open","High","Low","Adj Close","Volume"]
                drop.append(tickers[i])
            except:
                print(tickers[i]," :failed to fetch data...retrying")
                continue
        attempt+=1


    tickers = ohlc_intraday.keys() # redefine tickers variable after removing any tickers with corrupted data

    ################################Backtesting####################################

    #Merging renko df with original ohlc df
    ohlc_renko = {}
    df = copy.deepcopy(ohlc_intraday)
    tickers_signal = {}
    tickers_ret = {}
    for ticker in tickers:
        print("merging for ",ticker)
        renko = renko_DF(df[ticker])
        renko.columns = ["Date","open","high","low","close","uptrend","bar_num"]
        df[ticker]["Date"] = df[ticker].index
        ohlc_renko[ticker] = df[ticker].merge(renko.loc[:,["Date","bar_num"]],how="outer",on="Date")
        ohlc_renko[ticker]["bar_num"].fillna(method='ffill',inplace=True)
        ohlc_renko[ticker]["macd"]= MACD(ohlc_renko[ticker],12,26,9)[0]
        ohlc_renko[ticker]["macd_sig"]= MACD(ohlc_renko[ticker],12,26,9)[1]
        ohlc_renko[ticker]["macd_slope"] = slope(ohlc_renko[ticker]["macd"],5)
        ohlc_renko[ticker]["macd_sig_slope"] = slope(ohlc_renko[ticker]["macd_sig"],5)
        tickers_signal[ticker] = ""
        tickers_ret[ticker] = []


    #Identifying signals and calculating daily return
    for ticker in tickers:
        print("calculating daily returns for ",ticker)
        for i in range(len(ohlc_intraday[ticker])):
            if tickers_signal[ticker] == "":
                tickers_ret[ticker].append(0)
                if i > 0:
                    if ohlc_renko[ticker]["bar_num"][i]>=2 and ohlc_renko[ticker]["macd"][i]>ohlc_renko[ticker]["macd_sig"][i] and ohlc_renko[ticker]["macd_slope"][i]>ohlc_renko[ticker]["macd_sig_slope"][i]:
                        tickers_signal[ticker] = "Buy"
                    elif ohlc_renko[ticker]["bar_num"][i]<=-2 and ohlc_renko[ticker]["macd"][i]<ohlc_renko[ticker]["macd_sig"][i] and ohlc_renko[ticker]["macd_slope"][i]<ohlc_renko[ticker]["macd_sig_slope"][i]:
                        tickers_signal[ticker] = "Sell"

            elif tickers_signal[ticker] == "Buy":
                tickers_ret[ticker].append((ohlc_renko[ticker]["Adj Close"][i]/ohlc_renko[ticker]["Adj Close"][i-1])-1)
                if i > 0:
                    if ohlc_renko[ticker]["bar_num"][i]<=-2 and ohlc_renko[ticker]["macd"][i]<ohlc_renko[ticker]["macd_sig"][i] and ohlc_renko[ticker]["macd_slope"][i]<ohlc_renko[ticker]["macd_sig_slope"][i]:
                        tickers_signal[ticker] = "Sell"
                    elif ohlc_renko[ticker]["macd"][i]<ohlc_renko[ticker]["macd_sig"][i] and ohlc_renko[ticker]["macd_slope"][i]<ohlc_renko[ticker]["macd_sig_slope"][i]:
                        tickers_signal[ticker] = ""

            elif tickers_signal[ticker] == "Sell":
                tickers_ret[ticker].append((ohlc_renko[ticker]["Adj Close"][i-1]/ohlc_renko[ticker]["Adj Close"][i])-1)
                if i > 0:
                    if ohlc_renko[ticker]["bar_num"][i]>=2 and ohlc_renko[ticker]["macd"][i]>ohlc_renko[ticker]["macd_sig"][i] and ohlc_renko[ticker]["macd_slope"][i]>ohlc_renko[ticker]["macd_sig_slope"][i]:
                        tickers_signal[ticker] = "Buy"
                    elif ohlc_renko[ticker]["macd"][i]>ohlc_renko[ticker]["macd_sig"][i] and ohlc_renko[ticker]["macd_slope"][i]>ohlc_renko[ticker]["macd_sig_slope"][i]:
                        tickers_signal[ticker] = ""
        ohlc_renko[ticker]["ret"] = np.array(tickers_ret[ticker])

    #calculating overall strategies's KPIs
    strategy_df = pd.DataFrame()
    for ticker in tickers:
        strategy_df[ticker] = ohlc_renko[ticker]["ret"]
    strategy_df["ret"] = strategy_df.mean(axis=1)
    CAGR(strategy_df)
    sharpe(strategy_df,0.025)
    max_dd(strategy_df)

    #visualizing strategies returns
    (1+strategy_df["ret"]).cumprod().plot()

    #calculating individual stock's KPIs
    cagr = {}
    sharpe_ratios = {}
    max_drawdown = {}
    for ticker in tickers:
        print("calculating KPIs for ",ticker)
        cagr[ticker] =  CAGR(ohlc_renko[ticker])
        sharpe_ratios[ticker] =  sharpe(ohlc_renko[ticker],0.025)
        max_drawdown[ticker] =  max_dd(ohlc_renko[ticker])

    KPI_df = pd.DataFrame([cagr,sharpe_ratios,max_drawdown],index=["Return","Sharpe Ratio","Max Drawdown"])
    KPI_df.T