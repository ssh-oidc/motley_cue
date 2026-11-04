"""Module for loading and describing motley_cue configuration."""

from configparser import ConfigParser
from typing import List, Optional, Dict
import logging
import os
from pathlib import Path
from dataclasses import dataclass, fields, field

from flaat.requirements import (
    IsTrue,
    OneOf,
    AllOf,
    Requirement,
    Unsatisfiable,
    get_vo_requirement,
    get_audience_requirement,
)

from motley_cue.mapper.exceptions import InternalException


class Config:
    """Class for motley_cue configuration."""

    def __init__(self, config_parser):
        """Create a configuration object from a ConfigParser.

        Args:
            config_parser (ConfigParser): ConfigParser object

        Raises:
            InternalException: if configuration does not contain mandatory section [mapper]
        """
        warn_about_swallowed_options(config_parser)
        self.CONFIG = Configuration.load(config_parser)

        self.__trusted_ops = [
            entry.op_url for entry in self.CONFIG.authorisation.all_op_authz.values()
        ]
        self.__info_ops = {
            canonical_url(entry.op_url): entry.get_info()
            for entry in self.CONFIG.authorisation.all_op_authz.values()
        }

    def get_op_info(self, op_url: str) -> Optional[Dict]:
        """Get information about an OP.

        Args:
            op_url (str): OP URL

        Returns:
            Optional[Dict]: information about the OP
        """
        return self.__info_ops.get(canonical_url(op_url))

    @property
    def trusted_ops(self):
        """Return list of trusted OPs"""
        return self.__trusted_ops

    @property
    def authorisation(self):
        """Return all authorisation sections in configuration"""
        return self.CONFIG.authorisation

    @property
    def log_file(self):
        """Return log file name"""
        return self.CONFIG.mapper.log_file

    @property
    def log_level(self):
        """return log level"""
        return self.CONFIG.mapper.log_level

    @property
    def docs_url(self):
        """return url to be used as location for swagger docs"""
        return self.CONFIG.mapper.docs_url if self.CONFIG.mapper.enable_docs else None

    @property
    def redoc_url(self):
        """return url to be used as location for redoc docs"""
        return self.CONFIG.mapper.redoc_url if self.CONFIG.mapper.enable_docs else None

    @property
    def api_version(self):
        """return api version"""
        return self.CONFIG.mapper.api_version

    @property
    def otp(self):
        """Return OTP configuration"""
        return self.CONFIG.otp

    @property
    def privacy(self):
        """Return privacy policy configuration"""
        return self.CONFIG.privacy

    @property
    def verbosity(self):
        """
        Translate given log level to verbosity needed by flaat as follows:
            CRITICAL -> 0
            ERROR -> 1
            WARNING / WARN -> 1
            INFO -> 2
            DEBUG -> 3
        default is 1
        """
        if self.log_level == "CRITICAL":
            return 0
        if self.log_level in ["ERROR", "WARNING", "WARN"]:
            return 1
        if self.log_level == "INFO":
            return 2
        if self.log_level == "DEBUG":
            return 3
        return 1

    @staticmethod
    def from_files(list_of_config_files: List):
        """Load motley_cue configuration from given list of files.
        Processing is stopped, once a give file is found.

        If no configuration is found in given list, default locations are checked.
        If none of the files exist, raise an InternalException.
        """
        list_of_config_files.extend(Config._reload_motley_cue_configs())
        config_parser = ConfigParser()
        for filename in list_of_config_files:
            fpath = Path(filename)
            if fpath.exists():
                files_read = config_parser.read(fpath)
                logging.getLogger(__name__).debug("Read config from %s", files_read)
                return Config(config_parser)
        raise InternalException(
            "No configuration file found at given or default locations: " f"{list_of_config_files}"
        )

    @staticmethod
    def _reload_motley_cue_configs():
        """Return a list of default configuration paths.

        Config locations, by priority:
        $MOTLEY_CUE_CONFIG
        ./motley_cue.conf
        ~/.config/motley_cue/motley_cue.conf
        /etc/motley_cue/motley_cue.conf
        """
        files = []
        filename = os.environ.get("MOTLEY_CUE_CONFIG")
        if filename:
            files += [Path(filename)]
        files += [
            Path("motley_cue.conf").absolute(),
            Path("~/.config/motley_cue/motley_cue.conf").expanduser(),
        ]
        files += [Path("/etc/motley_cue/motley_cue.conf")]
        return files


