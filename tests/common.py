from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


def count_pixels(stats: dict, numeric_categories=False) -> int:
    category_counts = 0
    for key, val in stats.items():
        if numeric_categories:
            try:
                int(key)
            except ValueError:
                continue
        if key in ["count", "min", "max", "mean", "median", "sum", "nodata"]:
            continue
        category_counts += val
    return category_counts


def synthetic_gr4j_inputs(path):

    time = pd.date_range(start="2000-07-01", end="2002-07-01", freq="D")

    pr = 3 * np.ones(len(time))
    pr = xr.DataArray(pr, coords={"time": time}, dims="time", name="pr")
    pr.to_netcdf(Path(path).joinpath("pr.nc"))

    tas = 280 + 20 * np.cos(np.arange(len(time)) * 2 * np.pi / 365.0)
    tas = xr.DataArray(tas, coords={"time": time}, dims="time", name="tas")
    tas.to_netcdf(Path(path).joinpath("tas.nc"))

    evap = 3 + 3 * np.cos(-30 + np.arange(len(time)) * 2 * np.pi / 365.0)
    evap = xr.DataArray(evap, coords={"time": time}, dims="time", name="evap")
    evap.to_netcdf(Path(path).joinpath("evap.nc"))


def make_bnds(params, delta):
    """Return low and high parameter bounds by subtracting and adding delta*params to params.

    Parameters
    ----------
    params : sequence
      Parameters.
    delta : float [0,1]
      Relative delta to subtract and add to parameters.

    Returns
    -------
    (tuple, tuple)
      Low and high bounds for parameters.

    """
    arr = np.asarray(params)
    d = np.abs(arr * delta)
    return tuple(arr - d), tuple(arr + d)


def _convert_2d(fn):
    """Take the 1D Salmon time series and convert it to a 2D time series.

    Example
    -------
    >>> fn = "./testdata/raven-gr4j-cemaneige/Salmon-River-Near-Prince-George_meteo_daily.nc"
    >>> fn2 = "./testdata/raven-gr4j-cemaneige/Salmon-River-Near-Prince-George_meteo_daily_2d.nc"
    >>> _convert_2d(fn).to_netcdf(fn2, 'w')
    """

    features = {
        "name": "Salmon",
        "area": 4250.6,
        "elevation": 843.0,
        "latitude": 54.4848,
        "longitude": -123.3659,
    }

    ds = xr.open_dataset(fn, decode_times=False).rename({"nstations": "region"})

    for v in ds.data_vars:
        if v not in ["lon", "lat"]:
            ds[v] = ds[v].expand_dims("region", axis=1)

    # Add geometry feature variables
    for key, val in features.items():
        ds[key] = xr.DataArray(name=key, data=[val], dims=("region"))

    return ds


def _convert_3d(fn):
    """Take the 1D Salmon time series and convert it to a 3D time series.

    Example
    -------
    >>> fn = "./testdata/raven-gr4j-cemaneige/Salmon-River-Near-Prince-George_meteo_daily.nc"
    >>> fn3 = "./testdata/raven-gr4j-cemaneige/Salmon-River-Near-Prince-George_meteo_daily_3d.nc"
    >>> _convert_3d(fn).to_netcdf(fn3, 'w')
    """
    lon = [-123.3659, -120]
    lat = [54.4848, 56]
    ds = xr.open_dataset(fn).rename({"nstations": "lat"})

    out = xr.Dataset(
        coords={"lon": (["lon"], lon), "lat": (["lat"], lat), "time": ds.time}
    )
    for v in ds.data_vars:
        if v not in ["lon", "lat"]:
            data = np.zeros((len(out.time), len(out.lon), len(out.lat)))
            data[:, 1, 0] = ds.data_vars[v].data[:]
            out[v] = xr.DataArray(
                data=data, dims=("time", "lon", "lat"), attrs=ds.data_vars[v].attrs
            )

    return out
