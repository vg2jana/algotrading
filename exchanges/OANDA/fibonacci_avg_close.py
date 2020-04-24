import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import pandas as pd
import time
import json
import logging
import os
import requests
import sys
from decimal import Decimal


def market_order(instrument, units, tp_price=None, sl_price=None):
    data = {
        "order": {
            "timeInForce": "FOK",
            "instrument": str(instrument),
            "units": str(units),
            "type": "MARKET",
            "positionFill": "OPEN_ONLY"
        }
    }

    if tp_price is not None:
        data["order"]["takeProfitOnFill"] = {"price": tp_price}
    if sl_price is not None:
        data["order"]["stopLossOnFill"] = {"price": "{0:.5f}".format(sl_price), "timeInForce": "GTC"}

    r = orders.OrderCreate(accountID=account_id, data=data)
    client.request(r)

    return r.response


def limit_order(instrument, price, units):
    data = {
        "order": {
            "price": "{0:.5f}".format(price),
            "timeInForce": "GTC",
            "instrument": instrument,
            "units": units,
            "type": "LIMIT",
            "positionFill": "DEFAULT"
        }
    }

    r = orders.OrderCreate(accountID=account_id, data=data)
    client.request(r)

    return r.response


def market_if_touched_order(instrument, price, units, tp_price=None, sl_price=None, my_id=None):
    if my_id is None:
        my_id = "0"
    data = {
        "order": {
            "price": "{0:.5f}".format(price),
            "timeInForce": "GTC",
            "instrument": instrument,
            "units": units,
            "type": "MARKET_IF_TOUCHED",
            "positionFill": "REDUCE_ONLY",
            "clientExtensions": {
                "comment": "Test",
                "tag": "strategy",
                "id": my_id
            }
        }
    }

    if tp_price is not None:
        data["order"]["takeProfitOnFill"] = {"price": "{0:.5f}".format(tp_price)}
    if sl_price is not None:
        data["order"]["stopLossOnFill"] = {"price": "{0:.5f}".format(sl_price), "timeInForce": "GTC"}

    r = orders.OrderCreate(accountID=account_id, data=data)
    client.request(r)

    return r.response


def amend_trade(trade_id, tp_price=None, sl_price=None):
    data = {}
    if tp_price is not None:
        data["takeProfit"] = {"price": "{0:.5f}".format(tp_price)}
    if sl_price is not None:
        data["stopLoss"] = {"price": "{0:.5f}".format(sl_price), "timeInForce": "GTC"}

    r = trades.TradeCRCDO(account_id, trade_id, data)
    client.request(r)

    return r.response


def cancel_orders(orderIDs):
    for i in orderIDs:
        r = orders.OrderCancel(account_id, i)
        client.request(r)


def amend_order(order, price=None, units=None):
    if price is None:
        price = order['price']
    if units is None:
        units = order['units']
    if type(price) != str:
        price = "{0:.5f}".format(price)
    data = {
        "order": {
            "price": price,
            "units": units,
            "type": order['type'],
            "timeInForce": order['timeInForce'],
            "instrument": order['instrument']
        }
    }

    r = orders.OrderReplace(account_id, order['id'], data)
    client.request(r)

    return r.response


def open_trades():
    result = {}
    r = trades.OpenTrades(account_id)
    client.request(r)

    return r.response


def open_orders():
    result = {}
    r = orders.OrdersPending(accountID=account_id)
    client.request(r)

    for o in r.response['orders']:
        ins = o.get('instrument', None)
        if ins is None:
            continue
        if ins not in result:
            result[ins] = []
        result[ins].append(o)

    return result


def open_positions():
    result = {}
    r = positions.OpenPositions(accountID=account_id)
    client.request(r)
    for p in r.response['positions']:
        result[p['instrument']] = p

    return result


def close_positions(instrument, side=None):
    temp = o_positions.get(instrument, {})
    if len(temp) == 0:
        return
    l_units = abs(int(temp["long"]["units"]))
    s_units = abs(int(temp["short"]["units"]))
    if side == 'long':
        s_units = 0
    elif side == 'short':
        l_units = 0

    data = {
        "longUnits": str(l_units) if l_units > 0 else "NONE",
        "shortUnits": str(s_units) if s_units > 0 else "NONE"
    }
    r = positions.PositionClose(account_id, instrument, data)
    try:
        client.request(r)
    except oandapyV20.exceptions.V20Error as e:
        log.warning(e)
    else:
        return r.response


