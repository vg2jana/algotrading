import random
import math
import json
import fxcmpy
import os
import sys
import time
from datetime import datetime
from copy import deepcopy


def connect():
    global con
    print("Reconnecting to FXCM...")
    con = fxcmpy.fxcmpy(access_token=data['global']['token'], log_level='info', server='demo', log_file='fxcm_api.log')
    con.subscribe_data_model('Order')
    con.subscribe_data_model('OpenPosition')
    return con


def call_api(api, args=None):
    while True:
        try:
            if api == 'orders':
                result = con.get_orders()
            elif api == 'summary':
                result = con.get_summary()
            elif api == 'positions':
                result = con.get_open_positions()
        except Exception as e:
            print(e)
            try:
                if con.is_connected() is False:
                    con.connect()
                    con.subscribe_data_model('Order')
                    con.subscribe_data_model('OpenPosition')
                else:
                    connect()
            except Exception as e:
                print(e)
        else:
            break

    return result


class Symbol:
    def __init__(self, symbol, config):
        self.symbol = symbol
        self.is_subscribed = False
        self.positions = []
        self.orders = []
        self.summary = {}
        self.config = config

    def subscribe(self):
        con.subscribe_market_data(self.symbol)

    def close_positions(self):
        if len(self.positions) == 0:
            return

        close = False
        tp = self.config['takeProfit']
        ohlc = con.get_last_price(self.symbol)

        if self.summary['buyAmount'] == 0 or self.summary['sellAmount'] == 0:
            tp = tp / 2

        if ohlc['Bid'] > self.summary['buyPrice'] + tp:
            close = True
        if ohlc['Ask'] < self.summary['sellPrice'] - tp:
            close = True

        return close

    def get_summary(self):
        buy_amount = 0
        sell_amount = 0
        buy_price = 0
        sell_price = 0
        for p in self.positions:
            if p.get_isBuy() is True:
                buy_amount += p.get_amount()
                buy_price = p.get_open()
            else:
                sell_amount += p.get_amount()
                sell_price = p.get_open()

        summary = {
            'buyAmount': buy_amount * self.config['qtyFactor'],
            'sellAmount': sell_amount * self.config['qtyFactor'],
            'buyPrice': buy_price,
            'sellPrice': sell_price
        }

        self.summary = summary
        return summary

    def run(self):
        if len(self.positions) == 0:
            if os.path.exists('STOP'):
                return
            isBuy = random.choice([True, False])
            amount = self.config['amount']
            if isBuy is True:
                con.create_market_buy_order(self.symbol, amount)
            else:
                con.create_market_sell_order(self.symbol, amount)
        else:
            summary = self.get_summary()
            buy_amount = summary['buyAmount']
            sell_amount = summary['sellAmount']

            if buy_amount > sell_amount:
                isBuy = False
                price = summary['buyPrice'] - self.config['swing']
                amount = buy_amount * self.config['ratio'] - sell_amount
            else:
                isBuy = True
                price = summary['sellPrice'] + self.config['swing']
                amount = sell_amount * self.config['ratio'] - buy_amount

            amount = math.ceil(amount)

            if len(self.orders) == 0:
                try:
                    con.create_entry_order(symbol.symbol, isBuy, amount, 'GTC', rate=price, limit=price*3)
                except:
                    pass


class SwingTrading:
    def __init__(self, symbols):
        self.symbols = {}
        for s in symbols:
            self.symbols[s.symbol] = s
        self.positions = None

    def before_run(self):
        orders = con.orders
        positions = con.open_pos

        for s in self.symbols.values():
            s.orders = []
            s.positions = []

        try:
            for ordID, order in orders.items():
                s = self.symbols.get(order.get_currency(), None)
                if s is None:
                    continue
                s.orders.append(order)

            for ordID, order in positions.items():
                s = self.symbols.get(order.get_currency(), None)
                if s is None:
                    continue
                s.positions.append(order)
        except Exception as e:
            print(e)

    def run(self):
        for symbol, s in self.symbols.items():
            if con.is_subscribed(symbol) is False:
                s.subscribe()
            s.run()

    def close(self):
        for symbol in self.symbols:
            if symbol.close_positions() is True:
                con.close_all_for_symbol(symbol.symbol)
                time.sleep(2)
                for o in symbol.orders:
                    try:
                        o.delete()
                    except:
                        pass

con = None
with open('config.json', 'r') as f:
    data = json.load(f)
connect()

symbols = []
for s, c in data["symbols"].items():
    symbol = Symbol(s, c)
    symbols.append(symbol)

swing = SwingTrading(symbols)

start_time = datetime.now()
lapsed_seconds = 60
while True:
    if lapsed_seconds >= 45:
        call_api('orders')
        call_api('positions')
        start_time = datetime.now()
    swing.before_run()
    swing.run()
    curr_time = datetime.now()
    lapsed_seconds = curr_time - start_time
    lapsed_seconds = lapsed_seconds.total_seconds()
