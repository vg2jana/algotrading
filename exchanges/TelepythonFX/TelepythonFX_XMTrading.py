import pandas as pd


########## MT5 imports ############

import time
import MetaTrader5 as mt5


#### Operations parameters ##########

lot = float(input('Input lot size: '))
N_TP=float(input ('Numbers of TP? ')) #entre 1,2,3 (Number of tp that do you want to operate)
SIN_SL=False
sufix=input('Input sufix')




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

#----------------------------------------------------------------------------------------------------------------------------------

print("""\n /$$$$$$$$      /$$         /$$$$$$$            /$$    /$$                               /$$$$$$$$/$$   /$$        /$$$$$$  /$$$$$$ /$$$$$$$ /$$$$$$/$$$$$$$$/$$$$$$$ 
|__  $$__/     | $$        | $$__  $$          | $$   | $$                              | $$_____| $$  / $$       /$$__  $$/$$__  $| $$__  $|_  $$_| $$_____| $$__  $$
   | $$ /$$$$$$| $$ /$$$$$$| $$  \ $$/$$   /$$/$$$$$$ | $$$$$$$  /$$$$$$ /$$$$$$$       | $$     |  $$/ $$/      | $$  \__| $$  \ $| $$  \ $$ | $$ | $$     | $$  \ $$
   | $$/$$__  $| $$/$$__  $| $$$$$$$| $$  | $|_  $$_/ | $$__  $$/$$__  $| $$__  $$      | $$$$$   \  $$$$/       | $$     | $$  | $| $$$$$$$/ | $$ | $$$$$  | $$$$$$$/
   | $| $$$$$$$| $| $$$$$$$| $$____/| $$  | $$ | $$   | $$  \ $| $$  \ $| $$  \ $$      | $$__/    >$$  $$       | $$     | $$  | $| $$____/  | $$ | $$__/  | $$__  $$
   | $| $$_____| $| $$_____| $$     | $$  | $$ | $$ /$| $$  | $| $$  | $| $$  | $$      | $$      /$$/\  $$      | $$    $| $$  | $| $$       | $$ | $$     | $$  \ $$
   | $|  $$$$$$| $|  $$$$$$| $$     |  $$$$$$$ |  $$$$| $$  | $|  $$$$$$| $$  | $$      | $$     | $$  \ $$      |  $$$$$$|  $$$$$$| $$      /$$$$$| $$$$$$$| $$  | $$
   |__/\_______|__/\_______|__/      \____  $$  \___/ |__/  |__/\______/|__/  |__/      |__/     |__/  |__/       \______/ \______/|__/     |______|________|__/  |__/
                                     /$$  | $$                                                                                                                        
                                    |  $$$$$$/                                                                                                                        
                                     \______/                                                                                                                         """)





print("""\n 

.     .       .  .   . .   .   . .    +  .
  .     .  :     .    .. :. .___---------___.
       .  .   .    .  :.:. _".^ .^ ^.  '.. :"-_. .
    .  :       .  .  .:../:            . .^  :.:\.
        .   . :: +. :.:/: .   .    .        . . .:\
 .  :    .     . _ :::/:               .  ^ .  . .:\
  .. . .   . - : :.:./.                        .  .:\
  .      .     . :..|:                    .  .  ^. .:|
    .       . : : ..||        .                . . !:|
  .     . . . ::. ::\(                           . :)/
 .   .     : . : .:.|. ######              .#######::|
  :.. .  :-  : .:  ::|.#######           ..########:|
 .  .  .  ..  .  .. :\ ########          :######## :/
  .        .+ :: : -.:\ ########       . ########.:/
    .  .+   . . . . :.:\. #######       #######..:/
      :: . . . . ::.:..:.\           .   .   ..:/
   .   .   .  .. :  -::::.\.       | |     . .:/
      .  :  .  .  .-:.":.::.\             ..:/
 .      -.   . . . .: .:::.:.\.           .:/
.   .   .  :      : ....::_:..:\   ___.  :/
   .   .  .   .:. .. .  .: :.:.:\       :/
     +   .   .   : . ::. :.:. .:.|\  .:/|
     .         +   .  .  ...:: ..|  --.:|
.      . . .   .  .  . ... :..:.."(  ..)"
 .   .       .      :  .   .: ::/  .  .::\

                  by @MRAMIREZ

""")

#-------------------------------------------------------------------------------------------------------------------------------
 

#####################################################################

# we show the data about the MetaTrader5 package

print("MetaTrader5 package author: ", mt5.__author__)
print("MetaTrader5 package version: ", mt5.__version__)
 
# We establish the connection with the MetaTrader 5 terminal

if not mt5.initialize('C:\\Program Files\\XMTrading MT5\\terminal64.exe'): #changue this for the path of your mt5
    print("initialize() failed, error code =",mt5.last_error())
    quit()


 
# We connect with the account indicating the password and the server (it is better to have it entered before in mt5)

