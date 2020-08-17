import datetime
import logging
from yahoo_fin import stock_info as si

#To make logging in notebook visible
logger = logging.getLogger('root')
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(format=FORMAT)
logger.setLevel(logging.DEBUG)

def getDurationDates(years):

    today = datetime.date.today()
    return today.replace(year=today.year-years), today


def getSP500(years=20):

    startDate, endDate = getDurationDates(years)
    stocks = dict.fromkeys(si.tickers_sp500())

    for ticker in stocks.keys():

        stock = Stock(ticker)

        try:
            historicalPrice = Historical(data=si.get_data(ticker=ticker, start_date=startDate, end_date=endDate, index_as_date=True, interval="1wk"),
                                         duration=years)
            stock.historicalPrice = historicalPrice
            logger.info("%s", ticker)

        except KeyError:
            logger.warning("KeyError for %s in function ", ticker)
            continue

        except AssertionError:
            logger.warning("AssertionError for %s", ticker)

        stocks[ticker] = stock

    return stocks


class Stock:
    def __init__(self, name):
        self.name = name
        self.historicalPrice = None

    def fiftyTwoLow(self):
        assert isinstance(self.historicalPrice, Historical)
        try:
            df = self.historicalPrice.data.iloc[-52:]
            return min(df['low'])

        except AttributeError:
            logger.warning("Could not generate 52 week low for %s as there was no historical price data.", self.name)

    def fiftyTwoHigh(self):
        assert isinstance(self.historicalPrice, Historical)
        try:
            df = self.historicalPrice.data.iloc[-52:]
            return max(df['high'])

        except AttributeError:
            logger.warning("Could not generate 52 week high for %s as there was no historical price data.", self.name)

class Historical:
    def __init__(self, data, duration):
        self.dateSourced = datetime.datetime.today().strftime("%d/%m/%Y")
        self.duration = str(duration) + " yrs"
        self.data = data