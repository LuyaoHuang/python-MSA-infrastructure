"""
Module for the service base class
"""
import sys
import json

import registry

from extra_handler import regist_http


class BaseService(object):
    """
    Base service class
    """
    name = 'BaseService'
    desc = 'Base Service of Microservice'
    version = '1.0'
    registry = None
    service_id = None

    @classmethod
    def prepare(cls, params):
        """
        This function should be called before start a service
        """
        cls.service_id = params.service_id
        registry_cls = registry.load_registry_cls(params.registry)
        cls.registry = registry_cls(cls, params.address)

    @regist_http('GET', '/info', regist=False)
    def service_info(self, _request):
        """
        Return the service information, and this function will be used as
        the service health check
        """
        info = {'name': self.name,
                'desc': self.desc,
                'version': self.version}
        return json.dumps(info)

    def request(self, target_service, method, path, data=None, header=None):
        """
        A helper request function to make the request between services more simple
        Usage:
            class serviceA(BaseService):
                name = 'serviceA'
                ...

                @http('GET', '/path')
                def method(self, request):
                    ...

            class serviceB(BaseService):
                def mothod():
                    self.request('serviceA', 'GET', '/path', data=data)
        """
        return self.registry.request(target_service, method, path, data, header)
