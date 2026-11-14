"""Lab C: ONE file holding several measurements with unhelpful channel names.

    python scripts/make_lab_c.py

data/lab_C.h5: three acquisitions (groups ``scan_000`` .. ``scan_002``, e.g. a kinetics
series where the absorption band grows). Each holds a dark, a reference and a sample spectrum,
but the channel names say nothing (``CH00``, ``ch_1``, ``noir``...). Only the annotations tell
what each spectrum is.
"""
from pathlib import Path

import numpy as np
from pymodaq_data.data import Axis, DataRaw, DataToExport
from pymodaq_data.h5modules.data_saving import DataToExportSaver
from pymodaq_data.h5modules.saving import H5SaverLowLevel

from spectrum_demo import simulation as sim
from spectrum_demo import vocab as v

DATA = Path(__file__).resolve().parent.parent / "data"
# the names differ from one scan to the next, as they do when several people/set-ups feed a file
NAMES = [("CH00", "CH01", "CH02"), ("noir", "ref", "echantillon"), ("ch_a", "ch_b", "ch_c")]


def make_scan(index: int, rng) -> DataToExport:
    spectro = sim.MockSpectrograph(n_pixels=512, absorption=0.1 * (index + 1))
    shots = [(False, False, v.SPECTRO.DarkSpectrum),
             (True, False, v.SPECTRO.ReferenceSpectrum),
             (True, True, v.SPECTRO.SampleSpectrum)]
    out = []
    for name, (shutter, sample, concept) in zip(NAMES[index], shots):
        values = spectro.simulate_spectrum(shutter_open=shutter, sample=sample, rng=rng)
        axis = Axis(label="Wavelength", units="nm", data=spectro.wavelengths, index=0)
        axis.add_extra_attribute(**{v.QUANTITY_KIND: str(v.QK.Wavelength),
                                    v.UNIT_IRI: str(v.UNIT.NanoM)})
        dwa = DataRaw(name, data=[values], units="counts", axes=[axis], labels=[name])
        dwa.add_extra_attribute(**{v.SEMANTIC_IRI: str(concept),
                                   v.QUANTITY_KIND: str(v.QK.Count),
                                   v.UNIT_IRI: str(v.UNIT.NUM)})
        out.append(dwa)
    return DataToExport(f"scan_{index:03d}", data=out)


def main():
    DATA.mkdir(exist_ok=True)
    rng = np.random.default_rng(3)
    path = DATA / "lab_C.h5"
    h5 = H5SaverLowLevel()
    h5.init_file(file_name=path, new_file=True,
                 metadata={"lab": "Lab C", v.TECHNIQUE_IRI: str(v.UV_VIS_SPECTROPHOTOMETRY)})
    try:
        for i in range(3):
            group = h5.get_set_group(h5.raw_group, f"scan_{i:03d}")
            DataToExportSaver(h5).add_data(group, make_scan(i, rng))
    finally:
        h5.close_file()
    print("written", path)


if __name__ == "__main__":
    main()
