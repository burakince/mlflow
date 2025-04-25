import logging
import os
import ssl
from dataclasses import dataclass
from typing import Union

import ldap3
from flask import Response, make_response, request
from werkzeug.datastructures import Authorization

from mlflow.server.auth import store as auth_store


_auth_store = auth_store
logger = logging.getLogger(__name__)



# LDAP server URI (e.g., ldaps://ldap.example.com)
LDAP_URI = os.getenv("LDAP_URI", "")

# Path to CA certificate file for LDAP TLS
LDAP_CA = os.getenv("LDAP_CA", "")

# TLS verification level (values: none | optional | required)
LDAP_TLS_VERIFY = os.getenv("LDAP_TLS_VERIFY", "required")


# Template for user bind DN
LDAP_LOOKUP_BIND = os.getenv("LDAP_LOOKUP_BIND", "")


# Attribute containing group DN
LDAP_GROUP_ATTRIBUTE = os.getenv("LDAP_GROUP_ATTRIBUTE", "")

# Base DN for group search
LDAP_GROUP_SEARCH_BASE_DN = os.getenv("LDAP_GROUP_SEARCH_BASE_DN", "")

# Filter template for group search
LDAP_GROUP_SEARCH_FILTER = os.getenv("LDAP_GROUP_SEARCH_FILTER", "")


# DN of regular users group
LDAP_GROUP_USER_DN = os.getenv("LDAP_GROUP_USER_DN", "")

# DN of administrators group
LDAP_GROUP_ADMIN_DN = os.getenv("LDAP_GROUP_ADMIN_DN", "")


# TLS verification mapping for different security levels
TLS_VERIFY_MAP = {
    "none": ssl.CERT_NONE,
    "optional": ssl.CERT_OPTIONAL,
    "required": ssl.CERT_REQUIRED
}

# Cache LDAP URI parsing result since it's constant
_PARSED_LDAP_URI = ldap3.utils.uri.parse_uri(LDAP_URI)

# Default ports mapping for SSL and non-SSL connections
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
        _auth_store.update_user(self.name, str(abs(hash(self.name))), self.is_admin) if _auth_store.has_user(self.name) \
            else _auth_store.create_user(self.name, str(abs(hash(self.name))), self.is_admin)


def resolve_user(username: str, password: str) -> UserInfo:
    """Authenticate user against LDAP and resolve group membership."""
    try:
        uri = _PARSED_LDAP_URI
        # Get port from URI or use default based on SSL status
        port = uri["port"] or _DEFAULT_PORTS[uri["ssl"]]
        
        # Configure TLS if SSL is enabled or CA certificate is provided
        tls = None
        if uri["ssl"] or LDAP_CA:
            tls = ldap3.Tls(
                validate=TLS_VERIFY_MAP.get(LDAP_TLS_VERIFY, ssl.CERT_REQUIRED),
                ca_certs_file=LDAP_CA if LDAP_CA else None,
            )

        # Initialize LDAP server connection
        server = ldap3.Server(
            host=uri["host"],
            port=port,
            use_ssl=uri["ssl"],
            tls=tls,
            get_info=ldap3.ALL if tls else ldap3.NONE
        )
        
        # Escape special characters in username
        escaped_username = ldap3.utils.dn.escape_rdn(username)
        # Format bind user string with escaped username
        bind_user = LDAP_LOOKUP_BIND % escaped_username
        
        with ldap3.Connection(
            server=server,
            user=bind_user,
            password=password,
            client_strategy=ldap3.SAFE_SYNC,
            auto_bind=True,
            read_only=True
        ) as c:
            # Search for user's group memberships
            status, _, result, _ = c.search(
                search_base=LDAP_GROUP_SEARCH_BASE_DN,
                search_filter=LDAP_GROUP_SEARCH_FILTER % bind_user,
                search_scope=ldap3.SUBTREE,
                attributes=LDAP_GROUP_ATTRIBUTE,
                get_operational_attributes=False
            )

            if not status:
                logger.warning(f"Search failed for user {username}")
                return UserInfo(name=username)

            # Check for admin group membership
            is_admin = any(g[LDAP_GROUP_ATTRIBUTE] == LDAP_GROUP_ADMIN_DN for g in result)
            if is_admin:
                logger.info(f"User {username} authenticated as admin")
                return UserInfo(name=username, is_admin=True)
                
            # Check for regular user group membership
            is_user = any(g[LDAP_GROUP_ATTRIBUTE] == LDAP_GROUP_USER_DN for g in result)
            if is_user:
                logger.info(f"User {username} authenticated as regular user")
            else:
                logger.warning(f"User {username} not found in any authorized groups")
            return UserInfo(name=username, is_user=is_user)
    except Exception as e:
        logger.error(f"Error resolving user {username}: {str(e)}", exc_info=True)
        raise


def authenticate_request_basic_auth() -> Union[Authorization, Response]:
    """Using for the basic.ini as auth function, authenticate the incoming request, grant the admin role if the user is in the admin group; otherwise, grant normal user access"""
    if request.authorization is None:
        logger.warning("Authentication cancelled by user")
        return _unauthorized_response("Your login has been cancelled")
      
    if not request.authorization.username or not request.authorization.password:
        logger.warning("Empty username or password provided")
        return _unauthorized_response("Username or password cannot be empty.")
    
    try:
        user = resolve_user(
            request.authorization.username,
            request.authorization.password
        )
    except Exception as e:
        logger.error(f"Authentication failed for user {request.authorization.username}: {str(e)}", exc_info=True)
        return _unauthorized_response("Please ensure you are included in the group and input correct credentials!")

    if user.authenticated:
        user.update()
        return request.authorization
    
    logger.warning(f"Authentication failed for user {request.authorization.username}: not in authorized groups")
    return _unauthorized_response("Please ensure you are included in the group and input correct credentials!")


def _unauthorized_response(message: str = "You are not authenticated. Please enter your username and password."):
    """Return an unauthorized response with a custom message."""
    res = make_response(message)
    res.status_code = 401
    res.headers["WWW-Authenticate"] = 'Basic realm="mlflow"'
    return res
