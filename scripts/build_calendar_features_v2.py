"""Regional calendar features for interval-grain checkpoint rows."""

import logging
from typing import Dict

import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

REGION_TIMEZONES = {
    'NSW1': 'Australia/Sydney',
    'QLD1': 'Australia/Brisbane',
    'VIC1': 'Australia/Melbourne',
    'SA1': 'Australia/Adelaide',
    'TAS1': 'Australia/Hobart',
}

REGION_PREFIX = {
    'NSW1': 'nsw',
    'QLD1': 'qld',
    'VIC1': 'vic',
    'SA1': 'sa',
    'TAS1': 'tas',
}

CALENDAR_FEATURE_DEFINITION_VERSION = '2.0.0-regional'


def _national_holidays() -> Dict[str, str]:
    holidays = {}
    for year in range(2020, 2027):
        holidays[f'{year}-01-01'] = "New Year's Day"
        holidays[f'{year}-01-26'] = 'Australia Day'
        holidays[f'{year}-04-25'] = 'ANZAC Day'
        holidays[f'{year}-12-25'] = 'Christmas Day'
        holidays[f'{year}-12-26'] = 'Boxing Day'
    holidays.update(
        {
            '2020-01-27': 'Australia Day (Observed)',
            '2025-01-27': 'Australia Day (Observed)',
            '2020-04-10': 'Good Friday',
            '2021-04-02': 'Good Friday',
            '2022-04-15': 'Good Friday',
            '2023-04-07': 'Good Friday',
            '2024-03-29': 'Good Friday',
            '2025-04-18': 'Good Friday',
            '2026-04-03': 'Good Friday',
        }
    )
    return holidays


def _nsw_holidays() -> Dict[str, str]:
    holidays = {
        '2020-04-11': 'Easter Saturday',
        '2020-04-13': 'Easter Monday',
        '2020-06-08': "Queen's Birthday",
        '2021-04-03': 'Easter Saturday',
        '2021-04-05': 'Easter Monday',
        '2021-06-14': "Queen's Birthday",
        '2022-04-16': 'Easter Saturday',
        '2022-04-18': 'Easter Monday',
        '2022-06-13': "Queen's Birthday",
        '2023-04-08': 'Easter Saturday',
        '2023-04-10': 'Easter Monday',
        '2023-06-12': "Queen's Birthday",
        '2024-03-30': 'Easter Saturday',
        '2024-04-01': 'Easter Monday',
        '2024-06-10': "Queen's Birthday",
        '2025-04-19': 'Easter Saturday',
        '2025-04-21': 'Easter Monday',
        '2025-06-09': "Queen's Birthday",
        '2026-04-04': 'Easter Saturday',
        '2026-04-06': 'Easter Monday',
        '2026-06-08': "Queen's Birthday",
        '2020-08-03': 'Bank Holiday (NSW)',
        '2021-08-02': 'Bank Holiday (NSW)',
        '2022-08-01': 'Bank Holiday (NSW)',
        '2023-08-07': 'Bank Holiday (NSW)',
        '2024-08-05': 'Bank Holiday (NSW)',
        '2025-08-04': 'Bank Holiday (NSW)',
        '2026-08-03': 'Bank Holiday (NSW)',
        '2020-10-05': 'Labour Day',
        '2021-10-04': 'Labour Day',
        '2022-10-03': 'Labour Day',
        '2023-10-02': 'Labour Day',
        '2024-10-07': 'Labour Day',
        '2025-10-06': 'Labour Day',
        '2026-10-05': 'Labour Day',
    }
    return holidays


def _qld_holidays() -> Dict[str, str]:
    return {
        '2020-04-13': 'Easter Monday',
        '2020-10-05': "Queen's Birthday",
        '2021-04-05': 'Easter Monday',
        '2021-10-04': "Queen's Birthday",
        '2022-04-18': 'Easter Monday',
        '2022-10-03': "Queen's Birthday",
        '2023-04-10': 'Easter Monday',
        '2023-10-02': "Queen's Birthday",
        '2024-04-01': 'Easter Monday',
        '2024-10-07': "Queen's Birthday",
        '2025-04-21': 'Easter Monday',
        '2025-10-06': "Queen's Birthday",
        '2026-04-06': 'Easter Monday',
        '2026-10-05': "Queen's Birthday",
        '2020-05-04': 'Labour Day',
        '2021-05-03': 'Labour Day',
        '2022-05-02': 'Labour Day',
        '2023-05-01': 'Labour Day',
        '2024-05-06': 'Labour Day',
        '2025-05-05': 'Labour Day',
        '2026-05-04': 'Labour Day',
    }


