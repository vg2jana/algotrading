//+------------------------------------------------------------------+
//|                                                CloseOnEquity.mq4 |
//|                        Copyright 2022, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2022, MetaQuotes Software Corp."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict

input double MAX_LOT = 0.1;   // Max Lot (Closes when lot size is higher than this value)

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
      bool trigger = False;
      
      for(int x=OrdersTotal()-1;x>=0;x--)
      {
         if(!OrderSelect(x,SELECT_BY_POS,MODE_TRADES)) continue;
         if(OrderMagicNumber() == 1111111) continue;
         if(OrderType()==OP_BUY || OrderType()==OP_SELL)
           {
            if(OrderLots() > MAX_LOT) {
                CloseGoldPositions();
                Sleep(1000);
                break;
            }
           }
      }   
  }
//+------------------------------------------------------------------+

void CloseForexPositions()
{
   for(int x=OrdersTotal()-1;x>=0;x--)
   {
      if(!OrderSelect(x,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderMagicNumber() == 1111111) continue;
      if((OrderType()==OP_BUY || OrderType()==OP_SELL) && (OrderSymbol() != "XAUUSDb"))
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
      if(OrderMagicNumber() == 1111111) continue;
      if((OrderType()==OP_BUY || OrderType()==OP_SELL) && (OrderSymbol() == "XAUUSDb"))
      {
         if(!OrderClose(OrderTicket(),OrderLots(),OrderClosePrice(),3,clrRed)){
            Print(GetLastError());
         }
      }
   }
   Print("GOLD Close complete.");
}
