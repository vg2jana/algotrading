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
        self.take_profit_order = None
        self.stop_loss_order = None
        self.next_stop_order = None
        self.position = {}
        self.orders = []
        self.side = side

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
            self.stop_loss_order = None
            self.next_stop_order = None
        except Exception as e:
            log.warning("Close warning: %s" % e)

    def update_orders(self):
        self.take_profit_order = None
        self.stop_loss_order = None
        self.next_stop_order = None

        for o in self.orders:
            if o['ordType'] == 'Limit':
                self.take_profit_order = o
            elif o['ordType'] == 'Stop':
                if o['side'] == self.side:
                    self.next_stop_order = o
                else:
                    self.stop_loss_order = o

    def manage_orders(self, opposite):
        sign = 1 if self.side == 'Buy' else -1
        tp_order = self.take_profit_order
        opp_tp_order = opposite.take_profit_order
        curr_open = False
        opposite_open = False
        entry_price = None
        opp_entry_price = None
        curr_qty = 0
        opp_qty = 0

        if len(opposite.position) > 0 and opposite.position['isOpen'] is True:
            opposite_open = True
            opp_entry_price = opposite.position['avgEntryPrice']
            opp_qty = abs(opposite.position['currentQty'])

        if len(self.position) > 0 and self.position['isOpen'] is True:
            curr_open = True
            entry_price = self.position['avgEntryPrice']
            curr_qty = abs(self.position['currentQty'])

        if curr_open is True:
            #
            # Take profit order
            #
            if opposite_open is False:
                tp_price = int(entry_price + (sign * entry_price * data['profitPercent'] / 300))
            else:
                tp_price = int(entry_price + (sign * entry_price * data['profitPercent'] / 100))

            if tp_order is None:
                self.client.new_order(orderQty=curr_qty, ordType="Limit", side=opposite.side, price=tp_price)
                time.sleep(5)
            elif (tp_order['orderQty'] != curr_qty) or (tp_order['price'] != tp_price):
                self.client.amend_order(orderID=tp_order['orderID'], orderQty=curr_qty, price=tp_price)
                time.sleep(5)

            #
            # Stop loss order
            #
            stop_loss_order = self.stop_loss_order
            if stop_loss_order is None and opp_tp_order is not None:
                self.client.new_order(orderQty=curr_qty, ordType="Stop", execInst="LastPrice",
                                          side=opposite.side, stopPx=opp_tp_order['price'])
                time.sleep(5)
            elif stop_loss_order is not None and opp_tp_order is not None:
                if stop_loss_order['orderQty'] != curr_qty or stop_loss_order['stopPx'] != opp_tp_order['price']:
                    self.client.amend_order(orderID=stop_loss_order['orderID'],
                                            orderQty=curr_qty, stopPx=opp_tp_order['price'])
                    time.sleep(5)

        #
        # Next stop order
        #
        next_order = self.next_stop_order
        if next_order is None and opposite_open is True and curr_qty < opp_qty and opposite.next_stop_order is None \
                and opp_tp_order is not None:
            if opp_tp_order['ordStatus'] == 'Filled':
                return
            if entry_price is None:
                entry_price = int(opp_entry_price + (sign * opp_entry_price * data['swingPercent'] / 100))

            qty = math.ceil(opp_qty * data['qtyFactor'])
            if tp_order is None:
                tp_price = int(entry_price + (sign * entry_price * data['profitPercent'] / 100))
            else:
                tp_price = tp_order['price']
            losing_sum = opp_qty * abs((1/opp_entry_price) - (1/tp_price))
            gaining_sum = qty * abs((1 / entry_price) - (1 / tp_price))

            if abs(gaining_sum - losing_sum) > tp_price:
                for n in range(1, 100000):
                    gaining_sum = (opp_qty + n) * abs((1/entry_price) - (1/tp_price))
                    if gaining_sum - losing_sum > tp_price:
                        break
                qty = opp_qty + n

            qty -= curr_qty
            if qty > 0:
                stop_price = int(entry_price)
                self.client.new_order(orderQty=qty, ordType="Stop",
                                      execInst="LastPrice", side=self.side, stopPx=stop_price)
                time.sleep(5)


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='app.log')
log = logging.getLogger()
config_file = "swing.json"
with open(config_file, 'r') as f:
    data = json.load(f)

test = data['testRun']
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

    if buy_user.time_to_close() is True or sell_user.time_to_close() is True:
        buy_user.close()
        sell_user.close()
        time.sleep(5)
        if os.path.exists('STOP'):
            log.info("Exiting on STOP signal.")
            os.remove('STOP')
            sys.exit(0)
        if os.path.exists('RELOAD'):
            with open(config_file, 'r') as f:
                data = json.load(f)
            os.remove('RELOAD')
        continue

    buy_user.update_orders()
    sell_user.update_orders()

    if (len(buy_position) == 0 or buy_position['isOpen'] is False) and (
            len(sell_position) == 0 or sell_position['isOpen'] is False):
        side = random.choice(('Buy', 'Sell'))
        if side == 'Buy':
            buy_user.client.new_order(ordType='Market', orderQty=data['startQty'], side=side)
        else:
            sell_user.client.new_order(ordType='Market', orderQty=data['startQty'], side=side)
        time.sleep(5)
        continue

    buy_user.manage_orders(sell_user)
    sell_user.manage_orders(buy_user)

    time.sleep(5)
