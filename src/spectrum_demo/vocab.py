"""IRIs used by the demo, and the names of the annotation attributes.

An *annotation* is a handful of extra attributes attached to a PyMoDAQ
``DataWithAxes`` (via ``add_extra_attribute``). PyMoDAQ already saves them
in the HDF5 file next to the data and reloads them, so the annotations travel
with the data.
"""
from rdflib import Namespace

SPECTRO = Namespace("https://w3id.org/pymodaq/spectro#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
QK = Namespace("http://qudt.org/vocab/quantitykind/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
OBO = Namespace("http://purl.obolibrary.org/obo/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
PROV = Namespace("http://www.w3.org/ns/prov#")

# Names of the extra attributes written on each DataWithAxes
SEMANTIC_IRI = "semantic_iri"              # what the spectrum IS (spectro:SampleSpectrum, ...)
QUANTITY_KIND = "quantity_kind"            # QUDT quantity kind of the values
UNIT_IRI = "unit_iri"                      # QUDT unit of the values
AXIS_QUANTITY_KIND = "axis_quantity_kind"  # QUDT quantity kind of the spectral axis
AXIS_UNIT_IRI = "axis_unit_iri"            # QUDT unit of the spectral axis

ANNOTATION_KEYS = (SEMANTIC_IRI, QUANTITY_KIND, UNIT_IRI, AXIS_QUANTITY_KIND, AXIS_UNIT_IRI)

# Attribute written on the file's RawData group
TECHNIQUE_IRI = "technique_iri"
UV_VIS_SPECTROPHOTOMETRY = OBO.CHMO_0000292
