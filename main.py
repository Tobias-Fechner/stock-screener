import datetime
import logging
from abc import ABC, abstractmethod
import pandas as pd
from yahoo_fin import stock_info as si

#To make logging in notebook visible
logger = logging.getLogger('root')
FORMAT = "[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
logging.basicConfig(format=FORMAT)
logger.setLevel(logging.DEBUG)

def _getDurationDates(years):

    today = datetime.date.today()
    return today.replace(year=today.year-years), today

def getTickers(tickerGroups=None):

    if tickerGroups is None:
        tickerGroups = ['sp500']

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
        self.price = None
        self.financials = {}
        self.stats = None

    def getHistoricalPrice(self, years):
        #scrape price data from yahoo finance using yahoo_fin's get_data
        try:
            assert isinstance(self.ticker, str)

            startDate, endDate = _getDurationDates(years)

            self.price = Price()
            self.price.historical = si.get_data(ticker=self.ticker,
                                                      start_date=startDate,
                                                      end_date=endDate,
                                                      index_as_date=True,
                                                      interval="1wk")
            logger.info("Success getting historical price for %s", self.ticker)

        except KeyError:
            logger.warning("KeyError getting historical price for %s", self.ticker)
            pass

        except AssertionError:
            logger.warning("AssertionError getting historical price for %s", self.ticker)
            pass

    def getFinancials(self, season='most-recent', yearly=True):

        #scrape data from 3 financial statements using yahoo_fin's get_financials
        try:
            assert isinstance(self.ticker, str)
            data = si.get_financials(ticker=self.ticker, yearly=yearly, quarterly=False)
            logger.info("Success getting financials for %s", self.ticker)

            #store balance sheet data
            self.financials[season] = Financial(self.ticker)
            self.financials[season].balanceSheet = data['yearly_balance_sheet']
            self.financials[season].incomeStatement = data['yearly_income_statement']
            self.financials[season].cashFlow = data['yearly_cash_flow']

        except KeyError:
            logger.warning("KeyError getting financials for %s", self.ticker)
            pass

        except AssertionError:
            logger.warning("AssertionError getting financials for %s", self.ticker)
            pass

    def generateDerivedFinancials(self, season='most-recent'):
        if not isinstance(self.stats, pd.DataFrame):
            self.getStatistics()

        self.financials[season].generateDerivedFinancials(self.stats)

    def getStatistics(self):
        self.stats = si.get_stats(self.ticker).set_index('Attribute')

class Price:
    def __init__(self):
        self.today = None
        self.historical = None
        self.fiftyTwoHigh = None
        self.fiftyTwoLow = None

    def generate52High(self):
        try:
            assert isinstance(self.historical, pd.DataFrame)
            df = self.historical.iloc[-52:]
            self.fiftyTwoHigh = max(df['high'])

        except AttributeError:
            logger.warning("Attribute error generating 52wk high. Check for empty historical price data.")

        except AssertionError:
            logger.warning("Assertion error generating 52wk high.")

    def generate52Low(self):
        try:
            assert isinstance(self.historical, pd.DataFrame)
            df = self.historical.iloc[-52:]
            self.fiftyTwoLow = min(df['low'])

        except AttributeError:
            logger.warning("Attribute error generating 52wk low. Check for empty historical price data.")

        except AssertionError:
            logger.warning("Assertion error generating 52wk low.")

    def generateSMA(self, windows=(10, 30, 40)):
        # Simple moving average, default 10 week/ 50 day
        try:
            assert isinstance(self.historical, pd.DataFrame)
            for window in windows:
                # Convert weeks to days
                days = window * 5
                # Calculate simple moving average
                self.historical["SMA" + str(days)] = self.historical['close'].rolling(
                    window=window).mean()

        except AssertionError:
            logger.warning("No historical price data.")

        except TypeError:
            if type(windows) is int:
                print("Must specify list of weeks/ windows, even if one item.")
                raise
            else:
                print("TypeError generating SMA.")
                raise

class Financial:
    def __init__(self, ticker):
        self.ticker = ticker
        self.year = None
        self.filing = None
        self.quarter = None
        self.balanceSheet = None
        self.incomeStatement = None
        self.cashFlow = None

    def generateDerivedFinancials(self, stats):
        assert isinstance(stats, pd.DataFrame)

        self.__calculateBookValue()
        self.__calculateEPS()
        self.__calculateSPS(stats.loc['Shares Outstanding 5'].values[0])

    @staticmethod
    def __calculateGrowthRate(df, columnName):

        growthRateName = columnName + 'GrowthRate'

        # Necessary to reverse year ordering as there is no override argument available in pct_change()
        df = df[list(sorted(df.columns))]
        df.loc[growthRateName] = df.loc[columnName].pct_change()
        return df[list(reversed(df.columns))]

    def __calculateBookValue(self):
        """
        Book value can also be thought of as the net asset value of a company calculated as total assets minus
        intangible assets (patents, goodwill) and liabilities.
        :return:
        """
        assert isinstance(self.balanceSheet, pd.DataFrame)

        self.balanceSheet.loc['bookValue'] = self.balanceSheet.loc['totalAssets'] - \
                                             self.balanceSheet.loc['totalLiab'] - \
                                             self.balanceSheet.loc['intangibleAssets'] - \
                                             self.balanceSheet.loc['goodWill']

        self.balanceSheet = self.__calculateGrowthRate(self.balanceSheet, 'bookValue')
        logger.info("Success calculating book value and growth rate for %s.", self.ticker)

    def __calculateEPS(self):
        """
        Earnings per share (EPS) is calculated as a company's profit divided by the outstanding shares of
        its common stock. The resulting number serves as an indicator of a company's profitability.
        :return:
        """
        self.incomeStatement.loc['earningsPerShare'] = self.incomeStatement.loc['netIncome'] / self.balanceSheet.loc['commonStock']

        self.incomeStatement = self.__calculateGrowthRate(self.incomeStatement, 'earningsPerShare')
        logger.info("Success calculating earnings per share (EPS) and growth rate for %s.", self.ticker)

    def __calculateSPS(self, sharesOutstanding):
        """
        Sales per share is a ratio that computes the total revenue earned per share over a designated period,
        whether quarterly, semi-annually, annually, or trailing twelve months (TTM).
        It is calculated by dividing total revenue by average total shares outstanding.
        It is also known as "revenue per share."


        WARNING: Weakness in current approach. We are using a single value for shares outstanding over the entire period.
                 Should try and source historical shares outstanding data and use average, for example. (!!)
        :return:
        """

        if not isinstance(sharesOutstanding, int) or not isinstance(sharesOutstanding, float):
            if 'M' in sharesOutstanding:
                shares = float(sharesOutstanding[:-1]) * 1000000
            elif 'B' in sharesOutstanding:
                shares = float(sharesOutstanding[:-1]) * 1000000000
            else:
                raise TypeError
        else:
            shares = sharesOutstanding

        self.incomeStatement.loc['salesPerShare'] = self.incomeStatement.loc['totalRevenue'] / shares

        self.incomeStatement = self.__calculateGrowthRate(self.incomeStatement, 'salesPerShare')
        logger.info("Success calculating sales per share (SPS) and growth rate for %s.", self.ticker)


