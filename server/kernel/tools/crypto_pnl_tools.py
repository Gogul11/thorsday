from langchain_core.tools import tool

@tool
def calculate_crypto_pnl(buy_quantity: float, buy_price: float, sell_price: float, fee_percent: float) -> dict:
    """Calculate net profit and ROI for a cryptocurrency trade.

    Args:
        buy_quantity (float): Amount of cryptocurrency bought (e.g., BTC).
        buy_price (float): Purchase price per unit in USD.
        sell_price (float): Sale price per unit in USD.
        fee_percent (float): Exchange fee percentage applied to both buy and sell transactions.

    Returns:
        dict: A dictionary containing:
            - net_profit (float): Profit after subtracting fees.
            - roi_percent (float): Return on investment as a percentage.
    """
    # Total cost of purchase before fees
    total_buy = buy_quantity * buy_price
    # Fee on purchase
    fee_buy = total_buy * fee_percent / 100.0
    # Total proceeds from sale before fees
    total_sell = buy_quantity * sell_price
    # Fee on sale
    fee_sell = total_sell * fee_percent / 100.0
    # Net profit after all fees
    net_profit = total_sell - fee_sell - (total_buy + fee_buy)
    # ROI based on total outflow (buy cost + buy fee)
    total_outflow = total_buy + fee_buy
    roi_percent = (net_profit / total_outflow) * 100.0 if total_outflow != 0 else 0.0
    return {"net_profit": net_profit, "roi_percent": roi_percent}
