import random
import math
import json
import fxcmpy


class Symbol:
    def __init__(self, symbol, connection, config):
        self.symbol = symbol
        self.con = connection
        self.is_subscribed = False
        self.positions = None
        self.config = config

    def subscribe(self):
        self.con.subscribe_market_data(self.symbol)

    def run(self):
        if self.positions is None:
            isBuy = random.choice([True, False])
            amount = self.config['amount']
            if isBuy is True:
                self.con.create_market_buy_order(self.symbol, amount)
            else:
                self.con.create_market_sell_order(self.symbol, amount)
        else:
            pos = self.positions[self.positions['amounK'] == self.positions['amountK'].max()]
            pos = pos.to_dict('records')[0]
            amount = math.ceil(pos['amountK'] * self.config['ratio'])
            ohlc = self.con.get_last_price(self.symbol).to_dict()

            close = False
            if pos['isBuy'] is True:
                if ohlc['Bid'] > pos['open'] + self.config['takeProfit']:
                    close = True
                isBuy = False
                price = pos['open'] - self.config['swing']
            else:
                if ohlc['Ask'] < pos['open'] - self.config['takeProfit']:
                    close = True
                isBuy = True
                price = pos['open'] + self.config['swing']

            if close is True:
                self.con.close_all_for_symbol(self.symbol)
            elif isBuy is True and ohlc['Bid'] > price:
                self.con.create_market_buy_order(self.symbol, amount)
            elif isBuy is False and ohlc['Ask'] < price:
                self.con.create_market_sell_order(self.symbol, amount)


class SwingTrading:
    def __init__(self, symbols, con):
        self.symbols = symbols
        self.open_positions = None
        self.con = con

    def before_run(self):
        df = self.con.get_open_positions()
        if df.empty is True:
            return
        for symbol in self.symbols:
            if symbol in df.columns:
                symbol.positions = df.loc[df['currency'] == symbol.symbol]

    def run(self):
        for symbol in self.symbols:
            if self.con.is_subscribed(symbol.symbol) is False:
                symbol.subscribe()
            symbol.run()


data = json.load('config.json')
con = fxcmpy.fxcmpy(access_token=data['global']['token'], log_level='error', server='demo')

symbols = []
for s, c in data["symbols"].items():
    symbol = Symbol(s, con ,c)
    symbols.append(symbol)

swing = SwingTrading(symbols, con)

while True:
    swing.before_run()
    swing.run()
