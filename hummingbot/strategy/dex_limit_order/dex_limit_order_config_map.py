# from hummingbot.client import settings
# from hummingbot.client.config.config_helpers import parse_cvar_value
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_connector,
    validate_decimal,
)
# from hummingbot.client.config.config_validators import validate_bool
from hummingbot.client.settings import (
    required_exchanges,
    requried_connector_trading_pairs,
    AllConnectorSettings,
)
from decimal import Decimal


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def market_validator(value: str) -> None:
    exchange = dex_limit_order_config_map["connector"].value
    return validate_market_trading_pair(exchange, value)


def market_on_validated(value: str) -> None:
    requried_connector_trading_pairs[dex_limit_order_config_map["connector"].value] = [value]


def market_prompt() -> str:
    connector = dex_limit_order_config_map.get("connector").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def order_amount_prompt() -> str:
    trading_pair = dex_limit_order_config_map["market"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


dex_limit_order_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="dex_limit_order"),
    "connector": ConfigVar(
        key="connector",
        prompt="Enter your DEX >>> ",
        prompt_on_new=True,
        validator=validate_connector,
        on_validated=exchange_on_validated),
    "market": ConfigVar(
        key="market",
        prompt=market_prompt,
        prompt_on_new=True,
        # validator=market_validator,
        # on_validated=market_on_validated
    ),
    "order_amount": ConfigVar(
        key="order_amount",
        prompt=order_amount_prompt,
        type_str="decimal",
        validator=lambda v: validate_decimal(v, Decimal("0")),
        prompt_on_new=True),
    "market_slippage_buffer": ConfigVar(
        key="market_slippage_buffer",
        prompt="How much buffer do you want to add to the price to account for slippage for orders on the first market "
               "(Enter 1 for 1%)? >>> ",
        prompt_on_new=True,
        default=Decimal("0.05"),
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "target_price": ConfigVar(
        key="target_price",
        prompt="What price are you looking for? ",
        prompt_on_new=True,
        validator=lambda v: validate_decimal(v),
        type_str="decimal"),
    "action": ConfigVar(
        # TODO input validation
        key="action",
        prompt="Are you looking to buy or sell? ",
        prompt_on_new=True),
}
