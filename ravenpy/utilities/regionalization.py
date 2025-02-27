"""
Tools for hydrological regionalization.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import xarray as xr

import ravenpy.models as models

from . import coords

LOGGER = logging.getLogger("PYWPS")

regionalisation_data_dir = Path(__file__).parent.parent / "data" / "regionalisation"


def regionalize(
    method,
    model,
    nash,
    params=None,
    props=None,
    target_props=None,
    size=5,
    min_NSE=0.6,
    **kwds,
):
    """Perform regionalization for catchment whose outlet is defined by coordinates.

    Parameters
    ----------
    method : {'MLR', 'SP', 'PS', 'SP_IDW', 'PS_IDW', 'SP_IDW_RA', 'PS_IDW_RA'}
      Name of the regionalization method to use.
    model : {'HMETS', 'GR4JCN', 'MOHYSE'}
      Model name.
    nash : pd.Series
      NSE values for the parameters of gauged catchments.
    params : pd.DataFrame
      Model parameters of gauged catchments. Needed for all but MRL method.
    props : pd.DataFrame
      Properties of gauged catchments to be analyzed for the regionalization. Needed for MLR and RA methods.
    target_props : pd.Series or dict
      Properties of ungauged catchment. Needed for MLR and RA methods.
    size : int
      Number of catchments to use in the regionalization.
    min_NSE : float
      Minimum calibration NSE value required to be considered as a donor.
    kwds : {}
      Model configuration parameters, including the forcing files (ts).

    Returns
    -------
    (qsim, ensemble)
    qsim : DataArray (time, )
      Multi-donor averaged predicted streamflow.
    ensemble : Dataset
      q_sim : DataArray  (realization, time)
        Ensemble of members based on number of donors.
      parameter : DataArray (realization, param)
        Parameters used to run the model.
    """
    # TODO: Include list of available properties in docstring.
    # TODO: Add error checking for source, target stuff wrt method chosen.

    # Select properties based on those available in the ungauged properties DataFrame.
    if isinstance(target_props, dict):
        ungauged_properties = pd.Series(target_props)
    elif isinstance(target_props, pd.Series):
        ungauged_properties = target_props
    elif isinstance(target_props, pd.DataFrame):
        ungauged_properties = target_props.to_series()
    else:
        raise ValueError

    cr = coords.realization(1 if method == "MLR" else size)
    cp = coords.param(model)

    # Filter on NSE
    valid = nash > min_NSE
    filtered_params = params.where(valid).dropna()
    filtered_prop = props.where(valid).dropna()

    # Check to see if we have enough data, otherwise raise error
    if len(filtered_prop) < size and method != "MLR":
        raise ValueError(
            "Hydrological_model and minimum NSE threshold \
                         combination is too strict for the number of donor \
                         basins. Please reduce the number of donor basins OR \
                         reduce the minimum NSE threshold."
        )

    # Rank the matrix according to the similarity or distance.
    if method in ["PS", "PS_IDW", "PS_IDW_RA"]:  # Physical similarity
        dist = similarity(filtered_prop, ungauged_properties)
    else:  # Geographical distance.
        dist = distance(filtered_prop, ungauged_properties)

    # Series of distances for the first `size` best donors
    sdist = dist.sort_values().iloc[:size]

    # Pick the donors' model parameters and catchment properties
    sparams = filtered_params.loc[sdist.index]
    sprop = filtered_prop.loc[sdist.index]

    # Get the list of parameters to run
    reg_params = regionalization_params(
        method, sparams, sprop, ungauged_properties, filtered_params, filtered_prop
    )

    # Run the model over all parameters and create ensemble DataArray
    m = models.get_model(model)()
    qsims = list()

    for i, params in enumerate(reg_params):
        kwds["params"] = params
        kwds["run_name"] = f"reg_{i}"
        m(**kwds)
        qsims.append(m.q_sim.copy(deep=True))

    qsims = xr.concat(qsims, dim=cr)

    # 3. Aggregate runs into a single result -> dataset
    if method in [
        "MLR",
        "SP",
        "PS",
    ]:  # Average (one realization for MLR, so no effect).
        qsim = qsims.mean(dim="realization", keep_attrs=True)
    elif (
        "IDW" in method
    ):  # Here we are replacing the mean by the IDW average, keeping attributes and dimensions.
        qsim = IDW(qsims, sdist)
    else:
        raise ValueError("No matching algorithm for {}".format(method))

    # Metadata handling
    # TODO: Store the basin_name

    # Create a DataArray for the parameters used in the regionalization
    param_da = xr.DataArray(
        reg_params,
        dims=("realization", "param"),
        coords={"param": cp, "realization": cr},
        attrs={"long_name": "Model parameters used in the regionalization."},
    )

    ens = xr.Dataset(
        data_vars={"q_sim": qsims, "parameter": param_da},
        attrs={
            "title": "Regionalization ensemble",
            "institution": "",
            "source": "RAVEN V.{} - {}".format(m.version, model),
            "history": "Created by raven regionalize.",
            "references": "",
            "comment": "Regionalization method: {}".format(method),
        },
    )

    # TODO: Add global attributes (model name, date, version, etc)
    return qsim, ens


def read_gauged_properties(properties):
    """Return table of gauged catchments properties over North America.

    Returns
    -------
    pd.DataFrame
      Catchment properties keyed by catchment ID.
    """
    f = regionalisation_data_dir / "gauged_catchment_properties.csv"
    proptable = pd.read_csv(f, index_col="ID")

    return proptable[properties]


def read_gauged_params(model):
    """Return table of NASH-Stucliffe Efficiency values and model parameters for North American catchments.

    Returns
    -------
    pd.DataFrame
      Nash-Sutcliffe Efficiency keyed by catchment ID.
    pd.DataFrame
      Model parameters keyed by catchment ID.
    """
    f = regionalisation_data_dir / f"{model}_parameters.csv"
    params = pd.read_csv(f, index_col="ID")

    return params["NASH"], params.iloc[:, 1:]


def haversine(lon1, lat1, lon2, lat2):
    """
    Return the great circle distance between two points on the earth.

    Parameters
    ----------
    lon1, lat1 : ndarray
        Longitude and latitude coordinates in decimal degrees.
    lon2, lat2 : ndarray
        Longitude and latitude coordinates in decimal degrees.

    Returns
    -------
    ndarray
      Distance between points 1 and 2 [km].

    """
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * (
        np.sin(dlon / 2.0) ** 2
    )

    c = 2 * np.arcsin(np.sqrt(a))
    km = 6367 * c
    return km


def distance(gauged, ungauged):
    """Return geographic distance [km] between ungauged and database of gauged catchments.

    Parameters
    ----------
    gauged : pd.DataFrame
      Table containing columns for longitude and latitude of catchment's centroid.
    ungauged : pd.Series
      Coordinates of the ungauged catchment.

    """
    lon, lat = ungauged.longitude, ungauged.latitude
    lons, lats = gauged.longitude, gauged.latitude

    return pd.Series(
        data=haversine(lons.values, lats.values, lon, lat), index=gauged.index
    )


def similarity(gauged, ungauged, kind="ptp"):
    """Return similarity measure between gauged and ungauged catchments.

    Parameters
    ----------
    gauged : DataFrame
      Gauged catchment properties.
    ungauged : DataFrame
      Ungauged catchment properties
    kind : {'ptp', 'std', 'iqr'}
      Normalization method: peak to peak (maximum - minimum), standard deviation, interquartile range.

    """

    stats = gauged.describe()

    if kind == "ptp":
        spread = stats.loc["max"] - stats.loc["min"]
    elif kind == "std":
        spread = stats.loc["std"]
    elif kind == "iqr":
        spread = stats.loc["75%"] - stats.loc["25%"]

    d = ungauged.values - gauged.values
    n = np.abs(d) / spread.values
    return pd.Series(data=n.sum(axis=1), index=gauged.index)


def regionalization_params(
    method,
    gauged_params,
    gauged_properties,
    ungauged_properties,
    filtered_params,
    filtered_prop,
):
    """Return the model parameters to use for the regionalization.

    Parameters
    ----------
    method : {'MLR', 'SP', 'PS', 'SP_IDW', 'PS_IDW', 'SP_IDW_RA', 'PS_IDW_RA'}
      Name of the regionalization method to use.
    gauged_params
      DataFrame of parameters for donor catchments (size = number of donors)
    gauged_properties
      DataFrame of properties of the donor catchments  (size = number of donors)
    ungauged_properties
      DataFrame of properties of the ungauged catchment (size = 1)
    filtered_params
      DataFrame of parameters of all filtered catchments (size = all catchments with NSE > min_NSE)
    filtered_prop
      DataFrame of properties of all filtered catchments (size = all catchments with NSE > min_NSE)

    Returns
    -------
    list
      List of model parameters to be used for the regionalization.
    """

    if method == "MLR" or "RA" in method:
        mlr_params, r2 = multiple_linear_regression(
            filtered_prop, filtered_params, ungauged_properties.to_frame().T
        )

        if method == "MLR":  # Return the multiple linear regression parameters.
            out = [
                mlr_params,
            ]

        elif "RA" in method:
            gp = gauged_params.copy()

            for p, r, col in zip(mlr_params, r2, gauged_params):
                # If we have an R2 > 0.5 then we consider this to be a better estimator

                if r > 0.5:
                    gp[col] = p

            out = gp.values

    else:
        out = gauged_params.values

    return out


def IDW(qsims, dist):
    """
    Inverse distance weighting.

    Parameters
    ----------
    qsims : DataArray
      Ensemble of hydrogram stacked along the `realization` dimension.
    dist : pd.Series
      Distance from catchment which generated each hydrogram to target catchment.

    Returns
    -------
    DataArray
      Inverse distance weighted average of ensemble.
    """

    # In IDW, weights are 1 / distance
    weights = xr.DataArray(
        1.0 / dist, dims="realization", coords={"realization": qsims.realization}
    )

    # Make weights sum to one
    weights /= weights.sum(axis=0)

    # Calculate weighted average.
    out = qsims.dot(weights)
    out.name = qsims.name
    out.attrs = qsims.attrs
    return out


def multiple_linear_regression(source, params, target):
    """
    Multiple Linear Regression for model parameters over catchment properties.

    Uses known catchment properties and model parameters to estimate model parameter over an
    ungauged catchment using its properties.

    Parameters
    ----------
    source : DataFrame
      Properties of gauged catchments.
    params : DataFrame
      Model parameters of gauged catchments.
    target : DataFrame
      Properties of the ungauged catchment.


    Returns
    -------
    (mrl_params, r2)
      A named tuple of the estimated model parameters and the R2 of the linear regression.
    """
    # Add constants to the gauged predictors
    x = sm.add_constant(source)

    # Add the constant 1 for the ungauged catchment predictors
    predictors = sm.add_constant(target, prepend=True, has_constant="add")

    # Perform regression for each parameter
    regression = [sm.OLS(params[param].values, x).fit() for param in params]

    # Perform prediction on each parameter based on the predictors
    mlr_parameters = [r.predict(exog=predictors)[0] for r in regression]

    # Extract the adjusted r_squared value for each parameter
    r2 = [r.rsquared_adj for r in regression]

    return mlr_parameters, r2
