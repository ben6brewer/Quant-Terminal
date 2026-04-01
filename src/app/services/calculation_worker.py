"""Generic background worker for running calculations off the main thread."""

from PySide6.QtCore import QObject, Signal


class CalculationWorker(QObject):
    """Generic worker that runs a callable in a background QThread.

    After run() completes, the result (or error) is stored on the instance
    and the owning QThread's event loop is stopped so that QThread.finished
    fires — which is the reliable cross-thread notification mechanism.

    Usage (preferred — via BaseModule._run_worker):
        worker = CalculationWorker(some_service.method, arg1, arg2)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread.finished.connect(handler, Qt.QueuedConnection)
        thread.start()
        # In handler: read worker.result / worker.error_msg
    """

    # Legacy signals — kept for files that still connect directly.
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.result = None
        self.error_msg = None

    def run(self):
        try:
            self.result = self._fn(*self._args, **self._kwargs)
        except Exception as e:
            self.error_msg = str(e)
        finally:
            # Stop the thread's event loop so QThread.finished will emit.
            # This is critical: without quit(), exec() blocks forever and
            # QThread.finished never fires.
            #
            # Do NOT emit self.finished/self.error here — signal emission
            # through shiboken6 on a background thread races with the main
            # thread's widget construction, corrupting the C++ heap.
            # Callers read self.result/self.error_msg via QThread.finished.
            thread = self.thread()
            if thread is not None:
                thread.quit()
