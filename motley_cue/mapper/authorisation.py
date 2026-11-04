"""
Authorisation module for motley_cue API.
"""

from enum import Enum
import logging

from fastapi import Request
from flaat import AuthWorkflow
from flaat.config import AccessLevel
from flaat.fastapi import Flaat
from flaat.requirements import CheckResult, Requirement
from flaat.user_infos import UserInfos
from flaat.exceptions import FlaatException

from motley_cue.mapper.config import Config, ConfigAuthorisation, canonical_url
from motley_cue.mapper.exceptions import Unauthorised

logger = logging.getLogger(__name__)


# We dynamically load the requirement in is_satisfied_by
class AuthRequirement(Requirement):
    """Base class for authorisation requirements corresponding to an OP."""

    # pylint: disable=too-few-public-methods
    def __init__(self, authorisation: ConfigAuthorisation):
        self.authorisation = authorisation


class AuthenticatedUserRequirement(AuthRequirement):
    """Requirement for a user to be able to login at the OP."""

    # pylint: disable=too-few-public-methods
    def is_satisfied_by(self, user_infos: UserInfos) -> CheckResult:
        """override method to use configured authorisation"""
        op_authz = self.authorisation.get_op_authz(user_infos)
        if op_authz is None:
            return CheckResult(False, "OP is not configured")

        return CheckResult(True, "OP is configured")


class AuthorisedUserRequirement(AuthRequirement):
    """Requirement for a user to meet the configured authorisation for the OP."""

    # pylint: disable=too-few-public-methods
    def is_satisfied_by(self, user_infos: UserInfos) -> CheckResult:
        """override method to use configured authorisation"""
        op_authz = self.authorisation.get_op_authz(user_infos)
        if op_authz is None:
            return CheckResult(False, "OP is not configured")

        return op_authz.get_user_requirement().is_satisfied_by(user_infos)


class AuthorisedAdminRequirement(AuthRequirement):
    """Requirement for an admin to meet the configured authorisation for the OP."""

    # pylint: disable=too-few-public-methods
    def is_satisfied_by(self, user_infos: UserInfos) -> CheckResult:
        """override method to use configured authorisation"""
        op_authz = self.authorisation.get_op_authz(user_infos)
        if op_authz is None:
            return CheckResult(False, "OP is not configured")

        return op_authz.get_admin_requirement().is_satisfied_by(user_infos)


class AuthorisationType(Enum):
    """Class to describe authorisation for an OP."""

    NOT_SUPPORTED = ("not supported", "OP is not supported.")
    NOT_CONFIGURED = (
        "not configured",
        "OP is supported but no authorisation is configured.",
    )
    ALL_USERS = ("all users", "All users from this OP are authorised.")
    INDIVIDUAL_USERS = (
        "individual users",
        "Users are authorised on an individual basis. "
        "Please contact a service administrator to request access.",
    )
    VO_BASED = ("VO-based", "Users who are in {} of the supported VOs are authorised")

    def __init__(self, mode, info):
        """Create authorisation type"""
        self.__mode = mode
        self.__info = info

    def description(self, vo_match="one", audience=""):
        """Return a description of the authorisation as a dict"""
        desc_dict = {
            "authorisation_type": self.__mode,
            "authorisation_info": self.__info.format(vo_match),
        }
        if audience is not None and audience != "" and audience != []:
            desc_dict["audience"] = audience
        return desc_dict