def to_bool(bool_str):
    """Convert a string to bool.
    Raise an InternalException if the string cannot be converted.
    """
    if bool_str.lower() in ["true", "yes", "1"]:
        return True
    if bool_str.lower() in ["false", "no", "0"]:
        return False
    raise InternalException(f"Error reading config file: unrecognised boolean value {bool_str}.")


def to_list(list_str):
    """Convert a string to a list.
    Raise an InternalException if the string is not a valid list, with square brackets.
    """
    # remove all whitespace
    stripped_list_str = list_str.replace("\n", "").replace(" ", "").replace("\t", "")
    # strip list of square brackets
    if stripped_list_str.startswith("[") and stripped_list_str.endswith("]"):
        stripped_list_str = stripped_list_str[1:-1].strip(",")
    else:
        raise InternalException(
            f"Could not parse string as list, must be contained in square brackets: {list_str}"
        )
    # check empty list
    if stripped_list_str == "":
        return []
    return [v.strip('"').strip("'") for v in stripped_list_str.split(",")]


def to_int(int_str):
    """Convert a string to int.
    Raise a FatalError if the string cannot be converted.
    """
    try:
        return int(int_str)
    except ValueError:
        raise InternalException(f"Error converting to int: unrecognised integer value {int_str}.")


def to_loglevel(loglevel_str):
    """Convert a string to a loglevel.
    Raise a FatalError if the string cannot be converted.
    """
    if loglevel_str.upper() in logging._nameToLevel.keys():
        return logging._nameToLevel[loglevel_str.upper()]
    raise InternalException(f"Error reading config file: unrecognised loglevel {loglevel_str}.")


def warn_about_swallowed_options(config: ConfigParser) -> None:
    """Warn about any option that has been folded into the value above it.

    The loud version of this failure is a value that no longer parses, and
    `swallowed_options_error` explains that one. The dangerous version is the
    quiet one: when the option above happens to take a free-form string, the
    indented line is absorbed with no error at all, and whatever it configured
    simply never takes effect.

    For the assurance tiers that is a security-relevant silence -- an OP whose
    tier expressions were all swallowed has no policy at all, so every one of
    its users falls through to the "full" tier and a full login shell, which is
    the opposite of what the operator wrote down.
    """
    for section in [config.default_section, *config.sections()]:
        for option, value in config[section].items():
            if not isinstance(value, str) or "\n" not in value:
                continue
            swallowed = swallowed_options(value)
            if swallowed:
                logging.getLogger(__name__).warning(
                    "In [%s], the value of '%s' spans several lines and has swallowed these "
                    "options: %s. An indented line continues the previous option's value, so "
                    "these are NOT in effect. Remove their leading whitespace.",
                    section,
                    option,
                    ", ".join(swallowed),
                )


def swallowed_options(value) -> List[str]:
    """Name the options an indented line has folded into `value`.

    In an INI file a line indented by even one space continues the previous
    option's value, and blank lines in between do not end it. So indenting

        authorised_vos = []
          assurance_based_shell_tier_full = ...

    makes the second line part of the first one's value: the option is never
    parsed as an option, and the policy it configures is silently inert. The
    only symptom is that the value ABOVE it stops parsing -- so the error names
    the wrong option, and prints a blob with no clue where it came from.
    """
    if not isinstance(value, str) or "\n" not in value:
        return []
    return [
        line.split("=", 1)[0].strip()
        for line in value.splitlines()[1:]
        if "=" in line and line.strip()
    ]


