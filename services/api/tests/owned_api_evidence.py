"""Native JUnit proof attachment without pytest's legacy XML attribute API."""
import pytest


@pytest.fixture
def record_property(request):
    def record(name, value):
        request.node.user_properties.append((name, value))
    return record
