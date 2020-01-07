import pandas
from strategies.strategy import SinglePosition


class ResistanceBreakout(SinglePosition):
    def __init__(self, dataframe):
        super(ResistanceBreakout, self).__init__(dataframe)
        self.weighted = False
        self.rolling_period = 20
    
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
        self.exit_price.append(self.dataframe["Adj Close"][i-1] - (self.dataframe["ATR"][i-1] * multiplier))
        self.exit_index = i
        net = (self.exit_price[-1] - self.entry_price[-1]) * multiplier
        self.returns.append((self.entry_index, self.exit_index, net))

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
