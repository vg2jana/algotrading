import pandas as pd
import pandas_datareader.data as pdr
import datetime


class Symbol:

    def __init__(self, symbol, conn=None, frequency=None, category=None, series_length=50):
        self.symbol = symbol
        self.conn = conn
        self.frequency = frequency
        self.category = category
        self.series_length = series_length

    def table_name(self):
        return "{}_{}".format(self.frequency, self.symbol)

    def pandas_url(self):
        if self.category in ('NIFTY', 'AUSTRALIA') and self.frequency == '1d':
            return pdr.get_data_yahoo

    def fetch_pandas(self):
        data = None
        attempt = 0
        method = self.pandas_url()

        while data is None and attempt < 5:
            try:
                data = method(self.symbol, datetime.date.today() - datetime.timedelta(self.series_length), datetime.date.today())
                data.dropna(inplace = True)
            except Exception as e:
                print("Error fetching data for symbol: {}".format(self.symbol))
                print(e)
                attempt += 1

        return data

    def write_to_db(self, dataframe):
        dataframe.to_sql(self.table_name(), self.conn, if_exists='replace', index=True, index_label='Datetime')

    def read_from_db(self):
        query = 'SELECT * FROM "{}"'.format(self.table_name())
        df = pd.read_sql_query(query, self.conn, parse_dates=('Datetime',), index_col='Datetime')
        return df
