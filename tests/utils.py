from typing import Callable, List, Dict, Optional
from fastapi import Request
from starlette.datastructures import Headers

from ldf_adapter.results import (
    Deployed,
    NotDeployed,
    Result,
    Status,
    Failure,
    Rejection,
    Question,
    Questionnaire,
)
from flaat.user_infos import UserInfos
from flaat.access_tokens import AccessTokenInfo


class Endpoint:
    """Class for describing motley_cue API endpoints."""

    def __init__(
        self,
        url: str,
        valid_response: Dict,
        children: List = [],
        params: List = [],
        mapper_method: str = "",
        protected: bool = False,
    ):
        self.url = url
        self.children = children
        self.params = params
        self.protected = protected
        self.mapper_method = mapper_method
        self.valid_response = valid_response
        self.callback_valid = lambda *x: valid_response


Info = Endpoint(
    url="/info",
    valid_response={"login_info": "", "supported_OPs": [], "ops_info": {}},
    mapper_method="info",
)

InfoAuthorisation = Endpoint(
    url="/info/authorisation",
    valid_response={"OP": "", "authorisation_type": "", "authorisation_info": ""},
    mapper_method="info_authorisation",
    protected=True,
)

InfoOp = Endpoint(
    url="/info/op",
    valid_response={"audience": "", "scopes": []},
    params=["url"],
    mapper_method="info_op",
)

VerifyUser = Endpoint(
    url="/verify_user",
    valid_response={"state": "", "verified": False},
    params=["username"],
    mapper_method="verify_user",
    protected=True,
)

User = Endpoint(
    url="/user",
    valid_response={"description": "", "endpoints": {}, "usage": ""},
    children=[
        Endpoint(
            child_url,
            valid_response=child_resp,
            mapper_method=child_mapper_method,
            protected=True,
        )
        for child_url, child_resp, child_mapper_method in [
            ("/user/deploy", {"state": "", "message": "", "credentials": {}}, "deploy"),
            ("/user/get_status", {"state": "", "message": ""}, "get_status"),
            (
                "/user/status",
                {
                    "state": "",
                    "message": "",
                    "credentials": {},
                    "username": "",
                    "sub": "",
                    "iss": "",
                },
                "get_full_status",
            ),
            ("/user/suspend", {"state": "", "message": ""}, "suspend"),
            (
                "/user/generate_otp",
                {"supported": False, "successful": False},
                "generate_otp",
            ),
        ]
    ],
)

Admin = Endpoint(
    url="/admin",
    valid_response={"description": "", "endpoints": {}, "usage": ""},
    children=[
        Endpoint(
            url=child_url,
            valid_response=child_resp,
            params=["iss", "sub"],
            mapper_method=child_mapper_method,
            protected=True,
        )
        for child_url, child_resp, child_mapper_method in [
            ("/admin/suspend", {"state": "", "message": ""}, "admin_suspend"),
            ("/admin/resume", {"state": "", "message": ""}, "admin_resume"),
        ]
    ],
)

Root = Endpoint(
    url="/",
    valid_response={"description": "", "endpoints": {}, "usage": ""},
    children=[Info, InfoAuthorisation, InfoOp, User, Admin, VerifyUser],
)


def getListOfEndpoints(
    endpoint: Endpoint, condition: Callable[[Endpoint], bool]
) -> List[Endpoint]:
    """Returns a list of endpoints that satisfy a given condition,
    from the subtree starting at the given endpoint"""
    endpoints = []
    if condition(endpoint):
        endpoints += [endpoint]
    if endpoint.children:
        for child in endpoint.children:
            endpoints += getListOfEndpoints(child, condition)
    return endpoints


PUBLIC_ENDPOINTS = getListOfEndpoints(
    Root, condition=lambda x: not x.protected and len(x.params) == 0
)
PROTECTED_ENDPOINTS = getListOfEndpoints(Root, condition=lambda x: x.protected)
QUERY_ENDPOINTS = getListOfEndpoints(Root, condition=lambda x: len(x.params) > 0)


def build_query_string(params: Dict = {}) -> str:
    """Builds a query string for an HTTP request with given query parameters"""
    return "&".join(["=".join(x) for x in params.items()])


def build_request(token: str = "") -> Request:
    """Builds a FastAPI Request with Authorization headers containing
    given token as Bearer token.
    """
    if token == "":
        headers = {}
    else:
        headers = Headers({"Authorization": f"Bearer {token}"}).raw
    return Request({"type": "http", "headers": headers, "path": "/"})


