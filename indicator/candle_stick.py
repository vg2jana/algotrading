

def three_candle_curve(dataframe):
    # Get the last 3 series
    df = dataframe[-3:].copy()
    df['Diff High'] = df.High.diff().gt(0)
    df['Diff Low'] = df.Low.diff().gt(0)
    df['Color'] = df['Adj Close'] > df['Open']
    pattern_high = (df['Diff High'][-2:] == (False, True)).all()
    pattern_low = (df['Diff Low'][-2:] == (False, True)).all()
    pattern_color = (df['Color'] == (False, True, True)).all() or (df['Color'] == (False, False, True)).all()

    if pattern_high == True and pattern_low == True and pattern_color == True:
        return True

    return False
