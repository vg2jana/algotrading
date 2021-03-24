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


class FxGBPUSD:
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.df = None
        self.max_df_rows = 1000
        self.signal_df = None

    # GBP_USD
    def clean(self, side=None):
        # Close positions
        close_positions(self.instrument, side=side)
        # Clear first order reference
        if side in ('long', None):
            pass
        if side in ('short', None):
            pass

    # GBP_USD
    def update_candles(self):
        new_candle = False
        granularity = self.config["granularity"]
        if self.df is None:
            _to = "{}Z".format(datetime.utcnow().isoformat())
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_to=_to, count=self.max_df_rows)
            self.df = pd.DataFrame(data)
            self.df["datetime"] = pd.to_datetime(self.df["datetime"])
            new_candle = True
        else:
            last_time = self.df.iloc[-1]["datetime"]
            diff = datetime.now(timezone.utc) - last_time.to_pydatetime()
            if diff.days == 0:
                return
            _from = last_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_from=_from, includeFirst=False)
            if len(data) > 0:
                _df = pd.DataFrame(data)
                _df["datetime"] = pd.to_datetime(_df["datetime"])
                self.df = pd.concat([self.df, _df], ignore_index=True)
                self.df = self.df.tail(self.max_df_rows)
                self.df.reset_index(drop=True, inplace=True)
                new_candle = True

        if new_candle is False:
            return

        # Update signals
        _df = pd.DataFrame(self.df)
        _df["buy_signal"] = (_df["volume"] > 80000) & (_df["close"] > _df["open"])
        _df["sell_signal"] = (_df["volume"] > 80000) & (_df["open"] > _df["close"])
        _df["exit_buy"] = (_df["close"] < _df["open"]) & (_df["close"].shift() < _df["open"].shift())
        _df["exit_sell"] = (_df["close"] > _df["open"]) & (_df["close"].shift() > _df["open"].shift())

        self.signal_df = _df

    # GBP_USD
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

        _df = self.signal_df.iloc[-1]
        if l_units == 0 or s_units == 0:
            if l_units == 0 and _df["buy_signal"] is True:
                log.info("%s: Market order LONG, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
            if s_units == 0 and _df["sell_signal"] is True:
                log.info("%s: Market order SHORT, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
            return

        if l_units > 0:
            if _df["exit_buy"] == True or _df["sell"] == True or l_price - self.config["stopLoss"] < _df["close"]:
                log.info("%s: Closing LONG position" % self.instrument)
                self.clean(side='long')
                return

        if s_units > 0:
            if _df["exit_sell"] == True or _df["buy"] == True or s_price + self.config["stopLoss"] > _df["close"]:
                log.info("%s: Closing SHORT position" % self.instrument)
                self.clean(side='short')
                return


class FxEURUSD:
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.df = None
        self.max_df_rows = 1000
        self.signal_df = None

    # EUR_USD
    def clean(self, side=None):
        # Close positions
        close_positions(self.instrument, side=side)
        # Clear first order reference
        if side in ('long', None):
            pass
        if side in ('short', None):
            pass

    # EUR_USD
    def update_candles(self):
        new_candle = False
        granularity = self.config["granularity"]
        if self.df is None:
            _to = "{}Z".format(datetime.utcnow().isoformat())
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_to=_to, count=self.max_df_rows)
            self.df = pd.DataFrame(data)
            self.df["datetime"] = pd.to_datetime(self.df["datetime"])
            new_candle = True
        else:
            last_time = self.df.iloc[-1]["datetime"]
            diff = datetime.now(timezone.utc) - last_time.to_pydatetime()
            if diff.total_seconds() < 15 * 60:
                return
            _from = last_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_from=_from, includeFirst=False)
            if len(data) > 0:
                _df = pd.DataFrame(data)
                _df["datetime"] = pd.to_datetime(_df["datetime"])
                self.df = pd.concat([self.df, _df], ignore_index=True)
                self.df = self.df.tail(self.max_df_rows)
                self.df.reset_index(drop=True, inplace=True)
                new_candle = True

        if new_candle is False:
            return

        candle_client.moving_average(self.df, 9)
        candle_client.moving_average(self.df, 20)
        candle_client.moving_average(self.df, 50)
        candle_client.moving_average(self.df, 200)

        # Drop the first 200 rows as the average is not accurate
        _df = pd.DataFrame(self.df.iloc[200:])
        _df["buy_signal"] = (_df["close_200_sma"].shift() > _df["close_50_sma"].shift()) & (
                                _df["close_200_sma"] < _df["close_50_sma"]) & (
                                _df["close_50_sma"] < _df["close_20_sma"]) & (
                                _df["close_20_sma"] < _df["close_9_sma"])
        _df["trend_high"] = (_df["close_200_sma"] < _df["close_50_sma"]) & (
                                _df["close_50_sma"] < _df["close_20_sma"]) & (
                                _df["close_50_sma"] < _df["close_9_sma"])
        _df["sell_signal"] = (_df["close_200_sma"].shift() < _df["close_50_sma"].shift()) & (
                                _df["close_200_sma"] > _df["close_50_sma"]) & (
                                _df["close_50_sma"] > _df["close_20_sma"]) & (
                                _df["close_20_sma"] > _df["close_9_sma"])
        _df["trend_low"] = (_df["close_200_sma"] > _df["close_50_sma"]) & (
                                _df["close_50_sma"] > _df["close_20_sma"]) & (
                                _df["close_50_sma"] > _df["close_9_sma"])

        self.signal_df = _df

    # EUR_USD
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

        _df = self.signal_df.iloc[-1]
        if l_units == 0 or s_units == 0:
            if l_units == 0 and _df["buy_signal"] is True:
                log.info("%s: Market order LONG, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
            if s_units == 0 and _df["sell_signal"] is True:
                log.info("%s: Market order SHORT, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
            return

        if l_units > 0 and ltp is not None:
            if _df["trend_high"] == True and ltp["sell"] - l_price >= 2 * self.config["takeProfit"]:
                log.info("%s: Closing LONG position for double take profit." % self.instrument)
                self.clean(side='long')
                return
            elif _df["trend_high"] == False:
                if l_price - ltp["sell"] >= self.config["stopLoss"]:
                    log.info("%s: Closing LONG position for stop loss." % self.instrument)
                    self.clean(side='long')
                    return
                elif ltp["sell"] - l_price >= self.config["takeProfit"]:
                    log.info("%s: Closing LONG position for single take profit." % self.instrument)
                    self.clean(side='long')
                    return

        if s_units > 0 and ltp is not None:
            if _df["trend_low"] == True and s_price - ltp["buy"] >= 2 * self.config["takeProfit"]:
                log.info("%s: Closing SHORT position for double take profit." % self.instrument)
                self.clean(side='short')
                return
            elif _df["trend_low"] == False:
                if ltp["buy"] - s_price >= self.config["stopLoss"]:
                    log.info("%s: Closing SHORT position for stop loss." % self.instrument)
                    self.clean(side='short')
                    return
                elif s_price - ltp["buy"] >= self.config["takeProfit"]:
                    log.info("%s: Closing SHORT position for single take profit." % self.instrument)
                    self.clean(side='short')
                    return


class FxAUDUSD:
    def __init__(self, instrument, config):
        self.instrument = instrument
        self.config = config
        self.df = None
        self.max_df_rows = 1000
        self.signal_df = None

    # AUD_USD
    def clean(self, side=None):
        # Close positions
        close_positions(self.instrument, side=side)
        # Clear first order reference
        if side in ('long', None):
            pass
        if side in ('short', None):
            pass

    # AUD_USD
    def update_candles(self):
        new_candle = False
        granularity = self.config["granularity"]
        if self.df is None:
            _to = "{}Z".format(datetime.utcnow().isoformat())
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_to=_to, count=self.max_df_rows)
            self.df = pd.DataFrame(data)
            self.df["datetime"] = pd.to_datetime(self.df["datetime"])
        else:
            last_time = self.df.iloc[-1]["datetime"]
            diff = datetime.now(timezone.utc) - last_time.to_pydatetime()
            if diff.total_seconds() < 60 * 60:
                return
            _from = last_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_from=_from, includeFirst=False)
            if len(data) > 0:
                _df = pd.DataFrame(data)
                _df["datetime"] = pd.to_datetime(_df["datetime"])
                self.df = pd.concat([self.df, _df], ignore_index=True)
                self.df = self.df.tail(self.max_df_rows)
                self.df.reset_index(drop=True, inplace=True)

        candle_client.macd(self.df, a=9, b=12, c=26)
        candle_client.moving_average(self.df, 20)
        candle_client.moving_average(self.df, 50)

        # Drop the first 200 rows as the average is not accurate
        _df = pd.DataFrame(self.df.iloc[50:])
        _df["buy_signal"] = (_df["close_20_sma"].shift() > _df["close_50_sma"].shift()) & (
                                _df["macdh"].shift() <= 0) & (_df["macdh"] > 0)
        _df["sell_signal"] = (_df["close_20_sma"].shift() < _df["close_50_sma"].shift()) & (
                                _df["macdh"].shift() >= 0) & (_df["macdh"] < 0)

        self.signal_df = _df

    # AUD_USD
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

        _df = self.signal_df.iloc[-1]
        if l_units == 0 or s_units == 0:
            if l_units == 0 and _df["buy_signal"] is True:
                log.info("%s: Market order LONG, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
            if s_units == 0 and _df["sell_signal"] is True:
                log.info("%s: Market order SHORT, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
            return

        if l_units > 0 and ltp is not None:
            if l_price - _df["close"] >= self.config["stopLoss"]:
                log.info("%s: Closing LONG position for stop loss." % self.instrument)
                self.clean(side='long')
                return
            elif _df["sell_signal"] == True:
                log.info("%s: Closing LONG position on short signal." % self.instrument)
                self.clean(side='long')
                return
            elif ltp["sell"] - l_price >= self.config["takeProfit"]:
                log.info("%s: Closing LONG position for take profit." % self.instrument)
                self.clean(side='long')
                return

        if s_units > 0 and ltp is not None:
            if _df["close"] - s_price >= self.config["stopLoss"]:
                log.info("%s: Closing SHORT position for stop loss." % self.instrument)
                self.clean(side='short')
                return
            elif _df["buy_signal"] == True:
                log.info("%s: Closing SHORT position on long signal." % self.instrument)
                self.clean(side='short')
                return
            elif s_price - ltp["buy"] >= self.config["takeProfit"]:
                log.info("%s: Closing SHORT position for take profit." % self.instrument)
                self.clean(side='short')
                return


class Practice:
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
        self.l_sl_price = None
        self.s_sl_price = None

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
            self.l_sl_price = None
        if side in ('short', None):
            self.s_last_price = None
            self.s_last_time = None
            self.s_sl_price = None

    def update_trend(self):
        new_candle = False
        granularity = self.config["granularity"]
        if self.df is None:
            _to = "{}Z".format(datetime.utcnow().isoformat())
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_to=_to, count=self.max_df_rows)
            self.df = pd.DataFrame(data)
            new_candle = True
        else:
            last_time = self.df.iloc[-1]["datetime"]
            data = candle_client.fetch_ohlc(self.instrument, granularity, t_from=last_time, includeFirst=False)
            if len(data) > 0:
                _df = pd.DataFrame(data)
                self.df = pd.concat([self.df, _df], ignore_index=True)
                self.df = self.df.tail(self.max_df_rows)
                self.df.reset_index(drop=True, inplace=True)
                new_candle = True

        if new_candle is False:
            return

        candle_client.moving_average(self.df, 9)
        candle_client.moving_average(self.df, 20)
        candle_client.moving_average(self.df, 50)
        candle_client.moving_average(self.df, 200)

        # Drop the first 200 rows as the average is not accurate
        _df = pd.DataFrame(self.df.iloc[200:])
        _df["buy_signal"] = (_df["close_200_sma"] > _df["close_50_sma"].shift()) & (_df["close_200_sma"] < _df["close_50_sma"]) & (
                _df["close_50_sma"] < _df["close_20_sma"]) & (_df["close_20_sma"] < _df["close_9_sma"])
        _df["trend_high"] = (_df["close_200_sma"] < _df["close_50_sma"]) & (_df["close_50_sma"] < _df["close_20_sma"]) & (
                _df["close_50_sma"] < _df["close_9_sma"])
        _df["sell_signal"] = (_df["close_200_sma"] < _df["close_50_sma"].shift()) & (_df["close_200_sma"] > _df["close_50_sma"]) & (
                _df["close_50_sma"] > _df["close_20_sma"]) & (_df["close_20_sma"] > _df["close_9_sma"])
        _df["trend_low"] = (_df["close_200_sma"] > _df["close_50_sma"]) & (_df["close_50_sma"] > _df["close_20_sma"]) & (
                _df["close_50_sma"] > _df["close_9_sma"])

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

        if l_units == 0 or s_units == 0:
            if l_units == 0 and self.signal_df.iloc[-1]["buy_signal"] is True:
                log.info("%s: Market order, Units: %s" % (self.instrument, self.config['qty']))
                market_order(self.instrument, self.config['qty'])
                self.l_last_time = self.signal_df.iloc[-1]["datetime"]
            if s_units == 0 and self.signal_df.iloc[-1]["sell_signal"] is True:
                log.info("%s: Market order, Units: %s" % (self.instrument, self.config['qty'] * -1))
                market_order(self.instrument, self.config['qty'] * -1)
                self.s_last_time = self.signal_df.iloc[-1]["datetime"]
            return

        if l_units > 0 and ltp is not None:
            tp_price = l_price + self.config['takeProfit']
            if (ltp['sell'] >= tp_price and self.signal_df["trend_high"] is False) or (
                    self.signal_df.iloc[-1]["trend_high"] is False and ltp['sell'] <= l_price):
                log.info("%s: TakeProfit - Cleaning Long order and positions" % self.instrument)
                self.clean(side='long')
                return
            if self.l_sl_price is not None and ltp['sell'] <= self.l_sl_price:
                log.info("%s: StopLoss hit - Cleaning Long order and positions" % self.instrument)
                self.clean(side='long')
                return

        if s_units > 0 and ltp is not None:
            tp_price = s_price - self.config['takeProfit']
            if (ltp['buy'] <= tp_price and self.signal_df["trend_low"] is False) or (
                    self.signal_df.iloc[-1]["trend_low"] is False and ltp['buy'] >= s_price):
                log.info("%s: Cleaning Short order and positions" % self.instrument)
                self.clean(side='short')
                return
            if self.s_sl_price is not None and ltp['buy'] >= self.s_sl_price:
                log.info("%s: StopLoss hit - Cleaning Short order and positions" % self.instrument)
                self.clean(side='short')
                return

        if l_units > 0 and ltp['sell'] >= l_price + self.config["stopLossAfter"]:
            self.l_sl_price = l_price

        if s_units > 0 and ltp['buy'] <= s_price - self.config["stopLossAfter"]:
            self.s_sl_price = s_price

        # if l_units == self.config['qty'] and self.signal_df.iloc[-1]["buy_signal"] is True and \
        #         self.signal_df.iloc[-1]["datetime"] != self.l_last_time:
        #     log.info("%s: Market Buy order, Units: %s" % (self.instrument, self.config['qty']))
        #     market_order(self.instrument, self.config['qty'])
        #     self.l_last_price = float(self.signal_df.iloc[-1]["close"])
        #     self.l_last_time = self.signal_df.iloc[-1]["datetime"]
        #
        # if s_units == self.config['qty'] and self.signal_df.iloc[-1]["sell_signal"] is True and \
        #         self.signal_df.iloc[-1]["datetime"] != self.s_last_time:
        #     log.info("%s: Market Sell order, Units: %s" % (self.instrument, self.config['qty'] * -1))
        #     market_order(self.instrument, self.config['qty'] * -1)
        #     self.s_last_price = float(self.signal_df.iloc[-1]["close"])
        #     self.s_last_time = self.signal_df.iloc[-1]["datetime"]

        # if l_units > self.config['qty'] and self.signal_df.iloc[-1]["buy_signal"] is True and \
        #         self.signal_df.iloc[-1]["datetime"] != self.l_last_time:
        #     gap = abs(self.l_last_price - self.signal_df.iloc[-1]["close"])
        #     if gap >= self.config["takeProfit"] * l_units / self.config['qty']:
        #         log.info("%s: Market Buy order, Units: %s" % (self.instrument, self.config['qty']))
        #         market_order(self.instrument, self.config['qty'])
        #         self.l_last_price = float(self.signal_df.iloc[-1]["close"])
        #         self.l_last_time = self.signal_df.iloc[-1]["datetime"]
        #
        # if s_units > self.config['qty'] and self.signal_df.iloc[-1]["sell_signal"] is True and \
        #         self.signal_df.iloc[-1]["datetime"] != self.s_last_time:
        #     gap = abs(self.s_last_price - self.signal_df.iloc[-1]["close"])
        #     if gap >= self.config["takeProfit"] * s_units / self.config['qty']:
        #         log.info("%s: Market Sell order, Units: %s" % (self.instrument, self.config['qty'] * -1))
        #         market_order(self.instrument, self.config['qty'] * -1)
        #         self.s_last_price = float(self.signal_df.iloc[-1]["close"])
        #         self.s_last_time = self.signal_df.iloc[-1]["datetime"]


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

o_positions = open_positions()
o_orders = open_orders()
symbols = []
symbol_list = []

for _symbol, _config in params["symbols"].items():
    log.info("Clearing existing positions for %s" % _symbol)
    clear_symbol(_symbol)
    _s = None
    if _symbol == "GBP_USD":
        _s = FxGBPUSD(_symbol, _config)
    elif _symbol == "EUR_USD":
        _s = FxEURUSD(_symbol, _config)
    elif _symbol == "AUD_USD":
        _s = FxAUDUSD(_symbol, _config)

    if _s is not None:
        symbol_list.append(_symbol)
        symbols.append(_s)

time.sleep(2)
stop_signal = False
nav = None

while True:

    try:
        if os.path.exists('STOP'):
            stop_signal = True

        o_positions = open_positions()
        # o_orders = open_orders()
        prices = get_prices(symbol_list)
        account_info = get_account_info()

        if nav is None:
            nav = account_info['NAV']

        for _symbol in symbols:
            o_p = o_positions.get(_symbol.instrument, {})
            # o_o = o_orders.get(_symbol.instrument, {})
            # if stop_signal is True and len(o_p) == 0:
            #     continue

            _symbol.update_candles()
            _symbol.run(o_p, prices.get(_symbol.instrument, None))

            if os.path.exists("CLOSE_%s" % _symbol.instrument):
                log.info("%s: Cleaning all orders and positions on CLOSE SIGNAL" % _symbol.instrument)
                _symbol.clean()
                os.remove("CLOSE_%s" % _symbol.instrument)

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