MOCK_TOKEN = "mock.access.token"
MOCK_ISS = "https://mock.issuer/oidc"
MOCK_SUB = "some-unique-mock-uid"
MOCK_VO = "some-vo"
MOCK_VO_CLAIM = "entitlements"
MOCK_HEADERS = {"Authorization": f"Bearer {MOCK_TOKEN}"}
MOCK_REQUEST = build_request(MOCK_TOKEN)
MOCK_USER_INFO = {"sub": MOCK_SUB, "iss": MOCK_ISS, MOCK_VO_CLAIM: [MOCK_VO]}
MOCK_TOKEN_INFO = AccessTokenInfo(
    complete_decode={
        "payload": {"sub": MOCK_SUB, "iss": MOCK_ISS, "wlcg.groups": ["another_group"]},
    },
    # flaat>=1.3 rejects UserInfos with unverified AT info in
    # get_user_infos_from_request (_reject_unusable_user_infos), so the mock
    # must look like a verified token.
    verification={"algorithm": "mock"},
)

MOCK_BAD_TOKEN = "badtoken"
MOCK_BAD_REQUEST = build_request(MOCK_BAD_TOKEN)

MOCK_OTP = "mock.one.time.token"
MOCK_OTP_REQUEST = build_request(MOCK_OTP)
MOCK_OTP_HEADERS = {"Authorization": f"Bearer {MOCK_OTP}"}


class MockUser:
    """Mock class for User in feudalAdapter"""

    def __init__(self, data) -> None:
        pass


def mock_failure() -> Callable[..., Result]:
    """mocks a function that raises a (feudal) Failure exception"""
    return lambda *x: (_ for _ in ()).throw(Failure(message=""))


def mock_rejection() -> Callable[..., Result]:
    """mocks a function that raises a (feudal) Rejection exception"""
    return lambda *x: (_ for _ in ()).throw(Rejection(message=""))


def mock_exception() -> Callable[..., Result]:
    """mocks a function that raises an exception"""
    return lambda *x: (_ for _ in ()).throw(Exception())


def mock_status_result(state: str, username: str = "") -> Callable[..., Result]:
    """mocks a function that returns a (feudal) Status result
    with given state and username"""
    if username == "":
        message = "No message"
    else:
        message = f"username {username}"
    return lambda *x: Status(state=state, message=message)


def mock_deployed_result(username: str = "") -> Callable[..., Result]:
    """mocks a function that returns a (feudal) Deployed result with given username"""
    credentials = {"ssh_user": username}
    message = "User was created and was added to groups."
    return lambda *x: Deployed(credentials=credentials, message=message)


def mock_not_deployed_result() -> Callable[..., Result]:
    """mocks a function that returns a (feudal) NotDeployed result"""
    return lambda *x: NotDeployed(message="")


def mock_flaat_get_user_infos_from_access_token(
    self, access_token: str, issuer_hint: str = ""
) -> Optional[UserInfos]:
    """Mock function in Flaat that returns a mock UserInfos object for a
    mock token. Otherwise return None.
    """
    if access_token == MOCK_TOKEN and MOCK_ISS in self.trusted_op_list:
        return UserInfos(
            access_token_info=MOCK_TOKEN_INFO,
            user_info=MOCK_USER_INFO,
            introspection_info=None,
        )
    return None


class MockTokenDB:
    def __init__(self) -> None:
        self.__db = {}

    def pop(self, otp: str) -> Optional[str]:
        token = None
        if otp in self.__db:
            token = self.__db[otp]
            del self.__db[otp]
        return token

    def store(self, otp: str, token: str) -> bool:
        stored_token = None
        success = False
        if otp in self.__db:
            stored_token = self.__db[otp]
        if not stored_token:
            self.__db[otp] = token
            success = True
        elif stored_token == token:
            success = True
        else:
            success = False
        return success

    def get(self, otp: str) -> Optional[str]:
        return self.__db.get(otp, None)

    def remove(self, otp: str) -> None:
        del self.__db[otp]

    def insert(self, otp: str, token: str) -> None:
        self.__db[otp] = token


class MockTokenManager:
    def __init__(self, otp_config) -> None:
        self.__db = MockTokenDB()

    @property
    def database(self):
        return self.__db

    @staticmethod
    def _new_otp(token: str) -> str:
        _ = token
        return MOCK_OTP
