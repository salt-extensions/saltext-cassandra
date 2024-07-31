import pytest

pytestmark = [
    pytest.mark.requires_salt_modules("cassandra.example_function"),
]


@pytest.fixture
def cassandra(modules):
    return modules.cassandra


def test_replace_this_this_with_something_meaningful(cassandra):
    echo_str = "Echoed!"
    res = cassandra.example_function(echo_str)
    assert res == echo_str
