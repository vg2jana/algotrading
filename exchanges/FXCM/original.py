import fxcmpy
import time

#initiating API connection and defining trade parameters
con = fxcmpy.fxcmpy(access_token="24fc9c161bf5887dab9ef3f1e7d44e31e9f92939", log_level='error', server='demo')
pair = 'EUR/USD'


#get historical data
# data = con.get_candles(pair, period='m5', number=250)
"""periods can be m1, m5, m15 and m30, H1, H2, H3, H4, H6 and H8, D1, W1, M1"""

#streaming data
"for streaming data, we first need to subscribe to a currency pair"
con.subscribe_market_data('EUR/USD')
last_price = con.get_last_price('EUR/USD')
price_info = con.get_prices('EUR/USD')
con.unsubscribe_market_data('EUR/USD')

#trading account data
accounts = con.get_accounts()

order = con.create_market_buy_order('EUR/USD', 1)

open_positions = con.get_open_positions()
open_summary = con.get_open_positions_summary()

closed_positions = con.get_closed_positions()

orders = con.get_orders()

#orders
# con.create_market_buy_order('EUR/USD', 1)
# con.create_market_buy_order('USD/CAD', 10)
# con.create_market_sell_order('USD/CAD', 20)
# con.create_market_sell_order('EUR/USD', 10)
#
# order = con.open_trade(symbol='USD/CAD', is_buy=False,
#                        is_in_pips=True,
#                        amount=10, time_in_force='GTC',
#                        stop=-9, trailing_step =True,
#                        order_type='AtMarket', limit=9)
#
# con.close_trade(trade_id=tradeId, amount=1000)
# con.close_all_for_symbol('USD/CAD')

#closing connection
con.close()