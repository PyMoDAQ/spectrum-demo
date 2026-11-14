"""Three ways to compute an absorbance spectrum from a PyMoDAQ dataset.

1. ``lab_a_script`` / ``lab_b_script``: what each lab writes for its own files.
   The conventions (channel names, units, axis) are hard-coded.
2. ``analyse_with_config``: one script, plus a hand-written configuration per lab.
3. ``analyse``: one script, no configuration. It reads the annotations stored
   with the data and asks the ontology what they mean.
"""
from dataclasses import dataclass, field

import numpy as np
from pymodaq_data.data import DataToExport, DataWithAxes

from . import semantics as sem
from . import vocab as v

H = 6.62607015e-34      # Planck constant, J.s
C = 299792458.0         # speed of light, m/s


@dataclass
class Result:
    wavelength_nm: np.ndarray
    absorbance: np.ndarray
    used: list = field(default_factory=list)       # names of the spectra used
    log: list = field(default_factory=list)        # human-readable reasoning

    @property
    def peak_wavelength_nm(self) -> float:
        return float(self.wavelength_nm[np.nanargmax(self.absorbance)])

    @property
    def peak_absorbance(self) -> float:
        return float(np.nanmax(self.absorbance))

    def __repr__(self):
        return (f"Result(peak at {self.peak_wavelength_nm:.1f} nm, "
                f"A max = {self.peak_absorbance:.3f}, from {self.used})")


def _absorbance(transmittance):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(transmittance > 0, -np.log10(transmittance), np.nan)


def _sorted(x, y, used, log):
    order = np.argsort(x)
    return Result(np.asarray(x)[order], np.asarray(y)[order], used, log)


# =========================================================================
# 1. Scripts written by each lab for its own files (no annotations needed)
# =========================================================================

def lab_a_script(dte: DataToExport) -> Result:
    """Lab A knows its channels are called background / reference / signal, in nm."""
    dark = dte.get_data_from_name("background")
    ref = dte.get_data_from_name("reference")
    sig = dte.get_data_from_name("signal")
    wavelength = sig.axes[0].get_data()
    t = (sig[0] - dark[0]) / (ref[0] - dark[0])
    return _sorted(wavelength, _absorbance(t), ["background", "reference", "signal"], [])


def lab_b_script(dte: DataToExport) -> Result:
    """Lab B knows its file holds one transmittance spectrum in percent, versus eV."""
    data = dte[0]
    wavelength = 1239.841984 / data.axes[0].get_data()
    return _sorted(wavelength, _absorbance(data[0] / 100), [data.name], [])


# =========================================================================
# 2. One script + a hand-written configuration per lab
# =========================================================================

#: Someone has to read each lab's documentation (or ask them) to write this.
MANUAL_CONFIG = {
    "LabA": dict(dark="background", reference="reference", sample="signal", axis="nm"),
    "LabB": dict(transmittance="Trans", transmittance_scale=0.01, axis="eV"),
}


def analyse_with_config(dte: DataToExport, config: dict) -> Result:
    first = dte[0]
    x = first.axes[0].get_data()
    if config["axis"] == "eV":
        x = 1239.841984 / x
    if "transmittance" in config:
        t = dte.get_data_from_name(config["transmittance"])[0] * config["transmittance_scale"]
        used = [config["transmittance"]]
    else:
        d, r, s = (dte.get_data_from_name(config[k])[0] for k in ("dark", "reference", "sample"))
        t = (s - d) / (r - d)
        used = [config[k] for k in ("dark", "reference", "sample")]
    return _sorted(x, _absorbance(t), used, [])


# =========================================================================
# 3. One script, no configuration: the annotations + the ontology
# =========================================================================

class AnnotationError(ValueError):
    """Raised when the data does not carry what the analysis needs (instead of guessing)."""


def check_annotations(dte: DataToExport) -> list:
    """List of human-readable problems; empty if every spectrum is fully annotated."""
    problems = []
    for dwa in dte:
        missing = [k for k in v.ANNOTATION_KEYS if not hasattr(dwa, k)]
        if missing:
            problems.append(f"'{dwa.name}' has no {', '.join(missing)}")
            continue
        for key in (v.UNIT_IRI, v.AXIS_UNIT_IRI):
            try:
                sem.to_si_factor(getattr(dwa, key))
            except KeyError:
                problems.append(f"'{dwa.name}': unit {getattr(dwa, key)} unknown to the ontology")
    return problems


def _find(dte: DataToExport, cls) -> list:
    return [dwa for dwa in dte if sem.is_a(getattr(dwa, v.SEMANTIC_IRI), cls)]


def _spectral_axis_nm(dwa: DataWithAxes, log: list) -> np.ndarray:
    values = dwa.axes[0].get_data()
    kind = getattr(dwa, v.AXIS_QUANTITY_KIND)
    unit = getattr(dwa, v.AXIS_UNIT_IRI)
    si = values * sem.to_si_factor(unit)
    if kind == str(v.QK.Wavelength):
        log.append(f"axis is a {sem.label(kind)} in {sem.label(unit)}: converted to nm")
        return si / 1e-9
    if kind == str(v.QK.Energy):
        log.append(f"axis is an {sem.label(kind)} in {sem.label(unit)}: "
                   "converted to wavelength with lambda = h c / E")
        return H * C / si / 1e-9
    raise AnnotationError(f"Don't know how to turn a {sem.label(kind)} axis into a wavelength")


def _values_as_fraction(dwa: DataWithAxes, log: list) -> np.ndarray:
    unit = getattr(dwa, v.UNIT_IRI)
    factor = sem.to_si_factor(unit)
    log.append(f"'{dwa.name}' is a {sem.label(getattr(dwa, v.SEMANTIC_IRI))} "
               f"in {sem.label(unit)}: multiplied by {factor:g} (QUDT) to get a fraction")
    return dwa[0] * factor


def analyse(dte: DataToExport) -> Result:
    """Absorbance spectrum of any annotated dataset, whatever its lab conventions."""
    problems = check_annotations(dte)
    if problems:
        raise AnnotationError("Cannot analyse without guessing:\n  - " + "\n  - ".join(problems))
    log = []

    transmittance = _find(dte, v.SPECTRO.TransmittanceSpectrum)
    if transmittance:
        dwa = transmittance[0]
        t = _values_as_fraction(dwa, log)
        used = [dwa.name]
    else:
        roles = {}
        for cls in (v.SPECTRO.DarkSpectrum, v.SPECTRO.ReferenceSpectrum, v.SPECTRO.SampleSpectrum):
            found = _find(dte, cls)
            if len(found) != 1:
                raise AnnotationError(f"Need exactly one {sem.label(cls)}, found {len(found)}")
            roles[cls] = found[0]
            log.append(f"'{found[0].name}' is the {sem.label(cls)}")
        dark, ref, sample = (roles[c][0] for c in (v.SPECTRO.DarkSpectrum,
                                                     v.SPECTRO.ReferenceSpectrum,
                                                     v.SPECTRO.SampleSpectrum))
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (sample - dark) / (ref - dark)
        log.append("transmittance = (sample - dark) / (reference - dark)")
        dwa = roles[v.SPECTRO.SampleSpectrum]
        used = [roles[c].name for c in roles]

    x = _spectral_axis_nm(dwa, log)
    log.append("absorbance = -log10(transmittance); axis sorted by increasing wavelength")
    return _sorted(x, _absorbance(t), used, log)
