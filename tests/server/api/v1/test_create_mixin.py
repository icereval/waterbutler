import pytest
import asyncio
from http import client
from unittest import mock

from waterbutler.core import exceptions
from waterbutler.server.api.v1.provider.create import CreateMixin

from tests.utils import async
from tests.utils import MockCoroutine


class BaseCreateMixinTest:

    def setup_method(self, method):
        self.mixin = CreateMixin()
        self.mixin.write = mock.Mock()
        self.mixin.request = mock.Mock()
        self.mixin.set_status = mock.Mock()
        self.mixin.get_query_argument = mock.Mock()


class TestValidatePut(BaseCreateMixinTest):

    def test_invalid_kind(self):
        self.mixin.get_query_argument.return_value = 'notaferlder'

        with pytest.raises(exceptions.InvalidParameters) as e:
            self.mixin.validate_put()

        assert e.value.message == 'Kind must be file, folder or unspecified (interpreted as file), not notaferlder'

    def test_default_kind(self):
        self.mixin.path = '/'
        self.mixin.get_query_argument.side_effect = ('file', Exception('Breakout'))

        with pytest.raises(Exception) as e:
            self.mixin.validate_put()

        assert self.mixin.kind == 'file'
        assert e.value.args == ('Breakout', )
        assert self.mixin.get_query_argument.has_call(mock.call('kind', default='file'))

    def test_name_required(self):
        self.mixin.path = '/'
        self.mixin.get_query_argument.side_effect = ('file', Exception('name required'))

        with pytest.raises(Exception) as e:
            self.mixin.validate_put()

        assert e.value.args == ('name required', )
        assert self.mixin.get_query_argument.has_call(mock.call('name'))

    def test_kind_must_be_folder(self):
        self.mixin.path = 'adlkjf'
        self.mixin.get_query_argument.return_value = 'folder'

        with pytest.raises(exceptions.InvalidParameters) as e:
            self.mixin.validate_put()

        assert e.value.message == 'Path must end with a / if kind is folder'

    def test_length_required_for_files(self):
        self.mixin.path = '/'
        self.mixin.request.headers = {}
        self.mixin.get_query_argument.side_effect = ('file', 'mynerm.txt')

        with pytest.raises(exceptions.InvalidParameters) as e:
            self.mixin.validate_put()

        assert self.mixin.path == '/mynerm.txt'
        assert e.value.code == client.LENGTH_REQUIRED
        assert e.value.message == 'Content-Length is required for file uploads'

    def test_payload_with_folder(self):
        self.mixin.path = '/'
        self.mixin.request.headers = {'Content-Length': 5000}
        self.mixin.get_query_argument.side_effect = ('folder', 'mynerm.txt', 'file', 'mynerm.txt')

        with pytest.raises(exceptions.InvalidParameters) as e:
            self.mixin.validate_put()

        assert e.value.code == client.REQUEST_ENTITY_TOO_LARGE
        assert e.value.message == 'Folder creation requests may not have a body'

        self.mixin.request.headers = {'Content-Length': 'notanumber'}

        with pytest.raises(exceptions.InvalidParameters) as e:
            self.mixin.validate_put()

        assert e.value.code == client.BAD_REQUEST
        assert e.value.message == 'Invalid Content-Length'


class TestCreateFolder(BaseCreateMixinTest):

    def test_created(self):
        metadata = mock.Mock()
        self.mixin.path = 'apath'
        metadata.serialized.return_value = {'day': 'tum'}
        self.mixin.provider = mock.Mock(
            create_folder=MockCoroutine(return_value=metadata)
        )

        yield from self.mixin.create_folder()

        assert self.mixin.set_status.assert_called_once_with(201) is None
        assert self.mixin.write.assert_called_once_with({'day': 'tum'}) is None
        assert self.mixin.provider.create_folder.assert_called_once_with('apath') is None


class TestUploadFile(BaseCreateMixinTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.mixin.wsock = mock.Mock()
        self.mixin.writer = mock.Mock()

    def test_created(self):
        metadata = mock.Mock()
        self.mixin.uploader = asyncio.Future()
        metadata.serialized.return_value = {'day': 'tum'}
        self.mixin.uploader.set_result((metadata, True))

        yield from self.mixin.upload_file()

        assert self.mixin.wsock.close.called
        assert self.mixin.writer.close.called
        assert self.mixin.set_status.assert_called_once_with(201) is None
        assert self.mixin.write.assert_called_once_with({'day': 'tum'}) is None

    @async
    def test_not_created(self):
        metadata = mock.Mock()
        self.mixin.uploader = asyncio.Future()
        metadata.serialized.return_value = {'day': 'ta'}
        self.mixin.uploader.set_result((metadata, False))

        yield from self.mixin.upload_file()

        assert self.mixin.wsock.close.called
        assert self.mixin.writer.close.called
        assert self.mixin.set_status.called is False
        assert self.mixin.write.assert_called_once_with({'day': 'ta'}) is None


