import sqlite3
import pandas as pd
import pandas_datareader.data as pdr
import datetime
from indicator.symbol import Symbol


if __name__ == '__main__':
    db = '/Users/jganesan/workspace/algotrading/symbols.sqlite3'
    conn = sqlite3.connect(db)
    symbols = {
                'NIFTY': ["ASIANPAINT.NS", "ADANIPORTS.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS",
                          "BAJFINANCE.NS", "BAJAJFINSV.NS", "BPCL.NS", "BHARTIARTL.NS",
                          "INFRATEL.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS",
                          "GAIL.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HEROMOTOCO.NS",
                          "HINDALCO.NS", "HINDPETRO.NS", "HINDUNILVR.NS", "HDFC.NS", "ITC.NS",
                          "ICICIBANK.NS", "IBULHSGFIN.NS", "IOC.NS", "INDUSINDBK.NS", "INFY.NS",
                          "KOTAKBANK.NS", "LT.NS", "LUPIN.NS", "M&M.NS", "MARUTI.NS", "NTPC.NS",
                          "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBIN.NS", "SUNPHARMA.NS",
                          "TCS.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TECHM.NS", "TITAN.NS",
                          "UPL.NS", "ULTRACEMCO.NS", "VEDL.NS", "WIPRO.NS", "YESBANK.NS", "ZEEL.NS"],

                'AUSTRALIA': ['CGF.AX', 'SUL.AX', 'XRO.AX', 'ABP.AX', 'AGL.AX', 'ALQ.AX', 'AWC.AX', 'AMC.AX', 'AMP.AX',
                              'ANN.AX', 'APA.AX', 'ALL.AX', 'ASX.AX', 'AZJ.AX', 'AST.AX', 'ANZ.AX', 'BOQ.AX', 'BEN.AX',
                              'BKL.AX', 'BSL.AX', 'BXB.AX', 'CTX.AX', 'CAR.AX', 'CIM.AX', 'CCL.AX', 'COH.AX', 'CBA.AX',
                              'CPU.AX', 'CWN.AX', 'CSL.AX', 'CSR.AX', 'DXS.AX', 'DOW.AX', 'FXJ.AX', 'FPH.AX', 'FBU.AX',
                              'FLT.AX', 'FMG.AX', 'CMG.AX', 'GWA.AX', 'HVN.AX', 'ILU.AX', 'IPL.AX', 'IAG.AX', 'IOF.AX',
                              'IFL.AX', 'JHX.AX', 'JHG.AX', 'JBH.AX', 'LLC.AX', 'MQG.AX', 'MPL.AX', 'MTS.AX', 'MIN.AX',
                              'MND.AX', 'NAB.AX', 'NCM.AX', 'OSH.AX', 'ORI.AX', 'ORG.AX', 'OZL.AX', 'PPT.AX', 'PTM.AX',
                              'PRY.AX', 'QAN.AX', 'QBE.AX', 'QUB.AX', 'RHC.AX', 'REA.AX', 'RRL.AX', 'RMD.AX', 'SFR.AX',
                              'STO.AX', 'SCG.AX', 'SEK.AX', 'SVW.AX', 'SGM.AX', 'SHL.AX', 'SPK.AX', 'SGP.AX', 'SUN.AX',
                              'SYD.AX', 'TAH.AX', 'A2M.AX', 'SGR.AX', 'TPM.AX', 'TCL.AX', 'TWE.AX', 'VCX.AX', 'WES.AX',
                              'WBC.AX', 'WPL.AX', 'WOW.AX', 'WOR.AX']
    }

    # for category, symbols in symbols.items():
    #     for symbol in symbols:
    #         print('Fetching data for symbol {}'.format(symbol))
    #         s = Symbol(conn, symbol, frequency='1d', category=category, series_length=252)
    #         data = s.fetch_data()
    #         if data is not None:
    #             s.write_to_db(data)
    s = Symbol(conn, 'XBTUSD', frequency='5m', category=None, series_length=252)
    conn.close()
