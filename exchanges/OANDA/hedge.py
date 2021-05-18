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
import re
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
    # if my_id is None:
    #     my_id = "0"
    data = {
        "order": {
            "price": "{0:.5f}".format(price),
            "timeInForce": "GTC",
            "instrument": instrument,
            "units": units,
            "type": "MARKET_IF_TOUCHED"
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
    logging.info(f"Received request to close position for {instrument}")
    temp = o_positions.get(instrument, {})
    if len(temp) == 0:
        logging.warning(f"Symbol {instrument} not in open positions list:\n{o_positions}")
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
    logging.info(f"Closing position for symbol {instrument} with payload:\n{data}")
    r = positions.PositionClose(account_id, instrument, data)
    try:
        client.request(r)
    except oandapyV20.exceptions.V20Error as e:
        log.warning(e)
    else:
        time.sleep(1)
        logging.info(f"Position closed for symbol {instrument}, response:\n{r.response}")
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
                result[_instrument] = {
                    "long": [],
                    "short": []
                }
            if int(t["currentUnits"]) > 0:
                result[_instrument]["long"].append(t)
            else:
                result[_instrument]["short"].append(t)

    return result


def get_prices(_symbols):
    _params = {"instruments": ",".join(_symbols)}
    r = pricing.PricingInfo(account_id, params=_params)
    try:
        client.request(r)
    except oandapyV20.exceptions.V20Error as _e:
        log.warning(_e)

    result = {}
    if r.response is not None:
        for p in r.response['prices']:
            result[p['instrument']] = {
                'buy': float(p['closeoutAsk']),
                'sell': float(p['closeoutBid'])
            }

    return result


def clear_symbol(instrument):
    # Cancel pending orders
    p_orders = [o['id'] for o in o_orders.get(instrument, [])]
    if len(p_orders) > 0:
        cancel_orders(p_orders)
    # Close positions
    close_positions(instrument)


class Hedge:
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.hedge_index = 0
        self.last_side = None

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
        # Clear reference
        self.hedge_index = 0
        self.last_side = None

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

        if self.hedge_index + 1 >= len(hedge_series):
            close = False
            if l_units > s_units:
                sl_price = l_price - self.config["pips"] * self.config["distance"]
                if ltp is not None and ltp["sell"] <= sl_price:
                    close = True
            else:
                sl_price = s_price + self.config["pips"] * self.config["distance"]
                if ltp is not None and ltp["buy"] >= sl_price:
                    close = True

            if close is True:
                log.info("%s: Stop loss reached, closing positions..." % self.instrument)
                self.clean()
                return

        if l_units == 0:
            log.info("%s: Market order, Units: %s" % (self.instrument, self.config['qty']))
            market_order(self.instrument, self.config['qty'])
            self.last_side = "long"
            return

        if l_units > s_units and self.last_side == "long":
            if ltp["sell"] <= l_price - self.config["pips"] * self.config["distance"]:
                qty = hedge_series[self.hedge_index] * self.config["qty"] * -1
                log.info("%s: Market order, Units: %s" % (self.instrument, qty))
                market_order(self.instrument, qty)
                self.last_side = "short"
                self.hedge_index += 1
                return

        if s_units > l_units and self.last_side == "short":
            if ltp["buy"] >= s_price + self.config["pips"] * self.config["distance"]:
                qty = hedge_series[self.hedge_index] * self.config["qty"]
                log.info("%s: Market order, Units: %s" % (self.instrument, qty))
                market_order(self.instrument, qty)
                self.last_side = "short"
                self.hedge_index += 1
                return

        if ltp["sell"] >= l_price + self.config["pips"] * self.config["distance"]:
            log.info("%s: Long trade take profit reached, closing positions..." % self.instrument)
            self.clean()

        if ltp["buy"] <= s_price - self.config["pips"] * self.config["distance"]:
            log.info("%s: Short trade take profit reached, closing positions..." % self.instrument)
            self.clean()


# class Symbol:
#     def __init__(self, instrument, config):
#         self.instrument = instrument
#         self.config = config
#         self.hedge_index = 0
#         self.last_side = None
#
#     def clean(self, side=None):
#         # Cancel pending orders
#         if side == 'long':
#             p_orders = [o['id'] for o in o_orders.get(self.instrument, []) if
#                             int(o['units']) > 0 and o['type'] == 'LIMIT']
#         elif side == 'short':
#             p_orders = [o['id'] for o in o_orders.get(self.instrument, []) if
#                             int(o['units']) < 0 and o['type'] == 'LIMIT']
#         else:
#             p_orders = [o['id'] for o in o_orders.get(self.instrument, [])]
#         cancel_orders(p_orders)
#         # Close positions
#         close_positions(self.instrument, side=side)
#         # Clear reference
#         self.hedge_index = 0
#         self.last_side = None
#
#     def run(self, o_pos, o_ord, o_trd, ltp):
#         l_price = None
#         s_price = None
#         l_units = 0
#         s_units = 0
#         if len(o_pos) > 0:
#             l_units = abs(int(o_pos["long"]["units"]))
#             s_units = abs(int(o_pos["short"]["units"]))
#             if l_units != 0:
#                 l_price = float(o_pos['long']['averagePrice'])
#             if s_units != 0:
#                 s_price = float(o_pos['short']['averagePrice'])
#
#         if self.hedge_index + 1 >= len(hedge_series):
#             close = False
#             if l_units > s_units:
#                 sl_price = l_price - self.config["pips"] * self.config["distance"]
#                 if ltp is not None and ltp["sell"] <= sl_price:
#                     close = True
#             else:
#                 sl_price = s_price + self.config["pips"] * self.config["distance"]
#                 if ltp is not None and ltp["buy"] >= sl_price:
#                     close = True
#
#             if close is True:
#                 log.info("%s: Stop loss reached, closing positions..." % self.instrument)
#                 self.clean()
#                 return
#
#         if l_units == 0:
#             log.info("%s: Market order, Units: %s" % (self.instrument, self.config['qty']))
#             market_order(self.instrument, self.config['qty'])
#             self.last_side = "long"
#             return
#
#         if len(o_ord) == 0 and self.last_side is not None and self.hedge_index + 1 < len(hedge_series):
#             qty = hedge_series[self.hedge_index] * self.config["qty"]
#             if self.last_side == "long" and l_price is not None:
#                 sell_price = l_price - self.config["pips"] * self.config["distance"]
#                 qty *= -1
#                 log.info("%s: Market if touched order, Units: %s" % (self.instrument, qty))
#                 market_if_touched_order(self.instrument, sell_price, qty)
#                 self.hedge_index += 1
#                 self.last_side = "short"
#             elif self.last_side == "short" and s_price is not None:
#                 buy_price = s_price + self.config["pips"] * self.config["distance"]
#                 log.info("%s: Market if touched order, Units: %s" % (self.instrument, qty))
#                 market_if_touched_order(self.instrument, buy_price, qty)
#                 self.hedge_index += 1
#                 self.last_side = "long"
#             return
#         elif len(o_ord) > 1:
#             pass
#
#         if l_units > 0 and o_trd.get("long", None) is not None:
#             _trades = o_trd["long"]
#             for trd in _trades:
#                 if trd.get("takeProfitOrder", None) is None:
#                     tp_price = l_price + self.config["pips"] * self.config["distance"]
#                     log.info("%s: Amending trade order of Long, Open: %s, TP: %s" % (self.instrument, l_price, tp_price))
#                     amend_trade(trd["id"], tp_price=tp_price)
#                     time.sleep(1)
#         elif l_units > 0 and o_trd.get("long", None) is None:
#             log.info("%s: Long trade executed, closing positions..." % self.instrument)
#             self.clean()
#
#         if s_units > 0 and o_trd.get("short", None) is not None:
#             _trades = o_trd["short"]
#             for trd in _trades:
#                 if trd.get("takeProfitOrder", None) is None:
#                     tp_price = s_price - self.config["pips"] * self.config["distance"]
#                     log.info("%s: Amending trade order of Short, Open: %s, TP: %s" % (self.instrument, s_price, tp_price))
#                     amend_trade(trd["id"], tp_price=tp_price)
#                     time.sleep(1)
#         elif s_units > 0 and o_trd.get("short", None) is None:
#             log.info("%s: Short trade executed, closing positions..." % self.instrument)
#             self.clean()


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
reconnect = False
symbols = []
o_positions = open_positions()
# o_trades = open_trades()
o_orders = open_orders()
symbol_list = []
hedge_series = (3, 8, 21, 55)

log.info("Clearing existing positions...")
for s, c in params["symbols"].items():
    symbol = Hedge(s, c)
    symbol.clean()
    symbols.append(symbol)
    symbol_list.append(s)

time.sleep(2)

while True:
    try:
        o_positions = open_positions()
        # o_orders = open_orders()
        # o_trades = open_trades()
        prices = get_prices(symbol_list)

        for symbol in symbols:
            o_p = o_positions.get(symbol.instrument, {})
            # o_o = o_orders.get(symbol.instrument, {})
            # o_t = o_trades.get(symbol.instrument, {})

            symbol.run(o_p, prices.get(symbol.instrument, None))

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
