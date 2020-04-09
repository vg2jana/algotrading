import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import pandas as pd
import time
import logging
import json


def ATR(DF, n):
    "function to calculate True Range and Average True Range"
    df = DF.copy()
    df['H-L'] = abs(df['High'] - df['Low'])
    df['H-PC'] = abs(df['High'] - df['Adj Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Adj Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1, skipna=False)
    df['ATR'] = df['TR'].rolling(n).mean()
    # df['ATR'] = df['TR'].ewm(span=n,adjust=False,min_periods=n).mean()
    df2 = df.drop(['H-L', 'H-PC', 'L-PC'], axis=1)
    return df2['ATR']


def candles(instrument):
    params = {"count": 800, "granularity": "M5"}
    candles = instruments.InstrumentsCandles(instrument=instrument, params=params)
    client.request(candles)
    ohlc_dict = candles.response["candles"]
    ohlc = pd.DataFrame(ohlc_dict)
    ohlc_df = ohlc.mid.dropna().apply(pd.Series)
    ohlc_df["volume"] = ohlc["volume"]
    ohlc_df.index = ohlc["time"]
    ohlc_df = ohlc_df.apply(pd.to_numeric)
    ohlc_df.columns = ["Open", "High", "Low", "Adj Close", "Volume"]
    return ohlc_df


def signals(data):
    data["ATR"] = ATR(data, 20)
    data["roll_max_cp"] = data["High"].rolling(20).max()
    data["roll_min_cp"] = data["Low"].rolling(20).min()
    data["roll_max_vol"] = data["Volume"].rolling(20).max()
    data.dropna(inplace=True)

    sig = []
    i = -1
    if data["High"][i] >= data["roll_max_cp"][i] and data["Volume"][i] > 1.5 * data["roll_max_vol"][i - 1]:
        sig.append("OPEN_BUY")

    if data["Low"][i] <= data["roll_min_cp"][i] and data["Volume"][i] > 1.5 * data["roll_max_vol"][i - 1]:
        sig.append("OPEN_SELL")

    if data["Adj Close"][i] < data["Adj Close"][i - 1] - data["ATR"][i - 1]:
        sig.append("CLOSE_BUY")

    if data["Adj Close"][i] > data["Adj Close"][i - 1] + data["ATR"][i - 1]:
        sig.append("CLOSE_SELL")

    return sig


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


def cancel_orders(orderIDs):
    for i in orderIDs:
        r = orders.OrderCancel(account_id, i)
        client.request(r)


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


def clean(instrument):
    # Cancel pending orders
    p_orders = [o['id'] for o in o_orders.get(instrument, [])]
    cancel_orders(p_orders)
    # Close positions
    close_positions(instrument)


def run(currency, o_pos):
    l_units = 0
    s_units = 0
    if len(o_pos) > 0:
        l_units = abs(int(o_pos["long"]["units"]))
        s_units = abs(int(o_pos["short"]["units"]))

    log.info("analyzing %s" % currency)
    data = candles(currency)
    sig = signals(data)
    if l_units == 0 and s_units == 0:
        if "OPEN_BUY" in sig:
            market_order(currency, pos_size)
        elif "OPEN_SELL" in sig:
            market_order(currency, pos_size * -1)
    else:
        if l_units > 0 and ("CLOSE_BUY" in sig or "OPEN_SELL" in sig):
            log.info("Closing long position for %s" % currency)
            clean(currency)
            return
        if s_units > 0 and ("CLOSE_SELL" in sig or "OPEN_BUY" in sig):
            log.info("Closing short position for %s" % currency)
            clean(currency)
            return


logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                    filename='resistance_breakout.log')
log = logging.getLogger()
with open('key.json', 'r') as f:
    key = json.load(f)

client = oandapyV20.API(access_token=key['token'], environment="practice")
account_id = "101-009-13015690-002"

pairs = ['EUR_USD', 'EUR_JPY', 'EUR_AUD', 'AUD_USD', 'AUD_CHF', 'AUD_NZD', 'GBP_HKD', 'GBP_USD', 'GBP_NZD', 'USD_JPY',
         'USD_CAD', 'USD_INR', 'USD_SGD', 'USD_HKD', 'NZD_USD', 'NZD_JPY', 'NZD_CAD', 'SGD_JPY', 'CAD_JPY', 'HKD_JPY']
pos_size = 1000

o_positions = open_positions()
o_orders = open_orders()
for p in pairs:
    clean(p)

# Continuous execution
starttime = time.time()
while True:
    try:
        o_positions = open_positions()
        for p in pairs:
            o_p = o_positions.get(p, {})
            log.info("passthrough at %s" % time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
            run(p, o_p)
        time.sleep(300 - ((time.time() - starttime) % 300.0))  # 5 minute interval between each new execution
    except KeyboardInterrupt:
        log.info('\n\nKeyboard exception received. Exiting.')
        exit()
