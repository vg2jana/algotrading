import pandas as pd
import logging
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from time import sleep
from exchanges.BitMEX.bitmex_symbol import BitMEXSymbol
from strategies.res_brkout import ResistanceBreakout, ResistanceBreakoutBackTest
from strategies.renko_macd import RenkoMACDBackTest
from exchanges.BitMEX.mywebsocket import MyWebSocket
from exchanges.BitMEX.rest_client import RestClient
from exchanges.BitMEX.order import Order


class ResistanceBreakOutBitMEX(ResistanceBreakout):
    def __init__(self, dataframe, symbol, websocket):
        self.symbol = symbol
        self.client = symbol.client
        self.ws = websocket
        self.qty = 1
        self.order = None
        self.logger = logging.getLogger()
        super(ResistanceBreakOutBitMEX, self).__init__(dataframe, duration=self.symbol.frequency)

    def teardown(self):
        self.logger.info("Teardown called.")
        if self.signal is not None:
            self.close_position()

    def update_book(self):
        self.book['ltp'] = self.ws.ltp()

    def update_dataframe(self):
        last_updated = self.dataframe.index[-1]
        start_time = last_updated + timedelta(minutes=1)
        df = self.symbol.fetch_data(start_time)
        self.dataframe = pd.concat([self.dataframe, df], sort=False)

    def open_position(self):
        side = self.signal
        if side is None:
            return

        order = None
        attempts = 5
        while attempts > 0:
            if order is None:
                order = Order(self)
                status = order.new(orderQty=self.qty, ordType="Market", side=side)
                if status is None:
                    attempts -= 1
                    sleep(1)
                    continue
            order.get_status()

            if order.ordStatus in ('Filled',):
                break
            elif order.ordStatus == 'Canceled':
                sleep(1)
                continue

            sleep(1)
        else:
            self.logger.warning("Unable to open position")
            return False

        self.entry_price = order.price
        self.position_index = len(self.dataframe) - 1
        self.logger.info("Position opened for {} at price {} side {}".format(self.symbol.symbol, self.entry_price, side))
        return True

    def close_position(self):
        attempts = 5
        close_order = None
        while attempts > 0:
            position = self.client.open_position()
            if type(position) is list and len(position) == 0:
                break
            if position is None:
                attempts -= 1
                sleep(1)
                continue
            if position.get("isOpen", True) is True:
                close_order = self.client.close_position()
                sleep(1)
            else:
                break
        else:
            self.ws.ws.exit()
            self.logger.fatal("Unable to close open position(s).")
            sys.exit(1)

        if close_order is not None:
            self.exit_price = close_order.get('price', 0)
            self.logger.info("Position closed for {} at price {}".format(self.symbol.symbol, self.exit_price))
        return True


def backtest(key, secret, product, frequency):
    # key = "VvD5-fMBfiZ9dlMtXP2pffHj"
    # secret = "jROi3UZ5q_hkVW2RnK3xbCQEnTzpLXcnbOdUCJTnQFrrdUgj"
    client = RestClient(False, key, secret, product)
    symbol = BitMEXSymbol(product, client=client, frequency=frequency)
    dataframe = pd.DataFrame(symbol.fetch_data(datetime.utcnow() - timedelta(days=2)))
    backtest = ResistanceBreakoutBackTest(dataframe)
    backtest.weighted = False
    backtest.rolling_period = 14
    backtest.min_profit = 13.5
    backtest.min_loss = 0
    backtest.setup()
    backtest.run()

    sum = 0
    for r in backtest.returns:
        sum += r[-1] - 13.5

    print(sum)


if __name__ == '__main__':
    with open("config.json", 'r') as f:
        data = json.load(f)

    bt = False
    test_env = False
    if bt is True or test_env is False:
        params = data['prod']
    else:
        params = data['test']

    key = params['key']
    secret = params['secret']
    product = params['symbol']
    frequency = '5m'

    if bt is True:
        backtest(key, secret, product, frequency)
        sys.exit(0)

    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                        filename='app.log')
    if test_env is True:
        endpoint = "https://testnet.bitmex.com/api/v1"
    else:
        endpoint = "https://www.bitmex.com/api/v1"

    client = RestClient(test_env, key, secret, product)
    websocket = MyWebSocket(endpoint, product, key, secret)
    websocket.connect_ws()
    symbol = BitMEXSymbol(product, client=client, frequency=frequency)
    dataframe = pd.DataFrame(symbol.fetch_data(datetime.utcnow() - timedelta(hours=4), count=200))
    res_bro = ResistanceBreakOutBitMEX(dataframe, symbol, websocket)
    backtest = ResistanceBreakout(dataframe)
    res_bro.weighted = False
    res_bro.rolling_period = 15
    res_bro.min_profit = 13.5
    res_bro.min_loss = 0
    res_bro.time_bound_run(60 * 60 * 24 * 3)
