import pandas as pd

########## MT5 imports ############

import time
import MetaTrader5 as mt5

from telethon import TelegramClient, events


def wait_for_signal():
    global p
    while True:
        f.seek(p)
        latest_data = f.read()
        p = f.tell()
        if latest_data:
            yield latest_data.rstrip()


# we show the data about the MetaTrader5 package
print("MetaTrader5 package author: ", mt5.__author__)
print("MetaTrader5 package version: ", mt5.__version__)

# We establish the connection with the MetaTrader 5 terminal

if not mt5.initialize('C:\\Program Files\\XMTrading MT5\\terminal64.exe'):
    print("initialize() failed, error code =", mt5.last_error())
    quit()

# We connect with the account indicating the password and the server (it is better to have it entered before in mt5)
account_info = mt5.account_info()
if account_info is not None:
    account_info_dict = mt5.account_info()._asdict()

    # We transform the dictionary into a DataFrame and print it
    df = pd.DataFrame(list(account_info_dict.items()), columns=['property', 'value'])
    print("account_info() as dataframe:")
    print(df)

###################################################################

test_channel = -1001504705915 # Test Channel
telepython_vip_channel = -1001302154811 # TelepythonFX VIP channel
number_of_tp = 1
lot = 0.01

filename = "C:\\Users\\Administrator\\Documents\\TelepythonFX\\telegram_dump.txt"
f = open(filename)
p = 0
f.seek(p)
f.read()
p = f.tell()
print('\n Waiting for a signal')
for line in wait_for_signal():
    try:
        signal = dict(eval(line))
    except Exception as e:
        print("Error when parsing signal line from file:")
        print(e)
        continue

    if signal["ChannelId"] != telepython_vip_channel:
        print("Message is for a different channel: {}".format(signal["ChannelId"]))
        continue

    symbol = signal["Symbol"]
    if symbol == "XAUUSD":
        symbol = "GOLD"

    side = signal["Side"]
    stop_loss = signal["StopLoss"]

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(symbol, "not found, can not call order_check()")
        mt5.shutdown()
        quit()

    # if the symbol is not available in MarketWatch, we add it
    if not symbol_info.visible:
        print(symbol, "is not visible, trying to switch on")
        if not mt5.symbol_select(symbol, True):
            print("symbol_select({}}) failed, exit", symbol)
            mt5.shutdown()
            quit()

    point = mt5.symbol_info(symbol).point

    deviation = 20
    if side == 'BUY':
        op_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).ask
    else:
        op_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).bid

    # Check for existing orders for the symbol with same side
    symbol_orders = mt5.positions_get(symbol=symbol)
    if symbol_orders is not None:
        if any(p.type == op_type for p in symbol_orders):
            print("Order already exists for symbol {} with same side".format(symbol))
            continue

    tpList = signal["TakeProfits"][:number_of_tp]
    for take_profit in tpList:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": 0.01,
            "type": op_type,
            "price": price,
            "sl": float(stop_loss),
            "tp": float(take_profit),
            "deviation": deviation,
            "magic": 234000,
            "comment": "TP:{}".format(tpList[0]),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # we send the commercial request
        result = mt5.order_send(request)
        # we check the result of the execution
        print("R. order_send(): by {} {} lots at {} with deviation={} points and TP = {} ".format(symbol, lot, price,
                                                                                                  deviation, take_profit))
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print("2. order_send failed, retcode={}".format(result.retcode))
            # we request the result in the form of a dictionary and display it element by element
            result_dict = result._asdict()
            for field in result_dict.keys():
                print("   {}={}".format(field, result_dict[field]))
                # if it is the structure of a commercial request, we also show it element by element
                if field == "request":
                    traderequest_dict = result_dict[field]._asdict()
                    for tradereq_filed in traderequest_dict:
                        print("       traderequest: {}={}".format(tradereq_filed, traderequest_dict[tradereq_filed]))
    print('\n Waiting for a signal')
