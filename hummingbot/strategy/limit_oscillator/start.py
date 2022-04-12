# import cmath
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.limit_oscillator import LimitOscillator
from hummingbot.strategy.limit_oscillator.limit_oscillator_config_map import limit_oscillator_config_map as c_map


def start(self):
    connector = c_map.get("connector").value.lower()
    market = c_map.get("market").value
    start_action = c_map.get("start_action").value.lower()
    high_price = c_map.get("high_price").value
    low_price = c_map.get("low_price").value

    amount = c_map.get("amount").value

    self._initialize_markets([(connector, [market])])
    base, quote = market.split("-")
    market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
    self.market_trading_pair_tuples = [market_info]

    self.strategy = LimitOscillator(market_info, start_action, high_price, low_price, amount)
