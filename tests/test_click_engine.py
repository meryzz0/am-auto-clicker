import sys
import time
import types
import unittest
from unittest.mock import patch

from am_auto_clicker.click_engine import ClickEngine


class FakeInputDevice:
    def __init__(self, capabilities, **kwargs):
        self.capabilities = capabilities
        self.kwargs = kwargs
        self.events = []
        self.closed = False

    def write(self, event_type, code, value):
        self.events.append((event_type, code, value))

    def syn(self):
        pass

    def close(self):
        self.closed = True


class ClickEngineTests(unittest.TestCase):
    def setUp(self):
        self.device = None

        def make_device(capabilities, **kwargs):
            self.device = FakeInputDevice(capabilities, **kwargs)
            return self.device

        fake_ecodes = types.SimpleNamespace(
            EV_KEY=1, EV_REL=2, REL_X=0, REL_Y=1,
            BTN_LEFT=272, BTN_RIGHT=273, BTN_MIDDLE=274,
        )
        self.fake_evdev = types.SimpleNamespace(UInput=make_device, ecodes=fake_ecodes)
        self.events = []
        self.engine = ClickEngine(lambda kind, payload: self.events.append((kind, payload)))
        self.modules_patch = patch.dict(sys.modules, {"evdev": self.fake_evdev})
        self.modules_patch.start()
        self.addCleanup(self.modules_patch.stop)

    def wait_for_finished(self, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(kind == "finished" for kind, _ in self.events):
                return
            time.sleep(0.01)
        self.fail("Click engine did not finish within the timeout")

    def test_click_limit_releases_button_and_closes_device(self):
        self.engine.start(interval_ms=10, button="left", limit=3)
        self.wait_for_finished()

        self.assertTrue(self.device.closed)
        self.assertTrue(any(kind == "started" for kind, _ in self.events))
        finished = next(payload for kind, payload in self.events if kind == "finished")
        self.assertEqual(finished["clicks"], 3)
        self.assertIsNone(finished["error"])
        left_events = [event for event in self.device.events if event[1] == 272]
        self.assertEqual([event[2] for event in left_events].count(1), 3)
        self.assertGreaterEqual([event[2] for event in left_events].count(0), 3)

    def test_invalid_button_is_rejected_before_worker_starts(self):
        with self.assertRaises(ValueError):
            self.engine.start(interval_ms=100, button="other", limit=0)
        self.assertFalse(self.engine.active)

    def test_unsupported_interval_and_limit_are_rejected(self):
        invalid_settings = (
            {"interval_ms": 9, "button": "left", "limit": 0},
            {"interval_ms": 5001, "button": "left", "limit": 0},
            {"interval_ms": 100, "button": "left", "limit": -1},
            {"interval_ms": 100, "button": "left", "limit": 10_000_001},
        )
        for settings in invalid_settings:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.engine.start(**settings)
        self.assertFalse(self.engine.active)

    def test_worker_reports_device_errors_and_closes_device(self):
        class FailingInputDevice(FakeInputDevice):
            def write(self, event_type, code, value):
                if value == 1:
                    raise PermissionError("synthetic input denied")
                super().write(event_type, code, value)

        def make_failing_device(capabilities, **kwargs):
            self.device = FailingInputDevice(capabilities, **kwargs)
            return self.device

        self.fake_evdev.UInput = make_failing_device
        self.engine.start(interval_ms=100, button="left", limit=1)
        self.wait_for_finished()
        finished = next(payload for kind, payload in self.events if kind == "finished")
        self.assertIsInstance(finished["error"], PermissionError)
        self.assertTrue(self.device.closed)
        self.assertTrue(any(event[2] == 0 for event in self.device.events))

    def test_stop_during_initial_delay_sends_no_clicks(self):
        self.engine.start(interval_ms=100, button="right", limit=0)
        time.sleep(0.04)
        self.engine.stop()
        self.wait_for_finished()
        finished = next(payload for kind, payload in self.events if kind == "finished")
        self.assertEqual(finished["clicks"], 0)
        self.assertTrue(self.device.closed)


if __name__ == "__main__":
    unittest.main()
