//+------------------------------------------------------------------+
//|                                                CloseOnEquity.mq4 |
//|                        Copyright 2022, MetaQuotes Software Corp. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2022, MetaQuotes Software Corp."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict

enum ENUM_RISK_TYPE {
Percent,
Money
};

input ENUM_RISK_TYPE RiskType = Money;  // Act on Risk Type
input double PercentValue = -5;           // Percent value (Negative value means close on Loss)
input double MoneyValue = 100;              // Money value (Negative value means close on Loss)

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
      
      if (RiskType == 0)
      {
         if(PercentValue < 0 && AccountEquity() <= AccountBalance() + (PercentValue * AccountBalance() / 100))
         {
            Print("Close triggered for negative Percent value");
            trigger = True;
         }
         else if(PercentValue > 0 && AccountEquity() >= AccountBalance() + (PercentValue * AccountBalance() / 100))
         {
            Print("Close triggered for positive Percent value");
            trigger = True;
         }
      }
      else
      {
         if(MoneyValue < 0 && AccountEquity() <= AccountBalance() + MoneyValue)
         {
            Print("Close triggered for negative Money value");
            trigger = True;
         }
         else if(MoneyValue > 0 && AccountEquity() >= AccountBalance() + MoneyValue)
         {
            Print("Close triggered for positive Money value");
            trigger = True;
         }
      }
      
      if(trigger == True)
      {
         CloseOpenPositions();
         Sleep(10000);
         START_BALANCE = AccountBalance();
      }
   
  }
//+------------------------------------------------------------------+

void CloseOpenPositions()
{
   for(int x=OrdersTotal()-1;x>=0;x--)
   {
      if(!OrderSelect(x,SELECT_BY_POS,MODE_TRADES)) continue;
      if(OrderType()==OP_BUY || OrderType()==OP_SELL)
      {
         if(!OrderClose(OrderTicket(),OrderLots(),OrderClosePrice(),3,clrRed)){
            Print(GetLastError());
         }
      }
   }
   Print("Close complete.");
}
