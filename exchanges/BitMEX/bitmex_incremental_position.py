import json
import random
import time
import os
import sys
import math
import logging
from rest_client import RestClient


def order_menu(start_price, start_qty, percent, side, ratio, count=5):
    menu = []
    sign = 1 if side == 'Buy' else -1
    price = start_price
    qty = start_qty
    while count > 0:
        price += sign * price * percent / 100
        menu.append((int(price), qty))
        count -= 1
        qty *= ratio

    return menu


class User:
    def __init__(self, test, key, secret, symbol, side):
        self.test = test
        self.symbol = symbol
        self.client = RestClient(test, key, secret, symbol)
        self.side = side
        self.take_profit_order = None
        self.order_menu = []

    def time_to_close(self):
        close = False
        if self.take_profit_order is not None:
            # o = self.client.get_orders(filter='{"orderID": "%s"}' % self.take_profit_order['orderID'])
            if self.take_profit_order['ordStatus'] == 'Filled':
                close = True

        return close

    def close(self):
        try:
            self.client.cancel_all()
            time.sleep(1)
            self.client.close_position()
            time.sleep(1)
            self.take_profit_order = None
            self.order_menu = []
        except Exception as e:
            log.warning("Close warning: %s" % e)

    def manage_orders(self, position, orders):
        stop_orders = []
        sign = 1 if self.side == 'Buy' else -1

        for o in orders:
            if o['side'] == self.side:
                stop_orders.append(o)

        curr_open = False
        entry_price = None
        curr_qty = 0
        if len(position) > 0 and position['isOpen'] is True:
            curr_open = True
            entry_price = position['avgEntryPrice']
            curr_qty = abs(position['currentQty'])

        if curr_open is True and len(self.order_menu) == 0:
            self.order_menu = order_menu(entry_price, curr_qty, config['percent'], self.side,
                                         ratio=config['qtyFactor'], count=config['count'])
            for o in self.order_menu:
                price, qty = o
                order = self.client.new_order(orderQty=qty, ordType="Stop", side=self.side,
                                              stopPx=price, execInst='LastPrice')
                while order is None or order.get('ordStatus', None) != 'New':
                    time.sleep(5)
                    order = self.client.new_order(orderQty=qty, ordType="Stop", side=self.side,
                                                  stopPx=price, execInst='LastPrice')
                time.sleep(1)

        if curr_qty > config['startQty'][self.side]:
            count = len(stop_orders)
            last_filled_order = self.order_menu[::-1][count]
            offset = int(abs(entry_price - last_filled_order[0]) / 2)
            side = 'Sell' if self.side == 'Buy' else 'Buy'

            if self.take_profit_order is None:
                self.take_profit_order = self.client.new_order(orderQty=curr_qty, ordType="Stop", side=side,
                                                               pegPriceType='TrailingStopPeg', pegOffsetValue=offset)
                return
            else:
                response, order = self.client.get_orders(filter='{"orderID": "%s"}' % self.take_profit_order['orderID'])
                if response.status_code == 200 and order is None:
                    self.take_profit_order = None
                elif response.status_code != 200:
                    pass
                else:
                    self.take_profit_order = order

            tp_order = self.take_profit_order
            if tp_order is not None and \
                    (tp_order['orderQty'] != curr_qty) or (int(tp_order['pegOffsetValue']) != offset):
                self.client.amend_order(orderID=tp_order['orderID'], orderQty=curr_qty, pegOffsetValue=offset)
                time.sleep(5)


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename=os.path.basename(__file__).replace('.py', '.log'))
log = logging.getLogger()
config_file = "config.json"
with open(config_file, 'r') as f:
    config = json.load(f)

test = config['testRun']
if test is True:
    config['user2'] = config['test']['user1']
    config['user1'] = config['test']['user2']
else:
    config['user1'] = config['prod']['user1']
    config['user2'] = config['prod']['user2']

buy_user = User(test, config['user1']['key'], config['user1']['secret'], config['symbol'], 'Buy')
sell_user = User(test, config['user2']['key'], config['user2']['secret'], config['symbol'], 'Sell')
buy_user.close()
sell_user.close()
stop_signal = False
buy_clordid = ''
sell_clordid = ''

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
        if len(buy_orders) <= 1:
            sell_user.close()
        time.sleep(5)
    elif sell_user.time_to_close() is True:
        sell_user.close()
        if len(sell_orders) <= 1:
            buy_user.close()
        time.sleep(5)

    if stop_signal is False and ((len(buy_position) == 0 or buy_position['isOpen'] is False) or (
            len(sell_position) == 0 or sell_position['isOpen'] is False)):
        if os.path.exists('RELOAD'):
            with open(config_file, 'r') as f:
                config = json.load(f)
            os.remove('RELOAD')
        if len(buy_position) == 0 or buy_position['isOpen'] is False:
            buy_user.client.new_order(ordType='Market', orderQty=config['startQty']['Buy'], side='Buy')

        if len(sell_position) == 0 or sell_position['isOpen'] is False:
            sell_user.client.new_order(ordType='Market', orderQty=config['startQty']['Sell'], side='Sell')
        time.sleep(5)
        continue

    buy_user.manage_orders(buy_position, buy_orders)
    sell_user.manage_orders(sell_position, sell_orders)

    time.sleep(5)