class Authorisation(Flaat):
    """Extension for Flaat:

    - configures Flaat parameters in given config file
    - more flexible authorisation:
        - per OP configuration
        - individual user authorisation
    - stringify authorisation info
    """

    def __init__(self, config: Config):
        """Initialise Authorisation from given Config object"""
        super().__init__()
        self.set_trusted_OP_list(config.trusted_ops)
        self.set_verbosity(config.verbosity)
        self.__authorisation = config.authorisation
        self.access_levels = [
            AccessLevel("authenticated_user", AuthenticatedUserRequirement(self.__authorisation)),
            AccessLevel("authorised_user", AuthorisedUserRequirement(self.__authorisation)),
            AccessLevel("authorised_admin", AuthorisedAdminRequirement(self.__authorisation)),
        ]
        self.__warn_about_unbound_audience()

    def __warn_about_unbound_audience(self) -> None:
        """Say so when a token issued for another service is accepted here.

        An empty `audience` means no audience check at all, so a token is
        accepted whatever service it was issued for -- every other relying party
        of that OP holds a credential that works here too. Combined with
        `authorise_all`, that credential is a shell account on this host.

        That is a legitimate configuration, and how ssh-oidc is often deployed,
        so this is a warning rather than a refusal. But it is a decision, and
        nothing in the config made it visible as one.

        One line for the whole config, not one per OP: a service with a dozen
        trusted OPs was producing a dozen identical warnings per worker on every
        start, which is how a message earns being ignored.
        """
        unbound = [
            op_authz.op_url
            for op_authz in self.__authorisation.all_op_authz.values()
            if op_authz.authorise_all and not op_authz.audience
        ]
        if unbound:
            logger.warning(
                "%d OP(s) authorise every user with no audience bound (%s): a token issued "
                "for any other service of those OPs is accepted here, and grants a local "
                "account. Set 'audience' per OP to bind tokens to this service.",
                len(unbound),
                ", ".join(unbound),
            )

    def info(self, request: Request) -> dict:
        """Return authorisation information for issuer of token.
        OIDC Access Token should be found in request headers.
        """
        # get OP from request
        try:
            user_infos = self.get_user_infos_from_request(request)
        except FlaatException as ex:
            logger.info("Error while trying to get user infos from request: %s", ex)
            user_infos = None
        if user_infos is None:
            raise Unauthorised("Could not get user infos from request.")
        op_authz = self.__authorisation.get_op_authz(user_infos)
        # if OP not supported
        if op_authz is None:
            return {
                "OP": user_infos.issuer,
                **AuthorisationType.NOT_SUPPORTED.description(),
            }
        # if all users from this OP are authorised
        if op_authz.authorise_all:
            return {
                "OP": op_authz.op_url,
                **AuthorisationType.ALL_USERS.description(audience=op_authz.audience),
            }
        # if authorised VOs are specified
        if len(op_authz.authorised_vos) > 0:
            return {
                "OP": op_authz.op_url,
                **AuthorisationType.VO_BASED.description(
                    vo_match=op_authz.vo_match, audience=op_authz.audience
                ),
                "supported_VOs": op_authz.authorised_vos,
            }
        # if individual users are specified
        if len(op_authz.authorised_users) > 0:
            return {
                "OP": op_authz.op_url,
                **AuthorisationType.INDIVIDUAL_USERS.description(audience=op_authz.audience),
            }

        # OP is supported but no authorisation is configured
        return {
            "OP": op_authz.op_url,
            **AuthorisationType.NOT_CONFIGURED.description(audience=op_authz.audience),
        }

    def authenticated_user_required(self, func):
        """Decorator that only allows users from supported OPs.
        OIDC Access Token should be found in request headers.
        """
        return self.access_level("authenticated_user")(func)

    def authorised_user_required(self, func):
        """Decorator that only allows users from supported OPs that meet the
        configured authorisation requirements.
        OIDC Access Token should be found in request headers.
        """
        return self.access_level("authorised_user")(func)

    def authorised_admin_required(self, func):
        """Decorator that only allows admins from supported OPs that meet the
        configured authorisation requirements.
        OIDC Access Token should be found in request headers.
        """

        def _check_request(user_infos: UserInfos, *_, **kwargs) -> CheckResult:
            user_iss = kwargs.get("iss", "")
            if "iss" in kwargs and user_iss == "":
                # an endpoint that takes an iss and was given an empty one used
                # to skip the same-issuer check entirely. Nothing matches an
                # empty issuer today, so this changed no outcome -- but a check
                # that is skipped by passing "" is not a check.
                return CheckResult(False, "Empty 'iss' given")
            if user_iss != "":
                op_authz = self.__authorisation.get_op_authz(user_infos)
                if op_authz is None:
                    return CheckResult(False, "No OP config")

                if not op_authz.authorise_admins_for_all_ops and canonical_url(
                    op_authz.op_url
                ) != canonical_url(user_iss):
                    logger.info(
                        "Admin from issuer %s is not authorised to manage users of issuer '%s'",
                        op_authz.op_url,
                        user_iss,
                    )
                    return CheckResult(
                        False,
                        f"Admin from issuer {op_authz.op_url} is not authorised to manage "
                        f"users of issuer '{user_iss}'",
                    )

            return CheckResult(True, "Request is authorised")

        auth_flow = AuthWorkflow(
            self,
            user_requirements=self._get_access_level_requirement("authorised_admin"),
            request_requirements=_check_request,
        )
        return auth_flow.decorate_view_func(func)

    @staticmethod
    def merged_userinfo(user_infos: UserInfos) -> dict:
        """Flatten a (flaat) UserInfos into the single claim dict feudalAdapter expects.

        A user's claims can arrive in any of three places -- the userinfo
        endpoint, the access token body (when it is a JWT) and token
        introspection -- and which one carries what differs per OP. feudalAdapter
        is deliberately unaware of all this and just reads claims out of one
        dict, so the merging happens here.

        Precedence matches flaat's own `UserInfos.__getitem__` (user_info >
        introspection_info > access_token_info.body), so feudalAdapter sees the
        same value for a claim that authorisation did. Since `user_info` is
        applied last, this can only ever *add* claims that were missing from it,
        never change one that was already there.

        Returns a new dict: `user_infos` is cached by flaat and shared between
        requests using the same access token, so it must not be modified.
        """
        merged = {}
        access_token_info = getattr(user_infos, "access_token_info", None)
        for source in [
            getattr(access_token_info, "body", None),
            getattr(user_infos, "introspection_info", None),
            getattr(user_infos, "user_info", None),
        ]:
            if source:
                merged.update(source)
        return merged

    def get_uid_from_request(self, request: Request):
        """Get a (flaat) UserInfos object from given request.
        OIDC Access Token should be found in request headers.
        """
        try:
            user_infos = self.get_user_infos_from_request(request)
        except Exception:  # pylint: disable=broad-except
            return None
        if user_infos is None:
            return None
        return {"sub": user_infos.subject, "iss": user_infos.issuer}
