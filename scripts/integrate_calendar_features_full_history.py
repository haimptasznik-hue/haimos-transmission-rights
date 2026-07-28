#!/usr/bin/env python3
"""
Integrate calendar features across all 79 historical checkpoints.
Writes calendar-augmented checkpoints to new directory, preserving v1.0 baseline.
"""

import sys
import os
import gzip
import logging
import pandas as pd
from pathlib import Path
from build_calendar_features_v2 import add_calendar_features

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def integrate_all_checkpoints(
    source_dir: str,
    output_dir: str,
    sample_only: bool = False
) -> dict:
    """
    Integrate calendar features into all checkpoints.
    
    Args:
        source_dir: Source checkpoint directory (v1.0)
        output_dir: Output directory for calendar-augmented checkpoints
        sample_only: If True, only process first, middle, last checkpoints
    
    Returns:
        Dictionary with integration results
    """
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
    # List all checkpoints
    checkpoint_dirs = sorted([
        d for d in os.listdir(source_dir)
        if os.path.isdir(os.path.join(source_dir, d))
    ])
    
    logger.info(f"Found {len(checkpoint_dirs)} checkpoints: {checkpoint_dirs[0]} to {checkpoint_dirs[-1]}")
    
    # Sample if requested
    if sample_only:
        months_to_process = [
            checkpoint_dirs[0],
            checkpoint_dirs[len(checkpoint_dirs)//2],
            checkpoint_dirs[-1]
        ]
        logger.info(f"Sample mode: processing {months_to_process}")
    else:
        months_to_process = checkpoint_dirs
    
    results = {
        'total': len(checkpoint_dirs),
        'processed': 0,
        'errors': 0,
        'months': {}
    }
    
    for month in months_to_process:
        try:
            # Source checkpoint
            source_path = os.path.join(
                source_dir, month,
                'historical_market_feature_store_5min.csv.gz'
            )
            
            # Load checkpoint
            logger.info(f"Loading {month}...")
            with gzip.open(source_path, 'rt') as f:
                df = pd.read_csv(f)
            
            # Convert timestamp
            df['observation_timestamp_utc'] = pd.to_datetime(df['observation_timestamp_utc'])
            
            # Add calendar features
            logger.info(f"Adding calendar features to {len(df)} rows...")
            df_with_calendar = add_calendar_features(df)
            
            # Create output checkpoint directory
            output_month_dir = os.path.join(output_dir, month)
            os.makedirs(output_month_dir, exist_ok=True)
            
            # Write calendar-augmented checkpoint
            output_path = os.path.join(
                output_month_dir,
                'historical_market_feature_store_5min.csv.gz'
            )
            
            logger.info(f"Writing {month} to {output_path}...")
            with gzip.open(output_path, 'wt') as f:
                df_with_calendar.to_csv(f, index=False)
            
            # Verify write
            with gzip.open(output_path, 'rt') as f:
                df_verify = pd.read_csv(f)
            
            n_rows_written = len(df_verify)
            n_cols_written = len(df_verify.columns)
            n_null = df_verify.isnull().sum().sum()
            
            results['months'][month] = {
                'status': 'SUCCESS',
                'rows': n_rows_written,
                'columns': n_cols_written,
                'nulls': n_null
            }
            
            logger.info(
                f"✓ {month}: {n_rows_written} rows × {n_cols_written} columns, "
                f"{n_null} nulls"
            )
            
            results['processed'] += 1
            
        except Exception as e:
            logger.error(f"✗ {month}: {type(e).__name__}: {e}")
            results['months'][month] = {
                'status': 'FAILED',
                'error': str(e)
            }
            results['errors'] += 1
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Integration Summary:")
    logger.info(f"  Total checkpoints: {results['total']}")
    logger.info(f"  Processed: {results['processed']}")
    logger.info(f"  Errors: {results['errors']}")
    logger.info(f"  Success rate: {100*results['processed']/results['total']:.1f}%")
    logger.info(f"{'='*60}\n")
    
    return results

if __name__ == '__main__':
    # Paths
    repo_root = Path(__file__).parent.parent
    source_dir = repo_root / 'data' / 'derived' / 'historical_feature_store' / 'checkpoints'
    output_dir = repo_root / 'data' / 'derived' / 'historical_feature_store_calendar_v1' / 'checkpoints'
    
    # Check if we're doing sample mode
    sample_mode = '--sample' in sys.argv
    
    if sample_mode:
        logger.info("Running in SAMPLE mode (first, middle, last only)")
    else:
        logger.info("Running FULL integration (all 79 checkpoints)")
    
    # Run integration
    results = integrate_all_checkpoints(
        source_dir=str(source_dir),
        output_dir=str(output_dir),
        sample_only=sample_mode
    )
    
    # Exit with error code if any failures
    sys.exit(0 if results['errors'] == 0 else 1)
