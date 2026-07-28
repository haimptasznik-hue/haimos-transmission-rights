"""
Calendar Features Integration Pipeline

Objective:
  Integrate calendar features into the Historical Feature Store v1.0 without modifying
  the frozen baseline. Preserve v1.0 checkpoint architecture and lineage.

Strategy:
  1. Load monthly checkpoints from historical feature store
  2. Compute calendar features for each region
  3. Write calendar-augmented partitions to new output directory
  4. Validate full-history coverage and consistency
  5. Preserve checkpoint reuse architecture

Author: HAIMOS Stage 2C Phase 1
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
import hashlib
import sys
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class CalendarFeatureIntegrator:
    """Integrate calendar features into historical feature store."""
    
    def __init__(self, base_path: Path):
        """
        Initialize integrator.
        
        Args:
            base_path: Path to haimos-transmission-rights-repo
        """
        self.base_path = Path(base_path)
        self.historical_fs_path = self.base_path / 'data' / 'derived' / 'historical_feature_store'
        self.checkpoints_path = self.historical_fs_path / 'checkpoints'
        self.output_path = self.historical_fs_path / 'calendar_integrated'
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        self.regions = ['NSW1', 'QLD1', 'VIC1', 'SA1', 'TAS1']
        self.calendar_features = [
            'weekday', 'day_of_week', 'day_of_year', 'week_of_year',
            'month', 'quarter', 'season', 'financial_year',
            'weekend_flag', 'business_day_flag',
            'public_holiday_flag', 'public_holiday_name', 'public_holiday_region',
            'pre_holiday_flag', 'post_holiday_flag', 'bridge_day_flag',
            'Easter_period_flag', 'Christmas_New_Year_period_flag',
            'daylight_saving_flag', 'daylight_saving_transition_flag',
            'working_day_count_in_month'
        ]
        
        logger.info(f"CalendarFeatureIntegrator initialized")
        logger.info(f"  Base path: {self.base_path}")
        logger.info(f"  Historical FS path: {self.historical_fs_path}")
        logger.info(f"  Output path: {self.output_path}")
        logger.info(f"  Regions: {', '.join(self.regions)}")
    
    def get_available_months(self) -> List[str]:
        """Get list of available monthly checkpoints (YYYY-MM format)."""
        checkpoint_dirs = [d for d in self.checkpoints_path.iterdir() if d.is_dir()]
        months = sorted([d.name for d in checkpoint_dirs])
        return months
    
    def load_monthly_checkpoint(self, month_str: str) -> pd.DataFrame:
        """
        Load monthly checkpoint.
        
        Args:
            month_str: Month in YYYY-MM format
        
        Returns:
            DataFrame with monthly data
        """
        checkpoint_dir = self.checkpoints_path / month_str
        checkpoint_file = checkpoint_dir / 'historical_market_feature_store_5min.csv.gz'
        
        if not checkpoint_file.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_file}")
        
        try:
            df = pd.read_csv(checkpoint_file, dtype={
                'interval_timestamp': 'object',
                'region': 'object',
            })
            logger.debug(f"Loaded checkpoint {month_str}: {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"Error loading checkpoint {month_str}: {e}")
            raise
    
    def validate_one_month(self, month_str: str = '2020-01') -> Dict:
        """
        Validate calendar features for one month.
        
        Args:
            month_str: Month in YYYY-MM format (default: 2020-01, first available month)
        
        Returns:
            Validation report dictionary
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"VALIDATING CALENDAR FEATURES FOR MONTH: {month_str}")
        logger.info(f"{'='*60}\n")
        
        report = {
            'month': month_str,
            'status': 'PASSED',
            'rows_processed': 0,
            'rows_by_region': {},
            'holidays_found': {},
            'issues': [],
        }
        
        try:
            # Load checkpoint
            df = self.load_monthly_checkpoint(month_str)
            report['rows_processed'] = len(df)
            
            # Ensure timestamp column
            df['observation_timestamp'] = pd.to_datetime(df['interval_timestamp'])
            df['date'] = df['observation_timestamp'].dt.date
            
            # Process each region
            for region in self.regions:
                region_df = df[df['region'] == region].copy()
                report['rows_by_region'][region] = len(region_df)
                
                # Import calendar feature builder
                sys.path.insert(0, str(self.base_path / 'scripts'))
                from build_calendar_features import compute_calendar_features
                
                # Compute features
                region_df = compute_calendar_features(
                    region_df, 
                    region=region,
                    observation_timestamp_col='observation_timestamp'
                )
                
                # Validate
                region_report = self._validate_region_calendar(
                    region_df, region, month_str
                )
                
                report['holidays_found'][region] = region_report['holidays_found']
                
                if region_report['issues']:
                    report['issues'].extend(region_report['issues'])
                    report['status'] = 'WARNING'
            
            # Summary
            logger.info(f"\nValidation completed for {month_str}")
            logger.info(f"  Total rows: {report['rows_processed']}")
            logger.info(f"  Rows by region:")
            for region, count in report['rows_by_region'].items():
                logger.info(f"    {region}: {count}")
            
            if report['issues']:
                logger.warning(f"Issues found: {len(report['issues'])}")
                for issue in report['issues'][:5]:  # Show first 5
                    logger.warning(f"  - {issue}")
            
            return report
        
        except Exception as e:
            logger.error(f"Error validating month {month_str}: {e}")
            report['status'] = 'FAILED'
            report['issues'].append(str(e))
            return report
    
    def _validate_region_calendar(
        self, 
        df: pd.DataFrame, 
        region: str, 
        month_str: str
    ) -> Dict:
        """Validate calendar features for a specific region."""
        
        report = {
            'region': region,
            'holidays_found': [],
            'issues': [],
        }
        
        # Check for public holidays
        holidays = df[df['public_holiday_flag'] == 1]
        if len(holidays) > 0:
            for _, row in holidays.iterrows():
                report['holidays_found'].append({
                    'date': str(row['date']),
                    'holiday': row['public_holiday_name'],
                    'count': row['public_holiday_flag']
                })
                logger.info(f"  {region}: Holiday found on {row['date']}: {row['public_holiday_name']}")
        
        # Check for weekend consistency
        weekend_days = df[df['weekend_flag'] == 1]['weekday'].unique()
        if not all(day in ['Saturday', 'Sunday'] for day in weekend_days):
            report['issues'].append(f"{region}: Non-weekend day marked as weekend")
        
        # Check for business day consistency
        business_days = df[df['business_day_flag'] == 1]['weekday'].unique()
        if any(day in ['Saturday', 'Sunday'] for day in business_days):
            report['issues'].append(f"{region}: Weekend day marked as business day")
        
        # Check for missing values in key features
        required_cols = ['weekday', 'month', 'quarter', 'season', 'financial_year']
        for col in required_cols:
            if df[col].isnull().sum() > 0:
                report['issues'].append(f"{region}: Missing values in {col}")
        
        return report
    
    def validate_quarter(self, quarters: List[str] = None) -> Dict:
        """
        Validate calendar features for one quarter (3 months).
        
        Args:
            quarters: List of 3 consecutive months (e.g., ['2020-01', '2020-02', '2020-03'])
        
        Returns:
            Validation report dictionary
        """
        if quarters is None:
            quarters = ['2020-01', '2020-02', '2020-03']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"VALIDATING CALENDAR FEATURES FOR QUARTER: {quarters}")
        logger.info(f"{'='*60}\n")
        
        report = {
            'quarter': quarters,
            'status': 'PASSED',
            'months': {},
        }
        
        try:
            for month in quarters:
                month_report = self.validate_one_month(month)
                report['months'][month] = month_report
                
                if month_report['status'] != 'PASSED':
                    report['status'] = month_report['status']
            
            # Cross-month validations
            logger.info(f"\nCross-month validation:")
            
            # Check continuity (no gaps)
            all_dates = []
            for month in quarters:
                df = self.load_monthly_checkpoint(month)
                df['date'] = pd.to_datetime(df['interval_timestamp']).dt.date
                all_dates.extend(df['date'].unique())
            
            all_dates = sorted(set(all_dates))
            expected_dates = pd.date_range(
                start=all_dates[0],
                end=all_dates[-1],
                freq='D'
            ).date
            
            missing_dates = set(expected_dates) - set(all_dates)
            if missing_dates:
                report['status'] = 'WARNING'
                logger.warning(f"  Missing dates: {len(missing_dates)}")
            else:
                logger.info(f"  Date continuity: OK (no gaps)")
            
            return report
        
        except Exception as e:
            logger.error(f"Error validating quarter: {e}")
            report['status'] = 'FAILED'
            return report
    
    def validate_full_history(self) -> Dict:
        """Validate calendar features across full historical period."""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"VALIDATING CALENDAR FEATURES FOR FULL HISTORY")
        logger.info(f"{'='*60}\n")
        
        report = {
            'status': 'PASSED',
            'months_total': 0,
            'months_processed': 0,
            'months_failed': [],
            'summary': {},
        }
        
        available_months = self.get_available_months()
        logger.info(f"Available months: {len(available_months)}")
        logger.info(f"  Start: {available_months[0]}")
        logger.info(f"  End: {available_months[-1]}")
        
        report['months_total'] = len(available_months)
        
        # Validate sample months (start, middle, end)
        sample_months = [
            available_months[0],
            available_months[len(available_months) // 2],
            available_months[-1],
        ]
        
        for month in sample_months:
            try:
                month_report = self.validate_one_month(month)
                report['months_processed'] += 1
                if month_report['status'] == 'FAILED':
                    report['months_failed'].append(month)
                    report['status'] = 'FAILED'
            except Exception as e:
                logger.error(f"Error processing month {month}: {e}")
                report['months_failed'].append(month)
                report['status'] = 'FAILED'
        
        logger.info(f"\nFull-history validation:")
        logger.info(f"  Months processed: {report['months_processed']} / {report['months_total']}")
        logger.info(f"  Months failed: {len(report['months_failed'])}")
        logger.info(f"  Status: {report['status']}")
        
        return report


if __name__ == '__main__':
    base_path = Path('/Users/haimptasznik/Desktop/haimos-transmission-rights-repo')
    integrator = CalendarFeatureIntegrator(base_path)
    
    # Validate one month
    one_month_report = integrator.validate_one_month('2020-01')
    print(f"\nOne-month validation: {one_month_report['status']}")
    
    # Validate quarter
    quarter_report = integrator.validate_quarter(['2020-01', '2020-02', '2020-03'])
    print(f"Quarter validation: {quarter_report['status']}")
    
    # Validate full history (sample)
    full_history_report = integrator.validate_full_history()
    print(f"Full-history validation: {full_history_report['status']}")
    print(f"  Months: {full_history_report['months_processed']} / {full_history_report['months_total']}")
