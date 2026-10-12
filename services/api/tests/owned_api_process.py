"""Owned OS process harness; never used by production or worker dispatch."""
import asyncio
import multiprocessing
import os
import socket
import sys
import time
import uuid


def serve(config, control):
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    import uvicorn
    from buyeros_api.api import auth, idempotency
    from buyeros_api.api.app import create_app
    from buyeros_api.api.jwks import JwksKeyCache
    from buyeros_api.api.verifier import TokenVerifier
    from buyeros_api.settings import get_settings

    # All values are owned fixture values; no inherited external DB selectors.
    for name in ('BUYEROS_DATABASE_URL', 'DATABASE_URL', 'BUYEROS_EXECUTION_DATABASE_URL',
                 'BUYEROS_TEST_DATABASE_URL'):
        os.environ.pop(name, None)
    os.environ['BUYEROS_DATABASE_URL'] = config['runtime_dsn']
    os.environ['BUYEROS_AUTH0_ISSUER'] = config['issuer']
    os.environ['BUYEROS_AUTH0_AUDIENCE'] = config['audience']
    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=config['jwks']), cache_seconds=300)
    auth._verifier_from_settings = lambda: TokenVerifier(
        cache, issuer=config['issuer'], audience=config['audience'])

    from buyeros_api.providers.resend_delivery import ResendDeliveryAdapter
    async def refuse_submit(*args, **kwargs):
        control.send({'phase': 'provider-attempt'})
        raise AssertionError('owned API lifecycle cannot submit to a provider')
    ResendDeliveryAdapter.submit = refuse_submit
    if config.get('authority') is not None:
        from buyeros_api.api.routes import delivery
        delivery.selected_delivery_authorization = lambda **bindings: config['authority']

    original = idempotency.complete_idempotency
    def before_commit(outcome, *args, **kwargs):
        original(outcome, *args, **kwargs)
        if outcome.record.key == config.get('blocked_key'):
            control.send({'phase': 'before-commit', 'pid': os.getpid()})
            control.recv()  # parent hard-stops only this process at this boundary
    if config.get('phase') == 'before-commit':
        idempotency.complete_idempotency = before_commit

    original_app = create_app()
    async def app(scope, receive, send):
        async def observed(message):
            if (scope['type'] == 'http' and scope['method'] == 'POST'
                    and config.get('phase') == 'after-commit'
                    and message['type'] == 'http.response.start'):
                control.send({'phase': 'after-commit', 'status': message['status'], 'pid': os.getpid()})
                await asyncio.Event().wait()  # transaction committed; transport has no response
            await send(message)
        await original_app(scope, receive, observed)

    async def run():
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False, loop='asyncio'))
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            while not server.started:
                if task.done():
                    await task
                    raise AssertionError('owned API failed startup')
                await asyncio.sleep(0.01)
            control.send({'phase': 'ready', 'port': sock.getsockname()[1], 'pid': os.getpid()})
            while not task.done():
                if control.poll():
                    assert control.recv() == 'shutdown'
                    server.should_exit = True
                await asyncio.sleep(0.01)
            await task
        finally:
            sock.close()
    try:
        asyncio.run(run())
    finally:
        control.close()


class OwnedAPIProcess:
    def __init__(self, config):
        self.config = config
        self.process = None
        self.control = None
        self.ready = None
        self.exit = None

    def __enter__(self):
        ctx = multiprocessing.get_context('spawn')
        self.control, child_control = ctx.Pipe()
        self.process = ctx.Process(target=serve, args=(self.config, child_control))
        self.process.start()
        child_control.close()
        try:
            self.ready = self.event('ready', timeout=20)
            assert self.ready['pid'] == self.process.pid
            self.base_url = 'http://127.0.0.1:' + str(self.ready['port'])
            return self
        except BaseException:
            self.stop(hard=True)
            raise

    def event(self, phase, timeout=15):
        assert self.control.poll(timeout), 'owned process did not reach ' + phase
        event = self.control.recv()
        assert event['phase'] == phase, event
        return event

    def stop(self, *, hard=False):
        if self.process is None:
            return
        if self.process.is_alive():
            if hard:
                self.process.terminate()
            else:
                self.control.send('shutdown')
            self.process.join(timeout=10)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=5)
            raise AssertionError('owned API failed bounded shutdown')
        assert self.process.exitcode is not None
        self.exit = {'pid': self.process.pid, 'exitcode': self.process.exitcode, 'hard': hard,
                     'alive': self.process.is_alive()}

    def __exit__(self, *exc):
        self.stop(hard=exc[0] is not None)
        self.control.close()


def process_config(dsn, **extra):
    from tests import auth_fixtures as fx
    from tests.conftest import _require_disposable_test_dsn, runtime_role_dsn
    _require_disposable_test_dsn(dsn)
    label = 'owned-api-' + uuid.uuid4().hex
    return dict(runtime_dsn=runtime_role_dsn(dsn) + '?application_name=' + label,
                backend_label=label, issuer=fx.ISSUER,
                audience=fx.AUDIENCE, jwks=fx.jwks_document(), **extra)


def wait_for_backend_exit(dsn, pids):
    import psycopg
    deadline = time.monotonic() + 10
    with psycopg.connect(dsn, autocommit=True) as db:
        while True:
            rows = db.execute('SELECT pid FROM pg_stat_activity WHERE pid=ANY(%s)', (pids,)).fetchall()
            if not rows:
                return []
            assert time.monotonic() < deadline, rows
            time.sleep(0.01)


def runtime_backends(dsn, label):
    import psycopg
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT pid,state FROM pg_stat_activity WHERE usename='buyeros_api' AND application_name=%s ORDER BY pid", (label,)).fetchall()