def swallowed_options_error(option: str, value, reason: str) -> str:
    """Explain a conversion failure, blaming the indentation when that is the cause."""
    swallowed = swallowed_options(value)
    if not swallowed:
        return f"Option '{option}': {reason}"
    first_line = value.splitlines()[0].strip()
    return (
        f"Option '{option}' could not be parsed: its value runs on for "
        f"{len(value.splitlines())} lines and has swallowed these options: "
        f"{', '.join(swallowed)}. An indented line continues the previous option's value, "
        f"so those lines are part of this value instead of being options of their own. "
        f"Remove their leading whitespace. (Value up to the first line break: {first_line!r}.)"
    )


def canonical_url(url: str) -> str:
    """Strip URL of protocol info and ending slashes"""
    url = url.lower()
    if url.startswith("http://"):
        url = url[7:]
    if url.startswith("https://"):
        url = url[8:]
    if url.startswith("www."):
        url = url[4:]
    if url.endswith("/"):
        url = url[:-1]
    return url


@dataclass
class ConfigSection:
    @classmethod
    def __section__name__(cls) -> str:
        return "DEFAULT"

    @classmethod
    def load(cls, config: ConfigParser, section_name: Optional[str] = None):
        """Sets only the fields that are present in the config file"""
        try:
            if section_name is None:
                section_name = cls.__section__name__()
            field_names = set(f.name for f in fields(cls))
            try:
                return cls(
                    **{k: v for k, v in {**config[section_name]}.items() if k in field_names}
                )
            except InternalException as ex:
                # __post_init__ knows the option, only load() knows the section
                raise InternalException(f"[{section_name}] {ex.message}") from ex
        except KeyError:
            # logger.debug(
            #     "Missing config section %s, using default values.", cls.__section__name__()
            # )
            return cls()

    def __post_init__(self):
        """Converts some of the fields to the correct type"""
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None:
                continue
            field_type = field.type
            if hasattr(field.type, "__module__") and field.type.__module__ == "typing":
                if field.type.__str__().startswith(
                    "typing.Optional"
                ) or field.type.__str__().startswith("typing.Union"):
                    field_type = field.type.__args__[0]  # pyright: ignore
                elif field.type.__str__().startswith("typing.List"):
                    field_type = list  # treat as a list
                else:
                    return  # no conversion
            # if the field does not have the hinted type, convert it if possible
            if not isinstance(value, field_type):  # pyright: ignore
                try:
                    if field_type == int:
                        setattr(self, field.name, to_int(value))
                    if field_type == bool:
                        setattr(self, field.name, to_bool(value))
                    if field_type in [List, List[str], list]:
                        setattr(self, field.name, to_list(value))
                except InternalException as ex:
                    raise InternalException(
                        swallowed_options_error(field.name, value, ex.message)
                    ) from ex

    def to_dict(self) -> dict:
        """Converts the config to a dict"""
        return {field.name: getattr(self, field.name) for field in fields(self)}


@dataclass
class ConfigMapper(ConfigSection):
    """Config section for ldf_adapter."""

    log_level: str = "WARNING"
    log_file: Optional[str] = None  # equivalent to /dev/stderr
    enable_docs: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    api_version: str = "v1"

    @classmethod
    def __section__name__(cls):
        return "mapper"


