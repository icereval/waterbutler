from unittest import mock

import pytest
import tornado

from tests import utils
from tests.server.api.v1.utils import ServerTestCase

from waterbutler.auth.osf import settings
from waterbutler.auth.osf.handler import OsfAuthHandler
from waterbutler.core.exceptions import UnsupportedHTTPMethodError


class TestOsfAuthHandler(ServerTestCase):

    def setUp(self):
        super().setUp()

        self.handler = OsfAuthHandler()
        self.request = tornado.httputil.HTTPServerRequest(uri=settings.API_URL)

        mock_auth = utils.MockCoroutine(return_value={'auth': {}, 'callback_url': 'test.com'})
        self.mock_auth_patcher = mock.patch(
            'waterbutler.auth.osf.handler.OsfAuthHandler.make_request',
            mock_auth
        )
        self.mock_auth_patcher.start()

    def tearDown(self):
        self.mock_auth_patcher.stop()
        super().tearDown()

    @tornado.testing.gen_test
    async def test_supported_and_unsupported_methods(self):

        supported_methods = ['put', 'get', 'head', 'delete']
        post_actions = ['copy', 'rename', 'move']
        unsupported_methods = ['post', 'trace', 'connect', 'patch', 'ma1f0rmed']
        resource = 'test'
        provider = 'test'

        assert all(method in self.handler.ACTION_MAP.keys() for method in supported_methods)

        for is_source in [True, False]:
            for action in post_actions:
                self.request.method = 'post'
                await self.handler.get(resource, provider, self.request, action=action, is_source=is_source)

        for method in supported_methods:
            self.request.method = method
            await self.handler.get(resource, provider, self.request)

        for method in unsupported_methods:
            self.request.method = method
            with pytest.raises(UnsupportedHTTPMethodError):
                await self.handler.get(resource, provider, self.request)

    @tornado.testing.gen_test
    async def test_permissions_post_copy_source_destination(self):

        resource = 'test'
        provider = 'test'
        action = 'copy'
        self.request.method = 'post'

        self.handler.build_payload = mock.Mock()

        for is_source in [True, False]:
            await self.handler.get(resource, provider, self.request, action=action, is_source=is_source)
            if is_source:
                self.handler.build_payload.assert_called_with({
                    'nid': resource,
                    'provider': provider,
                    'action': 'download'
                }, cookie=None, view_only=None)
            else:
                self.handler.build_payload.assert_called_with({
                    'nid': resource,
                    'provider': provider,
                    'action': 'upload'
                }, cookie=None, view_only=None)
