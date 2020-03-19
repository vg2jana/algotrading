import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.trades as trades
import pandas as pd
import time
from decimal import Decimal


token = '83e8d0aafd0cb5570b32f08940871118-a21bed79d55fbd13dc3eef40d9e07a48'
client = oandapyV20.API(access_token=token, environment="practice")
account_id = "101-009-13015690-002"


def market_order(instrument, units, positionFill='DEFAULT'):
    data = {
        "order": {
            "timeInForce": "FOK",
            "instrument": str(instrument),
            "units": str(units),
            "type": "MARKET",
            "positionFill": positionFill
        }
    }
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


def market_if_touched_order(instrument, price, units):
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
    del price

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
        result[p['instrument']] = float(p['unrealizedPL'])

    return result


def close_positions(instrument):
    data = {
        "longUnits": "ALL",
        "shortUnits": "ALL"
    }
    r = positions.PositionClose(account_id, instrument, data)
    client.request(r)

    return r.response


# m_order = market_order("EUR_USD", 10)
# m_price = float(m_order['orderFillTransaction']['price'])
#
# for n in range(1, 10):
#     price = m_price + (n * 0.001)
#     market_if_touched_order("EUR_USD", price, (n + 1) * 10)
#     time.sleep(2)
#
# for n in range(1, 11):
#     price = m_price - (n * 0.001)
#     market_if_touched_order("EUR_USD", price, n * -10)
#     time.sleep(2)

while True:
    result = get_positions()
    if result["EUR_USD"] > 100:
        close_positions("EUR_USD")
        o_orders = open_orders()
        cancel_orders([o['id'] for o in o_orders])
        break
    time.sleep(2)