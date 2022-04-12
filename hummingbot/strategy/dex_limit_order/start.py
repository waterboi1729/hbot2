from decimal import Decimal

# from hummingbot.core.rate_oracle.rate_oracle import RateOracle
# from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.dex_limit_order.dex_limit_order import DexLimitOrder
from hummingbot.strategy.dex_limit_order.dex_limit_order_config_map import dex_limit_order_config_map


def start(self):
    connector = dex_limit_order_config_map.get("connector").value.lower()
    market_info = dex_limit_order_config_map.get("market").value
    target_price = Decimal(dex_limit_order_config_map.get("target_price").value)
    action = dex_limit_order_config_map.get("action").value.lower()
    order_amount = dex_limit_order_config_map.get("order_amount").value
    # min_profitability = dex_limit_order_config_map.get("min_profitability").value / Decimal("100")
    market_slippage_buffer = dex_limit_order_config_map.get("market_slippage_buffer").value / Decimal("100")
    # use_oracle_conversion_rate = dex_limit_order_config_map.get("use_oracle_conversion_rate").value
    # secondary_to_primary_quote_conversion_rate = dex_limit_order_config_map.get("secondary_to_primary_quote_conversion_rate").value

    self._initialize_markets([(connector, [market_info])])
    base_1, quote_1 = market_info.split("-")

    market_info = MarketTradingPairTuple(self.markets[connector], market_info, base_1, quote_1)
    self.market_trading_pair_tuples = [market_info]

    # if use_oracle_conversion_rate:
    #     rate_source = RateOracle.get_instance()
    # else:
    #     rate_source = FixedRateSource()
    #     # rate_source.add_rate(f"{quote_2}-{quote_1}", secondary_to_primary_quote_conversion_rate)

    self.strategy = DexLimitOrder()
    self.strategy.init_params(market_info=market_info,
                              target_price = target_price,
                              action = action,
                              order_amount=order_amount,
                              market_slippage_buffer=market_slippage_buffer)
