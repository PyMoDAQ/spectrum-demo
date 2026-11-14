"""Save and reload a DataToExport with PyMoDAQ's own HDF5 savers.

Nothing specific to the ontology happens here: PyMoDAQ already writes the
``units`` and every ``extra_attribute`` of each DataWithAxes as HDF5
attributes, and gives them back on loading.
"""
from pathlib import Path

from pymodaq_data.data import DataToExport
from pymodaq_data.h5modules.data_saving import DataLoader, DataToExportSaver
from pymodaq_data.h5modules.saving import H5SaverLowLevel


def save(path, dte: DataToExport, detector: str = "Spectrometer", **file_metadata) -> Path:
    """Write ``dte`` in a new PyMoDAQ HDF5 file; ``file_metadata`` goes on the RawData group."""
    path = Path(path)
    h5 = H5SaverLowLevel()
    h5.init_file(file_name=path, new_file=True, metadata=file_metadata)
    try:
        group = h5.get_set_group(h5.raw_group, detector)
        DataToExportSaver(h5).add_data(group, dte)
    finally:
        h5.close_file()
    return path


def load(path) -> tuple[DataToExport, dict]:
    """Reload all data of a PyMoDAQ HDF5 file, plus the attributes of its RawData group."""
    h5 = H5SaverLowLevel()
    h5.init_file(file_name=Path(path), new_file=False, mode="r")
    try:
        dte = DataLoader(h5).load_all("/RawData", DataToExport(Path(path).stem))
        attrs = {k: (str(val) if not isinstance(val, (int, float)) else val)
                 for k, val in h5.raw_group.attrs.to_dict().items()
                 if k not in ("CLASS", "TITLE", "VERSION")}
    finally:
        h5.close_file()
    return dte, attrs
