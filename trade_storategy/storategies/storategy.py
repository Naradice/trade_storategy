from trade_storategy.storategies.strategy_base import Storategy
import modules.finance_client as fc

class EMACross(Storategy):
    pass

class WMACross(Storategy):
    pass

class MACDCross(Storategy):
    
    key = "macd_cross"
    
    def __get_macd_trend(self):
        #1:long, -1:short
        data = self.client.get_rate_with_indicaters(self.data_length)
        if type(data) != type(None) and self.signal_column_name in data and len(data[self.signal_column_name]) == self.data_length:
                signal = data[self.signal_column_name].iloc[-1]
                macd = data[self.macd_column_name].iloc[-1]
                self.logger.debug(f"macd: {macd}, signal:{signal}")
                if macd >= signal:
                    return 1, data[self.close_column_name].iloc[-1]
                else:
                    return -1, data[self.close_column_name].iloc[-1]
        return 0, None
    
    def __init__(self, financre_client: fc.Client, macd_process = None, interval_mins: int = 30, data_length=100, logger=None) -> None:
        """ When MACD cross up, return buy signal
            When MACD cross down, return sell signal

        Args:
            financre_client (fc.Client): data client
            interval_mins (int, optional): interval mins to get data. Defaults to -1.
            data_length (int, optional): length to caliculate the MACD. Defaults to 100.
            macd_process (Process, optional): You can specify specific parameter of MACD Process. Defaults to None.
        """
        super().__init__(financre_client, interval_mins, data_length, logger)
        if macd_process == None:
            macd = fc.utils.MACDpreProcess()
        else:
            if macd_process.kinds == "MACD":
                macd = macd_process
            else:
                raise Exception("MACDCross accept only MACDProcess")
        if financre_client.have_process(macd) == False:
            financre_client.add_indicater(macd)
            
        self.macd_column_name = macd.columns["MACD"]
        self.signal_column_name = macd.columns["Signal"]
        column_dict = self.client.get_ohlc_columns()
        if type(column_dict) == dict:
            self.close_column_name = column_dict["Close"]
        else:
            self.close_column_name = "Close"
        self.current_trend, _ = self.__get_macd_trend()
        self.logger.info(f"initialized macd storategy: trend is {self.current_trend}")
            
    def run(self, long_short = None):
        tick_trend, price = self.__get_macd_trend()
        signal = None
        if tick_trend != 0:
            if long_short != None:
                long_short = self.trend#0 by default
            if self.current_trend == 1 and tick_trend == -1:
                self.current_trend = tick_trend
                if long_short == 1:
                    self.logger.info("CloseSell signal raised.")
                    signal = CloseSellSignal(self.key, price=price)
                else:
                    self.logger.info("Sell signal raised.")
                    signal = SellSignal(self.key, price=price)
                self.trend = -1
            elif self.current_trend == -1 and tick_trend == 1:
                self.current_trend = tick_trend
                if long_short == -1:
                    self.logger.info("CloseBuy signal raised.")
                    signal = CloseBuySignal(self.key, price=price)
                else:
                    self.logger.info("Buy signal raised.")
                    signal = BuySignal(self.key, price=price)
            return signal

    def raise_signal(self):
        self.create_signal()
            
