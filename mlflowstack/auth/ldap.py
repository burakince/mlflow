import os
import ldap3
import ssl
from typing import Union
from dataclasses import dataclass
from flask import Response, make_response, request
from mlflow.server.auth import store as auth_store
from werkzeug.datastructures import Authorization

import logging
from ldap3.utils.log import set_library_log_activation_level, get_library_log_detail_level, set_library_log_detail_level

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create a specific logger for LDAP and SSL
ldap_logger = logging.getLogger('ldap')
ldap_logger.setLevel(logging.DEBUG)

# Enable detailed LDAP library logging
set_library_log_activation_level(logging.DEBUG)
set_library_log_detail_level(get_library_log_detail_level() + 10)

# Create SSL logger
ssl_logger = logging.getLogger('ssl')
ssl_logger.setLevel(logging.DEBUG)

_auth_store = auth_store


LDAP_URI                    = os.getenv("LDAP_URI", "")
LDAP_CA                     = os.getenv("LDAP_CA", "")
LDAP_TLS_VERIFY             = os.getenv("LDAP_TLS_VERIFY", "required")
LDAP_LOOKUP_BIND            = os.getenv("LDAP_LOOKUP_BIND", "")

LDAP_GROUP_ATTRIBUTE        = os.getenv("LDAP_GROUP_ATTRIBUTE", "")
LDAP_GROUP_SEARCH_BASE_DN   = os.getenv("LDAP_GROUP_SEARCH_BASE_DN", "")
LDAP_GROUP_SEARCH_FILTER    = os.getenv("LDAP_GROUP_SEARCH_FILTER", "")

LDAP_GROUP_USER_DN          = os.getenv("LDAP_GROUP_USER_DN", "")
LDAP_GROUP_ADMIN_DN         = os.getenv("LDAP_GROUP_ADMIN_DN", "")

# TLS verification mapping
TLS_VERIFY_MAP = {
    "none": ssl.CERT_NONE,
    "optional": ssl.CERT_OPTIONAL,
    "required": ssl.CERT_REQUIRED
}

# Cache LDAP URI parsing result since it's constant
_PARSED_LDAP_URI = ldap3.utils.uri.parse_uri(LDAP_URI)
_DEFAULT_PORTS = {True: 636, False: 389}  # ssl: port mapping

@dataclass(frozen=True)
class UserInfo:
    """user information obect, to keep user data information and group membersip inclusive auth-store update"""
    name: str
    is_user: bool = False
    is_admin: bool = False

    @property
    def authenticated(self) -> bool:
        return self.is_admin or self.is_user

    def update(self) -> None:
        if not self.authenticated:
            return
            
        # Combine create/update into single operation
        _auth_store.update_user(self.name, self.name, self.is_admin) if _auth_store.has_user(self.name) \
            else _auth_store.create_user(self.name, self.name, self.is_admin)


def resolve_user(username: str, password: str) -> UserInfo:
    """Resolve user and group membership"""
    uri = _PARSED_LDAP_URI
    port = uri["port"] or _DEFAULT_PORTS[uri["ssl"]]
    
    # Enhanced TLS configuration
    tls = None
    if uri["ssl"] or LDAP_CA:
        tls = ldap3.Tls(
            validate=TLS_VERIFY_MAP.get(LDAP_TLS_VERIFY, ssl.CERT_REQUIRED),
            ca_certs_file=LDAP_CA if LDAP_CA else None,
        )

    server = ldap3.Server(
        host=uri["host"],
        port=port,
        use_ssl=uri["ssl"],
        tls=tls,
        get_info=ldap3.ALL if tls else ldap3.NONE
    )
    
    escaped_username = ldap3.utils.dn.escape_rdn(username)
    bind_user = LDAP_LOOKUP_BIND % escaped_username
    
    with ldap3.Connection(
        server=server,
        user=bind_user,
        password=password,
        client_strategy=ldap3.SAFE_SYNC,
        auto_bind=True,
        read_only=True
    ) as c:
        status, _, result, _ = c.search(
            search_base=LDAP_GROUP_SEARCH_BASE_DN,
            search_filter=LDAP_GROUP_SEARCH_FILTER % bind_user,
            search_scope=ldap3.SUBTREE,
            attributes=LDAP_GROUP_ATTRIBUTE,
            get_operational_attributes=False
        )

        if not status:
            return UserInfo(name=username)

        # Use any() for more efficient group checking
        is_admin = any(g[LDAP_GROUP_ATTRIBUTE] == LDAP_GROUP_ADMIN_DN for g in result)
        if is_admin:
            return UserInfo(name=username, is_admin=True)
            
        is_user = any(g[LDAP_GROUP_ATTRIBUTE] == LDAP_GROUP_USER_DN for g in result)
        return UserInfo(name=username, is_user=is_user)



def authenticate_request_basic_auth() -> Union[Authorization, Response]:
    """Using for the basic.ini as auth function, authenticate the incoming request, grant the admin role if the user is in the admin group; otherwise, grant normal user access"""
    if request.authorization is None:
        return _unauthorized_response("Your login has been cancelled")
      
    if not request.authorization.username or not request.authorization.password:
        return _unauthorized_response("Username or password cannot be empty.")
    
    try:
        user = resolve_user(
            request.authorization.username,
            request.authorization.password
        )
    except Exception as e:
        ldap_logger.error(f"Authentication failed for user {request.authorization.username}: {str(e)}", exc_info=True)
        return _unauthorized_response("Please ensure you are included in the group and input correct credentials!")

    if user.authenticated:
        user.update()
        return request.authorization
    
    return _unauthorized_response("Please ensure you are included in the group and input correct credentials!")


def _unauthorized_response(message: str = "You are not authenticated. Please enter your username and password."):
    """Return an unauthorized response with a custom message."""
    res = make_response(message)
    res.status_code = 401
    res.headers["WWW-Authenticate"] = 'Basic realm="mlflow"'
    return res
