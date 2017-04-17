import argparse
import signal
import eventlet

from nameko.runners import ServiceRunner
from logging import getLogger

LOGGER = getLogger(__name__)

def get_args():
    parser = argparse.ArgumentParser(description='This is a service example')
    parser.add_argument(
        '--service-id', dest='service_id', action='store',
        help='Id of service')
    parser.add_argument(
        '--registry', dest='registry', action='store',
        default='Consul',
        help='Service registry type')
    parser.add_argument(
        '--address', dest='address', action='store',
        default='0.0.0.0:8055',
        help='The address and port which for service')
    return parser.parse_args()

def run_service(service_cls):
    def _signal_handler(_signum, _frame):
        """
        Handler on signal
        """
        LOGGER.info('stop service')
        eventlet.spawn(runner.stop)

    params = get_args()
    runner = ServiceRunner(config={})
    service_cls.prepare(params)
    runner.add_service(service_cls)
    signal.signal(signal.SIGTERM, _signal_handler)
    runner.start()
    runnlet = eventlet.spawn(runner.wait)

    LOGGER.info('Start service')
    try:
        runnlet.wait()
    except KeyboardInterrupt:
        LOGGER.info('Stop service')
        runner.stop()


if __name__ == '__main__':
    import example_service
    run_service(example_service.SampleService)
