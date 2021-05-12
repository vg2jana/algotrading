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


def readSignal():
    global signalIndex
    with open(signalFile, "r") as f:
        data = f.readlines()

    result = data[signalIndex:]
    signalIndex = len(data)

    return result


def parseSignal(data):
    logging.info("Parsing signal:\n%s" % data)
    result = {}
    try:
        data = json.loads(data)
    except:
        logging.error("Unable to parse signal:\n%s" % data)
        return {}

    m = re.search("([A-Z]{6}) (Buy|Sell)", data["title"])
    if m is not None:
        result["symbol"] = m.group(1)
        result["side"] = m.group(2)

    m = re.search("([A-Z]{6}) [Cc]lose", data["title"])
    if m is not None:
        result["symbol"] = m.group(1)
        result["close"] = True

    m = re.search("[Cc]lose ([A-Z]{6})", data["title"])
    if m is not None:
        result["symbol"] = m.group(1)
        result["close"] = True

    m = re.search("([A-Z]{6}).*hit", data["title"])
    if m is not None:
        result["symbol"] = m.group(1)
        result["close"] = True

    m = re.search("Set TP:(\S+), SL:(\S+)", data["text"])
    if m is not None:
        result["tp"] = float(m.group(1))
        result["sl"] = float(m.group(2))

    if result.get("symbol", None) is not None:
        _symbol = result["symbol"]
        result["symbol"] = f"{_symbol[:3]}_{_symbol[3:]}"

    if "side" in result and ("tp" not in result or "sl" not in result):
        logging.error("Missing tp/sl in signal.")
        result = {}

    if "side" not in result and "close" not in result:
        logging.error("Unable to determine side/close.")
        result = {}

    return result


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='forextradingsignals.log')
log = logging.getLogger()
with open('key.json', 'r') as f:
    key = json.load(f)

log.info("Program S T A R T I N G")

token = key['token']
client = oandapyV20.API(access_token=token, environment="practice")
account_id = "101-009-13015690-006"
reconnect = False
signalIndex = 0
signalFile = "signal.log"
ledger = {}
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
            ledger[symbol] = signal

            if signal.get("close", False) is True:
                close_positions(symbol)
                ledger[symbol] = None
                updated = True
                continue

            if signal.get("side", None) is not None:
                qty = 1000
                if signal["side"] == "Sell":
                    qty *= -1
                log.info("%s: Market order, Units: %s" % (symbol, qty))
                market_order(symbol, qty)
                time.sleep(1)
                updated = True
                continue

        if updated is True:
            time.sleep(1)
            o_positions = open_positions()
            o_trades = open_trades()

        for symbol in o_trades.keys():
            if ledger.get(symbol, None) is None:
                close_positions(symbol)
                ledger[symbol] = None
                continue
            o_trd = o_trades[symbol]
            if o_trd.get("takeProfitOrder", None) is None:
                amend_trade(o_trd["id"], tp_price=ledger[symbol]["tp"], sl_price=ledger[symbol]["sl"])
                time.sleep(1)

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
