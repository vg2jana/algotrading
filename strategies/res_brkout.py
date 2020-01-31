import logging
import re

from datetime import datetime, timedelta
from strategies.base_strategy import SinglePositionBackTest, SinglePosition


def seconds(frequency):
    factor = 1
    match = re.match("(\d+)(\S)", frequency)
    counter, period = match.groups()
    counter = int(counter)
    if period == 'm':
        factor = 60
    elif period == 'h':
        factor = 60 * 60
    elif period == 'd':
        factor = 60 * 60 * 24

    return factor * counter


class ResistanceBreakoutBackTest(SinglePositionBackTest):
    def __init__(self, dataframe):
        super(ResistanceBreakoutBackTest, self).__init__(dataframe)
        self.weighted = False
        self.rolling_period = 20
        self.min_profit = 0
        self.min_loss = 0
        self.volume_factor = 1.5
    
    def setup(self):
        # Calculate rolling
        self.rolling(self.rolling_period, weighted=self.weighted, dropna=True)

    def open_position(self):
        i = self.iter
        self.entry_price = self.dataframe["Adj Close"][i]
        self.entry_index = i

    def close_position(self):
        i = self.iter
        multiplier = -1 if self.signal == 'Sell' else 1
        self.exit_price = self.dataframe["Adj Close"][i - 1] - (self.dataframe["ATR"][i - 1] * multiplier)
        net = (self.exit_price - self.entry_price) * multiplier
        if (net <= 0 and net <= self.min_loss) or (net > 0 and net >= self.min_profit):
            self.exit_index = i
            self.returns.append((self.entry_index, self.exit_index, net, self.entry_price, self.exit_price, self.signal))
            return True

        return False

    def enter_buy(self):
        i = self.iter
        if self.dataframe["High"][i] >= self.dataframe["roll_max_cp"][i] and \
                self.dataframe["Volume"][i] > self.volume_factor * self.dataframe["roll_max_vol"][i - 1]:
            return True
        
        return False

    def enter_sell(self):
        i = self.iter
        if self.dataframe["Low"][i] <= self.dataframe["roll_min_cp"][i] and \
                self.dataframe["Volume"][i] > self.volume_factor * self.dataframe["roll_max_vol"][i - 1] and \
                self.dataframe['rsi'][i - 1] - self.dataframe['rsi'][i] > 4:
            return True
        
        return False
    
    def exit_buy(self):
        i = self.iter
        if self.dataframe["Adj Close"][i] < self.dataframe["Adj Close"][i - 1] - (self.dataframe["ATR"][i - 1]):
            return True
        
        return False
    
    def exit_sell(self):
        i = self.iter
        if self.dataframe["Adj Close"][i] > self.dataframe["Adj Close"][i - 1] + (self.dataframe["ATR"][i - 1]):
            return True

        return False


