import os
import sys
import pytest


BASE_ENV_VARS = {
    "LDAP_URI": "ldap://my-ldap:3890/dc=mlflow,dc=test",
    "LDAP_LOOKUP_BIND": "uid=%s,ou=people,dc=mlflow,dc=test",
    "LDAP_GROUP_SEARCH_BASE_DN": "ou=groups,dc=mlflow,dc=test",
    "LDAP_GROUP_SEARCH_FILTER": "(&(objectclass=groupOfUniqueNames)(uniquemember=%s))",
    "LDAP_GROUP_USER_DN": "cn=test-user,ou=groups,dc=mlflow,dc=test",
    "LDAP_GROUP_ADMIN_DN": "cn=test-admin,ou=groups,dc=mlflow,dc=test",
    "LDAP_GROUP_ATTRIBUTE": "dn",
    "LDAP_GROUP_ATTRIBUTE_KEY": "",
}

@pytest.fixture(autouse=True)
def setup_ldap_env(monkeypatch):
    for key, value in BASE_ENV_VARS.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setattr(
        "ldap3.utils.uri.parse_uri",
        lambda x: {"host": "my-ldap", "port": 3890, "ssl": False} if x else None,
    )

    module_name = "mlflowstack.auth.ldap"
    if module_name in sys.modules:
        del sys.modules[module_name]

def test_resolve_user_lldap_admin_from_dn(mocker):
    from mlflowstack.auth.ldap import resolve_user, UserInfo

    mocker.patch("ldap3.utils.uri.parse_uri").return_value = {
        "host": "my-ldap",
        "port": 3890,
        "ssl": False,
    }
    mocker.patch("ldap3.utils.dn.escape_rdn").return_value = "admin1"
    mocker.patch("ldap3.Server")
    mocker.patch("ldap3.Tls")

    mock_conn = mocker.MagicMock()
    mocker.patch("ldap3.Connection").return_value.__enter__.return_value = mock_conn
    mock_conn.search.return_value = (
        True,
        None,
        [
            {
                "dn": "cn=test-admin,ou=groups,dc=mlflow,dc=test",
                "attributes": {"dn": []},
                "type": "searchResEntry",
            }
        ],
        None,
    )

    result = resolve_user("admin1", "admin1-123456")

    assert result == UserInfo(name="admin1", is_admin=True)
    mock_conn.search.assert_called_once_with(
        search_base="ou=groups,dc=mlflow,dc=test",
        search_filter="(&(objectclass=groupOfUniqueNames)(uniquemember=uid=admin1,ou=people,dc=mlflow,dc=test))",
        search_scope="SUBTREE",
        attributes="dn",
        get_operational_attributes=False,
    )

def test_resolve_user_lldap_admin_from_attributes_when_dn_is_list(mocker):
    mocker.patch.dict(os.environ, {"LDAP_GROUP_ATTRIBUTE_KEY": "attributes"})

    from mlflowstack.auth.ldap import resolve_user, UserInfo

    mocker.patch("ldap3.utils.uri.parse_uri").return_value = {
        "host": "my-ldap",
        "port": 3890,
        "ssl": False,
    }
    mocker.patch("ldap3.utils.dn.escape_rdn").return_value = "admin1"
    mocker.patch("ldap3.Server")
    mocker.patch("ldap3.Tls")

    mock_conn = mocker.MagicMock()
    mocker.patch("ldap3.Connection").return_value.__enter__.return_value = mock_conn
    mock_conn.search.return_value = (
        True,
        None,
        [
            {
                "dn": "something-else",
                "attributes": {"dn": ["cn=test-admin,ou=groups,dc=mlflow,dc=test"]},
                "type": "searchResEntry",
            }
        ],
        None,
    )

    result = resolve_user("admin1", "admin1-123456")

    assert result == UserInfo(name="admin1", is_admin=True)
    mock_conn.search.assert_called_once_with(
        search_base="ou=groups,dc=mlflow,dc=test",
        search_filter="(&(objectclass=groupOfUniqueNames)(uniquemember=uid=admin1,ou=people,dc=mlflow,dc=test))",
        search_scope="SUBTREE",
        attributes="dn",
        get_operational_attributes=False,
    )

def test_resolve_user_lldap_admin_from_attributes_when_dn_is_string(mocker):
    mocker.patch.dict(os.environ, {"LDAP_GROUP_ATTRIBUTE_KEY": "attributes"})

    from mlflowstack.auth.ldap import resolve_user, UserInfo

    mocker.patch("ldap3.utils.uri.parse_uri").return_value = {
        "host": "my-ldap",
        "port": 3890,
        "ssl": False,
    }
    mocker.patch("ldap3.utils.dn.escape_rdn").return_value = "admin1"
    mocker.patch("ldap3.Server")
    mocker.patch("ldap3.Tls")

    mock_conn = mocker.MagicMock()
    mocker.patch("ldap3.Connection").return_value.__enter__.return_value = mock_conn
    mock_conn.search.return_value = (
        True,
        None,
        [
            {
                "dn": "something-else",
                "attributes": {"dn": "cn=test-admin,ou=groups,dc=mlflow,dc=test"},
                "type": "searchResEntry",
            }
        ],
        None,
    )

    result = resolve_user("admin1", "admin1-123456")

    assert result == UserInfo(name="admin1", is_admin=True)
    mock_conn.search.assert_called_once_with(
        search_base="ou=groups,dc=mlflow,dc=test",
        search_filter="(&(objectclass=groupOfUniqueNames)(uniquemember=uid=admin1,ou=people,dc=mlflow,dc=test))",
        search_scope="SUBTREE",
        attributes="dn",
        get_operational_attributes=False,
    )

