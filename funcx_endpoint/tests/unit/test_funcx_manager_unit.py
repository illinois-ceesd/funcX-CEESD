import time
import uuid
from unittest import mock

from funcx_common.tasks import TaskState

from funcx_endpoint.executors.high_throughput.funcx_manager import Manager as FXManager
from funcx_endpoint.executors.high_throughput.messages import Task


@mock.patch("funcx_endpoint.executors.high_throughput.funcx_manager.zmq")
class TestFuncxManager:
    def test_task_to_worker_status_change(self, randomstring):
        task_type = randomstring()
        task_id = str(uuid.uuid4())
        task = Task(task_id, "RAW", b"")

        mgr = FXManager(uid="some_uid", worker_type=task_type)
        mgr.worker_map = mock.Mock()
        mgr.worker_map.get_worker.return_value = "some_work_id"
        mgr.task_queues[task_type].put(task)
        mgr.send_task_to_worker(task_type)

        assert task_id in mgr.task_status_deltas

        ts, state = mgr.task_status_deltas[task_id]
        assert time.monotonic() - ts < 20, "Expecting a timestamp"
        assert state == TaskState.RUNNING