@dataclass
class ConfigOTP(ConfigSection):
    """Config section for OTP."""

    use_otp: bool = True
    backend: str = "sqlite"
    # NOT /tmp: the database holds users' Access Tokens and the keyfile decrypts
    # them, so a world-writable directory means any local user can plant a key of
    # their choosing before first start and then read every token. /var/lib is
    # created 0700 and owned by the service (see debian/rules, rpm spec).
    db_location: str = "/var/lib/motley_cue/tokenmap.db"
    keyfile: str = "/var/lib/motley_cue/motley_cue.key"

    @classmethod
    def __section__name__(cls):
        return "mapper.otp"

    def __post_init__(self):
        super().__post_init__()
        if os.geteuid() != 0:
            # A non-root process (e.g. a pip install run by a developer for
            # testing) cannot write /var/lib: fall back to a user-owned
            # directory for the paths that were left at their defaults.
            # Parent directories are still created 0700 and the keyfile is
            # vetted exactly as before, so the security posture is unchanged.
            # Explicitly configured paths are honoured as-is and still fail
            # loudly when unusable.
            user_dir = Path("~/.config/motley_cue").expanduser()
            if self.db_location == "/var/lib/motley_cue/tokenmap.db":
                self.db_location = str(user_dir / "tokenmap.db")
            if self.keyfile == "/var/lib/motley_cue/motley_cue.key":
                self.keyfile = str(user_dir / "motley_cue.key")


@dataclass
class ConfigPrivacy(ConfigSection):
    """Config section for privacy policy."""

    privacy_contact: str = "NOT CONFIGURED"
    privacy_file: str = "/etc/motley_cue/privacystatement.md"

    @classmethod
    def __section__name__(cls):
        return "privacy"


