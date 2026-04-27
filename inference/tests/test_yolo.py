from unittest.mock import MagicMock

import numpy as np

from inference import yolo


def test_has_person_empty_frames() -> None:
    assert yolo.has_person([]) == (False, 0.0)


def test_has_person_detects_via_mock(monkeypatch) -> None:
    class FakeBoxes:
        def __init__(self) -> None:
            tensor = MagicMock()
            tensor.cpu.return_value.numpy.return_value.tolist.return_value = [0.42, 0.81]
            self.conf = tensor

        def __len__(self) -> int:
            return 2

    fake_result = MagicMock()
    fake_result.boxes = FakeBoxes()

    fake_model = MagicMock()
    fake_model.predict.return_value = [fake_result]
    monkeypatch.setattr(yolo, "_get_model", lambda: fake_model)

    found, max_conf = yolo.has_person([np.zeros((480, 640, 3), dtype=np.uint8)])
    assert found is True
    assert max_conf == 0.81


def test_has_person_returns_false_when_no_boxes(monkeypatch) -> None:
    fake_result = MagicMock()
    fake_result.boxes = None
    fake_model = MagicMock()
    fake_model.predict.return_value = [fake_result]
    monkeypatch.setattr(yolo, "_get_model", lambda: fake_model)

    found, max_conf = yolo.has_person([np.zeros((480, 640, 3), dtype=np.uint8)])
    assert found is False
    assert max_conf == 0.0
