import threading
import unittest
from unittest.mock import patch
import gradio as gr
import app


class UnloadTests(unittest.TestCase):
    def test_loaded_success(self):
        with patch.object(app, '_model', object()), patch.object(app, 'release_model') as release:
            self.assertIn('Model unloaded', app.unload())
            release.assert_called_once_with()

    def test_no_model_does_not_collect_or_touch_gpu(self):
        with patch.object(app, '_model', None), patch.object(app, 'release_model') as release:
            self.assertIn('No model is loaded', app.unload())
            release.assert_not_called()

    def test_busy_returns_without_waiting_or_interrupting(self):
        held, release_lock = threading.Event(), threading.Event()
        def holder():
            with app.LOCK:
                held.set()
                release_lock.wait(5)
        worker = threading.Thread(target=holder)
        worker.start()
        self.assertTrue(held.wait(2))
        try:
            with patch.object(app, 'release_model') as release:
                self.assertIn('Model is in use', app.unload())
                release.assert_not_called()
                self.assertTrue(worker.is_alive())
        finally:
            release_lock.set()
            worker.join(2)

    def test_error_releases_lock_and_ui_restores(self):
        with gr.Blocks() as ui:
            button = gr.Button('Unload experimental model')
            status = gr.Markdown()
            app.bind_busy_action(button, app.unload, [], [status], 'Unload experimental model',
                                 'Unloading model...', 0, queue_action=False)
        callbacks = {f.fn.__name__: f.fn for f in ui.fns.values() if f.fn}
        with patch.object(app, '_model', object()), patch.object(app, 'release_model', side_effect=RuntimeError('test failure')):
            self.assertFalse(callbacks['start'](None)[0]['interactive'])
            self.assertIn('test failure', callbacks['execute'](None)['value'])
        self.assertTrue(callbacks['finish']()[0]['interactive'])
        acquired = []
        def check_lock():
            locked = app.LOCK.acquire(blocking=False)
            acquired.append(locked)
            if locked:
                app.LOCK.release()
        worker = threading.Thread(target=check_lock)
        worker.start(); worker.join(2)
        self.assertEqual(acquired, [True])
        self.assertFalse(ui.config['dependencies'][1]['queue'])

    def test_real_ui_unload_actions_bypass_queue(self):
        ui = app.build_ui()
        for dependency in ui.config['dependencies']:
            function = ui.fns[dependency['id']].fn
            if function and function.__name__ == 'execute':
                closure = dict(zip(function.__code__.co_freevars, [c.cell_contents for c in function.__closure__]))
                if closure.get('action') is app.unload:
                    self.assertFalse(dependency['queue'])


if __name__ == '__main__':
    unittest.main()