@dataclass
class ConfigOPAuthZ(ConfigSection):
    """Config section for authorisation of one OP.

    Loaded from one ``[authorisation.<op>]`` section, with ``[DEFAULT]``
    supplying the values that section does not set. Every option below can
    therefore be configured once globally and overridden per OP.

    GROUP CLAIM SOURCES
    -------------------
    ``group_claims`` lists the token claims whose values become local group
    membership. feudalAdapter unions the configured claims: values that parse as
    AARC-G002 entitlements are mapped to group names, all others are used
    verbatim, and the result is filtered, masked and deduplicated. The default
    names the claims used by the supported OPs. A per-OP list limits the
    sources; an empty list disables claim-derived groups.

    ASSURANCE-BASED SHELL TIERS
    ---------------------------
    motley_cue evaluates each user's assurance claims against the
    ``assurance_based_shell_tier_*`` expressions (highest privilege first: full,
    then limited, then restricted) and passes the resulting tier to
    feudalAdapter, which maps it to a login shell.

    The expressions use the boolean grammar inherited from feudal's former
    ``assurance.require``: ``E -> E "&" E | E "|" E | "(" E ")" | string``,
    where ``&`` binds stronger than ``|``. A string matches if the user's
    assurance set contains it verbatim or prefixed with ``assurance_prefix``
    (so both ``https://refeds.org/assurance/profile/cappuccino`` and a bare
    ``acr`` value such as ``1`` are reachable). ``"+"`` matches if the user has
    any assurance claim at all, ``"*"`` always matches.

    The feature is opt-in: with the defaults below (all tier expressions empty)
    no expression matches, so every user resolves to "full" and feudalAdapter
    uses its default shell -- i.e. the same behaviour as before assurance-based
    shells existed. Operators enable tiers by configuring the expressions
    (typically with ``assurance_based_shell_tier_restricted = *`` as a
    catch-all).

    Enabling is per OP, and follows normal ``[DEFAULT]`` inheritance: a policy
    in ``[DEFAULT]`` applies to every OP (including one with no section of its
    own), while a policy in a single ``[authorisation.<op>]`` section leaves the
    other OPs untouched. Once an OP *does* have a policy, a user matching none
    of its expressions falls back to the least privileged tier rather than
    "full", so an expression that can never match cannot silently grant a full
    shell -- see ``assurance_based_shell_default_tier``.
    """

    op_url: str = ""
    scopes: list = field(default_factory=list)
    # user authorisation
    authorise_all: bool = False
    authorised_users: list = field(default_factory=list)
    authorised_vos: list = field(default_factory=list)
    vo_claim: str = "eduperson_entitlement"
    vo_match: str = "one"
    audience: str = ""
    # claims whose values are unioned into local group membership by feudal
    group_claims: list = field(
        default_factory=lambda: [
            "entitlements",
            "wlcg.groups",
        ]
    )
    # admin authorisation
    authorised_admins: list = field(default_factory=list)
    authorise_admins_for_all_ops: bool = False
    # assurance-based shell tiers
    # The refeds *root*, not the /assurance/ subtree: the REFEDS MFA profile is
    # https://refeds.org/profile/mfa, which does not live under /assurance/. A
    # prefix of the subtree would leave `profile/mfa` expanding to a URL no OP
    # ever asserts, so MFA could only be matched as an absolute URL.
    assurance_prefix: str = "https://refeds.org"
    # claims whose values are unioned into the evaluated assurance set
    assurance_claims: list = field(
        default_factory=lambda: ["assurance", "eduperson_assurance", "acr"]
    )
    assurance_based_shell_tier_full: str = ""
    assurance_based_shell_tier_limited: str = ""
    assurance_based_shell_tier_restricted: str = ""
    # Tier used when no expression matches. Empty means "decide automatically",
    # per OP: an OP with no tier expressions at all has the feature switched off
    # and gets "full" (unchanged behaviour), while an OP that does have a policy
    # falls back to the LEAST privileged tier -- otherwise an expression that
    # never matches (a typo, or a relative token that cannot expand to anything
    # a provider asserts) would silently hand out a full shell. Set it
    # explicitly to override in either direction.
    assurance_based_shell_default_tier: str = ""
    # optional cap on the resulting tier (e.g. an OP that cannot assert MFA caps
    # everyone at "limited"). Empty means no cap; it can only ever lower a tier.
    assurance_based_shell_max_tier: str = ""

    def get_info(self) -> dict:
        """Returns a dict with the info for this OP"""
        op_info = {
            "op_url": self.op_url,
            "scopes": self.scopes,
        }
        if self.audience and self.audience != "":
            op_info["audience"] = self.audience
        return op_info

    # methods used in conjunction with flaat
    def get_user_requirement(self) -> Requirement:
        """Creates a (flaat) Requirement object from this authorisation configuration,
        for API users.
        """
        req = OneOf()
        if self.authorise_all:
            user_has_same_issuer = lambda user_infos: canonical_url(
                user_infos.issuer
            ) == canonical_url(self.op_url)
            req.add_requirement(IsTrue(user_has_same_issuer))

        if len(self.authorised_vos) > 0:
            vo_claim = self.vo_claim
            vo_match = self.vo_match
            req.add_requirement(
                get_vo_requirement(self.authorised_vos, claim=vo_claim, match=vo_match)
            )

        if len(self.authorised_users) > 0:
            user_has_sub = lambda user_infos: user_infos.subject in self.authorised_users
            req.add_requirement(IsTrue(user_has_sub))

        all_req = AllOf()
        all_req.add_requirement(req)
        all_req.add_requirement(get_audience_requirement(self.audience))

        return all_req

    def get_admin_requirement(self) -> Requirement:
        """Creates a (flaat) Requirement object from this authorisation configuration,
        for API admins.
        """
        if len(self.authorised_admins) > 0:
            user_has_sub = lambda user_infos: user_infos.subject in self.authorised_admins
            return IsTrue(user_has_sub)

        return Unsatisfiable()


# Add more config sections here by inheriting from ConfigSection and providing a __section__name__
# method that returns the section name. The section name is used to load the right section from the
# config file. Provide default values for all fields in the class. The fields will be set to the
# values from the config file if they are present, otherwise the default values will be used.
# Then add a new field to the Configuration class below with the type of this section class.


