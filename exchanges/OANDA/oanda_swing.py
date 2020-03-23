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


def market_order(instrument, units, tp_price=None, tp_pips=None):
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
    elif tp_pips is not None:
        data["order"]["takeProfitOnFill"] = {"pips": str(int(tp_pips))}

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


def market_if_touched_order(instrument, price, units, tp_price=None, tp_pips=None):
    data = {
        "order": {
            "price": "{0:.5f}".format(price),
            "timeInForce": "GTC",
            "instrument": instrument,
            "units": units,
            "type": "MARKET_IF_TOUCHED",
            "positionFill": "DEFAULT"
        }
    }

    if tp_price is not None:
        data["order"]["takeProfitOnFill"] = {"price": "{0:.5f}".format(tp_price)}
    elif tp_pips is not None:
        data["order"]["takeProfitOnFill"] = {"pips": str(int(tp_pips))}

    r = orders.OrderCreate(accountID=account_id, data=data)
    client.request(r)

    return r.response


def amend_trade(tradeID, tp_price=None, tp_pips=None):
    data = {"takeProfit": {}}
    if tp_price is not None:
        data["takeProfit"] = {"price": "{0:.5f}".format(tp_price)}
    elif tp_pips is not None:
        data["takeProfit"] = {"distance": tp_pips}

    r = trades.TradeCRCDO(account_id, tradeID, data)
    client.request(r)

    return r.response


def cancel_orders(orderIDs):
    for i in orderIDs:
        r = orders.OrderCancel(account_id, i)
        client.request(r)


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
        self.first_order = None
        self.tp_pips = (10 ** (self.config['decimal'] - 1)) * self.config["takeProfit"]
        self.l_units = 0
        self.s_units = 0
        self.last_side = None

    def clean(self):
        # Cancel pending orders
        cancel_orders([o['id'] for o in o_orders.get(self.instrument, [])])
        # Close positions
        close_positions(self.instrument)
        # Clear first order reference
        self.first_order = None
        symbol.l_units = 0
        symbol.s_units = 0

    def run(self):
        o_pos = o_positions.get(self.instrument, {})
        if len(o_pos) > 0:
            symbol.l_units = abs(int(o_pos["long"]["units"]))
            symbol.s_units = abs(int(o_pos["short"]["units"]))
        if self.first_order is None:
            self.first_order = market_order(self.instrument, self.config['startQty'])
            m_price = float(self.first_order['orderFillTransaction']['price'])
            tid = int(self.first_order['orderFillTransaction']['tradeOpened']['tradeID'])
            amend_trade(tid, tp_price=m_price + self.config['takeProfit'] / 2)
            self.first_order["modified"] = False
            self.last_side = 'buy'
        else:
            m_price = float(self.first_order['orderFillTransaction']['price'])
            o_ord = o_orders.get(self.instrument, [])
            l_units = symbol.l_units
            s_units = symbol.s_units

            if len(o_ord) == 0:
                if l_units < s_units and self.last_side == 'sell':
                    units = int(s_units * self.config['ratio'] - l_units)
                    price = m_price
                    tp_price = m_price + self.config['takeProfit']
                    self.last_side = 'buy'
                    market_if_touched_order(self.instrument, price, units, tp_price=tp_price)
                elif s_units < l_units and self.last_side == 'buy':
                    units = int(l_units * self.config['ratio'] - s_units) * -1
                    price = m_price - self.config['swing']
                    tp_price = m_price - self.config['takeProfit']
                    self.last_side = 'sell'
                    market_if_touched_order(self.instrument, price, units, tp_price=tp_price)

            if self.first_order["modified"] is False and s_units > 0:
                tid = int(o_pos["long"]["tradeIDs"][0])
                result = amend_trade(tid, tp_price=m_price + self.config['takeProfit'])
                if result.get("errorMessage", None) is None:
                    self.first_order["modified"] = True


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='app.log')
log = logging.getLogger()
with open('config.json', 'r') as f:
    params = json.load(f)

token = params['global']['token']
client = oandapyV20.API(access_token=token, environment="practice")
account_id = params['global']['account_id']

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
    if os.path.exists('STOP'):
        stop_signal = True

    o_positions = open_positions()
    o_orders = open_orders()

    for symbol in symbols:
        o_p = o_positions.get(symbol.instrument, {})
        if stop_signal is True and len(o_p) == 0:
            continue

        if len(o_p) > 0:
            long_units = abs(int(o_p["long"]["units"]))
            short_units = abs(int(o_p["short"]["units"]))
            if long_units < symbol.l_units or short_units < symbol.s_units:
                symbol.clean()
                continue

        symbol.run()
    time.sleep(2)
