from __future__ import annotations

import logging
import os
import sys
import typing as t

import globus_sdk
from globus_sdk.scopes import AuthScopes, ScopeBuilder, SearchScopes

from ..web_client import FuncxWebClient
from .client_login import get_client_login, is_client_login
from .globus_auth import internal_auth_client
from .login_flow import do_link_auth_flow
from .tokenstore import get_token_storage_adapter

log = logging.getLogger(__name__)


def _get_funcx_all_scope() -> str:
    return os.getenv(
        "FUNCX_SCOPE",
        "https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all",
    )


class FuncxScopeBuilder(ScopeBuilder):
    # FIXME:
    # for some reason, the funcx resource server name on the production scope is
    # "funcx_service" even though this doesn't match the resource server ID and the
    # scope is in URL format
    # at some point, we ought to work out how to fix this to normalize this so that it
    # conforms to one of the known, pre-existing modes for scopes
    def __init__(self):
        super().__init__("funcx_service")
        self.all = _get_funcx_all_scope()


#: a ScopeBuilder in the style of globus_sdk.scopes for the FuncX service
#: it supports one scope named 'all', as in ``FuncxScopes.all``
FuncxScopes = FuncxScopeBuilder()


class LoginManager:
    """
    This class is primarily a wrapper over a sqlite tokenstorage adapter provided by the
    globus-sdk.
    See also: https://globus-sdk-python.readthedocs.io/en/stable/tokenstorage.html

    The purpose of the LoginManager is to hold a tokenstorage object and combine it with
    - a login flow which authenticates the user for the correct set of scopes
    - a helper method for ensuring that the user is logged in (only doing login if
      tokens are missing)
    - methods for building SDK client objects with correct RefreshTokenAuthorizer
      authorizers
    """

    SCOPES: dict[str, list[str]] = {
        FuncxScopes.resource_server: [FuncxScopes.all],
        AuthScopes.resource_server: [AuthScopes.openid],
        SearchScopes.resource_server: [SearchScopes.all],
    }

    def __init__(self, *, environment: str | None = None) -> None:
        self._token_storage = get_token_storage_adapter(environment=environment)

    @property
    def login_requirements(self) -> t.Iterator[tuple[str, list[str]]]:
        yield from self.SCOPES.items()

    def run_login_flow(
        self,
        *,
        scopes: list[str] | None = None,
    ):
        if is_client_login():
            # We don't need a login flow for a client login
            return

        # The authorization-via-weblink flow requires stdin; the user must visit
        # the weblink and enter generated code.
        if not sys.stdin.isatty() or sys.stdin.closed:
            # Not technically necessary; the login flow would just die with an EOF
            # during input(), but adding this message here is much more direct --
            # handle the non-happy path by letting the user know precisely the issue
            raise RuntimeError(
                "Unable to run native app login flow: stdin is closed or is not a TTY."
            )

        if scopes is None:  # flatten scopes to list of strings if none provided
            scopes = [
                s for _rs_name, rs_scopes in self.login_requirements for s in rs_scopes
            ]

        do_link_auth_flow(self._token_storage, scopes)

    def logout(self) -> bool:
        """
        Returns True if at least one set of tokens were found and revoked.
        """
        auth_client = internal_auth_client()
        tokens_revoked = False
        for rs, token_data in self._token_storage.get_by_resource_server().items():
            for tok_key in ("access_token", "refresh_token"):
                token = token_data[tok_key]
                auth_client.oauth2_revoke_token(token)
            self._token_storage.remove_tokens_for_resource_server(rs)
            tokens_revoked = True

        return tokens_revoked

    def ensure_logged_in(self) -> None:
        data = self._token_storage.get_by_resource_server()
        needs_login = False
        for rs_name, _rs_scopes in self.login_requirements:
            if rs_name not in data:
                needs_login = True
                break

        if needs_login:
            self.run_login_flow()

    def _get_authorizer(
        self, resource_server: str
    ) -> globus_sdk.authorizers.RenewingAuthorizer:
        log.debug("build authorizer for %s", resource_server)
        tokens = self._token_storage.get_token_data(resource_server)

        if is_client_login():
            # construct scopes for the specified resource server.
            # this is not guaranteed to contain always required scopes,
            # additional logic may be needed to handle client identities that
            # may be missing those.
            scopes = []
            for rs_name, rs_scopes in self.login_requirements:
                if rs_name == resource_server:
                    scopes.extend(rs_scopes)

            # if we already have a token use it. This token could be invalid
            # or for another client, but automatic retries will handle that
            access_token = None
            expires_at = None
            if tokens:
                access_token = tokens["access_token"]
                expires_at = tokens["expires_at_seconds"]

            return globus_sdk.ClientCredentialsAuthorizer(
                confidential_client=get_client_login(),
                scopes=scopes,
                access_token=access_token,
                expires_at=expires_at,
                on_refresh=self._token_storage.on_refresh,
            )
        else:
            if tokens is None:
                raise LookupError(
                    f"LoginManager could not find tokens for {resource_server}"
                )
            return globus_sdk.RefreshTokenAuthorizer(
                tokens["refresh_token"],
                internal_auth_client(),
                access_token=tokens["access_token"],
                expires_at=tokens["expires_at_seconds"],
                on_refresh=self._token_storage.on_refresh,
            )

    def get_auth_client(self) -> globus_sdk.AuthClient:
        return globus_sdk.AuthClient(
            authorizer=self._get_authorizer(AuthScopes.resource_server)
        )

    def get_search_client(self) -> globus_sdk.SearchClient:
        return globus_sdk.SearchClient(
            authorizer=self._get_authorizer(SearchScopes.resource_server)
        )

    def get_funcx_web_client(
        self, *, base_url: str | None = None, app_name: str | None = None
    ) -> FuncxWebClient:
        return FuncxWebClient(
            base_url=base_url,
            app_name=app_name,
            authorizer=self._get_authorizer(FuncxScopes.resource_server),
            transport_params = {"verify_ssl": False}
        )
