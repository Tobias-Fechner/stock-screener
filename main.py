import datetime
import logging
import pandas as pd
import numpy as np
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

        #scrape data from yahoo finance using yahoo_fin's get_data
        try:
            stock.historicalPrice = si.get_data(ticker=ticker, start_date=startDate, end_date=endDate, index_as_date=True, interval="1wk")
            logger.info("%s", ticker)
        except KeyError:
            logger.warning("KeyError for %s", ticker)
            continue
        except AssertionError:
            logger.warning("AssertionError for %s", ticker)
            continue

        stock.generateSMA()

        stocks[ticker] = stock

    return stocks


class Stock:
    def __init__(self, name):
        self.name = name
        self.historicalPrice = None
        self.fiftyTwoHigh = None
        self.fiftyTwoLow = None

    #52 week high
    def generate52High(self):
        try:
            assert isinstance(self.historicalPrice, pd.DataFrame)
            df = self.historicalPrice.iloc[-52:]
            self.fiftyTwoHigh = max(df['high'])

        except AttributeError:
            logger.warning("Attribute error generating 52wk high. Check for empty dataframe in %s.", self.name)

        except AssertionError:
            logger.warning("Assertion error generating 52wk high for %s", self.name)

    #52 week low
    def generate52Low(self):
        try:
            assert isinstance(self.historicalPrice, pd.DataFrame)
            df = self.historicalPrice.iloc[-52:]
            self.fiftyTwoLow = min(df['low'])

        except AttributeError:
            logger.warning("Attribute error generating 52wk low. Check for empty dataframe in %s.", self.name)

        except AssertionError:
            logger.warning("Assertion error generating 52wk low for %s", self.name)

    #Simple moving average, default 10 week/ 50 day
    #TODO: Account for change in sample rate. This assumes historical price data has weekly sampling.
    def generateSMA(self, windows=[10,30,40]):
        try:
            assert isinstance(self.historicalPrice, pd.DataFrame)
            for window in windows:
                #Convert weeks to days
                days = window*5
                #Calculate simple moving average
                self.historicalPrice["SMA" + str(days)] = self.historicalPrice['close'].rolling(window=window).mean()

        except AssertionError:
            logger.warning("Assertion error generating SMA for %s", self.name)

        except TypeError:
            if type(windows) is int:
                print("Must specify list of weeks/ windows, even if one item.")
                raise