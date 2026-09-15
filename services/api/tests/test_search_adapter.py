import pytest

from buyeros_api.providers.search import FixtureSearchAdapter, SearchCapability, is_activation_allowed


def test_unverified_provider_cannot_activate():
    assert not is_activation_allowed(SearchCapability(verified=False, max_results=10, bounded_price=False))
    assert not is_activation_allowed(SearchCapability(verified=True, max_results=10, bounded_price=False))
    assert is_activation_allowed(SearchCapability(verified=True, max_results=10, bounded_price=True))


@pytest.mark.asyncio
async def test_fixture_adapter_is_deterministic_and_bounded():
    adapter = FixtureSearchAdapter(
        [{"url": "https://ex.com", "title": "t"}, {"url": "https://ex2.com", "title": "t2"}]
    )
    first = await adapter.search("q", "DE", "de", 5)
    second = await adapter.search("q", "DE", "de", 5)
    assert first == second
    assert [r.url for r in first] == ["https://ex.com", "https://ex2.com"]


@pytest.mark.asyncio
async def test_fixture_adapter_respects_limit():
    adapter = FixtureSearchAdapter([{"url": f"https://e{i}.com", "title": "t"} for i in range(5)])
    assert len(await adapter.search("q", "DE", "de", 2)) == 2
