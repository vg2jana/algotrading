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
vip_channel = -1001302154811 # TelepythonFX VIP channel
chatList = [test_channel,]# vip_channel]

outFile = "C:\\Users\\Administrator\\Documents\\TelepythonFX\\telegram_dump.txt"


print('\n Waiting for a signal')

@client.on(events.NewMessage(chats=chatList))
async def newMessageListener(event):
    chatId = event.chat_id
    newMessage = event.message.message
    print(newMessage)

    messageList = newMessage.split()
    #pdb.set_trace()
    try:
        if 'SELL' in messageList[1]:
            messageList[1] = 'SELL'
        elif 'BUY' in messageList[1]:
            messageList[1] = 'BUY'
        else:
            return print("The message is not a signal \nWaiting for a signal")
    except:
        return print("The message is not a signal \nWaiting for a signal")
    
    if 'GOLD' in messageList[0]: #Some Brokers use GOLD instead of XAUUSD, if not your case, comment this line
        messageList[0] = 'XAUUSD'
    else:
        messageList[0] = messageList[0][1:]

    ########################################
    symbol = messageList[0]
    side = messageList[1]
    stopLoss = float(messageList[10])
    TP1 = float(messageList[4])
    TP2 = 0
    TP3 = 0
    try:
        TP2 = float(messageList[6]) #some signals dont provide tp2
    except:
        pass
    try:
        TP3 = float(messageList[8]) #same but for tp3
    except:
        pass

    dictMessage = {
            "ChannelId": chatId,
            "Symbol": symbol,
            "Side": side,
            "StopLoss": stopLoss,
            "TP1": TP1,
            "TP2": TP2,
            "TP3": TP3
        }

    with open(outFile, 'a') as f:
        f.write("{}\n".format(dictMessage))

    print('\n Waiting for a signal')

with client:
    client.run_until_disconnected()
