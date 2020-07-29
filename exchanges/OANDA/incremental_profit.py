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
            "positionFill": "DEFAULT"
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
            "positionFill": "DEFAULT",
            # "clientExtensions": {
            #     "comment": "Test",
            #     "tag": "strategy",
            #     "id": my_id
            # }
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


def close_positions(instrument, side=None, force=True):
    if force is True:
        _pos = open_positions()
    else:
        _pos = o_positions
    temp = _pos.get(instrument, {})
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


def get_prices():
    params = {"instruments": ",".join(symbol_list)}
    r = pricing.PricingInfo(account_id, params=params)
    try:
        client.request(r)
    except oandapyV20.exceptions.V20Error as e:
        log.warning(e)

    result = {}
    if r.response is not None:
        for p in r.response['prices']:
            result[p['instrument']] = {
                'buy': float(p['closeoutAsk']),
                'sell': float(p['closeoutBid'])
            }

    return result


class Symbol():
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.l_last_price = 0
        self.s_last_price = 0
        self.max_open_orders = 5
        self.l_fib_index = 0
        self.l_fib_series = []
        self.l_last_profit_pq = None
        self.s_fib_index = 0
        self.s_fib_series = []
        self.s_last_profit_pq = None

    def clean(self, side=None):
        # Close positions
        close_positions(self.instrument, side=side)
        # Clear references
        if side in ('long', None):
            self.l_fib_index = 0
            self.l_fib_series = []
            self.l_last_profit_pq = None
        if side in ('short', None):
            self.s_fib_index = 0
            self.s_fib_series = []
            self.s_last_profit_pq = None

    def compute_fib_series(self, price, side):
        for n in fib_series:
            qty = self.config['qty']
            if side == 'long':
                price -= self.config['stepSize'] * n
                self.l_fib_series.append((qty, price))
            else:
                price += self.config['stepSize'] * n
                self.s_fib_series.append((qty, price))
            qty *= 2

    def run(self, o_pos, ltp):
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

        if l_units == 0 or s_units == 0 and stop_signal is False:
            if l_units == 0:
                log.info("%s: LONG Market order, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
            if s_units == 0:
                log.info("%s: SHORT Market order, Units: -%s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'] * -1)
            return

        if len(self.l_fib_series) == 0 and l_units > 0 and l_price is not None:
            self.compute_fib_series(l_price, 'long')
            log.info("%s: LONG Fib series: %s" % (self.instrument, self.l_fib_series))
        if len(self.s_fib_series) == 0 and s_units > 0 and s_price is not None:
            self.compute_fib_series(l_price, 'short')
            log.info("%s: SHORT Fib series: %s" % (self.instrument, self.s_fib_series))

        if ltp is not None:
            #######################
            # LONG FIBONACCI
            #######################
            if len(self.l_fib_series) == 0:
                log.warning("%s: LONG Fib series length is 0" % self.instrument)
            elif self.l_fib_index + 1 <= len(self.l_fib_series):
                qty, price = self.l_fib_series[self.l_fib_index]
                if ltp['buy'] <= price:
                    log.info("%s: LONG Market order, FI: %s, FS: %s, Units: %s, Entry price: %s, Current price: %s" % (
                        self.instrument, self.l_fib_index, self.l_fib_series, qty, l_price, ltp['buy']))
                    market_order(self.instrument, qty)
                    self.l_fib_index += 1
            elif self.l_fib_index + 1 > len(self.l_fib_series):
                log.info("%s: LONG Fib index %s exceeds series length: %s" % (
                    self.instrument, self.l_fib_index + 1, len(self.l_fib_series)))

            #######################
            # SHORT FIBONACCI
            #######################
            if len(self.s_fib_series) == 0:
                log.warning("%s: SHORT Fib series length is 0" % self.instrument)
            elif self.s_fib_index + 1 <= len(self.s_fib_series):
                qty, price = self.s_fib_series[self.s_fib_index]
                if ltp['sell'] >= price:
                    log.info("%s: SHORT Market order, FI: %s, FS: %s, Units: -%s, Entry price: %s, Current price: %s" % (
                        self.instrument, self.s_fib_index, self.s_fib_series, qty, s_price, ltp['sell']))
                    market_order(self.instrument, qty * -1)
                    self.s_fib_index += 1
            elif self.s_fib_index + 1 > len(self.s_fib_series):
                log.info("%s: SHORT Fib index %s exceeds series length: %s" % (
                    self.instrument, self.s_fib_index + 1, len(self.s_fib_series)))

            #######################
            # LONG PROFIT/CLOSE
            #######################
            if self.l_last_profit_pq is None:
                tp_price = l_price + self.config['takeProfit']
                qty = min(l_units, 1000)
            else:
                tp_price = self.l_last_profit_pq[1]
                qty = self.l_last_profit_pq[0]

            if ltp['buy'] > tp_price + self.config['stepSize']:
                log.info("%s: LONG Market order, Last price: %s, Current unit: %s, Units: %s" % (
                    self.instrument, tp_price, l_units, qty))
                market_order(self.instrument, qty)
                self.l_last_profit_pq = [qty, ltp['buy']]

            # At least one profit order
            elif self.l_last_profit_pq is not None and self.l_last_profit_pq[1] > l_price + self.config['takeProfit']:
                if ltp['sell'] <= (l_price + self.l_last_profit_pq[1]) / 2 or l_units >= self.config['maxUnits']:
                    log.info("%s: Clearing LONG positions, Current unit: %s, Entry price: %s, Exit price: %s" % (
                        self.instrument, l_units, l_price, ltp['sell']))
                    self.clean(side='long')
                    return

            #######################
            # SHORT PROFIT/CLOSE
            #######################
            if self.s_last_profit_pq is None:
                tp_price = s_price - self.config['takeProfit']
                qty = min(s_units, 1000)
            else:
                tp_price = self.s_last_profit_pq[1]
                qty = self.s_last_profit_pq[0]

            if ltp['sell'] < tp_price - self.config['stepSize']:
                log.info("%s: SHORT Market order, Last price: %s, Current unit: %s, Units: -%s" % (
                    self.instrument, tp_price, s_units, qty))
                market_order(self.instrument, qty * -1)
                self.s_last_profit_pq = [qty, ltp['sell']]

            # At least one profit order
            elif self.s_last_profit_pq is not None and self.s_last_profit_pq[1] < s_price - self.config['takeProfit']:
                if ltp['buy'] >= (s_price + self.s_last_profit_pq[1]) / 2 or s_units >= self.config['maxUnits']:
                    log.info("%s: Clearing SHORT positions, Current unit: %s, Entry price: %s, Exit price: %s" % (
                        self.instrument, s_units, s_price, ltp['buy']))
                    self.clean(side='short')
                    return


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename=os.path.basename(__file__).replace('.py', '.log'))
log = logging.getLogger()
with open('key.json', 'r') as f:
    key = json.load(f)
with open('incremental_profit.json', 'r') as f:
    params = json.load(f)

token = key['token']
client = oandapyV20.API(access_token=token, environment="practice")
account_id = "101-009-13015690-002"

symbols = []
o_positions = open_positions()
symbol_list = []
for s, c in params["symbols"].items():
    symbol = Symbol(s, c)
    symbol.clean()
    symbols.append(symbol)
    symbol_list.append(s)

time.sleep(2)
refresh_time = 2
stop_signal = False
fib_series = (1, 2, 3, 5, 8, 13, 21, 34, 55)
while True:
    try:
        if os.path.exists('STOP'):
            stop_signal = True

        o_positions = open_positions()
        prices = get_prices()

        for symbol in symbols:
            o_p = o_positions.get(symbol.instrument, {})
            if stop_signal is True and len(o_p) == 0:
                continue

            symbol.run(o_p, prices.get(symbol.instrument, None))
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
