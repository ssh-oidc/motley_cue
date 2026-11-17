from motley_cue.mapper.config import Configuration
import os
import pytest
from dataclasses import fields

from .configs import (
    CONFIG_CUSTOM_DOC,
    CONFIG_DOC_ENABLED,
    CONFIG_EMPTY,
    CONFIG_NOT_SUPPORTED,
    CONFIG_OTP_NOT_SUPPORTED,
    CONFIG_OTP_SUPPORTED,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://aai.egi.com/oidc",
        "http://aai.egi.com/oidc/",
        "https://aai.egi.com/oidc",
        "http://www.aai.egi.com/oidc",
        "aai.egi.com/oidc",
        "HTTP://AAI.EGI.COM/OIDC",
    ],
)
@pytest.mark.parametrize("canonical_form", ["aai.egi.com/oidc"])
def test_canonical_url(test_config, url, canonical_form):
    assert test_config.canonical_url(url) == canonical_form


@pytest.mark.parametrize(
    "list_str,real_list",
    [
        *[
            (ls, ["a", "b", "c"])
            for ls in [
                "[a,b,c]",
                "[a,b,c,]",
                '["a","b","c"]',
                "['a','b','c']",
                "[a, \n\tb, \n\tc]",
                "\n[a,b, c]\n",
            ]
        ],
        ("[\n\t  ]", []),
        ("[]", []),
        ("[,,,]", []),
        ("[[,]]", ["[", "]"]),
        ("[ [a,b,]]", ["[a", "b", "]"]),
    ],
)
def test_to_list(test_config, list_str, real_list):
    assert test_config.to_list(list_str) == real_list


@pytest.mark.parametrize("list_str", ["ddads[df,a,]", "][", ",[]"])
def test_to_list_invalid(test_config, test_internal_exception, list_str):
    with pytest.raises(test_internal_exception):
        test_config.to_list(list_str)


@pytest.mark.parametrize(
    "bool_str,real_bool",
    [
        *[(bs, True) for bs in ["true", "True", "TRUE", "tRue"]],
        *[(bs, False) for bs in ["false", "False", "FALSE", "fAlse"]],
    ],
)
def test_to_bool(test_config, bool_str, real_bool):
    assert test_config.to_bool(bool_str) == real_bool


@pytest.mark.parametrize("bool_str", ["something", "", "\n", " true", "false "])
def test_to_bool_invalid(test_config, test_internal_exception, bool_str):
    with pytest.raises(test_internal_exception):
        test_config.to_bool(bool_str)


def test_empty_config(test_config):
    empty_config = test_config.Config(CONFIG_EMPTY).CONFIG
    default_config = Configuration()
    assert empty_config.to_dict() == default_config.to_dict()


@pytest.mark.parametrize(
    "config_parser,docs_url",
    [
        (CONFIG_NOT_SUPPORTED, None),
        (CONFIG_DOC_ENABLED, "/docs"),
        (CONFIG_CUSTOM_DOC, "/api/v1/docs"),
    ],
)
def test_docs_url(test_config, config_parser, docs_url):
    assert test_config.Config(config_parser).docs_url == docs_url


@pytest.mark.parametrize(
    "config_parser,use_otp,backend,db_location,keyfile",
    [
        (
            CONFIG_NOT_SUPPORTED,
            True,
            "sqlite",
            "/var/lib/motley_cue/tokenmap.db",
            "/var/lib/motley_cue/motley_cue.key",
        ),
        (
            CONFIG_OTP_NOT_SUPPORTED,
            False,
            "sqlite",
            "/var/lib/motley_cue/tokenmap.db",
            "/var/lib/motley_cue/motley_cue.key",
        ),
        (
            CONFIG_OTP_SUPPORTED,
            True,
            "sqlite",
            "/run/motley_cue/tokenmap.db",
            "/run/motley_cue/motley_cue.key",
        ),
    ],
)
def test_otp(test_config, config_parser, use_otp, backend, db_location, keyfile, monkeypatch):
    # system paths below only apply to root; pin euid so the test is
    # independent of the user running it (see test_otp_non_root_fallback)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    otp_config = test_config.Config(config_parser).otp
    assert otp_config.use_otp == use_otp
    assert otp_config.backend == backend
    assert otp_config.db_location == db_location
    assert otp_config.keyfile == keyfile


def test_otp_non_root_fallback(test_config, tmp_path, monkeypatch):
    """A non-root process cannot write /var/lib: defaults left untouched
    fall back to a user-owned directory, while explicitly configured paths
    are honoured as-is."""
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setenv("HOME", str(tmp_path))
    user_dir = tmp_path / ".config" / "motley_cue"

    otp_config = test_config.Config(CONFIG_NOT_SUPPORTED).otp
    assert otp_config.db_location == str(user_dir / "tokenmap.db")
    assert otp_config.keyfile == str(user_dir / "motley_cue.key")

    otp_config = test_config.Config(CONFIG_OTP_SUPPORTED).otp
    assert otp_config.db_location == "/run/motley_cue/tokenmap.db"
    assert otp_config.keyfile == "/run/motley_cue/motley_cue.key"


### F7: two config sections must not silently collapse onto one OP


@pytest.mark.parametrize(
    "second_url",
    [
        "https://aai.egi.com/oidc/",  # trailing slash
        "http://aai.egi.com/oidc",  # scheme
        "https://www.aai.egi.com/oidc",  # www.
    ],
)
def test_colliding_op_sections_are_refused(test_config, second_url):
    """canonical_url drops the scheme, a trailing slash and a leading "www.",
    so these all key the same. Silently keeping one meant the other OP's users
    were authorised by rules written for somebody else."""
    from configparser import ConfigParser

    config_parser = ConfigParser()
    config_parser.read_dict(
        {
            "authorisation.egi": {"op_url": "https://aai.egi.com/oidc", "authorise_all": "True"},
            "authorisation.egi_again": {"op_url": second_url, "authorise_all": "False"},
        }
    )
    with pytest.raises(Exception) as excinfo:
        test_config.Config(config_parser)
    assert "same OP" in str(excinfo.value)


