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


@pytest.mark.parametrize('area', [float('nan'), float('inf'), -1])
def test_nonfinite_or_negative_area_is_not_a_density(area):
    with pytest.raises(ValueError):
        measure([], area_m2=area)


@pytest.mark.parametrize('polygon', [
    [(0, 0), (1, 1), (2, 2)],
    [(0, 0), (1, float('nan')), (2, 2)],
    [(0, 0), (1,), (2, 2)],
])
def test_invalid_roi_cannot_produce_density(polygon):
    with pytest.raises(ValueError):
        measure([], polygon, 10)


def test_ground_contact_on_roi_boundary_is_included():
    assert measure([(2, 0, 8, 10)], [(0, 0), (10, 0), (10, 10), (0, 10)], 20) == {
        'count': 1, 'density_people_m2': .05}


def test_capped_count_is_not_published(monkeypatch):
    from vision.worker import build_parser, frame_record, publish_measurement
    args = build_parser().parse_args(['--source', 'test.mp4', '--max-det', '2'])
    record = frame_record([(0, 0, 2, 5)]*2, args, None, 0, 1)
    class NoRequest:
        def patch(self, *a, **kw):
            pytest.fail('A truncated count must not overwrite shelter occupancy')
    publish_measurement(NoRequest(), args, record)
    assert not record['published'] and record['detection_limit_reached']
    assert record['warnings']


def test_real_publish_contract_updates_density_and_zero_count(tmp_path, monkeypatch):
    import time
    from fastapi.testclient import TestClient
    from backend.app import create_app
    from vision.worker import build_parser, frame_record, publish_measurement, validate_args
    monkeypatch.setenv('SENSOR_KEY', 'vision-test-only')
    args = build_parser().parse_args(['--source', 'test.mp4', '--coverage', 'full',
                                    '--publish', '--shelter', 's1', '--area-m2', '12'])
    validate_args(args)
    app = create_app(str(tmp_path/'vision.db'), demo=True)
    with TestClient(app) as client:
        first = frame_record([(0, 0, 5, 10)]*3, args, None, 0, time.time())
        publish_measurement(client, args, first)
        assert first['published']
        shelter = app.state.store.get('shelter', 's1')
        assert shelter['occupancy'] == 3 and shelter['density_people_m2'] == .25
        empty = frame_record([], args, None, 1, time.time())
        publish_measurement(client, args, empty)
        shelter = app.state.store.get('shelter', 's1')
        assert empty['published'] and shelter['occupancy'] == 0
        assert shelter['density_people_m2'] == 0


def test_failed_sensor_request_does_not_stop_later_frames(monkeypatch):
    import httpx
    from vision.worker import build_parser, frame_record, publish_measurement
    monkeypatch.setenv('SENSOR_KEY', 'vision-test-only')
    args = build_parser().parse_args(['--source', 'test.mp4', '--shelter', 's1', '--coverage', 'full'])
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectTimeout('test offline')
        return httpx.Response(200, json={})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = frame_record([], args, None, 0, 1)
        publish_measurement(client, args, first)
        assert not first['published'] and first['publish_error'] == 'ConnectTimeout'
        next_frame = frame_record([], args, None, 1, 2)
        publish_measurement(client, args, next_frame)
        assert next_frame['published']


def test_partial_view_publish_is_rejected_before_loading_model(monkeypatch):
    from vision.worker import build_parser, validate_args
    monkeypatch.setenv('SENSOR_KEY', 'vision-test-only')
    args = build_parser().parse_args(['--source', 'test.mp4', '--publish', '--shelter', 's1'])
    with pytest.raises(ValueError, match='coverage full'):
        validate_args(args)