@dataclass
class ConfigAuthorisation:
    """All authorisation configs for all supported OPs."""

    all_op_authz: Dict[str, ConfigOPAuthZ] = field(default_factory=dict)
    # the bare [DEFAULT] section, i.e. the policy an OP inherits when it sets
    # nothing itself. Kept separately so that code handling an OP *without* its
    # own section (see AssuranceEvaluator) can apply the operator's defaults
    # instead of the built-in ones.
    default_op_authz: ConfigOPAuthZ = field(default_factory=ConfigOPAuthZ)

    @classmethod
    def load(cls, config: ConfigParser):
        """Loads all config sub-sections that start with the given section name"""
        subsection_prefix = "authorisation"
        all_op_authz = {}
        section_for_key = {}
        for section in config.sections():
            if section.startswith(f"{subsection_prefix}."):
                op_config = ConfigOPAuthZ.load(config, section_name=section)
                key = canonical_url(op_config.op_url)
                if key == "":
                    # A section with no op_url matches no issuer -- it used to be
                    # registered under the empty string, which was meaningless.
                    # Skip it, and do NOT treat a second one as a collision: they
                    # are a separate (and much older) misconfiguration, and
                    # refusing to start over one would be a regression.
                    logging.getLogger(__name__).warning(
                        "Ignoring config section [%s]: it sets no op_url, so it can never "
                        "apply to any token.",
                        section,
                    )
                    continue
                # canonical_url drops the scheme, a trailing slash and a leading
                # "www.", so two sections can collapse onto one key. That used to
                # be silent, and the loser kept none of its own authorisation:
                # its users were evaluated against the winner's rules. Refuse to
                # start instead, the same way a mistyped shell tier does.
                if key in section_for_key:
                    raise InternalException(
                        f"Config sections [{section_for_key[key]}] and [{section}] both "
                        f"resolve to the same OP '{key}'. Their authorisation settings "
                        "would silently override one another; give them distinct op_urls."
                    )
                section_for_key[key] = section
                all_op_authz[key] = op_config
        # ConfigOPAuthZ does not override __section__name__, so this reads [DEFAULT]
        return cls(all_op_authz, ConfigOPAuthZ.load(config))

    def to_dict(self) -> dict:
        """Converts the config to a dict"""
        return {k: v.to_dict() for k, v in self.all_op_authz.items()}

    def get_op_authz(self, user_infos) -> Optional[ConfigOPAuthZ]:
        """Returns the ConfigOPAuthZ object for OP given in user_infos.

        Args:
            user_infos: (flaat) UserInfo object

        Returns:
            Optional[OPAuthZ]: OPAuthZ object
        """
        return self.all_op_authz.get(canonical_url(user_infos.issuer), None)

    def get_group_claims(self, user_infos) -> List[str]:
        """Return the group claim sources configured for the OP in user_infos.

        Unknown OPs fall back to the operator's [DEFAULT] configuration, the
        same way assurance evaluation does, so the result is always a list.
        """
        op_authz = self.get_op_authz(user_infos)
        if op_authz is None:
            op_authz = self.default_op_authz
        return list(op_authz.group_claims)


@dataclass
class Configuration:
    """All configuration settings for motley_cue."""

    mapper: ConfigMapper = field(default_factory=ConfigMapper)
    otp: ConfigOTP = field(default_factory=ConfigOTP)
    privacy: ConfigPrivacy = field(default_factory=ConfigPrivacy)
    authorisation: ConfigAuthorisation = field(default_factory=ConfigAuthorisation)

    @classmethod
    def load(cls, config: ConfigParser):
        """Loads all config settings from the given config parser"""
        # ignore pyright error
        # BUT: when extending this class, make sure that the new field if of type ConfigSection
        # (or has 'load' and 'to_dict' methods)
        return cls(**{f.name: f.type.load(config) for f in fields(cls)})  # pyright: ignore

    def to_dict(self) -> dict:
        """Converts the config to a dict"""
        return {field.name: getattr(self, field.name).to_dict() for field in fields(self)}
