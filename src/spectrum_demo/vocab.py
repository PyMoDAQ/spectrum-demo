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

# Names of the extra attributes. The same pattern is used on a DataWithAxes and on each of its
# Axis, so an axis describes itself exactly like the data does.
SEMANTIC_IRI = "semantic_iri"    # what the dataset IS (spectro:SampleSpectrum, ...); data only
QUANTITY_KIND = "quantity_kind"  # QUDT quantity kind of the values (data) or of the axis
UNIT_IRI = "unit_iri"            # QUDT unit of the values (data) or of the axis

ANNOTATION_KEYS = (SEMANTIC_IRI, QUANTITY_KIND, UNIT_IRI)   # on a DataWithAxes
AXIS_ANNOTATION_KEYS = (QUANTITY_KIND, UNIT_IRI)            # on an Axis

# Attribute written on the file's RawData group
TECHNIQUE_IRI = "technique_iri"
UV_VIS_SPECTROPHOTOMETRY = OBO.CHMO_0000292
