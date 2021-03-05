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
import datetime
import sys

sys.path.append("../../../exchanges")
from exchanges.OANDA.indicator.candle_stick import Candles


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


class Symbol:
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.df = None
        self.max_df_rows = 1000
        self.signal_df = None
        self.l_last_price = None
        self.s_last_price = None
        self.l_last_time = None
        self.s_last_time = None

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
        if len(p_orders) > 0:
            cancel_orders(p_orders)
        # Close positions
        close_positions(self.instrument, side=side)
        # Clear first order reference
        if side in ('long', None):
            self.l_last_price = None
            self.l_last_time = None
        if side in ('short', None):
            self.s_last_price = None
            self.s_last_time = None

    def update_trend(self):
        granularity = self.config["granularity"]
        if self.df is None:
            _to = "{}Z".format(datetime.datetime.utcnow().isoformat())
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_to=_to, count=self.max_df_rows)
            self.df = pd.DataFrame(data)
        else:
            last_time = self.df.iloc[-1]["datetime"]
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_from=last_time, includeFirst=False)
            if len(data) > 0:
                _df = pd.DataFrame(data)
                self.df = pd.concat([self.df, _df])
                self.df = self.df.tail(self.max_df_rows)

        candle_client.moving_average(self.df, 9)
        candle_client.moving_average(self.df, 20)
        candle_client.moving_average(self.df, 50)
        candle_client.moving_average(self.df, 200)

        # Drop the first 200 rows as the average is not accurate
        _df = self.df.iloc[200:]
        _df["buy_signal"] = (_df["sma_200"] > _df["sma_50"].shift()) & (_df["sma_200"] < _df["sma_50"]) & (
                _df["sma_50"] < _df["sma_20"]) & (_df["sma_20"] < _df["sma_9"])
        _df["trend_high"] = (_df["sma_200"] < _df["sma_50"]) & (_df["sma_50"] < _df["sma_20"]) & (
                _df["sma_50"] < _df["sma_9"])
        _df["sell_signal"] = (_df["sma_200"] < _df["sma_50"].shift()) & (_df["sma_200"] > _df["sma_50"]) & (
                _df["sma_50"] > _df["sma_20"]) & (_df["sma_20"] > _df["sma_9"])
        _df["trend_low"] = (_df["sma_200"] > _df["sma_50"]) & (_df["sma_50"] > _df["sma_20"]) & (
                _df["sma_50"] > _df["sma_9"])

        self.signal_df = _df

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

        if l_units > 0:
            tp_price = l_price + self.config['takeProfit']
            if ltp is not None and ltp['sell'] >= tp_price and self.signal_df["trend_high"] is False:
                log.info("%s: Cleaning Long order and positions" % self.instrument)
                self.clean(side='long')
                return

        if s_units > 0:
            tp_price = s_price - self.config['takeProfit']
            if ltp is not None and ltp['buy'] <= tp_price and self.signal_df["trend_low"] is False:
                log.info("%s: Cleaning Short order and positions" % self.instrument)
                self.clean(side='short')
                return

        if l_units == 0 or s_units == 0:
            if l_units == 0 and self.signal_df[-1]["buy_signal"] is True:
                log.info("%s: Market order, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
                self.l_last_time = self.signal_df[-1]["datetime"]
            if s_units == 0 and self.signal_df[-1]["sell_signal"] is True:
                log.info("%s: Market order, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
                self.s_last_time = self.signal_df[-1]["datetime"]
            return

        if l_units == self.config['qty'] and self.signal_df[-1]["buy_signal"] is True and \
                self.signal_df[-1]["datetime"] != self.l_last_time:
            log.info("%s: Market Buy order, Units: %s" % (self.instrument, self.config['qty']))
            market_order(self.instrument, self.config['qty'])
            self.l_last_price = float(self.signal_df[-1]["close"])
            self.l_last_time = self.signal_df[-1]["datetime"]

        if s_units == self.config['qty'] and self.signal_df[-1]["sell_signal"] is True and \
                self.signal_df[-1]["datetime"] != self.s_last_time:
            log.info("%s: Market Sell order, Units: %s" % (self.instrument, self.config['qty'] * -1))
            market_order(self.instrument, self.config['qty'] * -1)
            self.s_last_price = float(self.signal_df[-1]["close"])
            self.s_last_time = self.signal_df[-1]["datetime"]

        if l_units > self.config['qty'] and self.signal_df[-1]["buy_signal"] is True and \
                self.signal_df[-1]["datetime"] != self.l_last_time:
            gap = abs(self.l_last_price - self.signal_df[-1]["close"])
            if gap >= self.config["takeProfit"] * l_units / self.config['qty']:
                log.info("%s: Market Buy order, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
                self.l_last_price = float(self.signal_df[-1]["close"])
                self.l_last_time = self.signal_df[-1]["datetime"]

        if s_units > self.config['qty'] and self.signal_df[-1]["sell_signal"] is True and \
                self.signal_df[-1]["datetime"] != self.s_last_time:
            gap = abs(self.s_last_price - self.signal_df[-1]["close"])
            if gap >= self.config["takeProfit"] * s_units / self.config['qty']:
                log.info("%s: Market Sell order, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
                self.s_last_price = float(self.signal_df[-1]["close"])
                self.s_last_time = self.signal_df[-1]["datetime"]


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='moving_average_only_prod.log')
log = logging.getLogger()
with open('key.json', 'r') as f:
    key = json.load(f)
with open('moving_average_only_prod.json', 'r') as f:
    params = json.load(f)

log.info("Program S T A R T I N G")

token = key['prod_token']
client = oandapyV20.API(access_token=token, environment="live")
candle_client = Candles(client)
account_id = "001-009-4204796-002"

symbols = []
o_positions = open_positions()
o_orders = open_orders()
symbol_list = []
log.info("Clearing existing positions...")
for s, c in params["symbols"].items():
    symbol = Symbol(s, c)
    symbol.clean()
    symbols.append(symbol)
    symbol_list.append(s)

time.sleep(2)
refresh_time = 2
stop_signal = False
nav = None

while True:

    try:
        if os.path.exists('STOP'):
            stop_signal = True

        o_positions = open_positions()
        o_orders = open_orders()
        prices = get_prices()
        account_info = get_account_info()

        if nav is None:
            nav = account_info['NAV']

        for symbol in symbols:
            o_p = o_positions.get(symbol.instrument, {})
            o_o = o_orders.get(symbol.instrument, {})
            # if stop_signal is True and len(o_p) == 0:
            #     continue

            symbol.update_trend()
            symbol.run(o_p, o_o, prices.get(symbol.instrument, None))

            if os.path.exists("CLOSE_%s" % symbol.instrument):
                log.info("%s: Cleaning all orders and positions on CLOSE SIGNAL" % symbol.instrument)
                symbol.clean()
                os.remove("CLOSE_%s" % symbol.instrument)

    except oandapyV20.exceptions.V20Error as e:
        log.warning(e)

    except requests.exceptions.ConnectionError as e:
        log.warning(e)
        while True:
            log.info("Retrying...")
            try:
                client = oandapyV20.API(access_token=token, environment="live")
                candle_client = Candles(client)
            except Exception as e:
                log.warning(e)
                time.sleep(60)
            else:
                break
    time.sleep(5)
