//+------------------------------------------------------------------+
//|                                                CloseOnEquity.mq4 |
//|                        Copyright 2022, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2022, MetaQuotes Software Corp."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict

input double GoldValue = -200;   // Gold value (Negative value means close on Loss)
input double ForexValue = -100;  // Forex value (Negative value means close on Loss)

double START_BALANCE;
//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//---
    START_BALANCE = AccountBalance();
//---
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
//---
   
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
      START_BALANCE = AccountBalance();
      bool trigger = False;
      double ForexProfit = 0;
      double GoldProfit = 0;
      
      for(int x=OrdersTotal()-1;x>=0;x--)
      {
         if(!OrderSelect(x,SELECT_BY_POS,MODE_TRADES)) continue;
         if(OrderType()==OP_BUY || OrderType()==OP_SELL)
           {
            if(OrderSymbol() == "XAUUSD")
              {
               GoldProfit += OrderProfit();
              }
            else
              {
               ForexProfit += OrderProfit();
              }
           }
        }
      
      if(GoldProfit <= GoldValue)
        {
         CloseGoldPositions();
         Sleep(1000);
        }
      
      if(ForexProfit <= ForexValue)
        {
         CloseForexPositions();
         Sleep(2000);
        }
   
  }
//+------------------------------------------------------------------+

void CloseForexPositions()
{
   for(int x=OrdersTotal()-1;x>=0;x--)
   {
      if(!OrderSelect(x,SELECT_BY_POS,MODE_TRADES)) continue;
      if((OrderType()==OP_BUY || OrderType()==OP_SELL) && (OrderSymbol() != "XAUUSD"))
      {
         if(!OrderClose(OrderTicket(),OrderLots(),OrderClosePrice(),3,clrRed)){
            Print(GetLastError());
         }
      }
   }
   Print("FOREX Close complete.");
}

void CloseGoldPositions()
{
   for(int x=OrdersTotal()-1;x>=0;x--)
   {
      if(!OrderSelect(x,SELECT_BY_POS,MODE_TRADES)) continue;
      if((OrderType()==OP_BUY || OrderType()==OP_SELL) && (OrderSymbol() == "XAUUSD"))
      {
         if(!OrderClose(OrderTicket(),OrderLots(),OrderClosePrice(),3,clrRed)){
            Print(GetLastError());
         }
      }
   }
   Print("GOLD Close complete.");
}