class Symbol():
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.l_tp_order = None
        self.s_tp_order = None
        self.l_tp_text = "%s_TAKE_PROFIT_LONG" % instrument
        self.s_tp_text = "%s_TAKE_PROFIT_SHORT" % instrument
        self.l_fib_index = 0
        self.s_fib_index = 0
        self.l_pq = []
        self.s_pq = []

    def clean(self, side=None):
        # Cancel pending orders
        if side == 'long':
            p_orders = [o['id'] for o in o_orders.get(self.instrument, []) if
                            int(o['units']) > 0 and o['type'] == 'LIMIT']
            tp_orders = ([o['id'] for o in o_orders.get(self.instrument, []) if
                          int(o['units']) < 0 and o['type'] == 'MARKET_IF_TOUCHED'])
            p_orders.extend(tp_orders)
        elif side == 'short':
            p_orders = [o['id'] for o in o_orders.get(self.instrument, []) if
                            int(o['units']) < 0 and o['type'] == 'LIMIT']
            tp_orders = ([o['id'] for o in o_orders.get(self.instrument, []) if
                          int(o['units']) > 0 and o['type'] == 'MARKET_IF_TOUCHED'])
            p_orders.extend(tp_orders)
        else:
            p_orders = [o['id'] for o in o_orders.get(self.instrument, [])]
        cancel_orders(p_orders)
        # Close positions
        close_positions(self.instrument, side=side)
        # Clear first order reference
        if side in ('long', None):
            self.l_tp_order = None
            self.l_fib_index = 0
            self.l_pq = []
        if side in ('short', None):
            self.s_tp_order = None
            self.s_fib_index = 0
            self.s_pq = []

    def run(self, o_pos, o_ord):
        l_price = None
        s_price = None
        l_units = 0
        s_units = 0
        if len(o_pos) > 0:
            l_units = abs(int(o_pos["long"]["units"]))
            s_units = abs(int(o_pos["short"]["units"]))
            if l_units != 0:
                l_price = float(o_pos['long']['averagePrice'])
            if s_units != 0:
                s_price = float(o_pos['short']['averagePrice'])

        l_tp_order = None
        s_tp_order = None
        l_orders = []
        s_orders = []
        for o in o_ord:
            if o['type'] == 'MARKET_IF_TOUCHED':
                if o.get('clientExtensions', None) is not None:
                    type = o['clientExtensions']['id']
                    if type == self.l_tp_text:
                        l_tp_order = o
                    elif type == self.s_tp_text:
                        s_tp_order = o
            elif o['type'] == 'LIMIT':
                units = int(o.get('units', '0'))
                if units > 0:
                    l_orders.append(o)
                elif units < 0:
                    s_orders.append(o)

        if (l_units == 0 or s_units == 0) and stop_signal is False:
            if l_units == 0 and self.l_tp_order is None:
                if len(l_orders) != 0:
                    log.info("%s LONG: Clearing pending orders" % self.instrument)
                    self.clean(side="long")
                    return
                log.info("%s LONG: Market order, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
                self.l_pq.append([0, self.config['qty']])
            if s_units == 0 and self.s_tp_order is None:
                if len(s_orders) != 0:
                    log.info("%s SHORT: Clearing pending orders" % self.instrument)
                    self.clean(side="short")
                    return
                log.info("%s SHORT: Market order, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
                self.s_pq.append([0, self.config['qty']])
            return

        if l_units > 0 and len(l_orders) == 0 and self.l_fib_index < len(fib_series):
            if self.l_pq[0][0] == 0:
                self.l_pq[0][0] = l_price
            offset = sum(fib_series[:self.l_fib_index+1]) * self.config['stepSize']
            order_price = l_price - offset
            log.info("%s LONG: Offset: %s, Price: %s, Units: %s, Index: %s" % (self.instrument, offset, order_price,
                                                                          l_units, self.l_fib_index))
            limit_order(self.instrument, order_price, l_units)
            self.l_fib_index += 1
            self.l_pq.append([order_price, l_units])

        if s_units > 0 and len(s_orders) == 0 and self.s_fib_index < len(fib_series):
            if self.s_pq[0][0] == 0:
                self.s_pq[0][0] = s_price
            offset = sum(fib_series[:self.s_fib_index+1]) * self.config['stepSize']
            order_price = s_price + offset
            log.info("%s SHORT: Offset: %s, Price: %s, Units: %s, Index: %s" % (self.instrument, offset, order_price,
                                                                          s_units, self.s_fib_index))
            limit_order(self.instrument, order_price, s_units * -1)
            self.s_fib_index += 1
            self.s_pq.append([order_price, s_units])

        if self.l_tp_order is None or self.s_tp_order is None:
            if l_units > 0 and self.l_tp_order is None:
                price = l_price + self.config['takeProfit']
                units = self.config['qty'] * -1
                log.info("%s LONG: Take profit order, price: %s, units: %s" % (self.instrument, price, units))
                self.l_tp_order = market_if_touched_order(self.instrument, price, units, my_id=self.l_tp_text)
            if s_units > 0 and self.s_tp_order is None:
                price = s_price - self.config['takeProfit']
                units = self.config['qty']
                log.info("%s SHORT: Take profit order, price: %s, units: %s" % (self.instrument, price, units))
                self.s_tp_order = market_if_touched_order(self.instrument, price, units, my_id=self.s_tp_text)
            return

        if l_tp_order is not None and self.l_tp_order is not None:
            price = l_price + self.config['takeProfit']
            if len(self.l_pq) > 2:
                total_qty = 0
                total_price = 0
                for x in self.l_pq[:-2]:
                    total_price += x[0] * x[1]
                    total_qty += x[1]
                price = total_price / total_qty
            tp_price = "{0:.5f}".format(price).rstrip('0').rstrip('.')
            units = l_units * -1
            if l_tp_order['price'].rstrip('0') != tp_price or l_tp_order['units'] != str(units):
                log.info("%s LONG: Amend TP, Price: %s, units: %s" % (self.instrument, tp_price, units))
                amend_order(l_tp_order, price=tp_price, units=units)

        if s_tp_order is not None and self.s_tp_order is not None:
            price = s_price - self.config['takeProfit']
            if len(self.s_pq) > 2:
                total_qty = 0
                total_price = 0
                for x in self.s_pq[:-2]:
                    total_price += x[0] * x[1]
                    total_qty += x[1]
                price = total_price / total_qty
            tp_price = "{0:.5f}".format(price).rstrip('0').rstrip('.')
            units = s_units
            if s_tp_order['price'].rstrip('0') != tp_price or s_tp_order['units'] != str(units):
                log.info("%s SHORT: Amend TP, Price: %s, units: %s" % (self.instrument, tp_price, units))
                amend_order(s_tp_order, price=tp_price, units=units)

        if self.l_tp_order is not None and l_tp_order is None:
            log.info("%s LONG: Close orders and position" % self.instrument)
            self.clean(side='long')
            return
        if self.s_tp_order is not None and s_tp_order is None:
            log.info("%s SHORT: Close orders and position" % self.instrument)
            self.clean(side='short')
            return


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='fibonacci_avg_close.log')
log = logging.getLogger()
with open('key.json', 'r') as f:
    key = json.load(f)
with open('fibonacci_buy_sell.json', 'r') as f:
    params = json.load(f)

token = key['token']
client = oandapyV20.API(access_token=token, environment="practice")
account_id = "101-009-13015690-006"

symbols = []
o_positions = open_positions()
o_orders = open_orders()
for s, c in params["symbols"].items():
    # if s not in ("EUR_USD", "GBP_USD"):
    #     continue
    symbol = Symbol(s, c)
    symbol.clean()
    symbols.append(symbol)

time.sleep(2)
refresh_time = 2
stop_signal = False
fib_series = (1, 2, 3, 5, 8, 13, 21, 34, 55)
while True:
    try:
        if os.path.exists('STOP'):
            stop_signal = True

        o_positions = open_positions()
        o_orders = open_orders()

        for symbol in symbols:
            o_p = o_positions.get(symbol.instrument, {})
            o_o = o_orders.get(symbol.instrument, {})
            if stop_signal is True and len(o_p) == 0:
                continue

            symbol.run(o_p, o_o)
    except oandapyV20.exceptions.V20Error as e:
        log.warning(e)
    except requests.exceptions.ConnectionError as e:
        log.warning(e)
        while True:
            log.info("Retrying...")
            try:
                client = oandapyV20.API(access_token=token, environment="practice")
            except Exception as e:
                log.warning(e)
                time.sleep(60)
            else:
                break
    time.sleep(5)
