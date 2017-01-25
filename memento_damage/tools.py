import os
import re
from subprocess import Popen, PIPE
from threading import Thread


def rmdir_recursive(d, exception_files=[]):
    for path in (os.path.join(d, f) for f in os.listdir(d)):
        if os.path.isdir(path):
            rmdir_recursive(path)
        else:
            remove = True
            for ef in exception_files:
                matches = re.findall(r'' + ef, path)
                if len(matches) > 0:
                    remove = False
                    break

            if remove:
                os.unlink(path)

    try:
        os.rmdir(d)
    except OSError, e:
        if e.errno != os.errno.ENOTEMPTY: pass


class Command(object):
    def __init__(self, cmd, pipe_stdout_callback=None, pipe_stderr_callback=None):
        self.cmd = cmd
        self.process = None
        self.pipe_stdout_callback = pipe_stdout_callback
        self.pipe_stderr_callback = pipe_stderr_callback

    def run(self, timeout, stdout_callback_args=(), stderr_callback_args=()):
        def target():
            try:
                self.process = Popen(self.cmd, stdout=PIPE, stderr=PIPE)
            except OSError as e:
                if self.pipe_stderr_callback:
                    if e.errno == os.errno.ENOENT:
                        self.pipe_stderr_callback('{} is not installed'.format(self.cmd[0]), *stderr_callback_args)
                    else:
                        self.pipe_stderr_callback(str(e), *stderr_callback_args)
                return
            except Exception, e:
                if self.pipe_stderr_callback:
                    self.pipe_stderr_callback(str(e), *stderr_callback_args)
                return

            if self.pipe_stdout_callback:
                stdout_thread = Thread(target=self.pipe_stdout_callback,
                                   args=(self.process.stdout, ) + stdout_callback_args)
                stdout_thread.daemon = True
                stdout_thread.start()

            if self.pipe_stderr_callback:
                stderr_thread = Thread(target=self.pipe_stderr_callback,
                                      args=(self.process.stderr, ) + stderr_callback_args)
                stderr_thread.daemon = True
                stderr_thread.start()

            self.process.wait()

        thread = Thread(target=target)
        thread.daemon = True
        thread.start()

        thread.join(timeout)
        try: self.process.terminate()
        except: pass

        if self.process:
            return self.process.returncode
        else: return -1