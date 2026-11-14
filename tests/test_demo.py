import pytest
from rdflib import Graph

from spectrum_demo import analysis, semantics, simulation, storage


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    folder = tmp_path_factory.mktemp("data")
    out = {}
    for lab, make in (("A", simulation.make_lab_a), ("B", simulation.make_lab_b)):
        out[lab] = storage.save(folder / f"lab_{lab}.h5", make(annotate=True), lab=f"Lab {lab}")
        out[lab + "_plain"] = storage.save(folder / f"lab_{lab}_plain.h5", make(annotate=False))
    return out


def test_annotations_survive_save_and_load(files):
    dte, _ = storage.load(files["B"])
    assert dte[0].unit_iri == "http://qudt.org/vocab/unit/PERCENT"
    assert dte[0].axes[0].unit_iri == "http://qudt.org/vocab/unit/EV"
    assert dte[0].axes[0].quantity_kind.endswith("quantitykind/Energy")
    assert dte[0].semantic_iri.endswith("#TransmittanceSpectrum")


@pytest.mark.parametrize("lab", ["A", "B"])
def test_generic_analysis_finds_the_band(files, lab):
    dte, _ = storage.load(files[lab])
    result = analysis.analyse(dte)
    assert result.peak_wavelength_nm == pytest.approx(450, abs=5)
    assert result.peak_absorbance == pytest.approx(0.3, abs=0.02)


def test_lab_scripts_fail_on_the_other_lab(files):
    a, _ = storage.load(files["A_plain"])
    b, _ = storage.load(files["B_plain"])
    with pytest.raises(AttributeError):
        analysis.lab_a_script(b)
    wrong = analysis.lab_b_script(a)          # silently wrong
    assert wrong.peak_absorbance < 0


def test_missing_annotations_are_reported(files):
    dte, _ = storage.load(files["B_plain"])
    with pytest.raises(analysis.AnnotationError, match="semantic_iri.*axis quantity_kind"):
        analysis.analyse(dte)


def test_jsonld_roundtrip(files, tmp_path):
    dte, attrs = storage.load(files["A"])
    path = semantics.export_jsonld(dte, tmp_path / "a.jsonld", "https://example.org/a.h5", attrs,
                                   analysis.analyse(dte))
    g = Graph().parse(path, format="json-ld")
    assert len(g) > 20


def test_ontology_hierarchy():
    from spectrum_demo.vocab import SPECTRO
    assert semantics.is_a(SPECTRO.DarkSpectrum, SPECTRO.IntensitySpectrum)
    assert not semantics.is_a(SPECTRO.TransmittanceSpectrum, SPECTRO.IntensitySpectrum)


def test_concept_tree_groups_datasets_of_both_labs_by_concept(files):
    from spectrum_demo import views
    loaded = {"Lab A": storage.load(files["A"])[0], "Lab B": storage.load(files["B"])[0]}
    results = {lab: analysis.analyse(dte) for lab, dte in loaded.items()}
    tree = views.concept_tree(loaded, results)

    def parent_label(label, file):
        return next(n.label for n in tree.walk() if any(c.label == label and c.file == file
                                                       for c in n.children))
    assert parent_label("background", "Lab A") == "dark spectrum"
    assert parent_label("reference", "Lab A") == "reference spectrum"
    assert parent_label("signal", "Lab A") == "sample spectrum"
    assert parent_label("Trans", "Lab B") == "transmittance spectrum"
    assert parent_label("absorbance", "Lab B") == "absorbance spectrum"
    # the three intensity spectra sit under "intensity spectrum", the transmittance does not
    intensity = tree.find("intensity spectrum")
    assert {c.label for c in intensity.children} == {"dark spectrum", "reference spectrum",
                                                     "sample spectrum"}
    # provenance links and the HDF5 path of each dataset (what a double click loads)
    assert [d.label for d in tree.find("absorbance", "Lab A").derived_from] == \
        ["background", "reference", "signal"]
    leaf = tree.find("Trans", "Lab B")
    assert storage.load_node(files["B"], leaf.path).name == "Trans"


def test_quantity_tree_and_text_rendering(files):
    from spectrum_demo import views
    loaded = {"Lab A": storage.load(files["A"])[0], "Lab B": storage.load(files["B"])[0]}
    text = views.render_text(views.quantity_tree(loaded), show_path=False)
    assert "Transmittance" in text and "Percent" in text and "Lab B: Trans" in text
