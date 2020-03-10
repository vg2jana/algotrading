import random
import math
import json
import fxcmpy
import os
import sys
import time


def connect():
    global con
    print("Reconnecting to FXCM...")
    con = fxcmpy.fxcmpy(access_token=data['global']['token'], log_level='error', server='demo')
    return con


class Symbol:
    def __init__(self, symbol, config):
        self.symbol = symbol
        self.is_subscribed = False
        self.positions = None
        self.orders = None
        self.config = config

    def subscribe(self):
        con.subscribe_market_data(self.symbol)

    def close_positions(self, pos, ohlc):
        close = False
        tp = self.config['takeProfit']
        if len(self.positions) == 1:
            tp = tp / 2

        if pos['isBuy'] is True:
            if ohlc['Bid'] > pos['open'] + tp:
                close = True
        else:
            if ohlc['Ask'] < pos['open'] - tp:
                close = True

        return close

    def run(self):
        if self.positions is None or len(self.positions) == 0:
            if os.path.exists('STOP'):
                return
            isBuy = random.choice([True, False])
            amount = self.config['amount']
            if isBuy is True:
                con.create_market_buy_order(self.symbol, amount)
            else:
                con.create_market_sell_order(self.symbol, amount)
        else:
            pos = self.positions[self.positions['amountK'] == self.positions['amountK'].max()]
            pos = pos.to_dict('records')[0]
            # amount = math.ceil(pos['amountK'] * self.config['ratio'])
            # amount = pos['amountK'] + self.config['amount']
            ohlc = con.get_last_price(self.symbol).to_dict()

            if pos['isBuy'] is True:
                isBuy = False
                price = pos['open'] - self.config['swing']
            else:
                isBuy = True
                price = pos['open'] + self.config['swing']

            if self.close_positions(pos, ohlc) is True:
                con.close_all_for_symbol(self.symbol)
            # elif isBuy is True and ohlc['Bid'] > price:
            #     con.create_market_buy_order(self.symbol, amount)
            # elif isBuy is False and ohlc['Ask'] < price:
            #     con.create_market_sell_order(self.symbol, amount)
            amount = self.positions.loc[self.positions['isBuy'] == pos['isBuy']]['amounK'].sum
            amount = math.ceil(amount.get_item() * self.config['ratio'])
            df = self.orders.loc[self.orders['isBuy'] == isBuy]
            if df.empty is True:
                try:
                    con.create_entry_order(symbol.symbol, isBuy, amount, 'GTC', rate=price, limit=price * 2)
                except:
                    pass


class SwingTrading:
    def __init__(self, symbols):
        self.symbols = symbols
        self.open_positions = None

    def before_run(self):
        while True:
            try:
                positions = con.get_open_positions()
                orders = con.get_orders()
            except Exception as e:
                print(e)
                try:
                    connect()
                except Exception as e:
                    print(e)
            else:
                break

        if positions.empty is True:
            if os.path.exists('STOP'):
                sys.exit(0)
            for symbol in self.symbols:
                symbol.positions = None
            return

        for symbol in self.symbols:
            # if symbol.symbol in df.currency.values:
            symbol.positions = positions.loc[positions['currency'] == symbol.symbol]
            symbol.orders = orders.loc[orders['currency'] == symbol.symbol]

    def run(self):
        for symbol in self.symbols:
            if con.is_subscribed(symbol.symbol) is False:
                symbol.subscribe()
            symbol.run()


con = None
with open('config.json', 'r') as f:
    data = json.load(f)
connect()

symbols = []
for s, c in data["symbols"].items():
    symbol = Symbol(s, c)
    symbols.append(symbol)

swing = SwingTrading(symbols)

while True:
    swing.before_run()
    swing.run()
    time.sleep(5)
