import pytz

from datetime import datetime
from strategies.base_strategy import SinglePositionBackTest, SinglePosition


class ResistanceBreakoutBackTest(SinglePositionBackTest):
    def __init__(self, dataframe):
        super(ResistanceBreakoutBackTest, self).__init__(dataframe)
        self.weighted = False
        self.rolling_period = 20
        self.min_profit = 0
        self.min_loss = 0
    
    def setup(self):
        # Calculate rolling
        self.rolling(self.rolling_period, weighted=self.weighted)

    def open_position(self):
        i = self.iter
        self.entry_price.append(self.dataframe["Open"][self.iter])
        self.entry_index = i

    def close_position(self):
        i = self.iter
        multiplier = -1 if self.signal == 'Sell' else 1
        exit_price = self.dataframe["Adj Close"][i-1] - (self.dataframe["ATR"][i-1] * multiplier)
        net = (exit_price - self.entry_price[-1]) * multiplier
        if (net <= 0 and net <= self.min_loss) or (net > 0 and net >= self.min_profit):
            self.exit_price.append(self.dataframe["Adj Close"][i-1] - (self.dataframe["ATR"][i-1] * multiplier))
            self.exit_index = i
            self.returns.append((self.entry_index, self.exit_index, net))
            return True

        return False

    def enter_buy(self):
        i = self.iter
        if self.dataframe["High"][i] >= self.dataframe["roll_max_cp"][i] and \
                self.dataframe["Volume"][i] > 1.5 * self.dataframe["roll_max_vol"][i - 1]:
            return True
        
        return False

    def enter_sell(self):
        i = self.iter
        if self.dataframe["Low"][i] <= self.dataframe["roll_min_cp"][i] and \
                self.dataframe["Volume"][i] > 1.5 * self.dataframe["roll_max_vol"][i - 1]:
            return True
        
        return False
    
    def exit_buy(self):
        i = self.iter
        if self.dataframe["Adj Close"][i] < self.dataframe["Adj Close"][i - 1] - self.dataframe["ATR"][i - 1]:
            return True
        
        return False
    
    def exit_sell(self):
        i = self.iter
        if self.dataframe["Adj Close"][i] > self.dataframe["Adj Close"][i - 1] + self.dataframe["ATR"][i - 1]:
            return True

        return False


class ResistanceBreakout(SinglePosition):
    def __init__(self, dataframe, duration='5m'):
        super(ResistanceBreakout, self).__init__(dataframe)
        self.weighted = False
        self.rolling_period = 20
        self.min_profit = 0
        self.min_loss = 0
        self.book = {'buy': None, 'sell': None, 'ltp': None}
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

    def update_book(self):
        # Override this method and update book info as per your exchange
        pass

    def update_dataframe(self):
        # Override this method and update ohlc dataframe info as per your exchange
        pass

    def before_run(self):
        # Calculate rolling
        self.rolling(self.rolling_period, weighted=self.weighted)

        # Update Buy/Sell/Ltp book
        self.update_book()

        last_updated = self.dataframe.index[-1]
        curr_time = datetime.now(last_updated.tz)
        seconds = curr_time - last_updated.to_pydatetime()
        if seconds.total_seconds() >= self.period:
            self.update_dataframe()

    def open_position(self):
        # self.entry_price.append(self.dataframe["Open"][-1])
        # self.entry_index = len(self.dataframe) - 1
        print("Open position")

    def close_position(self):
        i = self.iter
        multiplier = -1 if self.signal == 'Sell' else 1
        exit_price = self.dataframe["Adj Close"][i - 1] - (self.dataframe["ATR"][i - 1] * multiplier)
        net = (exit_price - self.entry_price[-1]) * multiplier
        if (net <= 0 and net <= self.min_loss) or (net > 0 and net >= self.min_profit):
            self.exit_price.append(self.dataframe["Adj Close"][i - 1] - (self.dataframe["ATR"][i - 1] * multiplier))
            self.exit_index = i
            self.returns.append((self.entry_index, self.exit_index, net))
            print('Close position')
            return True

        return False

    def enter_buy(self):
        if self.dataframe["High"][-1] >= self.dataframe["roll_max_cp"][-1] and \
                self.dataframe["Volume"][-1] > 1.5 * self.dataframe["roll_max_vol"][-2]:
            return True

        return False

    def enter_sell(self):
        if self.dataframe["Low"][-1] <= self.dataframe["roll_max_cp"][-1] and \
                self.dataframe["Volume"][-1] > 1.5 * self.dataframe["roll_max_vol"][-2]:
            return True

        return False

    def exit_buy(self):
        i = self.iter
        if self.dataframe["Adj Close"][i] < self.dataframe["Adj Close"][i - 1] - self.dataframe["ATR"][i - 1]:
            return True

        return False

    def exit_sell(self):
        i = self.iter
        if self.dataframe["Adj Close"][i] > self.dataframe["Adj Close"][i - 1] + self.dataframe["ATR"][i - 1]:
            return True

        return False
