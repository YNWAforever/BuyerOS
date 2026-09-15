from buyeros_api.services.safe_fetch import is_blocked_host, normalize_url


def test_blocks_private_loopback_link_local_and_ipv6_local():
    for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1", "fe80::1"):
        assert is_blocked_host(ip), ip


def test_allows_public_ipv4():
    assert not is_blocked_host("93.184.216.34")


def test_normalize_strips_fragment_and_default_port():
    assert normalize_url("HTTPS://Example.com:443/a#frag") == "https://example.com/a"


def test_normalize_keeps_non_default_port():
    assert normalize_url("http://example.com:8080/x") == "http://example.com:8080/x"
