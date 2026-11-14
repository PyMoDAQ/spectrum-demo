"""Write the simulated datasets in data/ (PyMoDAQ HDF5 files).

    python scripts/make_datasets.py

data/lab_A.h5, data/lab_B.h5            : annotated
data/lab_A_plain.h5, data/lab_B_plain.h5: same data without annotations
"""
from pathlib import Path

from spectrum_demo import simulation, storage
from spectrum_demo import vocab as v

DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    DATA.mkdir(exist_ok=True)
    for lab, make in (("A", simulation.make_lab_a), ("B", simulation.make_lab_b)):
        storage.save(DATA / f"lab_{lab}.h5", make(annotate=True), lab=f"Lab {lab}",
                     **{v.TECHNIQUE_IRI: str(v.UV_VIS_SPECTROPHOTOMETRY)})
        storage.save(DATA / f"lab_{lab}_plain.h5", make(annotate=False), lab=f"Lab {lab}")
    print("written:", *sorted(p.name for p in DATA.glob("*.h5")))


if __name__ == "__main__":
    main()
