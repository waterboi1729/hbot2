from hummingbot.client.config.config_var import ConfigVar


# Returns a market prompt that incorporates the connector value set by the user
def market_prompt() -> str:
    connector = limit_oscillator_config_map.get("connector").value
    return f'Enter the token trading pair on {connector} >>> '


# List of parameters defined by the strategy
limit_oscillator_config_map = {
    "strategy": ConfigVar(
        key="strategy",
        prompt="",
        default="limit_oscillator",
    ),
    "connector": ConfigVar(
        key="connector",
        prompt="Enter the name of the exchange >>> ",
        prompt_on_new=True,
    ),
    "market": ConfigVar(
        key="market",
        prompt=market_prompt,
        prompt_on_new=True,
    ),
    "start_action": ConfigVar(
        key="start_action",
        prompt="Start with a Buy or Sell? >>>  ",
        prompt_on_new=True,
    ),
    "amount": ConfigVar(
        key="amount",
        prompt="Size of all orders, in quote currency (USD)>>  ",
        prompt_on_new=True,
    ),
    "high_price": ConfigVar(
        key="high_price",
        prompt="What price should I SELL at?",
        prompt_on_new=True,
    ),
    "low_price": ConfigVar(
        key="low_price",
        prompt="What price should I BUY at?",
        prompt_on_new=True,
    ),

}
