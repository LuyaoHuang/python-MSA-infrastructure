import json
import pprint
import select
import paramiko
import threading
import traceback

from nameko.extensions import ProviderCollector, SharedExtension

from logging import getLogger

LOGGER = getLogger(__name__)


class GerritWatcherServer(ProviderCollector, SharedExtension):
    """
    A SharedExtension that wraps a gerrit client interface
    for processing gerrit event
    """
    def __init__(self, username=None, hostname=None,
                 port=None, keyfile=None):
        super(GerritWatcherServer, self).__init__()
        self.username = username
        self.hostname = hostname
        self.port = port
        self.keyfile = keyfile
        self._starting = False
        self._stop = threading.Event()
        self.client = None

    def _dispatch(self, fd):
        line = fd.readline()
        if not line:
            return
        data = json.loads(line)
        LOGGER.debug("Received data from Gerrit event stream: %s",
                     pprint.pformat(data))
        providers = self.filter_provider(data)
        for provider in providers:
            provider.handle_message(data)

    def filter_provider(self, msg):
        providers = []
        for provider in self._providers:
            if provider.is_match(msg):
                providers.append(provider)
        return providers

    def _listen(self, stdout, _stderr):
        poll = select.poll()
        poll.register(stdout.channel)
        while not self._stop.isSet():
            ret = poll.poll()
            for (fd, event) in ret:
                if fd != stdout.channel.fileno():
                    continue
                if event == select.POLLIN:
                    self._dispatch(stdout)
                else:
                    raise Exception("event on ssh connection")

    def _connect(self):
        """
        Attempts to connect and returns the connected client.
        """
        def _make_client():
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
            return client

        client = None
        try:
            client = _make_client()
            client.connect(self.hostname,
                           username=self.username,
                           port=self.port,
                           key_filename=self.keyfile)
            return client
        except (IOError, paramiko.SSHException) as e:
            LOGGER.error("Exception connecting to %s:%s",
                         self.hostname, self.port)
            if client:
                try:
                    client.close()
                except (IOError, paramiko.SSHException):
                    LOGGER.error("Failure closing broken client")
            else:
                raise e

    def _consume(self):
        """
        Consumes events using gerrit client.
        """
        _, stdout, stderr = self.client.exec_command("gerrit stream-events")

        self._listen(stdout, stderr)

        ret = stdout.channel.recv_exit_status()
        LOGGER.info("SSH exit status: %s", ret)

    def _run(self):
        while not self._stop.isSet():
            self.client = self._connect()
            try:
                self._consume()
            # pylint: disable=broad-except
            except Exception as e:
                LOGGER.error('Hit exception: %s Back Trace: %s',
                             e, traceback.format_exc())
            finally:
                LOGGER.info("Stop client")
                if self.client:
                    try:
                        self.client.close()
                    except (IOError, paramiko.SSHException):
                        LOGGER.error("Failure closing broken client")

    def start(self):
        if self._starting:
            return

        self._starting = True
        th = threading.Thread(target=self._run, args=())
        th.start()

    def stop(self):
        self._stop.set()
        self.client.close()
        super(GerritWatcherServer, self).stop()
