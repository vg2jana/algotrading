import logging
import time


class Order:

    def __init__(self, user):

        self.logging = logging.getLogger()
        self.ws = user.ws
        self.client = user.client
        self.orderID = None
        self.orderQty = None
        self.orderType = None
        self.side = None
        self.price = None
        self.execInst = None
        self.ordStatus = None
        self.text = None
        self.timestamp = None
        self.execType = None
        self.cumQty = None
        self.workingIndicator = None
        self.parent_order = user.parent_order
        self.wait = True

    def get_status(self):

        data = self.ws.ws.data['execution']
        executions = [o for o in data if o['orderID'] == self.orderID]

        if len(executions) < 1:
            return

        for k, v in executions[-1].items():
            if hasattr(self, k):
                setattr(self, k, v)

    def wait_for_status(self, *status):

        while True:
            self.get_status()
            if self.ordStatus in status:
                break
            if self.wait is False:
                break

    def new(self, **kwargs):
        order = self.client.new_order(**kwargs)

        if order is None:
            return None

        self.orderID = order['orderID']
        self.wait_for_status('New', 'Filled', 'PartiallyFilled', 'Canceled')
        self.logging.info("New order => OrderID: {}, Qty: {}, Price: {}, Side: {}, Status: {}".format(self.orderID,
                                                                                                      self.orderQty,
                                                                                                      self.price,
                                                                                                      self.side,
                                                                                                      self.ordStatus))

        return order

    def amend(self, **kwargs):

        order = self.client.amend_order(**kwargs)

        if order is None:
            return None

        self.wait_for_status('New', 'Filled', 'PartiallyFilled', 'Canceled')
        self.logging.info("Amend order => OrderID: {}, Qty: {}, Price: {}, Side: {}, Status: {}".format(self.orderID,
                                                                                                        self.orderQty,
                                                                                                        self.price,
                                                                                                        self.side,
                                                                                                        self.ordStatus))

        return order

    def cancel(self):

        order = self.client.cancel_order(orderID=self.orderID)

        if order is None:
            return None

        self.wait_for_status('Filled', 'PartiallyFilled', 'Canceled')
        self.logging.info("Cancel order => OrderID: {}, Qty: {}, Price: {}, Side: {}, Status: {}".format(self.orderID,
                                                                                                         self.orderQty,
                                                                                                         self.price,
                                                                                                         self.side,
                                                                                                         self.ordStatus))

        return order
