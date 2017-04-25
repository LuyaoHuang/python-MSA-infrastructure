import traceback

from functools import partial
from eventlet.event import Event

from nameko.web.handlers import HttpRequestHandler
from nameko.extensions import Entrypoint
from extra_extension import GerritWatcherServer

from logging import getLogger

LOGGER = getLogger(__name__)


class AutoregistHttpRequestHandler(HttpRequestHandler):
    """
    A http handler with auto service regist and deregist
    """
    def __init__(self, method, url, expected_exceptions=(),
                 regist=False):
        super(AutoregistHttpRequestHandler, self).__init__(method, url, expected_exceptions)
        self.regist = regist
        self.registry = None

    def start(self):
        super(AutoregistHttpRequestHandler, self).start()
        if self.regist:
            self.registry = self.container.service_cls.registry
            if not self.registry:
                LOGGER.info('Skip service regist')
                return
            self.registry.regist_url(self.url)

    def stop(self):
        if self.regist:
            if not self.registry:
                LOGGER.info('Skip service deregist')
            else:
                self.registry.deregist()
        super(AutoregistHttpRequestHandler, self).stop()


regist_http = AutoregistHttpRequestHandler.decorator


class GerritEventHandler(Entrypoint):
    """
    A gerrit event handler
    """
    server = GerritWatcherServer('test',
                                 '127.0.0.1',
                                 29418,
                                 'user_key')

    def __init__(self, **kargs):
        self.filters = kargs

    def is_match(self, msg):
        s_src = self.filters.viewitems()
        s_tgt = msg.viewitems()
        return s_src <= s_tgt

    def setup(self):
        self.server.register_provider(self)

    def stop(self):
        self.server.unregister_provider(self)
        super(GerritEventHandler, self).stop()

    def handle_message(self, msg):
        try:
            event = Event()
            self.container.spawn_worker(self, (msg,), {},
                                        handle_result=partial(self.handle_result, event))
            event.wait()
        # pylint: disable=broad-except
        except Exception as e:
            LOGGER.error('Hit exception: %s BackTrace: %s',
                         e, traceback.format_exc())

    # pylint: disable=unused-argument
    def handle_result(self, event, worker_ctx, result, exc_info):
        event.send(result, exc_info)
        return result, exc_info


gerrit_handler = GerritEventHandler.decorator