class MACDRenko(Storategy):
    
    key = "macd_renko"
    
    def __init__(self, financre_client: fc.Client, renko_process: fc.utils.RenkoProcess, macd_process: fc.utils.MACDpreProcess, slope_window = 5, interval_mins: int = -1, data_length=250, logger=None) -> None:
        super().__init__(financre_client, interval_mins, data_length, logger)
        
        if renko_process.kinds != "Renko":
            if financre_client.have_process(fc.utils.RenkoProcess()) is False:
                raise Exception("renko_process accept only RenkoProcess")
            
        if macd_process.kinds != "MACD":
            if financre_client.have_process(fc.utils.MACDpreProcess()) is False:
                raise Exception("macd_process accept only MACDProcess")
            
        self.macd_column_column = macd_process.columns["MACD"]
        self.macd_signal_column = macd_process.columns["Signal"]
        self.renko_bnum_column = renko_process.columns["NUM"]
        column_dict = self.client.get_ohlc_columns()
        if type(column_dict) == dict:
            self.close_column_name = column_dict["Close"]
        else:
            self.close_column_name = "Close"
        
        macd_slope = fc.utils.SlopeProcess(key="m", target_column=self.macd_column_column, window=slope_window)
        signal_slope = fc.utils.SlopeProcess(key="s", target_column=self.macd_signal_column, window=slope_window)
        self.slope_macd_column = macd_slope.columns["Slope"]
        self.slope_signal_column = signal_slope.columns["Slope"]
        
        financre_client.add_indicaters([renko_process, macd_process, macd_slope, signal_slope])

        
    def run(self, long_short: int = None):
        df = self.client.get_rate_with_indicaters(self.data_length)
        if long_short == None:
            long_short = self.trend#0 by default
        signal = None
        if len(df) > 0:
            last_df = df.iloc[-1]
            self.logger.debug(f"{last_df[self.renko_bnum_column]}, {last_df[self.macd_column_column]}, {last_df[self.macd_signal_column]}, {last_df[self.slope_macd_column]}, {last_df[self.slope_signal_column]}")
            if long_short == 0:
                if last_df[self.renko_bnum_column]>=2 and last_df[self.macd_column_column]>last_df[self.macd_signal_column] and last_df[self.slope_macd_column]>last_df[self.slope_signal_column]:
                    signal = BuySignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = 1
                elif last_df[self.renko_bnum_column]<=-2 and last_df[self.macd_column_column]<last_df[self.macd_signal_column] and last_df[self.slope_macd_column]<last_df[self.slope_signal_column]:
                    signal = SellSignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = -1
                        
            elif long_short == 1:
                if last_df[self.renko_bnum_column]<=-2 and last_df[self.macd_column_column]<last_df[self.macd_signal_column] and last_df[self.slope_macd_column]<last_df[self.slope_signal_column]:
                    signal = CloseSellSignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = -1
                elif last_df[self.macd_column_column]<last_df[self.macd_signal_column] and last_df[self.slope_macd_column]<last_df[self.slope_signal_column]:
                    signal = CloseSignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = 0
            elif long_short == -1:
                if last_df[self.renko_bnum_column]>=2 and last_df[self.macd_column_column]>last_df[self.macd_signal_column] and last_df[self.slope_macd_column]>last_df[self.slope_signal_column]:
                    signal = CloseBuySignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = 1
                elif last_df[self.macd_column_column]>last_df[self.macd_signal_column] and last_df[self.slope_macd_column]>last_df[self.slope_signal_column]:
                    signal = CloseSignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = 0
        return signal
    
class CCICross(Storategy):
    
    key = "cci_cross"
    
    def __init__(self, financre_client: fc.Client, cci_process = None, interval_mins: int = 30, data_length=100, logger=None) -> None:
        """ Raise Buy/Sell signal when CCI cross up/down 0

        Args:
            financre_client (fc.Client): any finance_client
            cci_process (ProcessBase, optional): you can provide CCIProcess. Defaults to None and CCIProcess with default parameter is used.
            interval_mins (int, optional): interval minutes to run this storategy. Defaults to 30.
            data_length (int, optional): data length to caliculate CCI. Defaults to 100.
            logger (Logger, optional): you can specify your logger. Defaults to None.

        Raises:
            Exception: when other than CCI process is provided.
        """
        super().__init__(financre_client, interval_mins, data_length, logger)
        if cci_process == None:
            cci_process = fc.utils.CCIProcess()
        else:
            if cci_process.kinds != "CCI":
                raise Exception("CCICross accept only CCIProcess")
        if financre_client.have_process(cci_process) == False:
            financre_client.add_indicater(cci_process)
            
        self.cci_column_name = cci_process.columns["CCI"]
        column_dict = self.client.get_ohlc_columns()
        if type(column_dict) == dict:
            self.close_column_name = column_dict["Close"]
        else:
            self.close_column_name = "Close"
        self.logger.info(f"initialized cci storategy")
        df = self.client.get_rate_with_indicaters(self.data_length)
        last_df = df.iloc[-1]
        current_cci = last_df[self.cci_column_name]
        if current_cci > 0:
            self.trend = 1
        else:
            self.trend = -1

            
    def run(self, long_short = None):
        
        df = self.client.get_rate_with_indicaters(self.data_length)
        
        if long_short == None:
            long_short = self.trend#0 by default
        signal = None
        if len(df) > 0:
            last_df = df.iloc[-1]
            current_cci = last_df[self.cci_column_name]
            self.logger.debug(f"{current_cci}")
            if long_short == 0:
                #don't return signal
                if current_cci > 0:
                    self.trend = 1
                else:
                    self.trend = -1
            elif long_short == 1:
                if current_cci < 0:
                    signal = CloseSellSignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = -1
            elif long_short == -1:
                if current_cci > 0:
                    signal = CloseBuySignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = 1
        return signal
    
