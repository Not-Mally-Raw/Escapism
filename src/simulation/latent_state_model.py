"""
Latent State Model for synthetic data generation.
Models customer liquidity cycles per 20M/month observation in spec.
"""
from datetime import datetime
import calendar

def is_post_salary_cycle(dt: datetime) -> bool:
    """
    Checks if a date falls in a clustered 'post-salary' liquidity window.
    Based on spec observation: salary clustering around 1st-5th, 15th, month-end.
    """
    day = dt.day
    last_day = calendar.monthrange(dt.year, dt.month)[1]
    
    if 1 <= day <= 5:
        return True
    if 15 <= day <= 17:
        return True
    if day >= last_day - 1:
        return True
    return False
