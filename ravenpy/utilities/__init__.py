from .regionalization import regionalize, read_gauged_properties, read_gauged_params

gis_error_message = (
        "`{}` requires installation of the RavenPy GIS libraries. These can be installed using the"
        " `pip install ravenpy[gis]` recipe or via Anaconda (`conda env -n ravenpy-env -f environment.yml`)"
        " from the RavenPy repository source files."
    )
