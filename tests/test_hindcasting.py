import datetime as dt
import tempfile

from fiona.io import ZipMemoryFile

from ravenpy.models import GR4JCN
from ravenpy.utilities import forecasting
from ravenpy.utilities.testdata import get_test_data

"""
Test to perform a hindcast using Caspar data on THREDDS.
Currently only runs GEPS, eventually will run GEPS, GDPS, REPS and RDPS.
To do so will need to add the actual data from Caspar, currently being downloaded
but this is a good proof of concept.
"""


class TestHindcasting:
    def test_hindcasting_GEPS(self, tmpdir):

        # Set the hindcasting date
        date = dt.datetime(2018, 6, 1)

        # Prepare a RAVEN model run using historical data, GR4JCN in this case.
        # This is a dummy run to get initial states. In a real forecast situation,
        # this run would end on the day before the forecast, but process is the same.
        ts = get_test_data(
            "raven-gr4j-cemaneige", "Salmon-River-Near-Prince-George_meteo_daily.nc"
        )
        model = GR4JCN(workdir=tmpdir)
        model(
            ts,
            start_date=dt.datetime(2000, 1, 1),
            end_date=dt.datetime(2002, 6, 1),
            area=44250.6,
            elevation=843.0,
            latitude=54.4848,
            longitude=-123.3659,
            params=(0.529, -3.396, 407.29, 1.072, 16.9, 0.947),
        )

        # Extract the final states that will be used as the next initial states
        rvc = model.outputs["solution"]

        # Collect the hindcast data for the date, location and climate model.
        # Limited to GEPS for now, for a restricted period (2017-06-01 to 2018-08-31)
        with open(get_test_data("watershed_vector", "LSJ_LL.zip")[0], "rb") as f:
            with ZipMemoryFile(f.read()) as z:
                region_coll = z.open("LSJ_LL.shp")
                fcst = forecasting.get_hindcast_day(
                    region_coll, date, climate_model="GEPS"
                )

        # write the forecast data to file
        ts = f"{tmpdir}/fcstfile.nc"
        fcst.to_netcdf(ts)

        # It is necessary to clean the model state because the input variables of the previous
        # model are not the same as the ones provided in the forecast model. therefore, if we
        # do not clean, the model will simply add the hindcast file to the list of available
        # data provided in the testdata above. Then the dates will not work, and the model errors.
        model = GR4JCN()

        model.rvc.parse(rvc.read_text())

        # And run the model with the forecast data.
        model(
            ts=ts,
            nc_index=range(fcst.dims.get("member")),
            start_date=dt.datetime(2018, 6, 1),
            end_date=dt.datetime(2018, 6, 10),
            area=44250.6,
            elevation=843.0,
            latitude=54.4848,
            longitude=-123.3659,
            params=(0.529, -3.396, 407.29, 1.072, 16.9, 0.947),
            overwrite=True,
            pr={
                "linear_transform": (1000.0, 0.0),
                "time_shift": -0.25,
                "deaccumulate": True,
            },
            tas={"time_shift": -0.25},
        )

        # The model now has the forecast data generated and it has 10 days of forecasts.
        assert len(model.q_sim.values) == 10
        # Also see if GEPS has 20 members produced.
        assert model.q_sim.values.shape[1] == 20
