"""The scikit-learn classifier passes the contract; its own prediction (numpy on the stored
numbers) is scikit-learn's, and a model is plain arrays."""

import io
from dataclasses import replace

import numpy as np
import pytest

from lekto.adapters.outbound.sklearn import SklearnClassifier
from lekto.adapters.outbound.sklearn.classifier import FORMAT, _Model, analyze, fit, fitted
from lekto.core.domain.errors import ClassifierError
from lekto.core.ports.classifier import TrainingExample
from tests.contracts.classifier import INSURER, INVOICE, ClassifierContract, corpus


@pytest.fixture
def classifier() -> SklearnClassifier:
    return SklearnClassifier()


class TestSklearnClassifier(ClassifierContract):
    pass


def test_words_and_pairs() -> None:
    assert analyze("Rechnung R-2026 vom 31.03.2026: 84,20 €") == [
        "rechnung",
        "r-2026",
        "vom",
        "rechnung r-2026",
        "r-2026 vom",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Stadtwerke Musterstadt Zählerstand",
        "Beispielbank Saldo",
        "nichts davon",
        "",
    ],
)
def test_the_prediction_is_scikit_learns(text: str) -> None:
    examples = corpus()
    (data, _), found = fit(examples), fitted(examples)
    prediction = _Model.load(data).predict(text)
    vector = found.vectorizer.transform([text])
    assert found.contact is not None and found.document_type is not None
    expected = dict(
        zip(found.contact.classes_, found.contact.predict_proba(vector)[0], strict=True)
    )
    assert {str(key): value for key, value in prediction.contacts} == pytest.approx(expected)
    kinds = dict(
        zip(
            found.document_type.classes_,
            found.document_type.predict_proba(vector)[0],
            strict=True,
        )
    )
    assert {str(key): value for key, value in prediction.document_types} == pytest.approx(kinds)
    for tag, model in found.tags.items():
        assert prediction.tags[tag] == pytest.approx(model.predict_proba(vector)[0][1], abs=1e-5)
    assert found.topic is not None
    topics = dict(zip(found.topic.classes_, found.topic.predict_proba(vector)[0], strict=True))
    assert {str(key): value for key, value in prediction.topics} == pytest.approx(topics)


def test_a_model_is_plain_arrays() -> None:
    data, summary = fit(corpus())
    with np.load(io.BytesIO(data), allow_pickle=False) as archive:
        assert str(archive["format"]) == FORMAT
        # Two classes: one row, for the second one (as scikit-learn keeps it).
        assert archive["contact_coef"].shape == (1, len(archive["terms"]))
    assert summary["classes"] == {
        "contact": 2,
        "document_type": 2,
        "topic": 2,
        "space": 0,
        "tags": 2,
    }


def test_a_model_from_before_topics_knows_none() -> None:
    data, _ = fit(corpus())
    with np.load(io.BytesIO(data), allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files if not name.startswith("topic_")}
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    prediction = _Model.load(buffer.getvalue()).predict("Stadtwerke Musterstadt Zählerstand")
    assert prediction.topics == [] and prediction.contacts


def test_a_model_from_before_spaces_knows_none() -> None:
    examples = [replace(item, space=str(index % 2)) for index, item in enumerate(corpus())]
    data, summary = fit(examples)
    classes = summary["classes"]
    assert isinstance(classes, dict) and classes["space"] == 2
    with np.load(io.BytesIO(data), allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files if not name.startswith("space_")}
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    prediction = _Model.load(buffer.getvalue()).predict("Stadtwerke Musterstadt Zählerstand")
    assert prediction.spaces == [] and prediction.contacts


def test_a_model_of_another_format() -> None:
    buffer = io.BytesIO()
    np.savez_compressed(buffer, format=np.array("other/9"))
    with pytest.raises(ClassifierError, match="another format"):
        _Model.load(buffer.getvalue())


def test_a_model_that_is_no_archive() -> None:
    """A single array (`.npy`) and a broken zip are no model either: the port's error, not
    numpy's or zipfile's (AD-K06)."""
    single = io.BytesIO()
    np.save(single, np.array([1.0, 2.0]))
    broken = io.BytesIO()
    np.savez_compressed(broken, format=np.array(FORMAT))
    for data in (single.getvalue(), broken.getvalue()[:40]):
        with pytest.raises(ClassifierError, match="cannot be read"):
            _Model.load(data)


def test_with_more_classes_too() -> None:
    insurer = [
        TrainingExample(f"Nord Versicherung Beitragsrechnung Police {n}", INSURER, INVOICE)
        for n in range(3)
    ]
    examples = [*corpus(), *insurer]
    (data, _), found = fit(examples), fitted(examples)
    text = "Nord Versicherung Beitrag"
    prediction = _Model.load(data).predict(text)
    assert found.contact is not None and len(found.contact.classes_) == 3
    probabilities = found.contact.predict_proba(found.vectorizer.transform([text]))[0]
    expected = dict(zip(found.contact.classes_, probabilities, strict=True))
    assert {str(key): value for key, value in prediction.contacts} == pytest.approx(expected)
    assert prediction.contacts[0][0] == INSURER
