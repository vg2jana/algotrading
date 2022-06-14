import pandas as pd


####Telegram imports############

import configparser
import json
import re
import asyncio
import pdb

from telethon.errors import SessionPasswordNeededError
from telethon import TelegramClient, events
from telethon.tl.functions.messages import (GetHistoryRequest)
from telethon.tl.types import (
PeerChannel
)

api_id = 14155598 #int value
api_hash = '0a4c62b754438db563008a67f2197ec7'       #string value

client = TelegramClient('anon', api_id, api_hash)

test_channel = -1001504705915 # Test Channel
telepython_vip_channel = -1001302154811 # TelepythonFX VIP channel
chatList = [telepython_vip_channel, test_channel]

outFile = "C:\\Users\\Administrator\\Documents\\TelepythonFX\\telegram_dump.txt"
# outFile = "telegram_dump.txt"

print('\n Waiting for a signal')


class Signal:
    def __init__(self):
        self.chat_id = None
        self.symbol = None
        self.side = None
        self.stop_loss = None
        self.take_profits = []
        self.error = False

    def message(self):
        dict_message = {
            "ChannelId": self.chat_id,
            "Symbol": self.symbol,
            "Side": self.side,
            "StopLoss": self.stop_loss,
            "TakeProfits": self.take_profits
        }

        return dict_message


def telepythonFX_VIP(messageList):
    signal = Signal()
    try:
        if 'SELL' in messageList[1]:
            messageList[1] = 'SELL'
        elif 'BUY' in messageList[1]:
            messageList[1] = 'BUY'
        else:
            signal.error = True
            return print("The message is not a signal \nWaiting for a signal")
    except:
        signal.error = True
        return print("The message is not a signal \nWaiting for a signal")

    if 'GOLD' in messageList[0]:
        messageList[0] = 'XAUUSD'
    else:
        messageList[0] = messageList[0][1:]

    signal.symbol = messageList[0]
    signal.side = messageList[1]
    signal.stop_loss = messageList[10]
    signal.take_profits.append(messageList[4])
    try:
        signal.take_profits.append((messageList[6]))
    except:
        pass
    try:
        signal.take_profits.append((messageList[8]))
    except:
        pass

    return signal


def blackswan_fx(messageList):
    signal = Signal()
    messageList = [m.replace(" ", "") for m in messageList]
    try:
        if messageList[1] != 'INSTANT':
            signal.error = True
            return print("The message is not a signal \nWaiting for a signal")
        if 'SELL' in messageList[2]:
            messageList[1] = 'SELL'
        elif 'BUY' in messageList[2]:
            messageList[1] = 'BUY'
        else:
            signal.error = True
            return print("The message is not a signal \nWaiting for a signal")
    except:
        signal.error = True
        return print("The message is not a signal \nWaiting for a signal")

    messageList[0] = messageList[0].replace("/", "")
    if 'GOLD' in messageList[0]:
        messageList[0] = 'XAUUSD'
    else:
        messageList[0] = messageList[0][1:]

    signal.symbol = messageList[0]
    signal.side = messageList[2]

    try:
        for index, m in enumerate(messageList):
            if m == "TP:" and messageList[index+1] != 'OPEN':
                signal.take_profits.append(messageList[index+1])
            elif m == "SL:":
                signal.stop_loss = messageList[index+1]
    except Exception as e:
        signal.error = True
        return print(e)

    return signal


@client.on(events.NewMessage(chats=chatList))
async def newMessageListener(event):
    chatId = event.chat_id
    newMessage = event.message.message
    print(newMessage)

    telegram_message = newMessage.split()

    retval = None
    if chatId == telepython_vip_channel:
        retval = telepythonFX_VIP(telegram_message)
    elif chatId == test_channel:
        retval = blackswan_fx(telegram_message)

    if retval is None or retval.error is True:
        return

    retval.chat_id = chatId
    dump_message = retval.message()
    print("Dumping to file: {}".format(dump_message))
    with open(outFile, 'a') as f:
        f.write("{}\n".format(dump_message))

    print('\n Waiting for a signal')

with client:
    client.run_until_disconnected()