def test_distinct_op_sections_are_kept(test_config):
    from configparser import ConfigParser

    config_parser = ConfigParser()
    config_parser.read_dict(
        {
            "authorisation.egi": {"op_url": "https://aai.egi.com/oidc"},
            "authorisation.other": {"op_url": "https://other.example.org/oidc"},
        }
    )
    assert len(test_config.Config(config_parser).trusted_ops) == 2


def test_op_sections_without_op_url_are_skipped_not_collided(test_config):
    """A section with no op_url matches no issuer and used to be registered
    under the empty string. Two of them are a separate, much older
    misconfiguration -- refusing to start over that would be a regression."""
    from configparser import ConfigParser

    config_parser = ConfigParser()
    config_parser.read_dict(
        {
            "authorisation.egi": {"op_url": "https://aai.egi.com/oidc"},
            "authorisation.leftover": {"authorise_all": "True"},
            "authorisation.another_leftover": {"authorise_all": "True"},
        }
    )
    assert test_config.Config(config_parser).trusted_ops == ["https://aai.egi.com/oidc"]


### An indented option is swallowed by the value above it


SWALLOWED = """
[mapper]
[authorisation.egi]
op_url = https://aai.egi.com/oidc
authorised_vos = []

  assurance_based_shell_tier_full = profile/mfa
  assurance_based_shell_tier_restricted = *
"""

SWALLOWED_QUIETLY = """
[mapper]
[authorisation.egi]
op_url = https://aai.egi.com/oidc
vo_claim = entitlements

  assurance_based_shell_tier_full = profile/mfa
  assurance_based_shell_tier_restricted = *
"""


def test_swallowed_options_are_named_in_the_error(test_config):
    """The value that fails to parse belongs to the option ABOVE the mistake,
    so the raw message points at the wrong place entirely."""
    from configparser import ConfigParser

    config_parser = ConfigParser()
    config_parser.read_string(SWALLOWED)
    with pytest.raises(Exception) as excinfo:
        test_config.Config(config_parser)

    message = str(excinfo.value)
    assert "[authorisation.egi]" in message  # which section
    assert "authorised_vos" in message  # which option failed
    assert "assurance_based_shell_tier_full" in message  # what was swallowed
    assert "leading whitespace" in message  # what to do about it


def test_quietly_swallowed_options_are_warned_about(test_config, caplog):
    """The dangerous case: absorbed into a free-form string, so nothing fails
    and the tier policy is simply never in effect -- which for assurance means
    every user of that OP gets a full shell."""
    import logging
    from configparser import ConfigParser

    config_parser = ConfigParser()
    config_parser.read_string(SWALLOWED_QUIETLY)
    with caplog.at_level(logging.WARNING):
        test_config.Config(config_parser)  # loads fine, which is the problem

    warnings = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "assurance_based_shell_tier_full" in warnings
    assert "NOT in effect" in warnings


def test_ordinary_multiline_values_are_not_flagged(test_config, caplog):
    """Lists are routinely written across several lines; only a line that looks
    like its own option is a mistake."""
    import logging
    from configparser import ConfigParser

    config_parser = ConfigParser()
    config_parser.read_string(
        "[mapper]\n[authorisation.egi]\nop_url = https://aai.egi.com/oidc\n"
        "authorised_vos = [\n    vo1,\n    vo2\n    ]\n"
    )
    with caplog.at_level(logging.WARNING):
        test_config.Config(config_parser)
    assert "swallowed" not in "\n".join(rec.getMessage() for rec in caplog.records)


### group claim sources for feudalAdapter

DEFAULT_VO_CLAIM = "entitlements"
DEFAULT_GROUP_CLAIMS = [
    "entitlements",
    "wlcg.groups",
]


def test_vo_claim_default(test_config):
    assert test_config.ConfigOPAuthZ().vo_claim == DEFAULT_VO_CLAIM


def test_group_claims_default(test_config):
    assert test_config.ConfigOPAuthZ().group_claims == DEFAULT_GROUP_CLAIMS


def test_group_claims_default_section_and_per_op_override(test_config):
    from configparser import ConfigParser
    from types import SimpleNamespace

    config_parser = ConfigParser()
    config_parser.read_dict(
        {
            "DEFAULT": {"group_claims": "[groups]"},
            "authorisation.op1": {"op_url": "https://one.example.org/oidc"},
            "authorisation.op2": {
                "op_url": "https://two.example.org/oidc",
                "group_claims": "[entitlements]",
            },
        }
    )
    authorisation = test_config.Config(config_parser).authorisation

    def claims_for(iss):
        return authorisation.get_group_claims(SimpleNamespace(issuer=iss))

    assert claims_for("https://one.example.org/oidc") == ["groups"]
    assert claims_for("https://two.example.org/oidc") == ["entitlements"]
    assert claims_for("https://unknown.example.org/oidc") == ["groups"]


def test_group_claims_accepts_empty_list(test_config):
    from configparser import ConfigParser
    from types import SimpleNamespace

    config_parser = ConfigParser()
    config_parser.read_dict(
        {
            "authorisation.op": {
                "op_url": "https://one.example.org/oidc",
                "group_claims": "[]",
            },
        }
    )
    authorisation = test_config.Config(config_parser).authorisation
    assert authorisation.get_group_claims(
        SimpleNamespace(issuer="https://one.example.org/oidc")
    ) == []
