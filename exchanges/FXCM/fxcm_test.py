import random
import math
import json
import fxcmpy
import os
import sys
import time
import logging
from datetime import datetime
from copy import deepcopy


def connect():
    global con
    global log
    print("Reconnecting to FXCM...")
    con = fxcmpy.fxcmpy(access_token=data['global']['token'], log_level='info', server='demo', log_file='fxcm_api.log')
    log = logging.getLogger('FXCM')
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

    def update_table(self, table_name, prev_count):
        orders = con.orders
        positions = con.open_pos

        lapsed = lapsed_seconds
        while lapsed <= refresh_time:
            try:
                if table_name == 'order':
                    count = len([o for o in orders.values() if o.get_currency() == self.symbol])
                    if count > prev_count:
                        break
                elif table_name == 'positions':
                    count = len([p for p in positions.values() if p.get_currency() == self.symbol])
                    if count > prev_count:
                        break
            except Exception as e:
                log.warning("update_table Loop warning: %s" % e)
            finally:
                ct = datetime.now()
                delta = ct - start_time
                lapsed = delta.total_seconds()

    def run(self):
        if len(self.positions) == 0:
            if os.path.exists('STOP'):
                return
            isBuy = random.choice([True, False])
            amount = self.config['amount']
            try:
                if isBuy is True:
                    con.create_market_buy_order(self.symbol, amount)
                else:
                    con.create_market_sell_order(self.symbol, amount)
            except Exception as e:
                log.warning("Market order warning: %s" % e)
            else:
                self.update_table('positions', 0)
        elif len(self.orders) == 0:
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

            try:
                con.create_entry_order(symbol.symbol, isBuy, amount, 'GTC', rate=price, limit=price*3)
            except Exception as e:
                log.warning("Entry order warning: %s" % e)
            else:
                self.update_table('order', 0)


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
            log.warning("before_run Loop warning: %s" % e)

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
                    except Exception as e:
                        log.warning("Close order warning: %s" % e)


con = None
log = None
with open('config.json', 'r') as f:
    data = json.load(f)
connect()

symbols = []
for s, c in data["symbols"].items():
    symbol = Symbol(s, c)
    symbols.append(symbol)

swing = SwingTrading(symbols)

start_time = datetime.now()
refresh_time = 60
lapsed_seconds = refresh_time
while True:
    if lapsed_seconds >= refresh_time:
        call_api('orders')
        call_api('positions')
        start_time = datetime.now()
    swing.before_run()
    swing.run()
    time.sleep(1)
    curr_time = datetime.now()
    lapsed_seconds = curr_time - start_time
    lapsed_seconds = lapsed_seconds.total_seconds()
