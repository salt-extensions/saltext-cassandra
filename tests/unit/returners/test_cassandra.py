import pytest

import saltext.cassandra.returners.cassandra_mod as cassandra_returner


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {"this_does_not_exist.please_replace_it": lambda: True},
    }
    return {
        cassandra_returner: module_globals,
    }


def test_replace_this_this_with_something_meaningful():
    assert "this_does_not_exist.please_replace_it" in cassandra_returner.__salt__
    assert cassandra_returner.__salt__["this_does_not_exist.please_replace_it"]() is True
