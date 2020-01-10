import time
import websocket
import logging
from exchanges.BitMEX.bitmex_websocket import BitMEXWebsocket


class MyWebSocket:

    def __init__(self, endpoint, symbol, key, secret, ws=None):

        self.endpoint = endpoint
        self.symbol = symbol
        self.key = key
        self.secret = secret
        self.logger = logging.getLogger()
        self.last_ltp = None
        self.last_ltp_timestamp = None

    def connect_ws(self):
        while True:
            self.logger.info('Attempting to connect WS')
            try:
                self.ws = BitMEXWebsocket(endpoint=self.endpoint, symbol=self.symbol,
                                          api_key=self.key, api_secret=self.secret)
                self.ws.get_instrument()
                break
            except Exception as e:
                self.logger.warning(e)
            time.sleep(1)
        self.logger.info('Connected to WS')

    def try_ping(self):

        try:
            if self.ws.ws.sock is None:
                self.connect_ws()
            self.ws.ws.sock.ping()
        except websocket.WebSocketConnectionClosedException as e:
            self.logger.warning(e)
            self.connect_ws()
        except Exception as e:
            self.logger.warning(e)
            self.connect_ws()

    def depth_info(self):
        self.try_ping()
        try:
            return self.ws.market_depth()
        except Exception as e:
            self.logger.warning("Error fetching market depth")
            self.logger.warning(e)

        return None

    def ticker(self):
        self.try_ping()
        try:
            return self.ws.get_ticker()
        except Exception as e:
            self.logger.warning("Error fetching ticker")
            self.logger.warning(e)

        return None

    def open_orders(self):
        self.try_ping()
        try:
            return self.ws.open_orders('')
        except Exception as e:
            self.logger.warning("Error fetching Open orders")
            self.logger.warning(e)

        return None

    def ltp(self):
        ltp = None

        while ltp is None:
            ticker = self.ticker()
            if ticker is not None and abs(ticker['last'] - ticker['mark']) < 500:
                ltp = ticker['last']

        # Restart websocket if ltp not updated for few minutes
        # if ltp != self.last_ltp:
        #     self.last_ltp = ltp
        #     self.last_ltp_timestamp = datetime.now()
        # elif self.last_ltp_timestamp is not None:
        #     time_diff = datetime.now() - self.last_ltp_timestamp
        #     if time_diff.total_seconds() > 180:
        #         self.logger.warning('LTP not updated for a long time')
        #         self.restart()

        return ltp

    def bid_ask(self):
        retval = None

        while retval is None:
            depth = self.depth_info()

            bids = [x for x in depth[0]['bids']]
            asks = [x for x in depth[0]['asks']]
            bid_prices, bid_volumes = list(zip(*bids))
            ask_prices, ask_volumes = list(zip(*asks))

            retval = {
                        "bid": {
                            "price": bid_prices,
                            "volume": bid_volumes
                        },
                        "ask": {
                            "price": ask_prices,
                            "volume": ask_volumes
                        }
            }

        return retval

    def clear_executions(self):
        self.ws.data['execution'].clear()

    def get_position(self):
        self.try_ping()
        for p in self.ws.data['position']:
            if p['isOpen'] is True and p.get('avgEntryPrice', None) is not None and p['symbol'] == self.symbol:
                return p
        return None

    def restart(self):
        self.ws.exit()
        time.sleep(5)
        self.connect_ws()
