import json
import random
import time
import os
import sys
import math
import logging
from rest_client import RestClient


class User:
    def __init__(self, test, key, secret, symbol, side):
        self.test = test
        self.symbol = symbol
        self.client = RestClient(test, key, secret, symbol)
        self.side = side
        self.take_profit_order = None
        self.limit_orders = []
        self.last_entry_price = []

    def time_to_close(self):
        close = False
        if self.take_profit_order is not None:
            o = self.client.get_orders(filter='{"orderID": "%s"}' % self.take_profit_order['orderID'])
            if o is not None and o['ordStatus'] == 'Filled':
                close = True

        return close

    def close(self):
        try:
            self.client.cancel_all()
            time.sleep(1)
            self.client.close_position()
            time.sleep(1)
            self.take_profit_order = None
            self.limit_orders = []
            self.last_entry_price = []
        except Exception as e:
            log.warning("Close warning: %s" % e)

    def manage_orders(self, position, orders):
        sign = 1 if self.side == 'Buy' else -1

        for o in orders:
            if o['ordType'] == 'Limit' and o['side'] != self.side:
                self.take_profit_order = o
        tp_order = self.take_profit_order

        curr_open = False
        entry_price = None
        curr_qty = 0
        if len(position) > 0 and position['isOpen'] is True:
            curr_open = True
            entry_price = position['avgEntryPrice']
            curr_qty = abs(position['currentQty'])

        if curr_open is True and len(self.limit_orders) == 0:
            self.limit_orders.append((entry_price, curr_qty))
            price = entry_price
            qty = curr_qty
            for i in fib_series[self.side]:
                price = int(price - i * data['step'] * price * sign)
                self.client.new_order(orderQty=qty, ordType="Limit", side=self.side, price=price)
                self.limit_orders.append((price, qty))
                time.sleep(1)
                qty *= data['qtyFactor']

        if curr_open is True:
            if len(self.last_entry_price) == 0:
                self.last_entry_price.append(int(entry_price))
            if tp_order is None:
                if self.side == 'Buy':
                    side = 'Sell'
                    price = int(entry_price * (1 + data['step']))
                else:
                    side = 'Buy'
                    price = int(entry_price * (1 - data['step']))
                self.client.new_order(orderQty=curr_qty, ordType="Limit", side=side, price=price)
            else:
                if self.last_entry_price[-1] != int(entry_price):
                    self.last_entry_price.append(int(entry_price))
                if len(self.last_entry_price) > 1:
                    tp_price = self.last_entry_price[-2]
                    if (tp_order['orderQty'] != curr_qty) or (tp_order['price'] != tp_price):
                        self.client.amend_order(orderID=tp_order['orderID'], orderQty=curr_qty, price=tp_price)
                        time.sleep(5)


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='app.log')
log = logging.getLogger()
config_file = "config.json"
with open(config_file, 'r') as f:
    data = json.load(f)

test = data['testRun']
if test is True:
    data['user2'] = data['test']['user1']
    data['user1'] = data['test']['user2']
else:
    data['user1'] = data['prod']['user1']
    data['user2'] = data['prod']['user2']

buy_user = User(test, data['user1']['key'], data['user1']['secret'], data['symbol'], 'Buy')
sell_user = User(test, data['user2']['key'], data['user2']['secret'], data['symbol'], 'Sell')
buy_user.close()
sell_user.close()
stop_signal = False
fib_series = {
    'Buy': (1, 2, 3, 5, 8),
    'Sell': (1, 2, 3, 5, 8, 13)
}

while True:
    buy_position = buy_user.client.open_position()
    sell_position = sell_user.client.open_position()
    buy_orders = buy_user.client.open_orders()
    sell_orders = sell_user.client.open_orders()

    if buy_position is None or sell_position is None or buy_orders is None or sell_orders is None:
        time.sleep(4)
        continue

    buy_user.position = buy_position
    sell_user.position = sell_position
    buy_user.orders = buy_orders
    sell_user.orders = sell_orders

    if os.path.exists('STOP'):
        stop_signal = True
    else:
        stop_signal = False

    if buy_user.time_to_close() is True:
        buy_user.close()
        time.sleep(5)
    if sell_user.time_to_close() is True:
        sell_user.close()
        time.sleep(5)

    if stop_signal is False and ((len(buy_position) == 0 or buy_position['isOpen'] is False) or (
            len(sell_position) == 0 or sell_position['isOpen'] is False)):
        if os.path.exists('RELOAD'):
            with open(config_file, 'r') as f:
                data = json.load(f)
            os.remove('RELOAD')
        if len(buy_position) == 0 or buy_position['isOpen'] is False:
            buy_user.client.new_order(ordType='Market', orderQty=data['startQty']['Buy'], side='Buy')

        if len(sell_position) == 0 or sell_position['isOpen'] is False:
            sell_user.client.new_order(ordType='Market', orderQty=data['startQty']['Sell'], side='Sell')
        time.sleep(5)
        continue

    buy_user.manage_orders(buy_position, buy_orders)
    sell_user.manage_orders(sell_position, sell_orders)

    time.sleep(5)
