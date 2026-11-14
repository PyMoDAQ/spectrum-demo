"""Simulated UV-vis absorption data from two imaginary labs.

``MockSpectrograph`` is copied from Bernhard Lang's PyMoDAQ extension tutorial
(https://github.com/bernhardlang/pymodaq_plugins_tutorial_extension,
``hardware/controller.py``, MIT licence, (c) 2026 Bernhard Lang), reduced to
what is needed here. It simulates a grating spectrometer with a dark shutter,
detector noise and a sample with an absorption band.

Both labs measure the same molecule (absorption band centred at 450 nm,
maximum absorbance 0.3), but they record and name things differently:

* **Lab A** (a PyMoDAQ set-up like the tutorial one): three raw spectra in
  detector counts, named ``background``, ``reference`` and ``signal``, along
  a wavelength axis in nm.
* **Lab B** (a camera spectrometer calibrated in photon energy): a single
  spectrum named ``Trans``, the transmittance already computed in percent,
  along a photon-energy axis in eV, in decreasing order (pixel order).
"""
from dataclasses import dataclass

import numpy as np
from pymodaq_data.data import Axis, DataRaw, DataToExport

from . import vocab as v

HC_EV_NM = 1239.841984  # h*c in eV.nm


# --------------------------------------------------------------------------
# Copied (and trimmed) from B. Lang's tutorial: hardware/controller.py
# --------------------------------------------------------------------------
@dataclass
class MockSpectrograph:
    integration_time: float = 50
    n_pixels: int = 1024
    readout_noise: int = 4
    dark_level: float = 150
    light_level: float = 500
    pe_per_lsb: float = 18.3
    adc_bits: int = 16
    wl_from: float = 300
    wl_to: float = 900
    absorption: float = 0.3

    def __post_init__(self):
        self.calculate_base_data()

    def calculate_base_data(self):
        n_pix = self.n_pixels
        self.wavelengths = np.linspace(self.wl_from, self.wl_to, n_pix)
        self.pixels = np.linspace(0, n_pix - 1, n_pix)
        self.spectrum = np.exp(-((self.pixels - n_pix / 2) / (n_pix / 3)) ** 4)
        self.absorption = self.absorption * np.exp(-((self.pixels - n_pix / 4) / (n_pix / 8)) ** 2)

    def simulate_spectrum(self, shutter_open: bool, sample: bool, rng=np.random):
        data = rng.normal(loc=self.dark_level * self.integration_time,
                          scale=self.readout_noise, size=self.n_pixels)
        if shutter_open:
            light = self.spectrum * self.light_level * self.integration_time * self.pe_per_lsb
            if sample:
                light *= np.power(10, -self.absorption)
            data += rng.poisson(light) / self.pe_per_lsb
        max_adc = (1 << self.adc_bits) - 1
        return np.where(data < max_adc, np.floor(data), max_adc)
# --------------------------------------------------------------------------


def true_absorbance(wavelength_nm):
    """Absorbance of the simulated molecule (same band as MockSpectrograph defaults)."""
    return 0.3 * np.exp(-((np.asarray(wavelength_nm) - 450.0) / 75.0) ** 2)


def make_lab_a(annotate: bool = True, seed: int = 1) -> DataToExport:
    """Lab A: raw dark / reference / sample spectra in counts, wavelength axis in nm."""
    rng = np.random.default_rng(seed)
    spectro = MockSpectrograph(n_pixels=512)
    dark = spectro.simulate_spectrum(shutter_open=False, sample=False, rng=rng)
    reference = spectro.simulate_spectrum(shutter_open=True, sample=False, rng=rng)
    signal = spectro.simulate_spectrum(shutter_open=True, sample=True, rng=rng)

    def spectrum(name, values, concept):
        axis = Axis(label="Wavelength", units="nm", data=spectro.wavelengths, index=0)
        dwa = DataRaw(name, data=[values], units="counts", axes=[axis], labels=[name])
        if annotate:
            # the axis describes itself, like the data does
            axis.add_extra_attribute(**{v.QUANTITY_KIND: str(v.QK.Wavelength),
                                        v.UNIT_IRI: str(v.UNIT.NanoM)})
            dwa.add_extra_attribute(**{v.SEMANTIC_IRI: str(concept),
                                       v.QUANTITY_KIND: str(v.QK.Count),
                                       v.UNIT_IRI: str(v.UNIT.NUM)})
        return dwa

    return DataToExport("LabA", data=[
        spectrum("background", dark, v.SPECTRO.DarkSpectrum),
        spectrum("reference", reference, v.SPECTRO.ReferenceSpectrum),
        spectrum("signal", signal, v.SPECTRO.SampleSpectrum),
    ])


def make_lab_b(annotate: bool = True, seed: int = 2, n_pixels: int = 400) -> DataToExport:
    """Lab B: transmittance in percent, photon-energy axis in eV (decreasing)."""
    rng = np.random.default_rng(seed)
    energy_ev = np.linspace(4.0, 1.5, n_pixels)          # pixel order: high to low energy
    wavelength_nm = HC_EV_NM / energy_ev
    transmittance_percent = 100 * 10 ** (-true_absorbance(wavelength_nm))
    transmittance_percent += rng.normal(scale=0.15, size=n_pixels)

    axis = Axis(label="Photon energy", units="eV", data=energy_ev, index=0)
    dwa = DataRaw("Trans", data=[transmittance_percent], units="%", axes=[axis], labels=["Trans"])
    if annotate:
        axis.add_extra_attribute(**{v.QUANTITY_KIND: str(v.QK.Energy),
                                    v.UNIT_IRI: str(v.UNIT.EV)})
        dwa.add_extra_attribute(**{v.SEMANTIC_IRI: str(v.SPECTRO.TransmittanceSpectrum),
                                   v.QUANTITY_KIND: str(v.QK.Transmittance),
                                   v.UNIT_IRI: str(v.UNIT.PERCENT)})
    return DataToExport("LabB", data=[dwa])
