# from cgi import print_exception
from decimal import Decimal
import logging
import asyncio
# from readline import get_current_history_length
from tokenize import String
import pandas as pd
from typing import List, Dict, Optional, Any
# from typing import Tuple
# from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.performance import PerformanceMetrics
# from hummingbot.connector.connector_base import ConnectorBase
# from hummingbot.connector.connector.uniswap.uniswap_connector import UniswapConnector
# from hummingbot.core.clock import Clock
from hummingbot.core.data_type.limit_order import LimitOrder
# from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.logger import HummingbotLogger
# from hummingbot.strategy.dex_limit_order.utils import create_arb_proposals, ArbProposal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

NaN = float("nan")
s_decimal_zero = Decimal(0)
amm_logger = None


class DexLimitOrder(StrategyPyBase):
    """
    This is a basic arbitrage strategy which can be used for most types of connectors (CEX, DEX or AMM).
    For a given order amount, the strategy checks both sides of the trade (market_1 and market_2) for arb opportunity.
    If presents, the strategy submits taker orders to both market.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global amm_logger
        if amm_logger is None:
            amm_logger = logging.getLogger(__name__)
        return amm_logger

    def init_params(self,
                    market_info: MarketTradingPairTuple,
                    # min_profitability: Decimal,
                    order_amount: Decimal,
                    target_price: Decimal,
                    action: String,
                    market_slippage_buffer: Decimal = Decimal("0"),
                    # concurrent_orders_submission: bool = True,
                    status_report_interval: float = 900,
                    rate_source: Any = FixedRateSource()):

        """
        Assigns strategy parameters, this function must be called directly after init.
        The reason for this is to make the parameters discoverable on introspect (it is not possible on init of
        a Cython class).
        :param market_info_1: The first market
        :param market_info_2: The second market
        :param min_profitability: The minimum profitability for execute trades (e.g. 0.0003 for 0.3%)
        :param order_amount: The order amount
        :param market_1_slippage_buffer: The buffer for which to adjust order price for higher chance of
        the order getting filled. This is quite important for AMM which transaction takes a long time where a slippage
        is acceptable rather having the transaction get rejected. The submitted order price will be adjust higher
        for buy order and lower for sell order.
        :param market_2_slippage_buffer: The slipper buffer for market_2
        :param concurrent_orders_submission: whether to submit both arbitrage taker orders (buy and sell) simultaneously
        If false, the bot will wait for first exchange order filled before submitting the other order.
        :param status_report_interval: Amount of seconds to wait to refresh the status report
        :param rate_source: Provider of conversion rates between tokens
        """
        self.market_info = market_info
        self.market, self.trading_pair, self.base_asset, self.quote_asset = self.market_info
        # self._min_profitability = min_profitability
        self.action = action
        self.order_amount = order_amount
        self.target_price = target_price
        self.market_slippage_buffer = market_slippage_buffer
        self._all_markets_ready = False

        self._ev_loop = asyncio.get_event_loop()
        self._main_task = None
        self._first_order_done_event: Optional[asyncio.Event] = None
        self._first_order_succeeded: Optional[bool] = None
        self._first_order_id = None

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self.add_markets([market_info.market])
        self._uniswap = None
        self._quote_eth_rate_fetch_loop_task = None
        self._market_1_quote_eth_rate = None

        self._rate_source = rate_source
        # TODO remove this... its a workaround
        self._ready_for_new_trade = False

    @property
    def min_profitability(self) -> Decimal:
        return self._min_profitability

    @property
    def order_amount(self) -> Decimal:
        return self._order_amount

    @order_amount.setter
    def order_amount(self, value):
        self._order_amount = value

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    def tick(self, timestamp: float):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self.active_markets])

            if not self._all_markets_ready:
                self.logger().warning("Markets are not ready. Please wait...")
                return
            else:
                self.logger().info("Markets are ready. Trading started.")
                self._ready_for_new_trade = True
        if self._ready_for_new_trade:
            if self._main_task is None or self._main_task.done():
                self._main_task = safe_ensure_future(self.main())

        else:
            # might get myself in a sticky situation with this async waiting, yet the tick only checks for ready for new trade. TBD
            return

    async def main(self):
        """
        Commenting most of this out, since the only thing I care about is monitoring price and setting a limit order.
        """
        # self._arb_proposals = await create_arb_proposals(self.market_info, self._market_info_2, self._order_amount)
        # arb_proposals = [
        #     t.copy() for t in self._arb_proposals
        #     if t.profit_pct(
        #         account_for_fee=True,
        #         rate_source=self._rate_source,
        #         first_side_quote_eth_rate=self._market_1_quote_eth_rate,
        #         second_side_quote_eth_rate=self._market_2_quote_eth_rate
        #     ) >= self._min_profitability
        # ]
        # if len(arb_proposals) == 0:
        #     if self._last_no_arb_reported < self.current_timestamp - 20.:
        #         self.logger().info("No arbitrage opportunity.\n" +
        #                            "\n".join(self.short_proposal_msg(self._arb_proposals, False)))
        #         self._last_no_arb_reported = self.current_timestamp
        #     return
        # self.apply_slippage_buffers(arb_proposals)
        # self.apply_budget_constraint(arb_proposals)
        # await self.execute_arb_proposals(arb_proposals)

        # Here's my pseudocode to start. Totally ignoring gas + slippage buffers for now.
        execute_trade = False
        current_price = await self.get_current_price(self.action)
        # output = await self.format_status()
        # self.logger().info(f"{output}")
        # self.logger().info(f" {self.format_status()}")

        if self.action == "sell":
            if (Decimal(self.target_price) <= Decimal(current_price)):
                self.logger().info(f"Current {self.base_asset} price is {current_price}. Sending a sell")
                execute_trade = True
        else:
            # Buy
            if (Decimal(self.target_price) >= Decimal(current_price)):
                self.logger().info(f"Current {self.base_asset} price is {current_price}. Sending a sell")
                execute_trade = True

        if execute_trade and self._ready_for_new_trade:
            self._ready_for_new_trade = False
            await self.execute_order(self.action, self.target_price)

        else:
            self.logger().info(f"Current {self.base_asset} price is {current_price} {self.quote_asset}, you want to {self.action} at at least {self.target_price}")
            self.logger().info("Not yet dawg.")

    async def get_current_price(self, action):
        buy_price = await self.market.get_quote_price(self.market_info.trading_pair, True, self.order_amount)
        sell_price = await self.market.get_quote_price(self.trading_pair, False, self._order_amount)
        buy_price = PerformanceMetrics.smart_round(Decimal(str(buy_price)), 8) if buy_price is not None else '-'
        sell_price = PerformanceMetrics.smart_round(Decimal(str(sell_price)), 8) if sell_price is not None else '-'
        # mid_price = PerformanceMetrics.smart_round(((buy_price + sell_price) / 2), 8) if '-' not in [buy_price, sell_price] else '-'

        # TODO never going to get mid price... should return buy vs sell price
        if action == "buy":
            return buy_price
        else:
            return sell_price

    async def execute_order(self, action, price):
        """
        Simplified method created by Derek. Should place an order on a DEX, given a
        market, pair, buy/sell action, and a price
        """

        place_order_fn = self.buy_with_specific_market if (action == "buy") else self.sell_with_specific_market

        self.log_with_clock(logging.INFO,
                            f"Placing {action} order for {self._order_amount} {self.market_info.base_asset} "
                            f"at {self.market_info.market.display_name} at {price} price")

        order_id = place_order_fn(self.market_info,
                                  self._order_amount,
                                  self.market_info.market.get_taker_order_type(),
                                  price,)

        self._first_order_id = order_id
        self.logger().info(f"Ayo placed an order! ID: {order_id}. No idea if it completes or not")
        self._first_order_done_event = asyncio.Event()

        # Not sure if I should have this waiting for the order to complete in a separate method
        await self._first_order_done_event.wait()

        self.handle_order_completed_status()

    def handle_order_completed_status(self):
        # Commenting out oscillator logic... realizing this should be restricted to just a Limit Order.
        # I'll copy all of this over and create a limit oscillator next

        # Success? Nice. Start an order of the opposite action
        if self._first_order_succeeded:
            self.logger().info("Order succeded and we know it!")
            # if self.action == "buy":
            #     self.action = "sell"

            # else:
            #     self.action = "buy"
        else:
            # Not success? Just try again. TODO figure out better logic.
            self.logger().info("Order failed...yeet it again and pray")

        # For now, always going to get ready for a new trade
        # self.logger().info(f"Initiating process for new {self.action} order")
        # self._ready_for_new_trade = True
        self.logger().info("All done, no more trades :)")

    # def apply_slippage_buffers(self, arb_proposals: List[ArbProposal]):
    #     """
    #     Updates arb_proposals by adjusting order price for slipper buffer percentage.
    #     E.g. if it is a buy order, for an order price of 100 and 1% slipper buffer, the new order price is 101,
    #     for a sell order, the new order price is 99.
    #     :param arb_proposals: the arbitrage proposal
    #     """
    #     for arb_proposal in arb_proposals:
    #         for arb_side in (arb_proposal.first_side, arb_proposal.second_side):
    #             market = arb_side.market_info.market
    #             arb_side.amount = market.quantize_order_amount(arb_side.market_info.trading_pair, arb_side.amount)
    #             s_buffer = self._market_1_slippage_buffer if market == self.market_info.market \
    #                 else self._market_2_slippage_buffer
    #             if not arb_side.is_buy:
    #                 s_buffer *= Decimal("-1")
    #             arb_side.order_price *= Decimal("1") + s_buffer
    #             arb_side.order_price = market.quantize_order_price(arb_side.market_info.trading_pair,
    #                                                                arb_side.order_price)

    # def apply_budget_constraint(self, arb_proposals: List[ArbProposal]):
    #     """
    #     Updates arb_proposals by setting proposal amount to 0 if there is not enough balance to submit order with
    #     required order amount.
    #     :param arb_proposals: the arbitrage proposal
    #     """
    #     for arb_proposal in arb_proposals:
    #         for arb_side in (arb_proposal.first_side, arb_proposal.second_side):
    #             market = arb_side.market_info.market
    #             token = arb_side.market_info.quote_asset if arb_side.is_buy else arb_side.market_info.base_asset
    #             balance = market.get_available_balance(token)
    #             required = arb_side.amount * arb_side.order_price if arb_side.is_buy else arb_side.amount
    #             if balance < required:
    #                 arb_side.amount = s_decimal_zero
    #                 self.logger().info(f"Can't arbitrage, {market.display_name} "
    #                                    f"{token} balance "
    #                                    f"({balance}) is below required order amount ({required}).")
    #                 continue

    # async def execute_arb_proposals(self, arb_proposals: List[ArbProposal]):
    #     """
    #     Execute both sides of the arbitrage trades. If concurrent_orders_submission is False, it will wait for the
    #     first order to fill before submit the second order.
    #     :param arb_proposals: the arbitrage proposal
    #     """
    #     for arb_proposal in arb_proposals:
    #         if any(p.amount <= s_decimal_zero for p in (arb_proposal.first_side, arb_proposal.second_side)):
    #             continue
    #         self.logger().info(f"Found arbitrage opportunity!: {arb_proposal}")
    #         for arb_side in (arb_proposal.first_side, arb_proposal.second_side):
    #             if not self._concurrent_orders_submission and arb_side == arb_proposal.second_side:
    #                 await self._first_order_done_event.wait()
    #                 if not self._first_order_succeeded:
    #                     self._first_order_succeeded = None
    #                     continue
    #                 self._first_order_succeeded = None
    #             side = "BUY" if arb_side.is_buy else "SELL"
    #             self.log_with_clock(logging.INFO,
    #                                 f"Placing {side} order for {arb_side.amount} {arb_side.market_info.base_asset} "
    #                                 f"at {arb_side.market_info.market.display_name} at {arb_side.order_price} price")
    #             place_order_fn = self.buy_with_specific_market if arb_side.is_buy else self.sell_with_specific_market
    #             order_id = place_order_fn(arb_side.market_info,
    #                                       arb_side.amount,
    #                                       arb_side.market_info.market.get_taker_order_type(),
    #                                       arb_side.order_price,
    #                                       )
    #             if not self._concurrent_orders_submission and arb_side == arb_proposal.first_side:
    #                 self._first_order_id = order_id
    #                 self._first_order_done_event = asyncio.Event()

    def ready_for_new_trade(self) -> bool:
        """
        Returns True if there is no outstanding unfilled order.
        """
        # outstanding_orders = self.market_info_to_active_orders.get(self._market_info, [])
        if len(self.market_info_to_active_orders.get(self.market_info, [])) > 0:
            return False
        return True

    # def short_proposal_msg(self, arb_proposal: List[ArbProposal], indented: bool = True) -> List[str]:
    #     """
    #     Composes a short proposal message.
    #     :param arb_proposal: The arbitrage proposal
    #     :param indented: If the message should be indented (by 4 spaces)
    #     :return A list of messages
    #     """
    #     lines = []
    #     for proposal in arb_proposal:
    #         side1 = "buy" if proposal.first_side.is_buy else "sell"
    #         side2 = "buy" if proposal.second_side.is_buy else "sell"
    #         profit_pct = proposal.profit_pct(True,
    #                                          rate_source=self._rate_source,
    #                                          first_side_quote_eth_rate=self._market_1_quote_eth_rate,
    #                                          second_side_quote_eth_rate = self._market_2_quote_eth_rate)
    #         lines.append(f"{'    ' if indented else ''}{side1} at {proposal.first_side.market_info.market.display_name}"
    #                      f", {side2} at {proposal.second_side.market_info.market.display_name}: "
    #                      f"{profit_pct:.2%}")
    #     return lines

    # def quotes_rate_df(self):
    #     columns = ["Quotes pair", "Rate"]
    #     quotes_pair = f"{self._market_info_2.quote_asset}-{self.market_info.quote_asset}"
    #     data = [[quotes_pair, PerformanceMetrics.smart_round(self._rate_source.rate(quotes_pair))]]

    #     return pd.DataFrame(data=data, columns=columns)

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, profitability and warnings(if any).
        """

        # active_orders = self.market_info_to_active_orders.get(self._market_info, [])
        columns = ["Exchange", "Market", "Sell Price", "Buy Price", "Mid Price"]
        data = []
        for market_info in [self.market_info]:
            market, trading_pair, base_asset, quote_asset = market_info
            buy_price = await market.get_quote_price(trading_pair, True, self._order_amount)
            sell_price = await market.get_quote_price(trading_pair, False, self._order_amount)

            # check for unavailable price data
            buy_price = PerformanceMetrics.smart_round(Decimal(str(buy_price)), 8) if buy_price is not None else '-'
            sell_price = PerformanceMetrics.smart_round(Decimal(str(sell_price)), 8) if sell_price is not None else '-'
            mid_price = PerformanceMetrics.smart_round(((buy_price + sell_price) / 2), 8) if '-' not in [buy_price, sell_price] else '-'

            data.append([
                market.display_name,
                trading_pair,
                sell_price,
                buy_price,
                mid_price
            ])
        markets_df = pd.DataFrame(data=data, columns=columns)
        lines = []
        lines.extend(["", "  Markets:"] + ["    " + line for line in markets_df.to_string(index=False).split("\n")])

        assets_df = self.wallet_balance_data_frame([self.market_info])
        lines.extend(["", "  Assets:"] +
                     ["    " + line for line in str(assets_df).split("\n")])

        warning_lines = self.network_warning([self.market_info])
        warning_lines.extend(self.balance_warning([self.market_info]))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def did_complete_buy_order(self, order_completed_event):
        self.first_order_done(order_completed_event, True)

    def did_complete_sell_order(self, order_completed_event):
        self.first_order_done(order_completed_event, True)

    def did_fail_order(self, order_failed_event):
        self.first_order_done(order_failed_event, False)

    def did_cancel_order(self, cancelled_event):
        self.first_order_done(cancelled_event, False)

    def did_expire_order(self, expired_event):
        self.first_order_done(expired_event, False)

    def first_order_done(self, event, succeeded):
        if self._first_order_done_event is not None and event.order_id == self._first_order_id:
            self._first_order_done_event.set()
            self._first_order_succeeded = succeeded

    # @property
    # def tracked_limit_orders(self) -> List[Tuple[ConnectorBase, LimitOrder]]:
    #     return self._sb_order_tracker.tracked_limit_orders

    # @property
    # def tracked_market_orders(self) -> List[Tuple[ConnectorBase, MarketOrder]]:
    #     return self._sb_order_tracker.tracked_market_orders

    # def start(self, clock: Clock, timestamp: float):
    #     if self.market_info.market.name in AllConnectorSettings.get_eth_wallet_connector_names() or \
    #             self._market_info_2.market.name in AllConnectorSettings.get_eth_wallet_connector_names():
    #         self._quote_eth_rate_fetch_loop_task = safe_ensure_future(self.quote_in_eth_rate_fetch_loop())

    # def stop(self, clock: Clock):
    #     if self._quote_eth_rate_fetch_loop_task is not None:
    #         self._quote_eth_rate_fetch_loop_task.cancel()
    #         self._quote_eth_rate_fetch_loop_task = None
    #     if self._main_task is not None:
    #         self._main_task.cancel()
    #         self._main_task = None

    # async def quote_in_eth_rate_fetch_loop(self):
    #     while True:
    #         try:
    #             if self.market_info.market.name in AllConnectorSettings.get_eth_wallet_connector_names() and \
    #                     "WETH" not in self.market_info.trading_pair.split("-"):
    #                 self._market_1_quote_eth_rate = await self.request_rate_in_eth(self.market_info.quote_asset)
    #                 self.logger().warning(f"Estimate conversion rate - "
    #                                       f"{self.market_info.quote_asset}:ETH = {self._market_1_quote_eth_rate} ")

    #             if self._market_info_2.market.name in AllConnectorSettings.get_eth_wallet_connector_names() and \
    #                     "WETH" not in self._market_info_2.trading_pair.split("-"):
    #                 self._market_2_quote_eth_rate = await self.request_rate_in_eth(self._market_info_2.quote_asset)
    #                 self.logger().warning(f"Estimate conversion rate - "
    #                                       f"{self._market_info_2.quote_asset}:ETH = {self._market_2_quote_eth_rate} ")
    #             await asyncio.sleep(60 * 1)
    #         except asyncio.CancelledError:
    #             raise
    #         except Exception as e:
    #             self.logger().error(str(e), exc_info=True)
    #             self.logger().network("Unexpected error while fetching ETH conversion rate.",
    #                                   exc_info=True,
    #                                   app_warning_msg="Could not fetch ETH conversion rate from Gateway API.")
    #             await asyncio.sleep(0.5)

    # async def request_rate_in_eth(self, quote: str) -> int:
    #     if self._uniswap is None:
    #         self._uniswap = UniswapConnector([f"{quote}-WETH"], "", None)
    #         await self._uniswap.initiate_pool()  # initiate to cache swap pool
    #     return await self._uniswap.get_quote_price(f"{quote}-WETH", True, 1)
