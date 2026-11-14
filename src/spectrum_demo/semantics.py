"""Everything that reads the ontology: labels, definitions, class hierarchy,
unit conversion factors, and the JSON-LD export.
"""
from functools import lru_cache
from pathlib import Path

from pymodaq_data.data import DataToExport
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, XSD

from . import vocab as v

ONTOLOGY_DIR = Path(__file__).resolve().parents[2] / "ontology"


@lru_cache(maxsize=1)
def ontology() -> Graph:
    """The demo vocabulary plus the QUDT / CHMO excerpt, as one rdflib graph."""
    g = Graph()
    g.parse(ONTOLOGY_DIR / "spectro.ttl", format="turtle")
    g.parse(ONTOLOGY_DIR / "external_excerpt.ttl", format="turtle")
    return g


def label(iri) -> str:
    g = ontology()
    iri = URIRef(iri)
    for lab in g.objects(iri, RDFS.label):
        if getattr(lab, "language", None) in ("en", None):
            return str(lab)
    return str(iri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def definition(iri) -> str:
    g = ontology()
    iri = URIRef(iri)
    for pred in (SKOS.definition, v.OBO.IAO_0000115, v.QUDT.plainTextDescription):
        for d in g.objects(iri, pred):
            return str(d)
    return ""


def is_a(concept, cls) -> bool:
    """True if ``concept`` is ``cls`` or one of its subclasses (rdfs:subClassOf*)."""
    g = ontology()
    return (URIRef(cls) == URIRef(concept)
            or URIRef(cls) in g.transitive_objects(URIRef(concept), RDFS.subClassOf))


def to_si_factor(unit_iri) -> float:
    """QUDT conversion multiplier of a unit to its SI unit (e.g. PERCENT -> 0.01, NanoM -> 1e-9)."""
    value = ontology().value(URIRef(unit_iri), v.QUDT.conversionMultiplier)
    if value is None:
        raise KeyError(f"No QUDT conversion factor known for unit {unit_iri}")
    return float(value)


# ---------------------------------------------------------------- JSON-LD export

def to_rdf(dte: DataToExport, file_iri: str, file_attrs: dict = None, result=None) -> Graph:
    """Describe a dataset (and optionally the analysis result) as RDF.

    Only the annotations are exported, not the arrays: the HDF5 file stays the
    data container, the RDF is the searchable description of what is in it.
    """
    g = Graph()
    for prefix, ns in [("spectro", v.SPECTRO), ("qudt", v.QUDT), ("quantitykind", v.QK),
                       ("unit", v.UNIT), ("obo", v.OBO), ("prov", v.PROV), ("sosa", v.SOSA)]:
        g.bind(prefix, ns)
    measurement = URIRef(f"{file_iri}#measurement")
    g.add((measurement, RDF.type, v.SPECTRO.AbsorptionMeasurement))
    file_attrs = file_attrs or {}
    if v.TECHNIQUE_IRI in file_attrs:
        g.add((measurement, v.SOSA.usedProcedure, URIRef(file_attrs[v.TECHNIQUE_IRI])))
    if "lab" in file_attrs:
        g.add((measurement, RDFS.label, Literal(f"absorption measurement, {file_attrs['lab']}")))

    nodes = {}
    for dwa in dte:
        if not hasattr(dwa, v.SEMANTIC_IRI):
            continue
        node = URIRef(f"{file_iri}#{dwa.path}" if hasattr(dwa, "path") else f"{file_iri}#{dwa.name}")
        nodes[dwa.name] = node
        g.add((measurement, v.SOSA.hasResult, node))
        g.add((node, RDF.type, URIRef(getattr(dwa, v.SEMANTIC_IRI))))
        g.add((node, RDFS.label, Literal(dwa.name)))
        if hasattr(dwa, "path"):
            g.add((node, v.SPECTRO.hdf5Path, Literal(dwa.path)))
        g.add((node, v.QUDT.hasQuantityKind, URIRef(getattr(dwa, v.QUANTITY_KIND))))
        g.add((node, v.QUDT.hasUnit, URIRef(getattr(dwa, v.UNIT_IRI))))
        axis = BNode()
        g.add((node, v.SPECTRO.hasSpectralAxis, axis))
        g.add((axis, RDF.type, v.SPECTRO.SpectralAxis))
        g.add((axis, v.QUDT.hasQuantityKind, URIRef(getattr(dwa, v.AXIS_QUANTITY_KIND))))
        g.add((axis, v.QUDT.hasUnit, URIRef(getattr(dwa, v.AXIS_UNIT_IRI))))

    if result is not None:
        absorbance = URIRef(f"{file_iri}#absorbance")
        g.add((absorbance, RDF.type, v.SPECTRO.AbsorbanceSpectrum))
        g.add((absorbance, v.QUDT.hasQuantityKind, v.QK.TransmittanceDensity))
        g.add((absorbance, v.QUDT.hasUnit, v.UNIT.UNITLESS))
        for name in result.used:
            g.add((absorbance, v.PROV.wasDerivedFrom, nodes[name]))
        peak = URIRef(f"{file_iri}#absorbance-peak")
        g.add((absorbance, v.SPECTRO.peakWavelength, peak))
        g.add((peak, RDF.type, v.QUDT.QuantityValue))
        g.add((peak, v.QUDT.hasQuantityKind, v.QK.Wavelength))
        g.add((peak, v.QUDT.numericValue, Literal(round(result.peak_wavelength_nm, 1),
                                                  datatype=XSD.double)))
        g.add((peak, v.QUDT.hasUnit, v.UNIT.NanoM))
    return g


def export_jsonld(dte: DataToExport, path, file_iri: str, file_attrs: dict = None,
                  result=None) -> Path:
    g = to_rdf(dte, file_iri, file_attrs, result)
    context = {p: str(ns) for p, ns in g.namespaces()
               if p in ("spectro", "qudt", "quantitykind", "unit", "obo", "prov", "sosa", "rdfs")}
    Path(path).write_text(g.serialize(format="json-ld", context=context, indent=2),
                          encoding="utf-8")
    return Path(path)
