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

sys.path.append("../../../exchanges")
from exchanges.OANDA.indicator.candle_stick import Candles


def market_order(instrument, units, tp_price=None, sl_price=None, tp_pips=None, sl_pips=None):
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

    if tp_pips is not None:
        data["order"]["takeProfitOnFill"] = {"distance": tp_pips}
    if sl_pips is not None:
        data["order"]["stopLossOnFill"] = {"distance": sl_pips, "timeInForce": "GTC"}

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
            result[_instrument] = t

    return result


def fibonacciWyckoff():
    o_positions = open_positions()
    o_trades = open_trades()

    signalList = readSignal()
    updated = False
    for line in signalList:
        signal = parseSignal(line)
        logging.info("Parsed signal: %s" % signal)
        if signal.get("symbol", None) is None:
            logging.warning("No symbol in parsed signal, ignoring signal.")
            continue

        symbol = signal["symbol"]
        side = signal.get("side", None)
        if symbol in o_positions:
            o_pos = o_positions[symbol]
            l_units = abs(int(o_pos["long"]["units"]))
            s_units = abs(int(o_pos["short"]["units"]))
            if side == "Buy" and l_units > 0:
                logging.warning(
                    f"Got Buy signal for {symbol}. But open position already found with units {l_units}. Ignoring singal.")
                continue
            if side == "Sell" and s_units > 0:
                logging.warning(
                    f"Got Sell signal for {symbol}. But open position already found with units {l_units}. Ignoring singal.")
                continue

        ledger[symbol] = signal

        if side is not None:
            qty = 1000
            if signal["side"] == "Sell":
                qty *= -1
            log.info("%s: Market order, Units: %s" % (symbol, qty))
            market_order(symbol, qty)
            updated = True

            timeout = 5
            o_pos = []
            while timeout > 0:
                o_positions = open_positions()
                if symbol in o_positions:
                    o_pos = o_positions[symbol]
                    break
                timeout -= 0.1
                time.sleep(0.1)

            if len(o_pos) > 0 and symbol in config:
                pips = config[symbol]["pips"]
                l_units = abs(int(o_pos["long"]["units"]))
                s_units = abs(int(o_pos["short"]["units"]))
                if l_units != 0:
                    l_price = float(o_pos['long']['averagePrice'])
                    if signal["side"] == 'Buy':
                        limit_order(symbol, l_price - pips * 5, qty + 1)
                        limit_order(symbol, l_price - pips * 5 * 2, qty + 2)
                        limit_order(symbol, l_price - pips * 5 * 3, qty + 3)
                if s_units != 0:
                    s_price = float(o_pos['short']['averagePrice'])
                    if signal["side"] == 'Sell':
                        limit_order(symbol, s_price + pips * 5, qty - 1)
                        limit_order(symbol, s_price + pips * 5 * 2, qty - 2)
                        limit_order(symbol, s_price + pips * 5 * 3, qty - 3)


def readSignal():
    global signalIndex
    with open(signalFile, "r") as f:
        data = f.readlines()

    result = data[signalIndex:]
    signalIndex = len(data)

    return result


def getRecentHighLow(instrument, timeframe="H1", average=False, period=12):
    _to = "{}Z".format(datetime.utcnow().isoformat())
    data = candle_client.fetch_ohlc(instrument, timeframe, t_to=_to, count=period)
    df = pd.DataFrame(data)
    return df["high"].max(), df["low"].min()


def parseSignal(data):
    logging.info("Parsing signal:\n%s" % data)
    result = {}
    try:
        data = json.loads(data)
    except:
        logging.error("Unable to parse signal:\n%s" % data)
        return {}

    m = re.search("(\S+)\s+(Buy|Sell)\s+Alert", data["text"])
    if m is not None:
        result["symbol"] = m.group(1)
        result["side"] = m.group(2)

    if result.get("symbol", None) is not None:
        _symbol = result["symbol"]
        result["symbol"] = f"{_symbol[:3]}_{_symbol[3:]}"

    if "symbol" not in result or "side" not in result:
        logging.error(f"Unable to determine symbol/side. Result: {result}")
        result = {}

    return result


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='wyckofftradingsignals.log')
log = logging.getLogger()
with open('key.json', 'r') as f:
    key = json.load(f)
with open('wyckofftradingsignals.json', 'r') as f:
    params = json.load(f)
config = params["symbols"]

log.info("Program S T A R T I N G")

token = key['token']
client = oandapyV20.API(access_token=token, environment="practice")
account_id = "101-009-13015690-006"
candle_client = Candles(client)
reconnect = False
signalIndex = 0
signalFile = "signal.log"
readSignal()

while True:
    try:
        o_positions = open_positions()
        o_trades = open_trades()

        signalList = readSignal()
        updated = False
        for line in signalList:
            signal = parseSignal(line)
            logging.info("Parsed signal: %s" % signal)
            if signal.get("symbol", None) is None:
                logging.warning("No symbol in parsed signal, ignoring signal.")
                continue

            symbol = signal["symbol"]
            side = signal.get("side", None)
            if symbol in o_positions:
                o_pos = o_positions[symbol]
                l_units = abs(int(o_pos["long"]["units"]))
                s_units = abs(int(o_pos["short"]["units"]))
                if side == "Buy" and s_units > 0:
                    logging.warning(f"Got Buy signal for {symbol}. But open position already found for Sell with units {s_units}. Ignoring singal.")
                    continue
                if side == "Sell" and l_units > 0:
                    logging.warning(f"Got Sell signal for {symbol}. But open position already found for Buy with units {l_units}. Ignoring singal.")
                    continue

            if side is not None:
                qty = 1000
                if signal["side"] == "Buy":
                    qty *= -1
                log.info("%s: Market order, Units: %s" % (symbol, qty))
                market_order(symbol, qty, tp_pips=config[symbol]["pips"] * 10, sl_pips=config[symbol]["pips"] * 30)

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

    time.sleep(1)
