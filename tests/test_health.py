"""Unit tests for the pure health-classification logic — no cluster required.
Run from the repo root:  python -m unittest discover -s tests
"""
import unittest
from src import health
from src import kube_client

TH = {
    "pod_restart_threshold": 5, "pod_pending_minutes": 10, "pod_terminating_minutes": 10,
    "node_cpu_percent": 85, "node_memory_percent": 85,
}


class TestClassifyPod(unittest.TestCase):
    def test_healthy_running_pod_is_none(self):
        self.assertIsNone(health.classify_pod({"phase": "Running", "ready": True, "restart_count": 0}, TH))

    def test_evicted(self):
        self.assertEqual(health.classify_pod({"phase": "Failed", "reason": "Evicted"}, TH), health.EVICTED)

    def test_crashloop_by_waiting_reason(self):
        self.assertEqual(health.classify_pod({"phase": "Running", "waiting_reason": "CrashLoopBackOff"}, TH), health.CRASHLOOP)

    def test_crashloop_by_restart_count(self):
        self.assertEqual(health.classify_pod({"phase": "Running", "restart_count": 7}, TH), health.CRASHLOOP)

    def test_restart_count_below_threshold_is_healthy(self):
        self.assertIsNone(health.classify_pod({"phase": "Running", "ready": True, "restart_count": 2}, TH))

    def test_imagepull(self):
        self.assertEqual(health.classify_pod({"phase": "Pending", "waiting_reason": "ImagePullBackOff"}, TH), health.IMAGEPULL)

    def test_oomkilled(self):
        self.assertEqual(health.classify_pod({"phase": "Running", "last_terminated_reason": "OOMKilled"}, TH), health.OOMKILLED)

    def test_healable_vs_alert_only(self):
        self.assertIn(health.EVICTED, health.HEALABLE)
        self.assertIn(health.IMAGEPULL, health.ALERT_ONLY)


class TestClassifyNode(unittest.TestCase):
    def test_ready_low_usage_is_clean(self):
        self.assertEqual(health.classify_node({"name": "n1", "ready": True, "cpu_percent": 10, "memory_percent": 10}, TH), [])

    def test_not_ready(self):
        self.assertIn("NotReady", health.classify_node({"name": "n1", "ready": False}, TH))

    def test_high_cpu(self):
        self.assertIn("HighCPU", health.classify_node({"name": "n1", "ready": True, "cpu_percent": 95}, TH))

    def test_pressure_condition(self):
        self.assertIn("DiskPressure", health.classify_node({"name": "n1", "ready": True, "conditions": {"DiskPressure": True}}, TH))


class TestQuantityParsing(unittest.TestCase):
    def test_cpu_millicores(self):
        self.assertAlmostEqual(kube_client.cpu_to_cores("500m"), 0.5)

    def test_cpu_nanocores(self):
        self.assertAlmostEqual(kube_client.cpu_to_cores("250000000n"), 0.25)

    def test_mem_mebibytes(self):
        self.assertEqual(kube_client.mem_to_bytes("512Mi"), 512 * 1024 ** 2)


if __name__ == "__main__":
    unittest.main()
