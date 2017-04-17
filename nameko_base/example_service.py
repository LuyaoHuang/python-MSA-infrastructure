import base_service

class SampleService(base_service.BaseService):
    name = 'SampleService'
    desc = 'Just a example'

    @base_service.regist_http('GET', '/test')
    def test(self, request):
        LOGGER.info('Method test in %s', self.name)
