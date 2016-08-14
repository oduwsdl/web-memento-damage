from subprocess import Popen, PIPE
from threading import Thread


class Command(object):
    def __init__(self, cmd, pipe_callback):
        self.cmd = cmd
        self.process = None
        self.pipe_callback = pipe_callback

    def run(self, timeout, args=()):
        def target():
            self.process = Popen(self.cmd, stdout=PIPE, stderr=PIPE)

            stdout_thread = Thread(target=self.pipe_callback,
                               args=(self.process.stdout, ) + args)
            stdout_thread.daemon = True
            stdout_thread.start()

            stdin_thread = Thread(target=self.pipe_callback,
                                  args=(self.process.stderr, ) + args)
            stdin_thread.daemon = True
            stdin_thread.start()

            self.process.wait()

        thread = Thread(target=target)
        thread.daemon = True
        thread.start()

        thread.join(timeout)
        try: self.process.terminate()
        except: pass

        return self.process.returncode