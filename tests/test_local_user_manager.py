import pytest

from ldf_adapter.results import Deployed

from .utils import (
    mock_deployed_result,
    mock_exception,
    mock_not_deployed_result,
    mock_status_result,
)
from .utils import mock_failure, mock_rejection, mock_exception
from .utils import MOCK_ISS, MOCK_SUB


def test_lum_login_info(test_local_user_manager):
    assert test_local_user_manager.login_info() == {
        "description": "Local SSH Test Service",
        "login_help": "Login via `mccli ssh {login_host}`.",
        "ssh_host": "localhost",
    }


@pytest.mark.parametrize("mocker", [mock_deployed_result()])
def test_deploy_success(test_local_user_manager_patched):
    response = test_local_user_manager_patched.deploy({})
    assert response["state"] == "deployed"
    assert set(response.keys()) == set(["state", "message", "credentials"])


@pytest.mark.parametrize("mocker", [mock_failure(), mock_exception()])
def test_deploy_fail(test_local_user_manager_patched, test_internal_server_error):
    with pytest.raises(test_internal_server_error):
        test_local_user_manager_patched.deploy({})


@pytest.mark.parametrize("mocker", [mock_rejection()])
def test_deploy_reject(test_local_user_manager_patched, test_unauthorised):
    with pytest.raises(test_unauthorised):
        test_local_user_manager_patched.deploy({})


@pytest.mark.parametrize(
    "mocker",
    [
        *[
            mock_status_result(state=state)
            for state in [
                "deployed",
                "not_deployed",
                "rejected",
                "pending",
                "suspended",
                "limited",
                "unknown",
            ]
        ],
        mock_not_deployed_result(),
    ],
)
def test_get_status_success(test_local_user_manager_patched):
    response = test_local_user_manager_patched.get_status({})
    assert set(response.keys()) == set(["state", "message"])


@pytest.mark.parametrize("mocker", [mock_exception()])
def test_get_status_fail(test_local_user_manager_patched, test_internal_server_error):
    with pytest.raises(test_internal_server_error):
        test_local_user_manager_patched.get_status({})


@pytest.mark.parametrize(
    "mocker",
    [
        *[
            mock_status_result(state=state)
            for state in ["suspended", "not_deployed", "rejected", "pending", "unknown"]
        ],
        mock_not_deployed_result(),
    ],
)
def test_suspend_success(test_local_user_manager_patched):
    response = test_local_user_manager_patched.suspend({})
    assert set(response.keys()) == set(["state", "message"])


@pytest.mark.parametrize("mocker", [mock_exception()])
def test_suspend_fail(test_local_user_manager_patched, test_internal_server_error):
    with pytest.raises(test_internal_server_error):
        test_local_user_manager_patched.suspend({})


@pytest.mark.parametrize(
    "mocker",
    [
        *[
            mock_status_result(state=state)
            for state in ["suspended", "not_deployed", "rejected", "pending", "unknown"]
        ],
        mock_not_deployed_result(),
    ],
)
def test_admin_suspend_success(test_local_user_manager_patched):
    response = test_local_user_manager_patched.admin_suspend(sub=MOCK_SUB, iss=MOCK_ISS)
    assert set(response.keys()) == set(["state", "message"])


@pytest.mark.parametrize("mocker", [mock_exception()])
def test_admin_suspend_fail(
    test_local_user_manager_patched, test_internal_server_error
):
    with pytest.raises(test_internal_server_error):
        test_local_user_manager_patched.admin_suspend(sub=MOCK_SUB, iss=MOCK_ISS)


@pytest.mark.parametrize(
    "mocker",
    [
        *[
            mock_status_result(state=state)
            for state in [
                "deployed",
                "not_deployed",
                "rejected",
                "pending",
                "limited",
                "unknown",
            ]
        ],
        mock_not_deployed_result(),
    ],
)
def test_admin_resume_success(test_local_user_manager_patched):
    response = test_local_user_manager_patched.admin_resume(sub=MOCK_SUB, iss=MOCK_ISS)
    assert set(response.keys()) == set(["state", "message"])


