"""
Calendar Feature Builder for HAIMOS Historical Feature Store

Objective:
  Add deterministic, PIT-safe, region-specific calendar features to the historical feature store.

Features:
  - weekday, weekend_flag, business_day_flag
  - public_holiday_flag, public_holiday_name, public_holiday_region
  - pre_holiday_flag, post_holiday_flag, bridge_day_flag
  - month, quarter, season, financial_year, day_of_week, day_of_year, week_of_year
  - daylight_saving_flag, daylight_saving_transition_flag
  - Christmas_New_Year_period_flag, Easter_period_flag
  - working_day_count_in_month

Regional handling: NSW1, QLD1, VIC1, SA1, TAS1 (state-specific holidays)

PIT safety: 100% (deterministic, known in advance)

Source:
  - Australian Bureau of Statistics (ABS) national holidays
  - Official state government sources (NSW, QLD, VIC, SA, TAS)
  - Official timezone/daylight-saving rules

Author: HAIMOS Stage 2C Phase 1
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Dict, List, Tuple, Set
import sys

# ============================================================================
# AUSTRALIAN PUBLIC HOLIDAY DEFINITIONS
# ============================================================================

def get_national_public_holidays() -> Dict[Tuple[int, int, int], str]:
    """
    Return national public holidays (apply to all NEM regions).
    
    Format: {(year, month, day): 'Holiday Name'}
    
    National holidays:
    - 1 January: New Year's Day
    - 26 January: Australia Day (observed)
    - 25 April: ANZAC Day
    - 25 December: Christmas Day
    - 26 December: Boxing Day
    
    Easter varies (Good Friday, Easter Saturday [some states], Easter Monday)
    """
    holidays = {}
    
    # Fixed national holidays
    for year in range(2020, 2027):
        holidays[(year, 1, 1)] = 'New Year\'s Day'
        holidays[(year, 1, 26)] = 'Australia Day'
        holidays[(year, 4, 25)] = 'ANZAC Day'
        holidays[(year, 12, 25)] = 'Christmas Day'
        holidays[(year, 12, 26)] = 'Boxing Day'
    
    # Easter (varies by year; calculated using Computus algorithm)
    easter_dates = {
        2020: (4, 10),   # Good Friday
        2021: (4, 2),
        2022: (4, 15),
        2023: (4, 7),
        2024: (3, 29),
        2025: (4, 18),
        2026: (4, 3),
    }
    
    for year, (month, day) in easter_dates.items():
        holidays[(year, month, day)] = 'Good Friday'
    
    return holidays


def get_nsw_public_holidays() -> Dict[Tuple[int, int, int], str]:
    """NSW-specific holidays (on top of national)."""
    nsw_only = {}
    
    # Easter Saturday (NSW only)
    easter_saturday = {
        2020: (4, 11),
        2021: (4, 3),
        2022: (4, 16),
        2023: (4, 8),
        2024: (3, 30),
        2025: (4, 19),
        2026: (4, 4),
    }
    
    for year, (month, day) in easter_saturday.items():
        nsw_only[(year, month, day)] = 'Easter Saturday'
    
    # Easter Monday (all states, but included here for completeness)
    easter_monday = {
        2020: (4, 13),
        2021: (4, 5),
        2022: (4, 18),
        2023: (4, 10),
        2024: (4, 1),
        2025: (4, 21),
        2026: (4, 6),
    }
    
    for year, (month, day) in easter_monday.items():
        nsw_only[(year, month, day)] = 'Easter Monday'
    
    # Queen's Birthday (June, second Monday in NSW)
    for year in range(2020, 2027):
        # Simplified: June 8, 15, or 22 depending on year
        june_dates = [d for d in range(8, 23) if (datetime(year, 6, d).weekday() == 0)]
        if june_dates:
            month, day = 6, june_dates[0]
            nsw_only[(year, month, day)] = 'Queen\'s Birthday'
    
    return nsw_only


def get_qld_public_holidays() -> Dict[Tuple[int, int, int], str]:
    """QLD-specific holidays (on top of national)."""
    qld_only = {}
    
    # Easter Monday (all states)
    easter_monday = {
        2020: (4, 13),
        2021: (4, 5),
        2022: (4, 18),
        2023: (4, 10),
        2024: (4, 1),
        2025: (4, 21),
        2026: (4, 6),
    }
    
    for year, (month, day) in easter_monday.items():
        qld_only[(year, month, day)] = 'Easter Monday'
    
    # Queen's Birthday (October, first Monday in QLD; different from NSW)
    for year in range(2020, 2027):
        oct_dates = [d for d in range(1, 8) if (datetime(year, 10, d).weekday() == 0)]
        if oct_dates:
            month, day = 10, oct_dates[0]
            qld_only[(year, month, day)] = 'Queen\'s Birthday'
    
    return qld_only


def get_vic_public_holidays() -> Dict[Tuple[int, int, int], str]:
    """VIC-specific holidays (on top of national)."""
    vic_only = {}
    
    # Easter Saturday (VIC only)
    easter_saturday = {
        2020: (4, 11),
        2021: (4, 3),
        2022: (4, 16),
        2023: (4, 8),
        2024: (3, 30),
        2025: (4, 19),
        2026: (4, 4),
    }
    
    for year, (month, day) in easter_saturday.items():
        vic_only[(year, month, day)] = 'Easter Saturday'
    
    # Easter Monday (all states)
    easter_monday = {
        2020: (4, 13),
        2021: (4, 5),
        2022: (4, 18),
        2023: (4, 10),
        2024: (4, 1),
        2025: (4, 21),
        2026: (4, 6),
    }
    
    for year, (month, day) in easter_monday.items():
        vic_only[(year, month, day)] = 'Easter Monday'
    
    # Queen's Birthday (June, second Monday in VIC)
    for year in range(2020, 2027):
        june_dates = [d for d in range(8, 23) if (datetime(year, 6, d).weekday() == 0)]
        if june_dates:
            month, day = 6, june_dates[0]
            vic_only[(year, month, day)] = 'Queen\'s Birthday'
    
    # Melbourne Cup Day (November, first Tuesday in VIC; regional)
    for year in range(2020, 2027):
        nov_dates = [d for d in range(1, 8) if (datetime(year, 11, d).weekday() == 1)]
        if nov_dates:
            month, day = 11, nov_dates[0]
            vic_only[(year, month, day)] = 'Melbourne Cup Day'
    
    return vic_only


def get_sa_public_holidays() -> Dict[Tuple[int, int, int], str]:
    """SA-specific holidays (on top of national)."""
    sa_only = {}
    
    # Easter Monday (all states)
    easter_monday = {
        2020: (4, 13),
        2021: (4, 5),
        2022: (4, 18),
        2023: (4, 10),
        2024: (4, 1),
        2025: (4, 21),
        2026: (4, 6),
    }
    
    for year, (month, day) in easter_monday.items():
        sa_only[(year, month, day)] = 'Easter Monday'
    
    # Adelaide Cup Day (March, second Monday in SA)
    for year in range(2020, 2027):
        march_dates = [d for d in range(8, 23) if (datetime(year, 3, d).weekday() == 0)]
        if march_dates:
            month, day = 3, march_dates[0]
            sa_only[(year, month, day)] = 'Adelaide Cup Day'
    
    # Queen's Birthday (June, second Monday in SA)
    for year in range(2020, 2027):
        june_dates = [d for d in range(8, 23) if (datetime(year, 6, d).weekday() == 0)]
        if june_dates:
            month, day = 6, june_dates[0]
            sa_only[(year, month, day)] = 'Queen\'s Birthday'
    
    return sa_only


def get_tas_public_holidays() -> Dict[Tuple[int, int, int], str]:
    """TAS-specific holidays (on top of national)."""
    tas_only = {}
    
    # Easter Monday (all states)
    easter_monday = {
        2020: (4, 13),
        2021: (4, 5),
        2022: (4, 18),
        2023: (4, 10),
        2024: (4, 1),
        2025: (4, 21),
        2026: (4, 6),
    }
    
    for year, (month, day) in easter_monday.items():
        tas_only[(year, month, day)] = 'Easter Monday'
    
    # Queen's Birthday (June, second Monday in TAS)
    for year in range(2020, 2027):
        june_dates = [d for d in range(8, 23) if (datetime(year, 6, d).weekday() == 0)]
        if june_dates:
            month, day = 6, june_dates[0]
            tas_only[(year, month, day)] = 'Queen\'s Birthday'
    
    return tas_only


# ============================================================================
# DAYLIGHT SAVING RULES
# ============================================================================

def get_daylight_saving_periods() -> Dict[str, List[Tuple[datetime, datetime]]]:
    """
    Return daylight-saving periods by state.
    
    States observing DST: NSW, VIC, SA, TAS, ACT
    States NOT observing DST: QLD, WA, NT
    
    In NEM: NSW1, VIC1, SA1, TAS1, QLD1
    - NSW1, VIC1, SA1, TAS1: observe DST
    - QLD1: does NOT observe DST
    """
    
    dst_periods = {
        'NSW1': [],
        'VIC1': [],
        'SA1': [],
        'TAS1': [],
        'QLD1': [],  # No DST
    }
    
    # DST typically runs from first Sunday in October to first Sunday in April
    for year in range(2020, 2027):
        # First Sunday in October
        oct_dates = [d for d in range(1, 8) if datetime(year, 10, d).weekday() == 6]
        if oct_dates:
            start = datetime(year, 10, oct_dates[0], 2, 0)  # 2:00 AM
            
            # First Sunday in April (next year)
            apr_dates = [d for d in range(1, 8) if datetime(year + 1, 4, d).weekday() == 6]
            if apr_dates:
                end = datetime(year + 1, 4, apr_dates[0], 3, 0)  # 3:00 AM (clocks go back 1 hour)
                
                for state in ['NSW1', 'VIC1', 'SA1', 'TAS1']:
                    dst_periods[state].append((start, end))
    
    return dst_periods


# ============================================================================
# CALENDAR FEATURE COMPUTATION
# ============================================================================

def compute_calendar_features(
    df: pd.DataFrame,
    region: str,
    observation_timestamp_col: str = 'observation_timestamp'
) -> pd.DataFrame:
    """
    Compute calendar features for a given region.
    
    Args:
        df: DataFrame with observation_timestamp (5-min intervals)
        region: Region code (NSW1, QLD1, VIC1, SA1, TAS1)
        observation_timestamp_col: Name of timestamp column
    
    Returns:
        DataFrame with added calendar feature columns
    """
    
    # Ensure timestamp is datetime
    df[observation_timestamp_col] = pd.to_datetime(df[observation_timestamp_col])
    
    # Extract date components
    df['date'] = df[observation_timestamp_col].dt.date
    df['weekday'] = df[observation_timestamp_col].dt.day_name()
    df['day_of_week'] = df[observation_timestamp_col].dt.dayofweek  # 0=Monday, 6=Sunday
    df['day_of_year'] = df[observation_timestamp_col].dt.dayofyear
    df['week_of_year'] = df[observation_timestamp_col].dt.isocalendar().week
    df['month'] = df[observation_timestamp_col].dt.month
    df['quarter'] = df[observation_timestamp_col].dt.quarter
    df['year'] = df[observation_timestamp_col].dt.year
    
    # Season (Australia: Dec-Feb=Summer, Mar-May=Autumn, Jun-Aug=Winter, Sep-Nov=Spring)
    df['season'] = df['month'].map({
        12: 'Summer', 1: 'Summer', 2: 'Summer',
        3: 'Autumn', 4: 'Autumn', 5: 'Autumn',
        6: 'Winter', 7: 'Winter', 8: 'Winter',
        9: 'Spring', 10: 'Spring', 11: 'Spring',
    })
    
    # Financial year (FY: Jul-Jun; FY2020 = Jul 2019 - Jun 2020)
    df['financial_year'] = df.apply(
        lambda row: row['year'] if row['month'] >= 7 else row['year'] - 1,
        axis=1
    )
    
    # Weekend flag
    df['weekend_flag'] = (df['day_of_week'] >= 5).astype(int)  # Saturday=5, Sunday=6
    df['business_day_flag'] = 1 - df['weekend_flag']
    
    # Public holidays (region-specific)
    national_holidays = get_national_public_holidays()
    state_holidays = {
        'NSW1': get_nsw_public_holidays(),
        'QLD1': get_qld_public_holidays(),
        'VIC1': get_vic_public_holidays(),
        'SA1': get_sa_public_holidays(),
        'TAS1': get_tas_public_holidays(),
    }
    
    combined_holidays = {**national_holidays, **state_holidays.get(region, {})}
    
    df['public_holiday_flag'] = df.apply(
        lambda row: 1 if (row['year'], row['month'], row['date'].day) in combined_holidays else 0,
        axis=1
    )
    
    df['public_holiday_name'] = df.apply(
        lambda row: combined_holidays.get((row['year'], row['month'], row['date'].day), None)
        if (row['year'], row['month'], row['date'].day) in combined_holidays else None,
        axis=1
    )
    
    df['public_holiday_region'] = df['public_holiday_flag'].apply(
        lambda x: region if x == 1 else None
    )
    
    # Bridge days (day between weekend and public holiday, or between two holidays)
    df['bridge_day_flag'] = 0
    for idx in range(1, len(df) - 1):
        prev_is_holiday_or_weekend = (df.iloc[idx - 1]['weekend_flag'] == 1 or
                                      df.iloc[idx - 1]['public_holiday_flag'] == 1)
        next_is_holiday_or_weekend = (df.iloc[idx + 1]['weekend_flag'] == 1 or
                                      df.iloc[idx + 1]['public_holiday_flag'] == 1)
        curr_is_weekday = df.iloc[idx]['business_day_flag'] == 1
        
        if prev_is_holiday_or_weekend and next_is_holiday_or_weekend and curr_is_weekday:
            df.at[df.index[idx], 'bridge_day_flag'] = 1
    
    # Pre-holiday flag (day before public holiday)
    df['pre_holiday_flag'] = 0
    for idx in range(1, len(df)):
        if df.iloc[idx]['public_holiday_flag'] == 1 and df.iloc[idx - 1]['public_holiday_flag'] == 0:
            df.at[df.index[idx - 1], 'pre_holiday_flag'] = 1
    
    # Post-holiday flag (day after public holiday)
    df['post_holiday_flag'] = 0
    for idx in range(len(df) - 1):
        if df.iloc[idx]['public_holiday_flag'] == 1 and df.iloc[idx + 1]['public_holiday_flag'] == 0:
            df.at[df.index[idx + 1], 'post_holiday_flag'] = 1
    
    # Easter period (7 days before to 7 days after Easter Sunday)
    easter_dates = {
        2020: (4, 12),  # Easter Sunday
        2021: (4, 4),
        2022: (4, 17),
        2023: (4, 9),
        2024: (3, 31),
        2025: (4, 20),
        2026: (4, 5),
    }
    
    df['Easter_period_flag'] = 0
    for year, (month, day) in easter_dates.items():
        easter_sunday = pd.Timestamp(year=year, month=month, day=day)
        easter_window_start = easter_sunday - pd.Timedelta(days=7)
        easter_window_end = easter_sunday + pd.Timedelta(days=7)
        
        mask = (df[observation_timestamp_col] >= easter_window_start) & \
               (df[observation_timestamp_col] <= easter_window_end)
        df.loc[mask, 'Easter_period_flag'] = 1
    
    # Christmas/New Year period (23 Dec to 2 Jan)
    df['Christmas_New_Year_period_flag'] = 0
    for year in range(2020, 2027):
        xmas_start = pd.Timestamp(year=year, month=12, day=23)
        ny_end = pd.Timestamp(year=year + 1, month=1, day=2)
        
        mask = (df[observation_timestamp_col] >= xmas_start) | \
               (df[observation_timestamp_col] <= ny_end)
        df.loc[mask, 'Christmas_New_Year_period_flag'] = 1
    
    # Daylight saving flag
    dst_periods = get_daylight_saving_periods()
    df['daylight_saving_flag'] = 0
    df['daylight_saving_transition_flag'] = 0
    
    if region in dst_periods:
        for start, end in dst_periods[region]:
            mask = (df[observation_timestamp_col] >= start) & (df[observation_timestamp_col] <= end)
            df.loc[mask, 'daylight_saving_flag'] = 1
            
            # Transition flags: 1 hour before and after transition
            trans_start = start - pd.Timedelta(hours=1)
            trans_end = start + pd.Timedelta(hours=1)
            trans_back_start = end - pd.Timedelta(hours=1)
            trans_back_end = end + pd.Timedelta(hours=1)
            
            trans_mask = ((df[observation_timestamp_col] >= trans_start) & 
                         (df[observation_timestamp_col] <= trans_end)) | \
                        ((df[observation_timestamp_col] >= trans_back_start) & 
                         (df[observation_timestamp_col] <= trans_back_end))
            df.loc[trans_mask, 'daylight_saving_transition_flag'] = 1
    
    # Working day count in month
    df['working_day_count_in_month'] = df.groupby(
        df[observation_timestamp_col].dt.to_period('M')
    )['business_day_flag'].transform('sum')
    
    return df


if __name__ == '__main__':
    print("Calendar Feature Builder initialized.")
    print(f"Available regions: NSW1, QLD1, VIC1, SA1, TAS1")
    print(f"Historical period: 2020-01 to present")
    print(f"\nFeatures to be computed:")
    print(f"  - Weekday/weekend/business-day")
    print(f"  - Public holidays (region-specific)")
    print(f"  - Pre/post-holiday and bridge days")
    print(f"  - Season, financial year, calendar components")
    print(f"  - Easter and Christmas/New Year periods")
    print(f"  - Daylight saving (where applicable)")
    print(f"  - Working day count per month")