def _vic_holidays() -> Dict[str, str]:
    return {
        '2020-04-11': 'Easter Saturday',
        '2020-04-13': 'Easter Monday',
        '2020-06-08': "Queen's Birthday",
        '2020-11-03': 'Melbourne Cup Day',
        '2021-04-03': 'Easter Saturday',
        '2021-04-05': 'Easter Monday',
        '2021-06-14': "Queen's Birthday",
        '2021-11-02': 'Melbourne Cup Day',
        '2022-04-16': 'Easter Saturday',
        '2022-04-18': 'Easter Monday',
        '2022-06-13': "Queen's Birthday",
        '2022-11-01': 'Melbourne Cup Day',
        '2023-04-08': 'Easter Saturday',
        '2023-04-10': 'Easter Monday',
        '2023-06-12': "Queen's Birthday",
        '2023-11-07': 'Melbourne Cup Day',
        '2024-03-30': 'Easter Saturday',
        '2024-04-01': 'Easter Monday',
        '2024-06-10': "Queen's Birthday",
        '2024-11-05': 'Melbourne Cup Day',
        '2025-04-19': 'Easter Saturday',
        '2025-04-21': 'Easter Monday',
        '2025-06-09': "Queen's Birthday",
        '2025-11-04': 'Melbourne Cup Day',
        '2026-04-04': 'Easter Saturday',
        '2026-04-06': 'Easter Monday',
        '2026-06-08': "Queen's Birthday",
        '2026-11-03': 'Melbourne Cup Day',
        '2020-03-09': 'Labour Day',
        '2021-03-08': 'Labour Day',
        '2022-03-14': 'Labour Day',
        '2023-03-13': 'Labour Day',
        '2024-03-11': 'Labour Day',
        '2025-03-10': 'Labour Day',
        '2026-03-09': 'Labour Day',
    }


def _sa_holidays() -> Dict[str, str]:
    return {
        '2020-03-09': 'Adelaide Cup Day',
        '2020-04-13': 'Easter Monday',
        '2020-06-08': "Queen's Birthday",
        '2021-03-08': 'Adelaide Cup Day',
        '2021-04-05': 'Easter Monday',
        '2021-06-14': "Queen's Birthday",
        '2022-03-14': 'Adelaide Cup Day',
        '2022-04-18': 'Easter Monday',
        '2022-06-13': "Queen's Birthday",
        '2023-03-13': 'Adelaide Cup Day',
        '2023-04-10': 'Easter Monday',
        '2023-06-12': "Queen's Birthday",
        '2024-03-11': 'Adelaide Cup Day',
        '2024-04-01': 'Easter Monday',
        '2024-06-10': "Queen's Birthday",
        '2025-03-10': 'Adelaide Cup Day',
        '2025-04-21': 'Easter Monday',
        '2025-06-09': "Queen's Birthday",
        '2026-03-09': 'Adelaide Cup Day',
        '2026-04-06': 'Easter Monday',
        '2026-06-08': "Queen's Birthday",
        '2020-10-05': 'Labour Day',
        '2021-10-04': 'Labour Day',
        '2022-10-03': 'Labour Day',
        '2023-10-02': 'Labour Day',
        '2024-10-07': 'Labour Day',
        '2025-10-06': 'Labour Day',
        '2026-10-05': 'Labour Day',
    }


def _tas_holidays() -> Dict[str, str]:
    return {
        '2020-04-13': 'Easter Monday',
        '2020-06-08': "Queen's Birthday",
        '2021-04-05': 'Easter Monday',
        '2021-06-14': "Queen's Birthday",
        '2022-04-18': 'Easter Monday',
        '2022-06-13': "Queen's Birthday",
        '2023-04-10': 'Easter Monday',
        '2023-06-12': "Queen's Birthday",
        '2024-04-01': 'Easter Monday',
        '2024-06-10': "Queen's Birthday",
        '2025-04-21': 'Easter Monday',
        '2025-06-09': "Queen's Birthday",
        '2026-04-06': 'Easter Monday',
        '2026-06-08': "Queen's Birthday",
        '2020-02-10': 'Royal Hobart Regatta',
        '2021-02-08': 'Royal Hobart Regatta',
        '2022-02-14': 'Royal Hobart Regatta',
        '2023-02-13': 'Royal Hobart Regatta',
        '2024-02-12': 'Royal Hobart Regatta',
        '2025-02-10': 'Royal Hobart Regatta',
        '2026-02-09': 'Royal Hobart Regatta',
        '2020-03-09': 'Eight Hours Day',
        '2021-03-08': 'Eight Hours Day',
        '2022-03-14': 'Eight Hours Day',
        '2023-03-13': 'Eight Hours Day',
        '2024-03-11': 'Eight Hours Day',
        '2025-03-10': 'Eight Hours Day',
        '2026-03-09': 'Eight Hours Day',
    }


def get_all_regional_holidays() -> Dict[str, Dict[str, str]]:
    national = _national_holidays()
    return {
        'NSW1': {**national, **_nsw_holidays()},
        'QLD1': {**national, **_qld_holidays()},
        'VIC1': {**national, **_vic_holidays()},
        'SA1': {**national, **_sa_holidays()},
        'TAS1': {**national, **_tas_holidays()},
    }