@pytest.mark.parametrize("mocker", [mock_exception()])
def test_admin_resume_fail(test_local_user_manager_patched, test_internal_server_error):
    with pytest.raises(test_internal_server_error):
        test_local_user_manager_patched.admin_resume(sub=MOCK_SUB, iss=MOCK_ISS)


@pytest.mark.parametrize(
    "mocker,username,verified",
    [
        *[
            (mock_status_result(state=state, username="same_user"), "same_user", True)
            for state in ["deployed", "suspended", "limited", "pending"]
        ],
        *[
            (mock_status_result(state=state, username="same_user"), username, False)
            for state in ["deployed", "suspended", "limited", "pending"]
            for username in ["not_same_user", "", None]
        ],
        *[
            (mock_not_deployed_result(), username, False)
            for username in ["user", "", None]
        ],
        *[
            (mock_status_result(state="rejected"), username, False)
            for username in ["user", "", None]
        ],
        *[
            (mock_status_result(state="unknown"), username, False)
            for username in ["user", "", None]
        ],
    ],
)
def test_verify_user_success(
    test_local_user_manager_patched, username: str, verified: bool
):
    response = test_local_user_manager_patched.verify_user({}, username)
    assert set(response.keys()) == set(["state", "verified"])
    assert response["verified"] == verified


@pytest.mark.parametrize(
    "mocker,username",
    [
        (mocker(), username)
        for mocker in [mock_exception, mock_rejection, mock_failure]
        for username in ["any_username", "", None]
    ],
)
def test_verify_user_fail(
    test_local_user_manager_patched, test_internal_server_error, username: str
):
    with pytest.raises(test_internal_server_error):
        test_local_user_manager_patched.verify_user({}, username)


@pytest.mark.parametrize("shell_tier", ["full", "limited", "restricted", None])
def test_deploy_passes_shell_tier(monkeypatch, shell_tier):
    """The deploy data sent to feudalAdapter carries shell_tier when set,
    and omits it when None (backward compatible)."""
    captured = {}

    class CapturingUser:
        def __init__(self, data):
            captured["data"] = data

        def reach_state(self, target):
            return Deployed(credentials={"ssh_user": "u"}, message="ok")

    from motley_cue.mapper import local_user_management

    monkeypatch.setattr(local_user_management, "User", CapturingUser)
    lum = local_user_management.LocalUserManager()
    lum.deploy({"sub": MOCK_SUB, "iss": MOCK_ISS}, shell_tier=shell_tier)

    user_data = captured["data"]["user"]
    if shell_tier is None:
        assert "shell_tier" not in user_data
    else:
        assert user_data["shell_tier"] == shell_tier


def test_deploy_forwards_merged_userinfo(monkeypatch):
    """Mapper.deploy hands feudalAdapter the claims merged from all token
    sources, not just the userinfo endpoint."""
    from flaat.access_tokens import AccessTokenInfo
    from flaat.user_infos import UserInfos

    from motley_cue.mapper import local_user_management
    from motley_cue.mapper.authorisation import Authorisation

    captured = {}

    class CapturingUser:
        def __init__(self, data):
            captured["data"] = data

        def reach_state(self, target):
            return Deployed(credentials={"ssh_user": "u"}, message="ok")

    monkeypatch.setattr(local_user_management, "User", CapturingUser)

    user_infos = UserInfos(
        access_token_info=AccessTokenInfo(
            complete_decode={"payload": {"wlcg.groups": ["/wlcg"]}}, verification=None
        ),
        user_info={"sub": MOCK_SUB, "iss": MOCK_ISS},
        introspection_info={"email": "user@example.org"},
    )
    lum = local_user_management.LocalUserManager()
    lum.deploy(Authorisation.merged_userinfo(user_infos), shell_tier="full")

    userinfo = captured["data"]["user"]["userinfo"]
    assert userinfo["sub"] == MOCK_SUB
    assert userinfo["iss"] == MOCK_ISS
    # claims that only exist outside the userinfo endpoint now reach feudal
    assert userinfo["wlcg.groups"] == ["/wlcg"]
    assert userinfo["email"] == "user@example.org"


