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
        data["order"]["takeProfitOnFill"] = {"distance": tp_pips}

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
        data["order"]["takeProfitOnFill"] = {"price": tp_price}
    elif tp_pips is not None:
        data["order"]["takeProfitOnFill"] = {"distance": tp_pips}

    r = orders.OrderCreate(accountID=account_id, data=data)
    client.request(r)

    return r.response


def amend_trade(tradeID, tp_price=None, tp_pips=None):
    data = {"takeProfit": {}}
    if tp_price is not None:
        data["takeProfit"] = {"price": tp_price}
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
        ins = o['instrument']
        if ins not in result:
            result[ins] = []
        result[ins].append(o)

    return result


def get_positions():
    result = {}
    r = positions.OpenPositions(accountID=account_id)
    client.request(r)
    for p in r.response['positions']:
        result[p['instrument']] = p

    return result


def close_positions(instrument):
    data = {
        "longUnits": "ALL",
        "shortUnits": "ALL"
    }
    r = positions.PositionClose(account_id, instrument, data)
    client.request(r)

    return r.response


class Symbol():
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.first_order = None
        self.tp_pips = (10 ** (self.config['decimal'] - 1)) * self.config["takeProfit"]

    def clean(self):
        # Cancel pending orders
        o_orders = open_orders()
        cancel_orders([o['id'] for o in o_orders[self.instrument]])
        # Close positions
        close_positions(self.instrument)

    def run(self):
        if self.first_order is None:
            tp_pips = self.tp_pips / 2
            self.first_order = market_order(self.instrument, self.config['startQty'], tp_pips=tp_pips)
            self.first_order["modified"] = False
        else:
            m_price = float(self.first_order['orderFillTransaction']['price'])
            o_pos = o_positions[self.instrument]
            o_ord = o_orders[self.instrument]
            long_units = o_pos["long"]["units"]
            short_units = o_pos["short"]["units"]

            if len(o_ord) == 0:
                if long_units < short_units:
                    units = short_units * self.config['ratio'] - long_units
                    price = m_price + self.config['swing']
                else:
                    units = long_units * self.config['ratio'] - short_units
                    units *= -1
                    price = m_price - self.config['swing']

                market_if_touched_order(self.instrument, price, units, tp_pips=self.tp_pips)

            if self.first_order["modified"] is False and short_units > 0:
                tid = int(o_pos["long"]["tradeIDs"][0])
                result = amend_trade(tid, tp_pips=self.tp_pips)
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
for s, c in params["symbols"].items():
    symbol = Symbol(s, c)
    symbol.clean()
    symbols.append(symbol)

refresh_time = 5
stop_signal = False
while True:
    if os.path.exists('STOP'):
        stop_signal = True

    o_positions = get_positions()
    o_orders = open_orders()
    for symbol in symbols:
        o_p = o_positions.get(symbol.instrument, {})
        if stop_signal is True and len(o_p) == 0:
            continue
        symbol.run()
        if len(o_p) > 0 and (o_p["long"]["units"] == 0 or o_p["short"]["units"] == 0):
            symbol.clean()
