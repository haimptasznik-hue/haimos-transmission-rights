"""
ERA5 loader — fetches u/v wind components via CDS API.
Falls back gracefully if credentials are missing.
"""
import os
import numpy as np
import pandas as pd
import yaml


def _load_credentials(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def fetch_era5(config, vault_path):
    """
    Download ERA5 10m and 100m wind components for the bounding box.
    Returns path to raw NetCDF file, or None if unavailable.
    Source: Copernicus Climate Data Store (CDS).
    Licence: Copernicus licence — https://cds.climate.copernicus.eu/cdsapp#!/terms/licence-to-use-copernicus-products
    """
    creds = _load_credentials(os.path.join(vault_path, config["credentials_file"]))
    if creds is None:
        return None, "no_credentials"

    try:
        import cdsapi
        c = cdsapi.Client(url=creds["url"], key=creds["key"])
        out_path = os.path.join(vault_path, "06_Raw_Data/Wind/Euston/raw/era5_wind_euston.nc")
        c.retrieve(
            config["dataset"],
            {
                "product_type": "reanalysis",
                "variable": config["variables"],
                "year": [str(y) for y in config["years"]],
                "month": [f"{m:02d}" for m in config["months"]],
                "day": [f"{d:02d}" for d in range(1, 32)],
                "time": [f"{h:02d}:00" for h in range(24)],
                "area": config["area"],
                "format": "netcdf",
            },
            out_path,
        )
        return out_path, "era5"
    except Exception as e:
        return None, f"era5_error:{e}"


def load_era5_netcdf(nc_path, lat, lon):
    """
    Parse ERA5 NetCDF → hourly DataFrame with u10, v10, ws10, u100, v100, ws100.
    """
    try:
        import netCDF4 as nc
        ds = nc.Dataset(nc_path)
        # Find nearest grid point
        lats = ds.variables["latitude"][:]
        lons = ds.variables["longitude"][:]
        lat_idx = int(np.argmin(np.abs(lats - lat)))
        lon_idx = int(np.argmin(np.abs(lons - lon)))

        times = nc.num2date(ds.variables["time"][:], ds.variables["time"].units)
        timestamps = pd.to_datetime([t.strftime("%Y-%m-%d %H:%M") for t in times])

        u10  = ds.variables["u10"][:, lat_idx, lon_idx]
        v10  = ds.variables["v10"][:, lat_idx, lon_idx]
        u100 = ds.variables["u100"][:, lat_idx, lon_idx]
        v100 = ds.variables["v100"][:, lat_idx, lon_idx]

        df = pd.DataFrame({
            "timestamp": timestamps,
            "u10": u10, "v10": v10,
            "ws10": np.sqrt(u10**2 + v10**2),
            "u100": u100, "v100": v100,
            "ws100": np.sqrt(u100**2 + v100**2),
        }).set_index("timestamp")
        df["source"] = "ERA5"
        return df, "era5"
    except Exception as e:
        return None, f"netcdf_error:{e}"
