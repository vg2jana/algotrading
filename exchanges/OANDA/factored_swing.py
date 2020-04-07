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
            "price": price,
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
    data = {
        "order": {
            "price": "{0:.5f}".format(price),
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


def close_positions(instrument):
    temp = o_positions.get(instrument, {})
    if len(temp) == 0:
        return
    l_units = abs(int(temp["long"]["units"]))
    s_units = abs(int(temp["short"]["units"]))

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
        self.tp_pips = (10 ** (self.config['decimal'] - 1)) * self.config["takeProfit"]
        l_units = 0
        s_units = 0
        self.last_side = None
        self.l_order = None
        self.s_order = None
        self.l_tp_order = None
        self.s_tp_order = None
        self.l_stop_order = None
        self.s_stop_order = None
        self.limit_count = 0
        self.l_tp_text = "%s_TAKE_PROFIT_LONG" % instrument
        self.l_sl_text = "%s_STOP_LOSS_LONG" % instrument
        self.s_tp_text = "%s_TAKE_PROFIT_SHORT" % instrument
        self.s_sl_text = "%s_STOP_LOSS_SHORT" % instrument

    def clean(self):
        # Cancel pending orders
        cancel_orders([o['id'] for o in o_orders.get(self.instrument, [])])
        # Close positions
        close_positions(self.instrument)
        # Clear first order reference
        self.l_stop_order = None
        self.s_stop_order = None
        self.l_tp_order = None
        self.s_tp_order = None
        self.limit_count = 0

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
        l_stop_order = None
        s_tp_order = None
        s_stop_order = None
        l_order = None
        s_order = None
        for o in o_ord:
            if o['type'] == 'MARKET_IF_TOUCHED':
                if o.get('clientExtensions', None) is not None:
                    type = o['clientExtensions']['id']
                    if type == 'LONG_TAKE_PROFIT':
                        l_tp_order = o
                    elif type == 'LONG_STOP_LOSS':
                        l_stop_order = o
                    elif type == 'SHORT_TAKE_PROFIT':
                        s_tp_order = o
                    elif type == 'SHORT_STOP_LOSS':
                        s_stop_order = o
            elif o['type'] == 'LIMIT':
                units = o.get('units', None)
                if units > 0:
                    l_order = o
                elif units < 0:
                    s_order = o

        if len(o_pos) == 0 and l_units == 0:
            market_order(self.instrument, self.config['startQty'])
            return

        if l_units > 0 and l_stop_order is None:
            self.l_stop_order = market_if_touched_order(self.instrument, l_price - self.config['stopLoss'],
                                    self.config['qty'] * -1, my_id=self.l_sl_text)

        if l_units > 0 and l_tp_order is None:
            self.l_tp_order = market_if_touched_order(self.instrument, l_price + self.config['takeProfit'],
                                    self.config['qty'] * -1, my_id=self.l_tp_text)

        if s_units > 0 and s_stop_order is None:
            self.s_stop_order = market_if_touched_order(self.instrument, s_price + self.config['stopLoss'],
                                    self.config['qty'], my_id=self.s_sl_text)

        if s_units > 0 and s_tp_order is None:
            self.s_tp_order = market_if_touched_order(self.instrument, s_price - self.config['takeProfit'],
                                    self.config['qty'], my_id=self.s_tp_text)

        if l_order is None and s_order is None:
            units = 0
            if l_units < s_units:
                opp_qty = s_units
                curr_qty = l_units
                qty = int(s_units * self.config['ratio'])
                units = qty - l_units
                price = l_price
            elif s_units < l_units:
                opp_qty = l_units
                curr_qty = s_units
                qty = int(l_units * self.config['ratio'])
                units = (qty - s_units) * -1
                price = l_price - self.config['swing']

            if units != 0:
                losing_sum = opp_qty * (self.config['takeProfit'] + self.config['swing'])
                gaining_sum = qty * self.config['takeProfit']
                if (gaining_sum - losing_sum) * self.config['startQty'] > self.config['maxProfit']:
                    for n in range(opp_qty + 1, 1000000):
                        gaining_sum = n * self.config['takeProfit']
                        if (gaining_sum - losing_sum) * self.config['startQty'] > self.config['maxProfit']:
                            break
                    if units < 0:
                        units = (n - curr_qty) * -1
                    else:
                        units = n - curr_qty

                limit_order(self.instrument, price, units)

        if l_tp_order is not None:
            tp_price = l_price + self.config['takeProfit']
            if s_units == 0:
                tp_price = tp_price / 4
            if l_tp_order['price'] != "{0:.5f}".format(tp_price) or l_tp_order['units'] != str(l_units * -1):
                amend_order(l_tp_order, price=tp_price, units=l_units * -1)

            if s_stop_order is not None:
                if s_stop_order['price'] != "{0:.5f}".format(tp_price) or s_stop_order['units'] != str(s_units):
                    amend_order(s_stop_order, price=tp_price, units=s_units)

        if s_tp_order is not None:
            tp_price = s_price - self.config['takeProfit']
            if s_units == 0:
                tp_price = tp_price / 4
            if s_tp_order['price'] != "{0:.5f}".format(tp_price) or s_tp_order['units'] != str(s_units):
                amend_order(s_tp_order, price=tp_price, units=s_units)

            if l_stop_order is not None:
                if l_stop_order['price'] != "{0:.5f}".format(tp_price) or l_stop_order['units'] != str(l_units * -1):
                    amend_order(l_stop_order, price=tp_price, units=l_units * -1)

        if self.l_tp_order is not None and l_tp_order is None:
            self.clean()
            return
        if self.s_tp_order is not None and s_tp_order is None:
            self.clean()
            return


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='app.log')
log = logging.getLogger()
with open('key.json', 'r') as f:
    key = json.load(f)
with open('factored_swing_config.json', 'r') as f:
    params = json.load(f)

token = key['token']
client = oandapyV20.API(access_token=token, environment="practice")
account_id = "101-009-13015690-004"

symbols = []
o_positions = open_positions()
o_orders = open_orders()
for s, c in params["symbols"].items():
    symbol = Symbol(s, c)
    symbol.clean()
    symbols.append(symbol)

time.sleep(2)
refresh_time = 2
stop_signal = False
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

            if len(o_p) == 0 and len(o_o) != 0:
                symbol.clean()

            symbol.run(o_p, o_o)
    except oandapyV20.exceptions.V20Error as e:
        log.warning(e)
    time.sleep(5)
