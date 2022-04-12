#!/usr/bin/env python

from decimal import Decimal
import logging
# from unicodedata import decimal

from hummingbot.core.event.events import OrderType
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase

hws_logger = None


class LimitOscillator(StrategyPyBase):
    # We use StrategyPyBase to inherit the structure. We also
    # create a logger object before adding a constructor to the class.
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 start_action,
                 high_price,
                 low_price,
                 amount,
                 ):

        super().__init__()
        self._market_info = market_info
        self._connector_ready = False
        self._order_placed = False
        # Set action to be the defined start action
        self.action = start_action
        self.high_price = Decimal(high_price)
        self.low_price = Decimal(low_price)
        self.quote_amount = Decimal(amount)
        self.add_markets([market_info.market])
        self.completed_trade_count = 0

    # After initializing the required variables, we define the tick method.
    # The tick method is the entry point for the strategy.
    def tick(self, timestamp: float):
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._market_info.market.name} is not ready. Please wait...")
                return
            else:
                self.logger().warning(f"{self._market_info.market.name} is ready. Trading started")

        # If an order is not already active, lets set one
        if not self._order_placed:

            if self.action == "buy":

                # compute the base amount to buy
                base_amount = round(self.quote_amount / self.low_price, 3)

                # The buy_with_specific_market method executes the trade for you. This
                # method is derived from the Strategy_base class.
                order_id = self.buy_with_specific_market(
                    self._market_info,  # market_trading_pair_tuple
                    base_amount,   # amount
                    OrderType.LIMIT,    # order_type
                    self.low_price           # price
                )

                self._order_placed = True
                self.logger().info(f"Submitted limit BUY order {order_id}")
                self.logger().info(f"Buy: {self.quote_amount} {self._market_info.quote_asset} worth of {self._market_info.base_asset} at price {self.low_price}")

            elif self.action == "sell":

                # compute the base amount to buy
                base_amount = round(self.quote_amount / self.high_price, 3)

                # sell it!
                order_id = self.sell_with_specific_market(
                    self._market_info,  # market_trading_pair_tuple
                    base_amount,   # amount
                    OrderType.LIMIT,    # order_type
                    self.high_price           # price
                )

                self._order_placed = True
                self.logger().info(f"Submitted limit SELL order {order_id}")
                self.logger().info(f"Sell: {self.quote_amount} {self._market_info.quote_asset} worth of {self._market_info.base_asset} at price {self.high_price}")

            else:
                # ugh
                self.logger().info(f"dawg parse ur strings better... action is {self.action}")

    # Emit a log message when the order completes
    def did_complete_buy_order(self, order_completed_event):
        self.logger().info(f"Your limit order {order_completed_event.order_id} has been executed")
        self.logger().info(order_completed_event)
        self.completed_trade_count += 1
        self.logger().info(f"Successfully completed {self.completed_trade_count} trades")
        self.logger().info("Switching new action to SELL")
        # Buy completed, time to sell
        self.action = "sell"
        self._order_placed = False

    def did_complete_sell_order(self, order_completed_event):
        self.logger().info(f"Your limit order {order_completed_event.order_id} has been executed")
        self.logger().info(order_completed_event)
        self.completed_trade_count += 1
        self.logger().info(f"Successfully completed {self.completed_trade_count} trades")
        self.logger().info("Switching new action to BUY")
        # Sell completed, time to buy
        self.action = "buy"
        self._order_placed = False
