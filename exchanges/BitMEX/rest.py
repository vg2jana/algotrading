import bitmex
import logging
import time


class RestClient:

    def __init__(self, test, key, secret, symbol):
        self.api = None
        self.symbol = symbol
        self.test = test
        self.key = key
        self.secret = secret
        self.logger = logging.getLogger()
        self.connect_api()

    def connect_api(self):
        while True:
            self.logger.info('Attempting to connect to REST Client')
            try:
                self.api = bitmex.bitmex(test=self.test, api_key=self.key, api_secret=self.secret)
                break
            except Exception as e:
                self.logger.warning(e)
            time.sleep(1)
        self.logger.info('Connected to REST Client')

    def new_order(self, **kwargs):

        kwargs['symbol'] = self.symbol
        order = None

        try:
            order, response = self.api.Order.Order_new(**kwargs).result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to place order with params: {}".format(kwargs))
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to place order with params: {}".format(kwargs))
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                self.logger.warning("Order: {}".format(order))
                order = None

        return order

    def amend_order(self, **kwargs):

        order = None

        try:
            order, response = self.api.Order.Order_amend(**kwargs).result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to amend order with params: {}".format(kwargs))
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to amend order with params: {}".format(kwargs))
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                self.logger.warning("Order: {}".format(order))
                order = None

        return order

    def cancel_order(self, **kwargs):

        order = None

        try:
            order, response = self.api.Order.Order_cancel(**kwargs).result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to cancel order with params: {}".format(kwargs))
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to cancel order with params: {}".format(kwargs))
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                self.logger.warning ("Order: {}".format(order))
                order = None

        if order is not None:
            order = order[0]

        return order

    def cancel_all(self):

        orders = None

        try:
            orders, response = self.api.Order.Order_cancelAll().result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to cancel all orders")
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to cancel all orders")
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                orders = None

        return orders

    def get_order(self, **kwargs):

        order = None

        try:
            order, response = self.api.Order.Order_getOrders(**kwargs).result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to get order with params: {}".format(kwargs))
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to get order with params: {}".format(kwargs))
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                self.logger.warning ("Order: {}".format(order))
                order = None

        if order is not None and len(order) > 0:
            order = order[0]

        return order

    def open_orders(self):

        orders = None

        try:
            orders, response = self.api.Order.Order_getOrders(filter='{"open": true}').result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to fetch open orders")
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to fetch open orders")
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                orders = None

        return orders

    def funding_rate(self):

        rate = None

        try:
            rate, response = self.api.Funding.Funding_get(reverse=True, symbol=self.symbol, count=1).result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to get funding rate")
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to get order with params")
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                self.logger.warning("Funding rate: {}".format(rate))
                rate = None

        if rate is not None and len(rate) > 0:
            rate = rate[0]

        return rate

    def trade_bucket(self, **kwargs):

        kwargs['symbol'] = self.symbol
        result = None

        try:
            result, response = self.api.Trade.Trade_getBucketed(**kwargs).result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to get trade bucket with params: {}".format(kwargs))
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to get trade bucket with params: {}".format(kwargs))
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                self.logger.warning("Result: {}".format(result))
                result = None

        return result

    def open_position(self):

        position = None

        try:
            position, response = self.api.Position.Position_get(filter='{"symbol": "%s"}' % self.symbol).result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to fetch open position")
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to fetch open position")
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                position = None

        if position is not None and len(position) > 0:
            position = position[0]

        return position

    def bid_ask_0(self):

        book = None

        try:
            book, response = self.api.OrderBook.OrderBook_getL2(symbol=self.symbol, depth=1).result()
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("Failed to fetch order book L2")
            time.sleep(2)
        else:
            if response.status_code != 200:
                self.logger.warning("Failed to fetch order book L2")
                self.logger.warning("Status code: {}, Reason: {}".format(response.status_code, response.reason))
                book = None

        if book is None:
            return None

        ask = 9999999
        bid = 1
        for d in book:
            if d['side'] == 'Sell':
                ask = d['price']
            else:
                bid = d['price']

        return {'bid': bid, 'ask': ask}
