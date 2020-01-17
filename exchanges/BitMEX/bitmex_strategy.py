import bitmex
import pandas as pd
import logging
import sys
from datetime import datetime, timedelta
from time import sleep
from copy import deepcopy
from exchanges.BitMEX.bitmex_symbol import BitMEXSymbol
from strategies.res_brkout import ResistanceBreakout
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

    def setup(self):
        self.close_position(force=True)

    def teardown(self):
        self.logger.info("Teardown called.")
        if self.signal is not None:
            self.close_position(force=True)

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
        while True:
            if order is None:
                order = Order(self)
                status = order.new(orderQty=self.qty, ordType="Market", side=side)
                if status is None:
                    sleep(1)
                    continue
            order.get_status()

            if order.ordStatus in ('Filled',):
                break
            elif order.ordStatus == 'Canceled':
                sleep(1)
                continue

        self.entry_price = order.price
        self.logger.info("Position opened for {} at price {} side {}".format(self.symbol.symbol, self.entry_price, side))

    def close_position(self, force=False):
        if force is False and self.close_price_within_limits() is False:
            return False
        if force is True:
            self.logger.info('Force closing any open position(s).')

        attempts = 5
        while attempts > 0:
            close_order = self.client.close_position()
            sleep(1)
            position = self.client.open_position()
            if position is None or position["isOpen"] is True:
                attempts -= 1
                continue
            break
        else:
            self.ws.ws.exit()
            self.logger.fatal("Unable to close open position(s).")
            sys.exit(1)

        if close_order is not None:
            self.exit_price = close_order.get('price', 0)
            self.logger.info("Position closed for {} at price {}".format(self.symbol.symbol, self.exit_price))
        return True



if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO, filemode='a',
                        filename='app.log')
    key = "UzlrFYMJJGo_A7QDihj3ZtY8"
    secret = "LuA5rSvqLGDghJ8A-6ZtDEgahvbIroqFPpRdKd-uI3DPSXQG"
    product = 'XBTUSD'
    frequency = '1m'
    test_env = True
    if test_env is True:
        endpoint = "https://testnet.bitmex.com/api/v1"
    else:
        endpoint = "https://www.bitmex.com/api/v1"

    client = RestClient(test_env, key, secret, product)
    websocket = MyWebSocket(endpoint, product, key, secret)
    websocket.connect_ws()
    symbol = BitMEXSymbol(product, client=client, frequency=frequency)
    dataframe = pd.DataFrame(symbol.fetch_data(datetime.utcnow() - timedelta(hours=1), count=100))
    res_bro = ResistanceBreakOutBitMEX(dataframe, symbol, websocket)
    res_bro.weighted = False
    res_bro.rolling_period = 10
    res_bro.min_profit = 13.5
    res_bro.setup()
    res_bro.time_bound_run(60 * 60 * 24 * 3)
