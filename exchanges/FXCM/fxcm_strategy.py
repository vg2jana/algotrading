import random
import math
import json
import fxcmpy
import os
import sys
import time
import logging


def connect():
    global con
    global log
    while True:
        try:
            if con is not None:
                log.info("Closing existing connection")
                con.close()
                time.sleep(10)
            print("Connecting to FXCM...")
            con = fxcmpy.fxcmpy(access_token=data['global']['token'], log_level='info', server='demo', log_file='fxcm_api.log')
            log = logging.getLogger('FXCM')
            con.subscribe_data_model('Order')
            con.subscribe_data_model('OpenPosition')
        except Exception as e:
            if hasattr(log, 'info'):
                log.error(e)
            time.sleep(30)
        else:
            break

    return con


def call_api(api, *args):
    while True:
        try:
            if api == 'orders':
                result = con.get_orders()
            elif api == 'summary':
                result = con.get_summary()
            elif api == 'positions':
                result = con.get_open_positions()
            elif api == 'delete':
                result = con.delete_order(*args)
        except Exception as e:
            log.warning("Call API warning: %s" % e)
            try:
                if con.is_connected() is False:
                    connect()
                    time.sleep(10)
            except Exception as e:
                log.warning("Call API reconnect warning: %s" % e)
        else:
            break

    return result


class Symbol:
    def __init__(self, symbol, config):
        self.symbol = symbol
        self.is_subscribed = False
        self.positions = []
        self.orders = []
        self.config = config
        self.prev_pos_count = 0

    def subscribe(self):
        con.subscribe_market_data(self.symbol)

    def close_positions(self):
        close = False
        if self.prev_pos_count != 0 and self.prev_pos_count < len(self.positions):
            close = True

        return close

    def get_summary(self):
        buy_amount = 0
        sell_amount = 0
        buy_price = 0
        sell_price = 0

        buy_pos = self.positions.loc[self.positions['isBuy'] == True]
        sell_pos = self.positions.loc[self.positions['isBuy'] == False]

        if not buy_pos.empty:
            buy_pos.reset_index(inplace=True)
            buy_amount = buy_pos['amountK'].sum().item()
            buy_price = buy_pos.iloc[0]['open'].item()

        if not sell_pos.empty:
            sell_pos.reset_index(inplace=True)
            sell_amount = sell_pos['amountK'].sum().item()
            sell_price = sell_pos.iloc[0]['open'].item()

        summary = {
            'buyAmount': buy_amount * self.config['qtyFactor'],
            'sellAmount': sell_amount * self.config['qtyFactor'],
            'buyPrice': buy_price,
            'sellPrice': sell_price
        }

        if summary['buyAmount'] > summary['sellAmount']:
            isBuy = False
            curr_qty = summary['buyAmount']
            opp_qty = summary['sellAmount']
            price = summary['buyPrice'] - self.config['swing']
        else:
            isBuy = True
            curr_qty = summary['sellAmount']
            opp_qty = summary['buyAmount']
            price = summary['sellPrice'] + self.config['swing']

        losing_sum = curr_qty * (self.config['takeProfit'] + self.config['swing'])
        for n in range(1, 10000):
            gaining_sum = (curr_qty + n) * self.config['takeProfit']
            if gaining_sum - losing_sum > self.config["minProfit"]:
                break

        summary['nextQty'] = (curr_qty + n) - opp_qty
        summary['nextSide'] = isBuy
        summary['nextPrice'] = price

        self.summary = summary
        return summary

    def run(self):
        limit = self.config['takeProfit'] * 10000
        if len(self.positions) == 0 and stop_signal is False:
            isBuy = random.choice([True, False])
            amount = self.config['amount']
            try:
                con.open_trade(self.symbol, isBuy, amount, 'FOK', 'AtMarket', limit=int(limit / 3))
            except Exception as e:
                log.warning("Market order warning: %s" % e)
            time.sleep(2)
        elif len(self.orders) == 0:
            summary = self.get_summary()
            try:
                con.create_entry_order(self.symbol, summary['nextSide'], summary['nextQty'], 'GTC',
                                       rate=summary['nextPrice'], limit=limit)
            except Exception as e:
                log.warning("Entry order warning: %s" % e)
            time.sleep(2)

        if len(self.positions) > 1:
            pos = self.positions.reset_index()
            pos0 = pos.iloc[0].to_dict()
            pos1 = pos.iloc[1].to_dict()
            if pos0['limit'] != pos1['limit']:
                try:
                    con.change_trade_stop_limit(pos0['tradeId'], False, pos1['limit'], is_in_pips=False)
                except Exception as e:
                    log.warning("Position limit change warning: %s" % e)
                time.sleep(2)



class SwingTrading:
    def __init__(self, symbols):
        self.symbols = symbols
        self.open_positions = None

    def before_run(self):
        orders = call_api('orders')
        positions = call_api("positions")

        if positions.empty is True and stop_signal is True:
            con.close()
            sys.exit(0)

        for symbol in self.symbols:
            if not positions.empty:
                symbol.positions = positions.loc[positions['currency'] == symbol.symbol]
            else:
                symbol.positions = []
            if not orders.empty:
                symbol.orders = orders.loc[orders['currency'] == symbol.symbol]
            else:
                symbol.orders = []

    def run(self):
        for symbol in self.symbols:
            symbol.run()
            symbol.prev_pos_count = len(symbol.positions)

    def close(self):
        for symbol in self.symbols:
            if symbol.close_positions() is False:
                continue
            con.close_all_for_symbol(symbol.symbol)
            time.sleep(2)
            for oid in symbol.orders['orderId'].to_list:
                try:
                    call_api('delete', int(oid))
                except Exception as e:
                    log.warning("Close order warning: %s" % e)


con = None
log = None
with open('config.json', 'r') as f:
    data = json.load(f)
connect()

symbols = []
for s, c in data["symbols"].items():
    symbol = Symbol(s, c)
    symbols.append(symbol)

swing = SwingTrading(symbols)
refresh_time = 30
stop_signal = False
while True:
    if os.path.exists('STOP'):
        stop_signal = True
    swing.before_run()
    swing.run()
    swing.close()
    time.sleep(refresh_time)
