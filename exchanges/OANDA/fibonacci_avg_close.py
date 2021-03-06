import oandapyV20
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import time
import json
import logging
import os
import requests


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
        self.l_fib_index = 0
        self.s_fib_index = 0
        self.l_pq = []
        self.s_pq = []

    def clean(self, side=None):
        # Cancel pending orders
        if side == 'long':
            p_orders = [o['id'] for o in o_orders.get(self.instrument, []) if
                            int(o['units']) > 0 and o['type'] == 'LIMIT']
            p_orders.extend(p_orders)
        elif side == 'short':
            p_orders = [o['id'] for o in o_orders.get(self.instrument, []) if
                            int(o['units']) < 0 and o['type'] == 'LIMIT']
            p_orders.extend(p_orders)
        else:
            p_orders = [o['id'] for o in o_orders.get(self.instrument, [])]
        cancel_orders(p_orders)
        # Close positions
        close_positions(self.instrument, side=side)
        # Clear first order reference
        if side in ('long', None):
            self.l_fib_index = 0
            self.l_pq = []
        if side in ('short', None):
            self.s_fib_index = 0
            self.s_pq = []

    def run(self, o_pos, o_ord, ltp):
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

        l_orders = []
        s_orders = []
        for o in o_ord:
            units = int(o.get('units', '0'))
            if units > 0:
                l_orders.append(o)
            elif units < 0:
                s_orders.append(o)

        if (l_units == 0 or s_units == 0) and stop_signal is False:
            if l_units == 0:
                if len(l_orders) != 0:
                    log.info("%s LONG: Clearing pending orders" % self.instrument)
                    self.clean(side="long")
                    return
                log.info("\nPositions: %s\nOrders: %s" % (o_pos, o_ord))
                log.info("%s LONG: Market order, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
                self.l_pq.append([0, self.config['qty']])
            if s_units == 0:
                if len(s_orders) != 0:
                    log.info("%s SHORT: Clearing pending orders" % self.instrument)
                    self.clean(side="short")
                    return
                log.info("\nPositions: %s\nOrders: %s" % (o_pos, o_ord))
                log.info("%s SHORT: Market order, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
                self.s_pq.append([0, self.config['qty']])
            return

        if l_units > 0 and len(l_orders) == 0 and self.l_fib_index < len(fib_series):
            if self.l_pq[0][0] == 0:
                self.l_pq[0][0] = l_price
            offset = sum(fib_series[:self.l_fib_index+1]) * self.config['stepSize']
            order_price = l_price - offset
            log.info("\nPositions: %s\nOrders: %s" % (o_pos, o_ord))
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
            log.info("\nPositions: %s\nOrders: %s" % (o_pos, o_ord))
            log.info("%s SHORT: Offset: %s, Price: %s, Units: %s, Index: %s" % (self.instrument, offset, order_price,
                                                                          s_units, self.s_fib_index))
            limit_order(self.instrument, order_price, s_units * -1)
            self.s_fib_index += 1
            self.s_pq.append([order_price, s_units])

        if l_units > 0:
            price = l_price + self.config['takeProfit']
            if len(self.l_pq) > 2:
                total_qty = 0
                total_price = 0
                for x in self.l_pq[:-2]:
                    total_price += x[0] * x[1]
                    total_qty += x[1]
                price = total_price / total_qty
            if ltp is not None and ltp['sell'] >= price:
                log.info("\nPositions: %s\nOrders: %s" % (o_pos, o_ord))
                log.info("%s LONG: Close orders and position" % self.instrument)
                self.clean(side='long')
                return

        if s_units > 0:
            price = s_price - self.config['takeProfit']
            if len(self.s_pq) > 2:
                total_qty = 0
                total_price = 0
                for x in self.s_pq[:-2]:
                    total_price += x[0] * x[1]
                    total_qty += x[1]
                price = total_price / total_qty
            if ltp is not None and ltp['buy'] <= price:
                log.info("\nPositions: %s\nOrders: %s" % (o_pos, o_ord))
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
symbol_list = []
for s, c in params["symbols"].items():
    # if s not in ("EUR_USD", "GBP_USD"):
    #     continue
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
        o_orders = open_orders()
        prices = get_prices()

        for symbol in symbols:
            o_p = o_positions.get(symbol.instrument, {})
            o_o = o_orders.get(symbol.instrument, {})
            if stop_signal is True and len(o_p) == 0:
                continue

            symbol.run(o_p, o_o, prices.get(symbol.instrument, None))
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
