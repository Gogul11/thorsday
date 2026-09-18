from langchain_core.tools import tool
import math

@tool
def compute_emi_and_schedule(principal: float, annual_rate_percent: float, years: int) -> str:
    """Calculate the monthly EMI for a loan and generate an amortization summary.

    Args:
        principal: Loan amount (e.g., 250000).
        annual_rate_percent: Annual interest rate in percent (e.g., 7.0).
        years: Loan tenure in years (e.g., 20).

    Returns:
        A string containing the EMI amount and a formatted amortization breakdown.
    """
    monthly_rate = annual_rate_percent / (12 * 100)
    n_months = int(years * 12)
    if monthly_rate == 0:
        emi = round(principal / n_months, 2)
    else:
        emi = round(principal * monthly_rate * (1 + monthly_rate) ** n_months / ((1 + monthly_rate) ** n_months - 1), 2)

    total_payment = round(emi * n_months, 2)
    total_interest = round(total_payment - principal, 2)

    summary = (
        f"Loan EMI Calculation Summary:\n"
        f"- Principal: ₹{principal:,.2f}\n"
        f"- Annual Interest Rate: {annual_rate_percent}%\n"
        f"- Tenure: {years} years ({n_months} months)\n"
        f"- Monthly EMI: ₹{emi:,.2f}\n"
        f"- Total Interest Payable: ₹{total_interest:,.2f}\n"
        f"- Total Amount Payable: ₹{total_payment:,.2f}\n\n"
    )

    balance = principal
    if n_months <= 12:
        lines = [f"{'Month':>5} | {'Payment':>10} | {'Interest':>10} | {'Principal':>10} | {'Balance':>12}"]
        lines.append('-' * len(lines[0]))
        for month in range(1, n_months + 1):
            interest = round(balance * monthly_rate, 2)
            principal_comp = round(emi - interest, 2)
            if month == n_months:
                principal_comp = balance
                emi_actual = round(interest + principal_comp, 2)
            else:
                emi_actual = emi
            balance = round(balance - principal_comp, 2)
            lines.append(f"{month:5d} | {emi_actual:10.2f} | {interest:10.2f} | {principal_comp:10.2f} | {max(balance, 0.0):12.2f}")
        return summary + "Monthly Amortization Schedule:\n" + "\n".join(lines)
    else:
        lines = [f"{'Year':>5} | {'Payment':>12} | {'Interest':>12} | {'Principal':>12} | {'Balance':>12}"]
        lines.append('-' * len(lines[0]))
        month = 1
        for yr in range(1, int(years) + 1):
            yr_interest = 0.0
            yr_principal = 0.0
            for _ in range(12):
                if balance <= 0:
                    break
                interest = round(balance * monthly_rate, 2)
                p_comp = round(emi - interest, 2)
                if month == n_months or balance - p_comp < 0:
                    p_comp = balance
                balance = round(balance - p_comp, 2)
                yr_interest += interest
                yr_principal += p_comp
                month += 1
            yr_payment = yr_principal + yr_interest
            lines.append(f"{yr:5d} | {yr_payment:12.2f} | {yr_interest:12.2f} | {yr_principal:12.2f} | {max(balance, 0.0):12.2f}")
        return summary + "Annual Amortization Breakdown:\n" + "\n".join(lines)