class ResistanceBreakout(SinglePosition):
    def __init__(self, dataframe, duration='5m'):
        super(ResistanceBreakout, self).__init__(dataframe)
        self.weighted = False
        self.rolling_period = 20
        self.min_profit = 0
        self.min_loss = 0
        self.volume_factor = 1.5
        self.book = {'buy': None, 'sell': None, 'ltp': None}
        # seconds = {
        #     '1m': 60,
        #     '3m': 60 * 3,
        #     '5m': 60 * 5,
        #     '15m': 60 * 15,
        #     '1h': 60 * 60 * 1,
        #     '4h': 60 * 60 * 4,
        #     '1d': 60 * 60 * 24
        # }
        self.period = seconds(duration)
        self.logger = logging.getLogger()

    def setup(self):
        # Close any open position
        self.close_position()
        # Calculate rolling
        self.rolling(self.rolling_period, weighted=self.weighted)

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
            # Calculate rolling
            self.rolling(self.rolling_period, weighted=self.weighted)

    def open_position(self):
        # Override this method to open a position. Use self.signal for Buy or Sell.
        # Also update self.position_index value
        print("Open position")

    def close_price_within_limits(self):
        multiplier = -1 if self.signal == 'Sell' else 1
        net = (self.exit_price - self.entry_price) * multiplier
        if (net < 0 and net <= self.min_loss) or (net > 0 and net >= self.min_profit):
            self.logger.info("CLOSE SATISFIED:\nEntry at: {}, Exit at: {}, Net: {}".format(self.entry_price, self.exit_price, net))
            return True
        return False

    def close_position(self):
        # Override this method to close open position.
        print("Close position")

    def enter_buy(self):
        if self.dataframe["High"][-1] >= self.dataframe["roll_max_cp"][-1] and \
                self.dataframe["Volume"][-1] > self.volume_factor * self.dataframe["roll_max_vol"][-2]:
            self.logger.info("Enter BUY satisfied:\n%s" % self.dataframe.iloc[-2:])
            return True

        return False

    def enter_sell(self):
        if self.dataframe["Low"][-1] <= self.dataframe["roll_min_cp"][-1] and \
                self.dataframe["Volume"][-1] > self.volume_factor * self.dataframe["roll_max_vol"][-2]:
            self.logger.info("Enter SELL satisfied:\n%s" % self.dataframe.iloc[-2:])
            return True

        return False

    def exit_buy(self):
        if self.book['ltp'] < self.dataframe["Adj Close"][-1] - self.dataframe["ATR"][-1] and \
                self.close_price_within_limits() is True:
            self.logger.info("Exit BUY satisfied:\n%s" % self.dataframe.iloc[-2:])
            return True

        return False

    def exit_sell(self):
        if self.book['ltp'] > self.dataframe["Adj Close"][-1] + self.dataframe["ATR"][-1] and \
                self.close_price_within_limits() is True:
            self.logger.info("Exit SELL satisfied:\n%s" % self.dataframe.iloc[-2:])
            return True

        return False