def _add_region_features(df: pd.DataFrame, region: str, timezone_name: str, holiday_map: Dict[str, str]) -> None:
    prefix = REGION_PREFIX[region]

    local_ts = df['observation_timestamp_utc'].dt.tz_convert(timezone_name)
    local_date = local_ts.dt.strftime('%Y-%m-%d')
    local_day_of_week = local_ts.dt.dayofweek
    local_month_key = local_ts.dt.strftime('%Y-%m')

    df[f'{prefix}_local_timestamp'] = local_ts
    df[f'{prefix}_local_date'] = local_date
    df[f'{prefix}_local_hour'] = local_ts.dt.hour
    df[f'{prefix}_local_day_of_week'] = local_day_of_week

    weekend_flag = (local_day_of_week >= 5).astype(int)
    holiday_flag = local_date.isin(holiday_map).astype(int)
    business_day_flag = ((weekend_flag == 0) & (holiday_flag == 0)).astype(int)

    df[f'{prefix}_weekend_flag'] = weekend_flag
    df[f'{prefix}_public_holiday_flag'] = holiday_flag
    df[f'{prefix}_public_holiday_name'] = local_date.map(holiday_map).fillna('')
    df[f'{prefix}_business_day_flag'] = business_day_flag

    holiday_set = set(holiday_map.keys())
    pre_holiday = local_date.apply(
        lambda d: 1 if (pd.Timestamp(d) + pd.Timedelta(days=1)).strftime('%Y-%m-%d') in holiday_set else 0
    )
    post_holiday = local_date.apply(
        lambda d: 1 if (pd.Timestamp(d) - pd.Timedelta(days=1)).strftime('%Y-%m-%d') in holiday_set else 0
    )
    bridge_day = ((business_day_flag == 1) & (pre_holiday == 1) & (post_holiday == 1)).astype(int)

    df[f'{prefix}_pre_holiday_flag'] = pre_holiday
    df[f'{prefix}_post_holiday_flag'] = post_holiday
    df[f'{prefix}_bridge_day_flag'] = bridge_day

    dst_seconds = local_ts.apply(lambda value: value.dst().total_seconds())
    dst_flag = (dst_seconds > 0).astype(int)
    utc_offset = local_ts.apply(lambda value: value.utcoffset().total_seconds())
    dst_transition = utc_offset.ne(utc_offset.shift(1)).astype(int)
    if len(dst_transition) > 0:
        dst_transition.iloc[0] = 0

    df[f'{prefix}_daylight_saving_flag'] = dst_flag
    df[f'{prefix}_daylight_saving_transition_flag'] = dst_transition

    easter_dates = {
        2020: (4, 12),
        2021: (4, 4),
        2022: (4, 17),
        2023: (4, 9),
        2024: (3, 31),
        2025: (4, 20),
        2026: (4, 5),
    }
    easter_flag = pd.Series(0, index=df.index)
    for year, (month, day) in easter_dates.items():
        easter_day = pd.Timestamp(year=year, month=month, day=day)
        window_start = (easter_day - pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        window_end = (easter_day + pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        region_mask = (local_date >= window_start) & (local_date <= window_end)
        easter_flag.loc[region_mask] = 1
    df[f'{prefix}_Easter_period_flag'] = easter_flag

    christmas_new_year = ((local_ts.dt.month == 12) & (local_ts.dt.day >= 23)) | (
        (local_ts.dt.month == 1) & (local_ts.dt.day <= 2)
    )
    df[f'{prefix}_Christmas_New_Year_period_flag'] = christmas_new_year.astype(int)

    business_day_counts = (
        pd.DataFrame(
            {
                'month_key': local_month_key,
                'local_date': local_date,
                'business_day_flag': business_day_flag,
            }
        )
        .query('business_day_flag == 1')
        .drop_duplicates(['month_key', 'local_date'])
        .groupby('month_key')
        .size()
    )
    df[f'{prefix}_working_day_count_in_month'] = local_month_key.map(business_day_counts).fillna(0).astype(int)


def add_calendar_features_regional(df: pd.DataFrame) -> pd.DataFrame:
    logger.info('Adding regional calendar features to %s rows...', len(df))

    output_df = df.copy()
    output_df['observation_timestamp_utc'] = pd.to_datetime(output_df['observation_timestamp_utc'], utc=True)

    output_df['utc_month'] = output_df['observation_timestamp_utc'].dt.month
    output_df['utc_quarter'] = output_df['observation_timestamp_utc'].dt.quarter
    output_df['utc_year'] = output_df['observation_timestamp_utc'].dt.year

    regional_holidays = get_all_regional_holidays()
    for region, timezone_name in REGION_TIMEZONES.items():
        _add_region_features(output_df, region, timezone_name, regional_holidays[region])

    output_df['calendar_feature_definition_version'] = CALENDAR_FEATURE_DEFINITION_VERSION
    output_df['holiday_source_lineage'] = 'National + state public holiday calendar curated in build_calendar_features_v2.py'
    output_df['holiday_jurisdiction_lineage'] = 'NSW1:NSW,QLD1:QLD,VIC1:VIC,SA1:SA,TAS1:TAS'

    logger.info('✓ Regional calendar features added')
    return output_df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    return add_calendar_features_regional(df)


if __name__ == '__main__':
    print('Calendar Features module initialized (v2 - regional explicit fields)')