account_info=mt5.account_info()
if account_info!=None:
     # we show the account data
     #print(account_info)
     # we display the data about the trading account in the form of a dictionary
     #print("Show account_info()._asdict():") #I comment because is not necessary see it again
     account_info_dict = mt5.account_info()._asdict()
     #for prop in account_info_dict:
         #print("  {}={}".format(prop, account_info_dict[prop]))
     #print()
 
     # We transform the dictionary into a DataFrame and print it
     df=pd.DataFrame(list(account_info_dict.items()),columns=['property','value'])
     print("account_info() as dataframe:")
     print(df)





###################################################################


# We connect with our telegram account

# Remember to use your own values from my.telegram.org!
api_id = 14155598 #int value
api_hash = '0a4c62b754438db563008a67f2197ec7'       #string value

client = TelegramClient('anon', api_id, api_hash)

#canal = -1001504705915 # Test channel
canal= -1001302154811 #example  # to connect with vip signal channel (is the channel ID)


print('\n Waiting for a signal')

@client.on(events.NewMessage(chats=canal))


################################################################################

# This function is the one that listens for new messages

async def newMessageListener(event):
    # Get message text
    print('------------------------------------------------------------NUEVA ORDEN--------------------------------------------------------------')
    newMessage = event.message.message
    print(newMessage)

    lista_operacion=newMessage.split()
    #pdb.set_trace()
    try:
        if 'SELL' in lista_operacion[1]:
            lista_operacion[1] = 'SELL'
        elif 'BUY' in lista_operacion[1]:
            lista_operacion[1] = 'BUY'
        else:
            return print("The message is not a signal \nWaiting for a signal")
    except:
        return print("The message is not a signal \nWaiting for a signal")
    
    if 'GOLD' in lista_operacion[0]: #Some Brokers use GOLD instead of XAUUSD, if not your case, comment this line
        lista_operacion[0]='GOLD'
    else:
        lista_operacion[0]=lista_operacion[0][1:]

    ########################################
    par=lista_operacion[0]+sufix
    op=lista_operacion[1]
    #entrada=float(lista_operacion[2])
    SL=float(lista_operacion[10])
    TP1=float(lista_operacion[4])
    try:
        TP2=float(lista_operacion[6]) #some signals dont provide tp2
    except:
        TP2='--'
    try:
        TP3=float(lista_operacion[8]) #same but for tp3
    except:
        TP3='--'

    print(newMessage.split())
    ########################################
    
    #Now we are going to pull the trade to MT5
    # we prepare the structure of the purchase requestpreparamos la estructura de la solicitud de compra
    symbol = par
    symbol_info = mt5.symbol_info(symbol)
    #print(symbol_info)
    if symbol_info is None:
            print(symbol, "not found, can not call order_check()")
            mt5.shutdown()
            quit()
 
    # if the symbol is not available in MarketWatch, we add it
    if not symbol_info.visible:
            print(symbol, "is not visible, trying to switch on")
            if not mt5.symbol_select(symbol,True):
                print("symbol_select({}}) failed, exit",symbol)
                mt5.shutdown()
                quit()

    
    point = mt5.symbol_info(symbol).point
    
    deviation = 20
    if op=='BUY':
        op_type=mt5.ORDER_TYPE_BUY
        price= mt5.symbol_info_tick(symbol).ask
        opposite_op_type=mt5.ORDER_TYPE_SELL
    if op=='SELL':
        op_type=mt5.ORDER_TYPE_SELL
        price= mt5.symbol_info_tick(symbol).bid
        opposite_op_type=mt5.ORDER_TYPE_BUY

    TP_list=[TP1,TP2,TP3]

    #print(mt5.ORDER_FILLING_RETURN)

    TP_cont=1
    for TP in TP_list:
        if TP_cont>N_TP:
            break
        if TP_cont==1: # we put SL only to the first TP (if you want to put them all, just add them here TP_cont ==2 and TP_cont==3)
            request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot,
                    "type": op_type,
                    "price": price,
                    "sl": SL,
                    "tp": TP,
                    "deviation": deviation,
                    "magic": 234000,
                    "comment": "TelePython FX copier",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
        if TP_cont!=1: #change this if you want to put SL to the different position 
            request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot,
                    "type": opposite_op_type,
                    "price": price,
                    "sl": TP,
                    "deviation": deviation,
                    "magic": 234001,
                    "comment": "TelePython FX copier",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }

        # we send the commercial request

        result = mt5.order_send(request)
        # we check the result of the execution
        print("R. order_send(): by {} {} lots at {} with deviation={} points and TP = {} ".format(symbol,lot,price,deviation,TP) );
        if result.retcode != mt5.TRADE_RETCODE_DONE:
                print("2. order_send failed, retcode={}".format(result.retcode))
             # we request the result in the form of a dictionary and display it element by element
                result_dict=result._asdict()
                for field in result_dict.keys():
                    print("   {}={}".format(field,result_dict[field]))
                    # if it is the structure of a commercial request, we also show it element by element
                    if field=="request":
                            traderequest_dict=result_dict[field]._asdict()
                            for tradereq_filed in traderequest_dict:
                                print("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))
                #print("shutdown() and quit")
                #mt5.shutdown()
                #quit()
 
        #print("2. order_send done, ", result)
        
        TP_cont=TP_cont+1

    print('\n Waiting for a signal')

with client:
    client.run_until_disconnected()