def test_resolve_user_ad_user_when_dn_is_list(mocker):
    mocker.patch.dict(os.environ, {"LDAP_GROUP_ATTRIBUTE_KEY": "attributes"})

    from mlflowstack.auth.ldap import resolve_user, UserInfo

    mocker.patch("ldap3.utils.uri.parse_uri").return_value = {
        "host": "my-ldap",
        "port": 3890,
        "ssl": False,
    }
    mocker.patch("ldap3.utils.dn.escape_rdn").return_value = "user1"
    mocker.patch("ldap3.Server")
    mocker.patch("ldap3.Tls")

    mock_conn = mocker.MagicMock()
    mocker.patch("ldap3.Connection").return_value.__enter__.return_value = mock_conn
    mock_conn.search.return_value = (
        True,
        None,
        [
            {
                "dn": "something-else",
                "attributes": {"dn": ["cn=test-user,ou=groups,dc=mlflow,dc=test"]},
                "type": "searchResEntry",
            }
        ],
        None,
    )

    result = resolve_user("user1", "user1-123456")

    assert result == UserInfo(name="user1", is_user=True)
    mock_conn.search.assert_called_once_with(
        search_base="ou=groups,dc=mlflow,dc=test",
        search_filter="(&(objectclass=groupOfUniqueNames)(uniquemember=uid=user1,ou=people,dc=mlflow,dc=test))",
        search_scope="SUBTREE",
        attributes="dn",
        get_operational_attributes=False,
    )

def test_resolve_user_ad_user_when_dn_is_string(mocker):
    mocker.patch.dict(os.environ, {"LDAP_GROUP_ATTRIBUTE_KEY": "attributes"})

    from mlflowstack.auth.ldap import resolve_user, UserInfo

    mocker.patch("ldap3.utils.uri.parse_uri").return_value = {
        "host": "my-ldap",
        "port": 3890,
        "ssl": False,
    }
    mocker.patch("ldap3.utils.dn.escape_rdn").return_value = "user1"
    mocker.patch("ldap3.Server")
    mocker.patch("ldap3.Tls")

    mock_conn = mocker.MagicMock()
    mocker.patch("ldap3.Connection").return_value.__enter__.return_value = mock_conn
    mock_conn.search.return_value = (
        True,
        None,
        [
            {
                "dn": "something-else",
                "attributes": {"dn": "cn=test-user,ou=groups,dc=mlflow,dc=test"},
                "type": "searchResEntry",
            }
        ],
        None,
    )

    result = resolve_user("user1", "user1-123456")

    assert result == UserInfo(name="user1", is_user=True)
    mock_conn.search.assert_called_once_with(
        search_base="ou=groups,dc=mlflow,dc=test",
        search_filter="(&(objectclass=groupOfUniqueNames)(uniquemember=uid=user1,ou=people,dc=mlflow,dc=test))",
        search_scope="SUBTREE",
        attributes="dn",
        get_operational_attributes=False,
    )

def test_resolve_user_ad_user(mocker):
    from mlflowstack.auth.ldap import resolve_user, UserInfo

    mocker.patch("ldap3.utils.uri.parse_uri").return_value = {
        "host": "my-ldap",
        "port": 3890,
        "ssl": False,
    }
    mocker.patch("ldap3.utils.dn.escape_rdn").return_value = "user1"
    mocker.patch("ldap3.Server")
    mocker.patch("ldap3.Tls")

    mock_conn = mocker.MagicMock()
    mocker.patch("ldap3.Connection").return_value.__enter__.return_value = mock_conn
    mock_conn.search.return_value = (
        True,
        None,
        [
            {
                "dn": "cn=test-user,ou=groups,dc=mlflow,dc=test",
                "attributes": {"dn": []},
                "type": "searchResEntry",
            }
        ],
        None,
    )

    result = resolve_user("user1", "user1-123456")

    assert result == UserInfo(name="user1", is_user=True)
    mock_conn.search.assert_called_once_with(
        search_base="ou=groups,dc=mlflow,dc=test",
        search_filter="(&(objectclass=groupOfUniqueNames)(uniquemember=uid=user1,ou=people,dc=mlflow,dc=test))",
        search_scope="SUBTREE",
        attributes="dn",
        get_operational_attributes=False,
    )

def test_resolve_user_search_failure(mocker):
    from mlflowstack.auth.ldap import resolve_user, UserInfo

    mocker.patch("ldap3.utils.uri.parse_uri").return_value = {
        "host": "my-ldap",
        "port": 3890,
        "ssl": False,
    }
    mocker.patch("ldap3.utils.dn.escape_rdn").return_value = "testuser"
    mocker.patch("ldap3.Server")
    mocker.patch("ldap3.Tls")

    mock_conn = mocker.MagicMock()
    mocker.patch("ldap3.Connection").return_value.__enter__.return_value = mock_conn
    mock_conn.search.return_value = (
        False,
        None,
        [],
        None,
    )

    result = resolve_user("testuser", "password")

    assert result == UserInfo(name="testuser", is_user=False, is_admin=False)
