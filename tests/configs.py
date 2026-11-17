from io import StringIO
from configparser import ConfigParser

from .utils import MOCK_SUB, MOCK_ISS, MOCK_VO, MOCK_VO_CLAIM


CONFIG_BASE = """
[mapper]
log_level = WARNING

[DEFAULT]
authorise_all = False
authorised_vos = []
vo_claim = entitlements
vo_match = one
authorised_users = []
authorised_admins = []
authorise_admins_for_all_ops = False
"""


def load_config(s_config: str) -> ConfigParser:
    buf = StringIO(s_config)
    config = ConfigParser()
    config.read_file(buf)
    return config


CONFIG_EMPTY = load_config("")

CONFIG_NOT_SUPPORTED = load_config(
    f"""
{CONFIG_BASE}
"""
)

CONFIG_SUPPORTED_NOT_AUTHORISED = load_config(
    f"""
{CONFIG_BASE}
[authorisation.OP]
op_url = {MOCK_ISS}
"""
)

CONFIG_AUTHORISE_ALL = load_config(
    f"""
{CONFIG_BASE}
[authorisation.OP]
op_url = {MOCK_ISS}
authorise_all = True
"""
)

CONFIG_INDIVIDUAL = load_config(
    f"""
{CONFIG_BASE}
[authorisation.OP]
op_url = {MOCK_ISS}
authorised_users = [
        {MOCK_SUB}
    ]
"""
)

CONFIG_VO_BASED = load_config(
    f"""
{CONFIG_BASE}
[authorisation.OP]
op_url = {MOCK_ISS}
authorised_vos = [
        {MOCK_VO}
    ]
vo_claim = {MOCK_VO_CLAIM}
"""
)

CONFIG_ADMIN = load_config(
    f"""
{CONFIG_BASE}
[authorisation.OP]
op_url = {MOCK_ISS}
authorised_admins = [
        {MOCK_SUB}
    ]
"""
)

CONFIG_ADMIN_FOR_ALL = load_config(
    f"""
{CONFIG_BASE}
[authorisation.OP]
op_url = {MOCK_ISS}
authorised_admins = [
        {MOCK_SUB}
    ]
authorise_admins_for_all_ops = True
"""
)

CONFIG_DOC_ENABLED = load_config(
    """
[mapper]
enable_docs = True
"""
)

CONFIG_CUSTOM_DOC = load_config(
    """
[mapper]
enable_docs = True
docs_url = /api/v1/docs
"""
)

CONFIG_INVALID_CUSTOM_DOC = load_config(
    """
[mapper]
enable_docs = True
docs_url = docs
"""
)


CONFIG_OTP_NOT_SUPPORTED = load_config(
    f"""
{CONFIG_BASE}
[mapper.otp]
use_otp = False
[authorisation.OP]
op_url = {MOCK_ISS}
authorise_all = True
"""
)

CONFIG_OTP_SUPPORTED = load_config(
    f"""
{CONFIG_BASE}
[mapper.otp]
use_otp = True
backend = sqlite
db_location = /run/motley_cue/tokenmap.db
keyfile = /run/motley_cue/motley_cue.key
[authorisation.OP]
op_url = {MOCK_ISS}
authorise_all = True
"""
)

CONFIGS = {
    "NOT_SUPPORTED": CONFIG_NOT_SUPPORTED,
    "SUPPORTED_NOT_AUTHORISED": CONFIG_SUPPORTED_NOT_AUTHORISED,
    "AUTHORISE_ALL": CONFIG_AUTHORISE_ALL,
    "INDIVIDUAL": CONFIG_INDIVIDUAL,
    "VO_BASED": CONFIG_VO_BASED,
    "ADMIN": CONFIG_ADMIN,
    "ADMIN_FOR_ALL": CONFIG_ADMIN_FOR_ALL,
    "DOC_ENABLED": CONFIG_DOC_ENABLED,
    "CUSTOM_DOC": CONFIG_CUSTOM_DOC,
    "INVALID_CUSTOM_DOC": CONFIG_INVALID_CUSTOM_DOC,
}

CONFIGS_AUTHENTICATED_USERS = {
    "SUPPORTED_NOT_AUTHORISED": CONFIG_SUPPORTED_NOT_AUTHORISED,
    "AUTHORISE_ALL": CONFIG_AUTHORISE_ALL,
    "INDIVIDUAL": CONFIG_INDIVIDUAL,
    "VO_BASED": CONFIG_VO_BASED,
}

CONFIGS_AUTHORISED_USERS = {
    "AUTHORISE_ALL": CONFIG_AUTHORISE_ALL,
    "INDIVIDUAL": CONFIG_INDIVIDUAL,
    "VO_BASED": CONFIG_VO_BASED,
}

CONFIGS_NOT_AUTHORISED_USERS = {
    "NOT_SUPPORTED": CONFIG_NOT_SUPPORTED,
    "SUPPORTED_NOT_AUTHORISED": CONFIG_SUPPORTED_NOT_AUTHORISED,
}

CONFIGS_AUTHORISED_ADMINS = {
    "ADMIN": CONFIG_ADMIN,
    "ADMIN_FOR_ALL": CONFIG_ADMIN_FOR_ALL,
}