class ResistanceBreakoutParentChildBackTest(SinglePositionBackTest):
    def __init__(self, dataframe, child_dataframe, parent_frequency, child_frequency='1m'):
        super(ResistanceBreakoutParentChildBackTest, self).__init__(dataframe)
        self.child_dataframe = child_dataframe.copy()
        self.child_ohlcv = []
        self.weighted = False
        self.rolling_period = 20
        self.min_profit = 0
        self.min_loss = 0
        self.volume_factor = 1.5
        self.best_price = 0
        self.parent_frequency = parent_frequency
        self.child_frequency = child_frequency
        self.parent_period = seconds(parent_frequency)
        self.child_period = seconds(child_frequency)
        self.logger = logging.getLogger()
        self.max_loss = -500

    def setup(self):
        # Calculate rolling
        self.rolling(self.rolling_period, weighted=self.weighted, dropna=True)

    def before_run(self):
        # self.child_dataframe["rsi"] = self.RSI(DF=self.child_dataframe)
        k = self.iter
        # Get the child frames between the current parent candle and the next
        prev_index = self.dataframe.index[k] - timedelta(seconds=(self.parent_period))
        start_index = prev_index + timedelta(seconds=1)
        end_index = prev_index + timedelta(seconds=(self.parent_period / self.child_period) * self.child_period - 1)
        frames = self.child_dataframe[start_index:end_index].copy()

        # Calculate ohlcv for child candles
        self.child_ohlcv = []
        data = {}
        for i in range(len(frames)):
            data = {
                "Open": frames['Open'].iloc[i],
                "High": max(frames['High'].iloc[0:i+1]),
                "Low": min(frames['Low'].iloc[0:i+1]),
                "Volume": sum(frames['Volume'].iloc[0:i+1]),
                "Adj Close": frames['Adj Close'].iloc[i],
            }
            # if i == 0:
            #     data['RSI Diff'] = frames['rsi'].iloc[i] - self.dataframe['rsi'].iloc[k-1]
            # else:
            #     data['RSI Diff'] = frames['rsi'].iloc[i] - frames['rsi'].iloc[i-1]
            # self.child_ohlcv.append(data)

    def open_position(self):
        self.best_price = self.entry_price

    def close_position(self):
        multiplier = -1 if self.signal == 'Sell' else 1
        net = (self.exit_price - self.entry_price) * multiplier
        if (net <= 0 and net <= self.min_loss) or (net > 0 and net >= self.min_profit):
            self.returns.append((self.signal, self.entry_price, self.exit_price, net, self.best_price))
            return True

        return False

    def enter_buy(self):
        i = self.iter

        for d in self.child_ohlcv:
            if d["High"] >= self.dataframe["roll_max_cp"][i] and \
                    d["Volume"] > self.volume_factor * self.dataframe["roll_max_vol"][i]:
                self.entry_price = d["Adj Close"]
                return True

        if self.dataframe["High"][i] >= self.dataframe["roll_max_cp"][i] and \
                self.dataframe["Volume"][i] > self.volume_factor * self.dataframe["roll_max_vol"][i - 1]:
            self.entry_price = self.dataframe["Adj Close"][i]
            return True

        return False

    def enter_sell(self):
        i = self.iter

        for d in self.child_ohlcv:
            if d["Low"] <= self.dataframe["roll_min_cp"][i] and \
                    d["Volume"] > self.volume_factor * self.dataframe["roll_max_vol"][i]:
                self.entry_price = d["Adj Close"]
                return True

        if self.dataframe["Low"][i] <= self.dataframe["roll_min_cp"][i] and \
                self.dataframe["Volume"][i] > self.volume_factor * self.dataframe["roll_max_vol"][i - 1]:
            self.entry_price = self.dataframe["Adj Close"][i]
            return True

        return False

    def exit_buy(self):
        i = self.iter

        for d in self.child_ohlcv:
            if d["High"] > self.best_price:
                self.best_price = d["High"]
            elif d["Adj Close"] <= self.entry_price + ((self.best_price - self.entry_price) / 2):
                self.exit_price = d["Adj Close"]
                return True
            if d["Adj Close"] < self.dataframe["Adj Close"][i] - (self.dataframe["ATR"][i]):
                self.exit_price = d["Adj Close"]
                return True
            if d["Adj Close"] - self.entry_price <= self.max_loss:
                self.exit_price = d["Adj Close"]
                return True

        if self.dataframe["Adj Close"][i] < self.dataframe["Adj Close"][i - 1] - (self.dataframe["ATR"][i - 1]):
            self.exit_price = self.dataframe["Adj Close"][i]
            return True

        if self.dataframe["High"][i] > self.best_price:
            self.best_price = self.dataframe["High"][i]
        elif self.dataframe["Adj Close"][i] <= self.entry_price + ((self.best_price - self.entry_price) / 2):
            self.exit_price = self.dataframe["Adj Close"][i]
            return True
        if self.dataframe["Adj Close"][i] - self.entry_price <= self.max_loss:
            self.exit_price = self.dataframe["Adj Close"][i]
            return True

        return False

    def exit_sell(self):
        i = self.iter

        for d in self.child_ohlcv:
            if d["Low"] < self.best_price:
                self.best_price = d["Low"]
            elif d["Adj Close"] >= self.entry_price - ((self.entry_price - self.best_price) / 2):
                self.exit_price = d["Adj Close"]
                return True
            if d["Adj Close"] > self.dataframe["Adj Close"][i] + (self.dataframe["ATR"][i]):
                self.exit_price = d["Adj Close"]
                return True
            if self.entry_price - d["Adj Close"] <= self.max_loss:
                self.exit_price = d["Adj Close"]
                return True

        if self.dataframe["Adj Close"][i] > self.dataframe["Adj Close"][i - 1] + (self.dataframe["ATR"][i - 1]):
            self.exit_price = self.dataframe["Adj Close"][i]
            return True

        if self.dataframe["Low"][i] < self.best_price:
            self.best_price = self.dataframe["Low"][i]
        elif self.dataframe["Adj Close"][i] >= self.entry_price - ((self.entry_price - self.best_price) / 2):
            self.exit_price = self.dataframe["Adj Close"][i]
            return True
        if self.entry_price - self.dataframe["Adj Close"][i] <= self.max_loss:
            self.exit_price = self.dataframe["Adj Close"][i]
            return True

        return False
