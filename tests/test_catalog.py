from extraction.catalog import DATASETS, get_dataset


def test_datasets_are_isolated():
    sroie = get_dataset("sroie")
    personal = get_dataset("personal")
    funsd = get_dataset("funsd")
    assert sroie.doc_type == "receipt"
    assert personal.doc_type == "receipt"
    assert funsd.doc_type == "form"
    assert sroie.fields == ("merchant", "date", "total")
    assert funsd.fields == ("title", "date", "reference")
    assert sroie.runs_dir != personal.runs_dir != funsd.runs_dir
    assert sroie.images_dir != personal.images_dir
    assert personal.accepts_uploads
    assert not sroie.accepts_uploads
    assert set(DATASETS) == {"sroie", "personal", "funsd"}


def test_unknown_dataset():
    import pytest

    with pytest.raises(ValueError, match="Unknown dataset"):
        get_dataset("invoices")
