# Task 1 review package
## commits
```
6b92180 fix(build): make buyeros-api installable so the worker path dependency resolves
4264b03 feat(worker): bootstrap buyeros_worker package and celery app
```
## stat (lockfiles excluded)
```
 services/api/pyproject.toml                |  7 +++++++
 services/worker/buyeros_worker/__init__.py |  2 ++
 services/worker/buyeros_worker/app.py      | 25 +++++++++++++++++++++++++
 services/worker/buyeros_worker/config.py   | 17 +++++++++++++++++
 services/worker/pyproject.toml             | 26 ++++++++++++++++++++++++++
 services/worker/tests/__init__.py          |  0
 services/worker/tests/test_app.py          | 21 +++++++++++++++++++++
 7 files changed, 98 insertions(+)
```
## diff (lockfiles excluded)
```diff
diff --git a/services/api/pyproject.toml b/services/api/pyproject.toml
index 6503bce..9598246 100644
--- a/services/api/pyproject.toml
+++ b/services/api/pyproject.toml
@@ -17,10 +17,17 @@ dev = [
   "pytest-asyncio>=0.24,<1",
 ]
 
 [tool.pytest.ini_options]
 testpaths = ["tests"]
 pythonpath = ["."]
 
 # NOTE (BO-005 spike): fastapi, asyncpg and pyjwt[crypto] are intentionally
 # omitted here; they are added when BO-004 (bearer identity) and the HTTP
 # layer (BO-003/BO-007+) are implemented. No auth or API route exists yet.
+
+[build-system]
+requires = ["hatchling"]
+build-backend = "hatchling.build"
+
+[tool.hatch.build.targets.wheel]
+packages = ["buyeros_api"]
diff --git a/services/worker/buyeros_worker/__init__.py b/services/worker/buyeros_worker/__init__.py
new file mode 100644
index 0000000..07c5de9
--- /dev/null
+++ b/services/worker/buyeros_worker/__init__.py
@@ -0,0 +1,2 @@
+__all__ = ["__version__"]
+__version__ = "0.1.0"
diff --git a/services/worker/buyeros_worker/app.py b/services/worker/buyeros_worker/app.py
new file mode 100644
index 0000000..6b5be3c
--- /dev/null
+++ b/services/worker/buyeros_worker/app.py
@@ -0,0 +1,25 @@
+from celery import Celery
+
+from .config import get_settings
+
+
+def build_app() -> Celery:
+    settings = get_settings()
+    app = Celery("buyeros_worker", broker=settings.broker_url)
+    app.conf.update(
+        task_ignore_result=True,
+        task_acks_late=True,
+        worker_prefetch_multiplier=1,
+        broker_connection_retry_on_startup=True,
+    )
+    return app
+
+
+celery_app = build_app()
+
+
+def configure_eager(app: Celery, enabled: bool) -> None:
+    app.conf.task_always_eager = bool(enabled)
+
+
+celery_app.autodiscover_tasks(["buyeros_worker"])
diff --git a/services/worker/buyeros_worker/config.py b/services/worker/buyeros_worker/config.py
new file mode 100644
index 0000000..9bd5ffd
--- /dev/null
+++ b/services/worker/buyeros_worker/config.py
@@ -0,0 +1,17 @@
+from functools import lru_cache
+
+from pydantic_settings import BaseSettings, SettingsConfigDict
+
+
+class WorkerSettings(BaseSettings):
+    model_config = SettingsConfigDict(env_prefix="BUYEROS_", extra="ignore")
+
+    broker_url: str = "redis://localhost:6379/0"
+    eager: bool = False
+    lease_seconds: int = 120
+    batch_size: int = 10
+
+
+@lru_cache
+def get_settings() -> WorkerSettings:
+    return WorkerSettings()
diff --git a/services/worker/pyproject.toml b/services/worker/pyproject.toml
new file mode 100644
index 0000000..7121a71
--- /dev/null
+++ b/services/worker/pyproject.toml
@@ -0,0 +1,26 @@
+[project]
+name = "buyeros-worker"
+version = "0.1.0"
+requires-python = ">=3.12"
+dependencies = [
+  "buyeros-api",
+  "celery>=5.4,<6",
+  "redis>=5,<6",
+  "psycopg[binary]>=3.2,<4",
+  "pydantic-settings>=2.5,<3",
+]
+
+[tool.uv.sources]
+buyeros-api = { path = "../api" }
+
+# NOTE (P8 worker): `buyeros_api` is installed from the local path `../api`.
+# `services/api` declares a hatchling build-system that packages only
+# `buyeros_api`, so the path dependency builds and `import buyeros_api` works
+# at runtime (not just under pytest).
+
+[dependency-groups]
+dev = ["pytest>=8.3,<9", "pytest-asyncio>=0.24,<1"]
+
+[tool.pytest.ini_options]
+testpaths = ["tests"]
+pythonpath = ["."]
diff --git a/services/worker/tests/__init__.py b/services/worker/tests/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/services/worker/tests/test_app.py b/services/worker/tests/test_app.py
new file mode 100644
index 0000000..f778507
--- /dev/null
+++ b/services/worker/tests/test_app.py
@@ -0,0 +1,21 @@
+from buyeros_worker.app import celery_app, configure_eager
+from buyeros_worker.config import WorkerSettings
+
+
+def test_settings_defaults_are_safe():
+    s = WorkerSettings()
+    assert s.lease_seconds == 120
+    assert s.batch_size == 10
+    assert s.eager is False
+
+
+def test_celery_app_is_named_and_has_no_result_backend():
+    assert celery_app.main == "buyeros_worker"
+    assert celery_app.conf.task_ignore_result is True
+
+
+def test_eager_mode_can_be_enabled():
+    configure_eager(celery_app, True)
+    assert celery_app.conf.task_always_eager is True
+    configure_eager(celery_app, False)
+    assert celery_app.conf.task_always_eager is False

```
## lockfile stat (contents omitted)
```
 services/api/uv.lock    |   2 +-
 services/worker/uv.lock | 711 ++++++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 712 insertions(+), 1 deletion(-)
```
