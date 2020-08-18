import datetime
import logging
from abc import ABC
import pandas as pd
import numpy as np
from yahoo_fin import stock_info as si

#To make logging in notebook visible
logger = logging.getLogger('root')
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(format=FORMAT)
logger.setLevel(logging.DEBUG)

def _getDurationDates(years):

    today = datetime.date.today()
    return today.replace(year=today.year-years), today

def getTickers(tickerGroups=['sp500']):

    funcsMapping = {'sp500': si.tickers_sp500,
                    'dow': si.tickers_dow,
                    'nasdaq': si.tickers_nasdaq,
                    'other': si.tickers_other}

    tickers = []

    for tickerGroup in tickerGroups:
        try:
            func = funcsMapping[tickerGroup]
            tickers.extend(func())
        except KeyError:
            logger.warning("No function mapping for ticker group %s.", tickerGroup)

    return sorted(set(tickers))

def getStockFromTicker(ticker, years=20):

    stock = Stock(ticker)
    stock.getHistoricalPrice(years)
    stock.generateSMA()
    stock.getFinancials()

    return stock

def getStockFromAllTickers(tickers, years=20):
    stocks = dict.fromkeys(tickers)

    for ticker in stocks.keys():

        stock = getStockFromTicker(ticker, years)
        stocks[ticker] = stock

    return stocks


class Stock:
    def __init__(self, ticker):
        self.ticker = ticker
        self.historicalPrice = None
        self.fiftyTwoHigh = None
        self.fiftyTwoLow = None
        self.balanceSheet = None
        self.incomeStatement = None
        self.cashFlow = None


    def generate52High(self):
        try:
            assert isinstance(self.historicalPrice, pd.DataFrame)
            df = self.historicalPrice.iloc[-52:]
            self.fiftyTwoHigh = max(df['high'])

        except AttributeError:
            logger.warning("Attribute error generating 52wk high. Check for empty dataframe in %s.", self.ticker)

        except AssertionError:
            logger.warning("Assertion error generating 52wk high for %s", self.ticker)


    def generate52Low(self):
        try:
            assert isinstance(self.historicalPrice, pd.DataFrame)
            df = self.historicalPrice.iloc[-52:]
            self.fiftyTwoLow = min(df['low'])

        except AttributeError:
            logger.warning("Attribute error generating 52wk low. Check for empty dataframe in %s.", self.ticker)

        except AssertionError:
            logger.warning("Assertion error generating 52wk low for %s", self.ticker)


    def generateSMA(self, windows=(10,30,40)):
        # Simple moving average, default 10 week/ 50 day
        # TODO: Account for change in sample rate. This assumes historical price data has weekly sampling.
        try:
            assert isinstance(self.historicalPrice, pd.DataFrame)
            for window in windows:
                #Convert weeks to days
                days = window*5
                #Calculate simple moving average
                self.historicalPrice["SMA" + str(days)] = self.historicalPrice['close'].rolling(window=window).mean()

        except AssertionError:
            logger.warning("Assertion error generating SMA for %s", self.ticker)

        except TypeError:
            if type(windows) is int:
                print("Must specify list of weeks/ windows, even if one item.")
                raise
            else:
                print("TypeError generating SMA for %s.", self.ticker)
                raise

    def getHistoricalPrice(self, years):

        startDate, endDate = _getDurationDates(years)

        #scrape price data from yahoo finance using yahoo_fin's get_data
        try:
            assert isinstance(self.ticker, str)
            self.historicalPrice = si.get_data(ticker=self.ticker, start_date=startDate, end_date=endDate, index_as_date=True, interval="1wk")
            logger.info("Success getting historical price for %s", self.ticker)

        except KeyError:
            logger.warning("KeyError getting historical price for %s", self.ticker)
            pass

        except AssertionError:
            logger.warning("AssertionError getting historical price for %s", self.ticker)
            pass

    def getFinancials(self, yearly=True):

        #scrape data from 3 financial statements using yahoo_fin's get_financials
        try:
            assert isinstance(self.ticker, str)
            data = si.get_financials(ticker=self.ticker, yearly=yearly, quarterly=False)

            #store balance sheet data
            self.balanceSheet = BalanceSheet(data['yearly_balance_sheet'])


            logger.info("Success getting financials for %s", self.ticker)

        except KeyError:
            logger.warning("KeyError getting financials for %s", self.ticker)
            pass

        except AssertionError:
            logger.warning("AssertionError getting financials for %s", self.ticker)
            pass

class Financial(ABC):
    def __init__(self):
        self.year = None
        self.filing = None
        self.quarter = None

class BalanceSheet(Financial):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.generateBalanceSheetInfo()

    def generateBalanceSheetInfo(self):
        raise NotImplementedError

    def __calculateBookValue(self):
        """
        Book value can also be thought of as the net asset value of a company calculated as total assets minus
        intangible assets (patents, goodwill) and liabilities.
        :return:
        """
        assert isinstance(self.data, pd.DataFrame)

        self.data.loc['bookValue'] = self.data.loc['totalAssets'] - \
                                     self.data.loc['totalLiab'] - \
                                     self.data.loc['intangibleAssets'] - \
                                     self.data.loc['goodWill']

        #necessary to reverse year ordering as there is no override arg available in pct_change()
        self.data = self.data[sorted(list(self.data.columns))]
        self.data.loc['bookValueGrowthRate'] = self.data.loc['bookValue'].pct_change()
        self.data = self.data[reversed(list(self.data.columns))]


class IncomeStatement(Financial):
    raise NotImplementedError

class CashFlow(Financial):
    raise NotImplementedError

