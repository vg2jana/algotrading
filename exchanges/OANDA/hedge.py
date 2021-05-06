import oandapyV20
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
from datetime import datetime, timezone


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


def close_positions(instrument, side=None, ratio=1.0):
    temp = o_positions.get(instrument, {})
    if len(temp) == 0:
        return
    l_units = abs(int(temp["long"]["units"]) * ratio)
    s_units = abs(int(temp["short"]["units"]) * ratio)
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


def open_trades():
    result = {}
    r = trades.OpenTrades(account_id)
    client.request(r)

    response = r.response
    if response is not None:
        oTrades = response.get("trades", [])
        for t in oTrades:
            _instrument = t["instrument"]
            if _instrument not in result:
                result[_instrument] = {}
            if int(t["currentUnits"]) > 0:
                result[_instrument]["long"] = t
            else:
                result[_instrument]["short"] = t

    return result


def get_account_info():
    result = None

    while result is None:
        r = accounts.AccountSummary(account_id)
        try:
            client.request(r)
        except oandapyV20.exceptions.V20Error as e:
            log.warning(e)

        if r.response is not None:
            result = r.response.get("account", None)
            if result is not None:
                result['unrealizedPL'] = float(result['unrealizedPL'])
                result['pl'] = float(result['pl'])
                result['NAV'] = float(result['NAV'])

    return result


def clear_symbol(instrument):
    # Cancel pending orders
    p_orders = [o['id'] for o in o_orders.get(instrument, [])]
    if len(p_orders) > 0:
        cancel_orders(p_orders)
    # Close positions
    close_positions(instrument)


class Symbol():
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.l_opened = False
        self.s_opened = False

    def clean(self, side=None):
        # Cancel pending orders
        if side == 'long':
            p_orders = [o['id'] for o in o_orders.get(self.instrument, []) if
                            int(o['units']) > 0 and o['type'] == 'LIMIT']
        elif side == 'short':
            p_orders = [o['id'] for o in o_orders.get(self.instrument, []) if
                            int(o['units']) < 0 and o['type'] == 'LIMIT']
        else:
            p_orders = [o['id'] for o in o_orders.get(self.instrument, [])]
        cancel_orders(p_orders)
        # Close positions
        close_positions(self.instrument, side=side)
        # Clear first order reference
        if side in ('long', None):
            self.l_opened = False
        if side in ('short', None):
            self.s_opened = False

    def run(self, o_pos, o_trd):
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
            if l_units == 0 and self.l_opened is False:
                log.info("%s: Market order, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
            if s_units == 0 and self.s_opened is False:
                log.info("%s: Market order, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
            return

        if l_units > 0:
            self.l_opened = True
            if o_trd.get("long", None) is not None and o_trd["long"].get("takeProfitOrder", None) is None:
                tp_price = l_price + self.config['takeProfit'] * self.config['pips']
                sl_price = l_price - self.config['stopLoss'] * self.config['pips']
                amend_trade(o_trd["long"]["id"], tp_price=tp_price, sl_price=sl_price)

        if s_units > 0:
            self.s_opened = True
            if o_trd.get("short", None) is not None and o_trd["short"].get("takeProfitOrder", None) is None:
                tp_price = s_price - self.config['takeProfit'] * self.config['pips']
                sl_price = s_price + self.config['stopLoss'] * self.config['pips']
                amend_trade(o_trd["short"]["id"], tp_price=tp_price, sl_price=sl_price)


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='hedge.log')
log = logging.getLogger()
with open('key.json', 'r') as f:
    key = json.load(f)
with open('hedge.json', 'r') as f:
    params = json.load(f)

log.info("Program S T A R T I N G")

token = key['token']
client = oandapyV20.API(access_token=token, environment="practice")
account_id = "101-009-13015690-006"

o_positions = open_positions()
o_orders = open_orders()
symbols = []
symbol_list = []

for s, c in params["symbols"].items():
    if s != "USD_JPY":
        continue
    symbol = Symbol(s, c)
    symbol.clean()
    symbols.append(symbol)
    symbol_list.append(s)

time.sleep(2)
stop_signal = False
nav = None
reconnect = False
inLoop = False

while True:

    try:
        if os.path.exists('STOP'):
            stop_signal = True

        o_positions = open_positions()
        # o_orders = open_orders()
        o_trades = open_trades()
        account_info = get_account_info()

        if nav is None:
            nav = account_info['NAV']

        net = account_info['NAV'] - nav
        if net >= 150 or (len(o_trades) == 0 and inLoop is True):
            log.info("ALL: Reached limits, Net={}, Margin={}".format(net, account_info['marginUsed']))

            for symbol in symbols:
                symbol.clean()

            time.sleep(30)

            account_info = get_account_info()
            nav = account_info['NAV']
            inLoop = False

            if net < 0:
                log.info("Stopping on hitting a loss.")
                break
            elif stop_signal is True:
                log.info("Stopping on signal.")
                break

            continue

        for _symbol in symbols:
            o_p = o_positions.get(_symbol.instrument, {})
            # o_o = o_orders.get(_symbol.instrument, {})
            o_t = o_trades.get(_symbol.instrument, None)

            _symbol.run(o_p, o_t)
            inLoop = True

    except oandapyV20.exceptions.V20Error as e:
        log.warning(e)
        if "Insufficient authorization to perform request" in e.msg:
            reconnect = True
        else:
            time.sleep(5)

    except requests.exceptions.ConnectionError as e:
        log.warning(e)
        reconnect = True

    if reconnect is True:
        while True:
            log.info("Retrying...")
            try:
                client = oandapyV20.API(access_token=token, environment="practice")
                reconnect = False
            except Exception as e:
                log.warning(e)
                time.sleep(60)
            else:
                break
    time.sleep(5)
