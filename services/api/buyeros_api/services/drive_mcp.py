"""Fimmick-owned Drive MCP gateway. Only four code-owned read tools are reachable.

OAuth consent/refresh belongs to the independently provisioned Fimmick gateway.
The endpoint and its credential are server secrets; callers cannot supply either.
No logging, disk cache, retry, model tools, or provider response persistence.
"""
import asyncio
import json
import os
import re
from urllib.parse import urlsplit

import httpx
from ..api.errors import ApiError

ID = r'[A-Za-z0-9_-]{1,128}'
TOOLS = frozenset({'buyeros_drive_status', 'buyeros_drive_list_folders',
                   'buyeros_drive_list_items', 'buyeros_drive_read_item'})
PROTOCOL = '2025-06-18'


def unavailable():
    return ApiError(503, 'DRIVE_UNAVAILABLE', 'Google Drive is unavailable; ask a workspace admin to check the connection')


def configured():
    url = urlsplit(os.environ.get('BUYEROS_DRIVE_MCP_URL', ''))
    return bool(url.scheme == 'https' and url.hostname and not url.username and not url.password
                and not url.query and not url.fragment and os.environ.get('BUYEROS_DRIVE_MCP_TOKEN'))


def identifier(value):
    return isinstance(value, str) and re.fullmatch(ID, value) is not None


class DriveMCP:
    async def call(self, tool, workspace_id, project_id, **arguments):
        if tool not in TOOLS or not configured():
            raise unavailable()
        headers = {'Authorization': 'Bearer ' + os.environ['BUYEROS_DRIVE_MCP_TOKEN'],
                   'Accept': 'application/json, text/event-stream'}
        endpoint = os.environ['BUYEROS_DRIVE_MCP_URL']

        async def rpc(client, method, params=None, ident=None):
            message = {'jsonrpc': '2.0', 'method': method}
            if params is not None:
                message['params'] = params
            if ident is not None:
                message['id'] = ident
            async with client.stream('POST', endpoint, json=message, headers=headers) as response:
                if ident is None:
                    if response.status_code != 202:
                        raise unavailable()
                    return None
                if response.status_code != 200:
                    raise unavailable()
                session_id = response.headers.get('Mcp-Session-Id')
                if session_id:
                    if not re.fullmatch(r'[!-~]{1,200}', session_id):
                        raise unavailable()
                    headers['Mcp-Session-Id'] = session_id
                content_type = response.headers.get('content-type', '').split(';')[0]
                if content_type not in {'application/json', 'text/event-stream'}:
                    raise unavailable()
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise unavailable()
                    if content_type == 'text/event-stream':
                        # Accept one bounded response event, ignoring notifications.
                        normalized = bytes(raw).replace(b'\r\n', b'\n')
                        for event in normalized.split(b'\n\n')[:-1]:
                            data = b'\n'.join(line[5:].lstrip(b' ') for line in event.splitlines() if line.startswith(b'data:'))
                            if data:
                                value = json.loads(data)
                                if value.get('id') == ident:
                                    if value.get('jsonrpc') != '2.0' or 'error' in value or not isinstance(value.get('result'), dict):
                                        raise unavailable()
                                    return value['result']
                if content_type != 'application/json':
                    raise unavailable()
                value = json.loads(raw)
                if value.get('jsonrpc') != '2.0' or value.get('id') != ident or 'error' in value or not isinstance(value.get('result'), dict):
                    raise unavailable()
                return value['result']

        try:
            async with asyncio.timeout(12), httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
                init = await rpc(client, 'initialize', {'protocolVersion': PROTOCOL, 'capabilities': {},
                    'clientInfo': {'name': 'buyeros-drive-readonly', 'version': '1'}}, 1)
                if init.get('protocolVersion') != PROTOCOL or not isinstance(init.get('capabilities', {}).get('tools'), dict):
                    raise unavailable()
                headers['MCP-Protocol-Version'] = PROTOCOL
                await rpc(client, 'notifications/initialized')
                result = await rpc(client, 'tools/call', {'name': tool, 'arguments': {
                    'workspace_id': str(workspace_id), 'project_id': str(project_id), **arguments}}, 2)
                if result.get('isError') or not isinstance(result.get('structuredContent'), dict):
                    raise unavailable()
                return result['structuredContent']
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError, AttributeError, KeyError) as exc:
            # Never propagate raw upstream errors, URLs, credentials or content.
            raise unavailable() from None

    async def status(self, workspace_id, project_id):
        value = await self.call('buyeros_drive_status', workspace_id, project_id)
        if value.get('connected') is not True or type(value.get('retention_seconds')) is not int or value != {'workspace_id': str(workspace_id), 'project_id': str(project_id),
                     'oauth_owner': 'fimmick', 'scope': 'https://www.googleapis.com/auth/drive.readonly',
                     'connected': True, 'residency_preference': 'HK', 'retention_seconds': 0}:
            raise unavailable()

    async def folders(self, workspace_id, project_id):
        await self.status(workspace_id, project_id)
        value = await self.call('buyeros_drive_list_folders', workspace_id, project_id, limit=100)
        if set(value) != {'folder_ids'} or not isinstance(value['folder_ids'], list) or len(value['folder_ids']) > 100:
            raise unavailable()
        ids = value['folder_ids']
        if not all(identifier(item) for item in ids) or len(set(ids)) != len(ids):
            raise unavailable()
        return ids

    async def items(self, workspace_id, project_id, folders):
        await self.status(workspace_id, project_id)
        value = await self.call('buyeros_drive_list_items', workspace_id, project_id, folder_ids=folders, limit=100)
        if set(value) != {'items'} or not isinstance(value['items'], list) or len(value['items']) > 100:
            raise unavailable()
        seen = set()
        for item in value['items']:
            if (not isinstance(item, dict) or set(item) != {'id', 'folder_id'} or not identifier(item['id'])
                    or item['folder_id'] not in folders or item['id'] in seen):
                raise unavailable()
            seen.add(item['id'])
        return value['items']

    async def read(self, workspace_id, project_id, folders, item_id):
        # The gateway must resolve the current direct parent, reject shortcuts,
        # public links/trash, and return bounded plain text without names/URLs.
        await self.status(workspace_id, project_id)
        value = await self.call('buyeros_drive_read_item', workspace_id, project_id,
                                folder_ids=folders, item_id=item_id, max_bytes=12000)
        if (set(value) != {'id', 'folder_id', 'text'} or value['id'] != item_id or value['folder_id'] not in folders
                or not isinstance(value['text'], str) or not value['text'].strip()
                or len(value['text'].encode('utf-8')) > 12000 or '\x00' in value['text']):
            raise unavailable()
        return value['text']


def adapter():
    return DriveMCP()