@pytest.mark.parametrize(
    "status_result,expected",
    [
        # username taken from credentials.ssh_user when present
        ({"state": "deployed", "credentials": {"ssh_user": "wlcg001"}}, "wlcg001"),
        # credentials take precedence over the message
        (
            {
                "state": "deployed",
                "message": "username other",
                "credentials": {"ssh_user": "wlcg001"},
            },
            "wlcg001",
        ),
        # fall back to parsing the message (verify_user convention: 2nd word)
        ({"state": "deployed", "message": "username wlcg003"}, "wlcg003"),
        ({"state": "suspended", "message": "username wlcg004"}, "wlcg004"),
        # no username available for these states
        ({"state": "not_deployed", "message": "username wlcg005"}, None),
        ({"state": "unknown", "message": "username wlcg006"}, None),
        # message without a second word yields no username
        ({"state": "deployed", "message": "deployed"}, None),
        ({"state": "deployed"}, None),
    ],
)
def test_extract_username(test_local_user_manager, status_result, expected):
    assert test_local_user_manager.extract_username(status_result) == expected


@pytest.mark.parametrize(
    "mocker",
    [
        mock_deployed_result(),
        mock_not_deployed_result(),
        *[
            mock_status_result(state=state)
            for state in [
                "deployed",
                "not_deployed",
                "rejected",
                "pending",
                "suspended",
                "limited",
                "unknown",
            ]
        ],
        mock_failure(),
        mock_rejection(),
        mock_exception(),
    ],
)
def test_reach_state_no_userinfo(
    test_local_user_manager_patched, test_internal_server_error
):
    with pytest.raises(test_internal_server_error):
        state = 0  # any number (of State type)
        test_local_user_manager_patched._reach_state(None, state)


@pytest.mark.parametrize("group_claims", [["groups"], [], None])
def test_deploy_passes_group_claims(monkeypatch, group_claims):
    """The deploy data carries the OP's group claim sources when set, and
    omits the field when None (backward compatible)."""
    captured = {}

    class CapturingUser:
        def __init__(self, data):
            captured["data"] = data

        def reach_state(self, target):
            return Deployed(credentials={"ssh_user": "u"}, message="ok")

    from motley_cue.mapper import local_user_management

    monkeypatch.setattr(local_user_management, "User", CapturingUser)
    lum = local_user_management.LocalUserManager()
    lum.deploy(
        {"sub": MOCK_SUB, "iss": MOCK_ISS}, group_claims=group_claims
    )

    user_data = captured["data"]["user"]
    if group_claims is None:
        assert "group_claims" not in user_data
    else:
        assert user_data["group_claims"] == group_claims


def test_mapper_deploy_passes_configured_group_claims():
    """Mapper.deploy selects the claim sources for the token's OP, not just
    the global defaults, and hands them to local user management."""
    from configparser import ConfigParser
    from types import SimpleNamespace

    from motley_cue.mapper import Mapper
    from motley_cue.mapper.config import Config

    config_parser = ConfigParser()
    config_parser.read_dict(
        {
            "DEFAULT": {"group_claims": "[groups]"},
            "authorisation.op": {
                "op_url": MOCK_ISS,
                "group_claims": "[entitlements, eduperson_entitlement]",
            },
        }
    )
    mapper = Mapper.__new__(Mapper)
    mapper._Mapper__config = Config(config_parser)
    mapper._Mapper__authorisation = SimpleNamespace(
        get_user_infos_from_request=lambda request: SimpleNamespace(
            subject=MOCK_SUB, issuer=MOCK_ISS
        ),
        merged_userinfo=lambda user_infos: {
            "sub": MOCK_SUB,
            "iss": MOCK_ISS,
        },
    )
    mapper._Mapper__assurance = SimpleNamespace(evaluate=lambda user_infos: "full")
    captured = {}
    mapper._Mapper__lum = SimpleNamespace(
        deploy=lambda userinfo, **kwargs: captured.update(
            {"userinfo": userinfo, **kwargs}
        )
    )

    mapper.deploy(None)

    assert captured["shell_tier"] == "full"
    assert captured["group_claims"] == ["entitlements", "eduperson_entitlement"]
    assert captured["userinfo"] == {"sub": MOCK_SUB, "iss": MOCK_ISS}
