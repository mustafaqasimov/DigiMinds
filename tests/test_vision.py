import pytest
from vision.measure import measure


def test_counts_ground_contact_in_roi_not_box_center():
    polygon = [(0, 50), (100, 50), (100, 100), (0, 100)]
    result = measure([(10, 0, 20, 70), (30, 0, 40, 40), (120, 0, 140, 70)], polygon, 50)
    assert result == {'count': 1, 'density_people_m2': .02}


def test_frame_counts_do_not_accumulate():
    boxes = [(0, 0, 5, 10), (5, 0, 10, 10)]
    assert measure(boxes)['count'] == 2
    assert measure(boxes)['count'] == 2
    assert measure([])['count'] == 0


def test_no_unmeasured_density_or_invalid_calibration():
    assert measure([(0, 0, 5, 10)])['density_people_m2'] is None
    with pytest.raises(ValueError):
        measure([], area_m2=0)
    with pytest.raises(ValueError):
        measure([], polygon=[(0, 0)])
