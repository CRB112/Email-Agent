"""Exercise real Graph builders, auth, and middleware over an offline HTTP transport."""
from tempfile import TemporaryDirectory
from threading import Event
from time import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from azure.core.credentials import AccessToken
from azure.identity import AuthenticationRequiredError

from app.agents.microsoft import MicrosoftGraphAgent
from app.microsoftGraph import email as graph
from app.services.journal import RunJournal
from app.services.sifting import sift
from tests.fakes import make_rule


class CachedBrowserCredential:
    """Model Azure's separate CAE/non-CAE caches without any browser or network."""
    def __init__(self):
        self.interactions = []
        self.requests = []
        self.closed = False
        self.cached = None

    def authenticate(self, *, scopes, enable_cae=False):
        self.interactions.append((tuple(scopes), enable_cae))
        self.cached = (tuple(scopes), enable_cae)
        return SimpleNamespace(home_account_id='offline-test-account')

    def get_token(self, *scopes, enable_cae=False, **kwargs):
        key = (scopes, enable_cae)
        self.requests.append(key)
        if key != self.cached:
            raise AuthenticationRequiredError(scopes, message='No token in this cache partition')
        return AccessToken('offline-test-token', int(time()) + 3600)

    def close(self):
        self.closed = True


class MicrosoftTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.credential = CachedBrowserCredential()
        self.requests = []
        self.responses = []
        self.factory = graph.GraphClientFactory.create_with_default_middleware
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def handler(self, request):
        self.requests.append(request)
        self.assertEqual(request.headers['Authorization'], 'Bearer offline-test-token')
        self.assertNotIn('me-token-to-replace', str(request.url))
        if self.responses:
            return self.responses.pop(0)
        path = request.url.path
        if path == '/v1.0/me/mailFolders':
            return httpx.Response(200, json={'value': [{'id': 'archive-id', 'displayName': 'Archive', 'childFolderCount': 0}]})
        if path == '/v1.0/me/mailFolders/archive':
            return httpx.Response(200, json={'id': 'archive-id'})
        if path == '/v1.0/me/mailFolders/inbox/messages':
            if '$skiptoken' in request.url.params:
                return httpx.Response(200, json={'value': []})
            return httpx.Response(200, json={
                'value': [{'id': 'email-1', 'subject': 'Invoice', 'receivedDateTime': '2026-01-01T00:00:00Z',
                           'from': {'emailAddress': {'address': 'billing@example.com'}},
                           'body': {'content': 'Payment due', 'contentType': 'text'}}],
                '@odata.nextLink': 'https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$skiptoken=page2'})
        if request.method == 'PATCH' and path == '/v1.0/me/messages/email-1':
            return httpx.Response(200, json={'id': 'email-1'})
        if request.method == 'POST' and path == '/v1.0/me/messages/email-1/move':
            return httpx.Response(200, json={'id': 'email-moved'})
        if request.method == 'DELETE' and path == '/v1.0/me/messages/email-moved':
            return httpx.Response(204)
        self.fail(f'Unexpected offline HTTP request: {request.method} {request.url}')

    def make_client(self, *, options):
        client = httpx.AsyncClient(transport=httpx.MockTransport(self.handler), trust_env=False)
        return self.factory(client=client, options=options)

    def connect(self):
        with patch.object(graph, 'InteractiveBrowserCredential', return_value=self.credential) as constructor, \
             patch.object(graph.GraphClientFactory, 'create_with_default_middleware', side_effect=self.make_client):
            agent = MicrosoftGraphAgent.authenticate()
        self.assertTrue(constructor.call_args.kwargs['disable_automatic_authentication'])
        return agent

    async def test_preview_and_apply_use_real_me_routes_and_one_login(self):
        agent = self.connect()
        try:
            folders = await agent.list_destinations()
            self.assertEqual(folders, {'Archive': 'archive-id'})
            options = {'rules': [make_rule(actions={
                'Mark': {'Mark_type': 'Read'}, 'Move': {'Folder': 'archive'}, 'Delete': {}})]}
            journal = RunJournal(agent.mailbox_key, self.directory.name)
            preview = await sift(agent, options, 'since_last', Event(), Mock(), preview=True, journal=journal)
            self.assertTrue(all(request.method == 'GET' for request in self.requests))
            self.assertEqual(preview.examined, 1)
            self.assertEqual(len(self.credential.interactions), 1)
            result = await sift(agent, options, 'since_last', Event(), Mock(), prepared=preview.batch, journal=journal)
            self.assertEqual(result.modifications, 3)
            self.assertEqual([request.method for request in self.requests[-3:]], ['PATCH', 'POST', 'DELETE'])
            self.assertEqual(len(self.credential.interactions), 1)
            self.assertTrue(all(key == self.credential.cached for key in self.credential.requests))
            self.assertTrue(any('$skiptoken' in request.url.params for request in self.requests))
        finally:
            await agent.close()
        self.assertTrue(self.credential.closed)

    async def test_expired_session_does_not_launch_another_login(self):
        agent = self.connect()
        self.credential.cached = None
        try:
            with self.assertRaises(AuthenticationRequiredError):
                await agent.get_emails()
            self.assertEqual(len(self.credential.interactions), 1)
            self.assertEqual(self.requests, [])
        finally:
            await agent.close()

    async def test_preserved_middleware_still_disables_automatic_retries(self):
        agent = self.connect()
        self.responses = [httpx.Response(503, json={'error': {'code': 'ServiceUnavailable', 'message': 'offline failure'}})]
        try:
            from kiota_abstractions.api_error import APIError
            with self.assertRaises(APIError):
                await agent.list_destinations()
            self.assertEqual(len(self.requests), 1)
        finally:
            await agent.close()


class MicrosoftReauthenticationTests(unittest.TestCase):
    def test_real_credential_does_not_open_browser_on_silent_cache_miss(self):
        credential = graph.InteractiveBrowserCredential(disable_automatic_authentication=True)
        try:
            with patch.object(credential, '_acquire_token_silent', side_effect=AuthenticationRequiredError(graph.SCOPES)), \
                 patch.object(credential, '_request_token') as browser:
                with self.assertRaises(AuthenticationRequiredError):
                    credential.get_token(*graph.SCOPES, enable_cae=graph.ENABLE_CAE)
                browser.assert_not_called()
        finally:
            credential.close()

    def test_ui_explains_reauthentication_even_when_wrapped(self):
        from app.pages.main_page import error_text
        from app.services.execution import ProcessingFailure
        original = AuthenticationRequiredError(graph.SCOPES)
        wrapped = ProcessingFailure('Request failed', [])
        wrapped.__cause__ = original
        self.assertIn('Log out, then log in again', error_text(wrapped))
