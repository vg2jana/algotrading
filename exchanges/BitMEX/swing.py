import json
import random
import time
import math
import logging
from rest_client import RestClient


class User:
    def __init__(self, test, key, secret, symbol, side):
        self.test = test
        self.symbol = symbol
        self.client = RestClient(test, key, secret, symbol)
        self.take_profit_order = None
        self.position = {}
        self.orders = []
        self.side = side

    def open_position(self):
        while True:
            pos = self.client.open_position()
            if pos is None:
                time.sleep(5)
                continue
            self.position = pos
            return pos

    def get_open_orders(self):
        while True:
            orders = self.client.open_orders()
            if orders is None:
                time.sleep(5)
                continue
            self.orders = orders
            return orders

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
        except Exception as e:
            log.warning("Close warning: %s" % e)

    def manage_orders(self, opposite):
        sign = 1 if self.side == 'Buy' else -1
        if self.position['isOpen'] is True:
            tp_order = None
            stop_exists = False
            curr_qty = abs(self.position['currentQty'])
            opp_qty = abs(opposite.position['currentQty'])

            for o in self.orders:
                if o['ordType'] == 'MarketIfTouched':
                    tp_order = o
                    self.take_profit_order = o

            for o in opposite.orders:
                if o['ordType'] == 'Stop':
                    stop_exists = True

            if tp_order is None:
                tp_price = int(self.position['avgEntryPrice'] + (sign *
                    self.position['avgEntryPrice'] * data['profitPercent'] / 100))
                self.client.new_order(orderQty=curr_qty, ordType="MarketIfTouched", execInst="LastPrice",
                                          side=opposite.side, stopPx=tp_price)
                time.sleep(5)
            elif tp_order['orderQty'] != curr_qty:
                self.client.amend_order(orderID=tp_order['orderID'], orderQty=curr_qty)
                time.sleep(5)

            if stop_exists is False and curr_qty > opp_qty:
                entry_price = self.position['avgEntryPrice']
                opp_entry_price = self.position['avgEntryPrice'] - int(sign *
                        self.position['avgEntryPrice'] * data['swingPercent'] / 100)
                opp_exit_price = math.ceil(opp_entry_price - (sign * opp_entry_price * data['profitPercent'] / 100))
                curr_sum = curr_qty * abs(opp_exit_price - entry_price)
                for n in range(1, 10000):
                    opp_sum = (curr_qty + n) * abs(opp_exit_price - opp_entry_price)
                    if opp_sum - curr_sum > opp_entry_price * 0.01:
                        break

                qty = curr_qty + n - opp_qty
                if qty > 0:
                    stop_price = int(self.position['avgEntryPrice'] - (sign *
                        self.position['avgEntryPrice'] * data['swingPercent'] / 100))
                    opposite.client.new_order(orderQty=qty, ordType="Stop", execInst="LastPrice",
                                               side=opposite.side, stopPx=stop_price)
                    time.sleep(5)


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='app.log')
log = logging.getLogger()
config_file = "swing.json"
with open(config_file, 'r') as f:
    data = json.load(f)

test = True
if test is True:
    data['user1'] = data['test']['user1']
    data['user2'] = data['test']['user2']
else:
    data['user1'] = data['prod']['user1']
    data['user2'] = data['prod']['user2']

buy_user = User(test, data['user1']['key'], data['user1']['secret'], data['symbol'], 'Buy')
sell_user = User(test, data['user2']['key'], data['user2']['secret'], data['symbol'], 'Sell')
buy_user.close()
sell_user.close()

while True:
    buy_position = buy_user.open_position()
    sell_position = sell_user.open_position()
    buy_orders = buy_user.get_open_orders()
    sell_orders = sell_user.get_open_orders()

    if buy_user.time_to_close() is True or sell_user.time_to_close() is True:
        buy_user.close()
        sell_user.close()
        time.sleep(5)
        continue

    if (len(buy_position) == 0 or buy_position['isOpen'] is False) and (
            len(sell_position) == 0 or sell_position['isOpen'] is False):
        side = random.choice(('Buy', 'Sell'))
        if side == 'Buy':
            buy_user.client.new_order(ordType='Market', orderQty=data['startQty'])
        else:
            sell_user.client.new_order(ordType='Market', orderQty=data['startQty'])
        time.sleep(5)

    buy_user.manage_orders(sell_user)
    sell_user.manage_orders(buy_user)

    time.sleep(5)