class CCIBoader(Storategy):
    
    key = "cci_boader"
    
    def __init__(self, financre_client: fc.Client, cci_process = None, upper=100, lower = -100, interval_mins: int = 30, data_length=100, logger=None) -> None:
        """ Raise Buy/Sell signal when CCI cross up/down uppser/lower

        Args:
            financre_client (fc.Client): any finance_client
            cci_process (ProcessBase, optional): you can provide CCIProcess. Defaults to None and CCIProcess with default parameter is used.
            upper (int, option): upper value to raise Buy Signal. Defaults to 100
            lower (int, option): lower value to raise Sell Signal. Defaults to -100
            interval_mins (int, optional): interval minutes to run this storategy. Defaults to 30.
            data_length (int, optional): data length to caliculate CCI. Defaults to 100.
            logger (Logger, optional): you can specify your logger. Defaults to None.

        Raises:
            Exception: when other than CCI process is provided.
            ValueException: when lower >= upper
        """
        super().__init__(financre_client, interval_mins, data_length, logger)
        if lower >= upper:
            raise ValueError("lower should be lower than upper")
        else:
            self.upper = upper
            self.lower = lower
            
        if cci_process == None:
            cci_process = fc.utils.CCIProcess()
        else:
            if cci_process.kinds != "CCI":
                raise Exception("CCICross accept only CCIProcess")
        if financre_client.have_process(cci_process) == False:
            financre_client.add_indicater(cci_process)
            
        self.cci_column_name = cci_process.columns["CCI"]
        column_dict = self.client.get_ohlc_columns()
        if type(column_dict) == dict:
            self.close_column_name = column_dict["Close"]
        else:
            self.close_column_name = "Close"
        self.logger.info(f"initialized cci storategy")
        df = self.client.get_rate_with_indicaters(self.data_length)
        last_df = df.iloc[-1]
        current_cci = last_df[self.cci_column_name]
        if current_cci >= upper:
            self.trend = 1
        elif current_cci <= lower:
            self.trend = -1
        else:
            self.trend = 0

            
    def run(self, long_short = None):
        
        df = self.client.get_rate_with_indicaters(self.data_length)
        
        if long_short == None:
            long_short = self.trend#0 by default
        signal = None
        if len(df) > 0:
            last_df = df.iloc[-1]
            current_cci = last_df[self.cci_column_name]
            self.logger.debug(f"{current_cci}")
            if long_short != 1:
                if current_cci >= self.upper:
                    if current_cci >= self.upper * 2:
                        self.logger.info(f"Buy signal is not raised as cci is too high {current_cci}")
                    else:
                        self.logger.debug(f"Buy signal is raised as cci over 100: {current_cci}")
                        signal = CloseBuySignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = 1
                elif self.lower < current_cci:
                    self.trend = 0
                    if long_short == -1:
                        signal = CloseSignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
            elif long_short != -1:
                if current_cci <= self.lower:
                    if current_cci <= self.lower * 2:
                        self.logger.info(f"Sell signal is not raised as cci is too low {current_cci}")
                    else:
                        self.logger.debug(f"Buy signal is raised as cci over -100: {current_cci}")
                        signal = CloseSellSignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
                    self.trend = -1
                elif self.upper > current_cci:
                    self.trend = 0
                    if long_short == 1:
                        signal = CloseSignal(std_name=self.key, price=df[self.close_column_name].iloc[-1])
        return signal