import re
import requests
import socket
import uuid

from logging import getLogger

LOGGER = getLogger(__name__)

def load_registry_cls(registry_type):
    module = sys.modules[__name__]
    cls_name = registry_type + 'Registry'
    cls = getattr(module, cls_name, None)
    if not cls:
        raise Exception('Cannot find registry %s', registry_type)

    return cls


class ConsulRegistry(object):
    """
    Consul service registry helper class
    """
    def __init__(self, service_cls, addr,
                 consul_url='http://127.0.0.1:8500',
                 fabio_url='http://127.0.0.1:9999'):
        # TODO: load this from config
        self.consul_url = consul_url
        self.fabio_url = fabio_url
        self.service_cls = service_cls
        self.addr = addr
        self.register_url = '%s/v1/agent/service/register' % consul_url
        self.deregister_url = '%s/v1/agent/service/deregister' % consul_url

    def regist_url(self, url, fabio=True, health_check=True, with_host=True):
        address, port = parse_address(self.addr)
        if not address:
            return
        elif address == '0.0.0.0':
            # TODO: if ip is 0.0.0.0 ?
            address = socket.gethostbyname_ex(socket.gethostname())[2][0]

        name = self.service_cls.name
        # TODO: make this fabio be a plugin ?
        if fabio:
            # TODO: support multi path in tags
            if with_host:
                tags = ['urlprefix-%s.com/' % name]
            else:
                tags = ['urlprefix-/']
        else:
            tags = None

        if health_check:
            checks = {
                "http": "http://%s:%d%s" % (address, port, url),
                "interval": "10s",
                "timeout": "1s"
            }
        else:
            checks = None

        self.service_id = self.regist(name, address, int(port),
                                      self.service_cls.service_id,
                                      tags, checks)

    def regist(self, service_name, address, port,
               service_id=None, tags=None, checks=None):
        """
        Regist a new service to consul
        """
        tmp_service_id = service_id if service_id else str(uuid.uuid1())
        data = {'ID': tmp_service_id,
                'Name': service_name,
                'Address': address,
                'Port': port,
                'Tags': tags,
                'check': checks}
        LOGGER.info('Regist Data: %s', data)

        r = requests.put(self.register_url, data=json.dumps(data))
        if r.status_code != 200:
            LOGGER.error('Fail to regist to consul: %s', r.text)
        else:
            LOGGER.info('Regist success')
            return tmp_service_id

    def deregist(self, service_id=None):
        """
        Deregist a new service to consul
        """
        if not service_id:
            service_id = self.service_id

        r = requests.post('%s/%s' % (self.deregister_url, service_id))
        if r.status_code != 200:
            LOGGER.error('Fail to deregist to consul: %s', r.text)
        else:
            LOGGER.info('Deregist Success')

    def health_check(self):
        """
        Return a unhealth service list with info
        """
        ret_list = []

        consul_url = self.consul_url + '/v1/health/state/critical'
        r = requests.get(consul_url)
        if r.status_code != 200:
            raise Exception('Fail to get health info from consul: %s', r.text)
        data = r.json()
        for info in data:
            if info['Status'] != 'critical':
                continue
            ret_list.append({'service_name': info['ServiceName'],
                             'service_id': info['ServiceID']})
        return ret_list

    def request(self, target_service, method, path, data=None, header=None):
        if not header:
            header = {}
        header['Host'] = '{}.com'.format(target_service)
        url = self.fabio_url + path
        return requests.request(method, url, data=data, headers=header)


def parse_address(address_string):
    """
    A helper function to parse config ip address
    """
    address_re = re.compile(r'^((?P<address>[^:]+):)?(?P<port>\d+)$')
    match = address_re.match(address_string)
    if match is None:
        raise Exception(
            'Misconfigured bind address `{}`. '
            'Should be `[address:]port`'.format(address_string)
        )
    address = match.group('address') or ''
    port = int(match.group('port'))
    return address, port
