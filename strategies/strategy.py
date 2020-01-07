from backtest.backtest import Backtest


class Strategy(Backtest):
    def __init__(self, dataframe):
        super(Strategy, self).__init__()
        self.dataframe = dataframe.copy()
        self.signal = None
        self.iter = None
        self.entry_price = []
        self.exit_price = []
        self.entry_index = None
        self.exit_index = None

    def setup(self):
        pass
    
    def average_true_range(self, DF, n, weighted=False):
        "function to calculate True Range and Average True Range"
        df = DF.copy()
        df['H-L'] = abs(df['High'] - df['Low'])
        df['H-PC'] = abs(df['High'] - df['Adj Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Adj Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1, skipna=False)
        if weighted is False:
            df['ATR'] = df['TR'].rolling(n).mean()
        else:
            df['ATR'] = df['TR'].ewm(span=n, adjust=False, min_periods=n).mean()
        df2 = df.drop(['H-L', 'H-PC', 'L-PC'], axis=1)
        return df2['ATR']
    
    def rolling(self, n=20, weighted=False):
        self.dataframe["ATR"] = self.average_true_range(self.dataframe, n, weighted=weighted)
        self.dataframe["roll_max_cp"] = self.dataframe["High"].rolling(n).max()
        self.dataframe["roll_min_cp"] = self.dataframe["Low"].rolling(n).min()
        self.dataframe["roll_max_vol"] = self.dataframe["Volume"].rolling(n).max()
        self.dataframe.dropna(inplace=True)

    def wait_for_signal(self):
        pass

    def enter_buy(self):
        pass

    def exit_buy(self):
        pass

    def enter_sell(self):
        pass

    def exit_sell(self):
        pass

    def open_position(self):
        pass

    def close_position(self):
        pass

    def run(self):
        pass


class SinglePosition(Strategy):
    def __init__(self, dataframe):
        super(SinglePosition, self).__init__(dataframe)

    def wait_for_signal(self):
        if self.enter_buy() is True:
            self.signal = 'Buy'
        elif self.enter_sell() is True:
            self.signal = 'Sell'

    def run(self):
        for i in range(len(self.dataframe)):
            self.iter = i

            if self.signal is None:
                self.wait_for_signal()
                if self.signal is not None:
                    self.open_position()

            elif self.signal == 'Buy':
                if self.exit_buy() is True or self.enter_sell() is True:
                    self.close_position()
                    self.signal = None

            elif self.signal == 'Sell':
                if self.exit_sell() is True or self.enter_buy() is True:
                    self.close_position()
                    self.signal = None
