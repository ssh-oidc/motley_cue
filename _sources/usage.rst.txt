.. _usage:

Usage
=====

The full API specification is described :doc:`here <api>`.


API authentication
------------------

First, you'll need an OIDC AccessToken to authenticate.

You might want to check out the `oidc-agent <https://github.com/indigo-dc/oidc-agent>`_ for that. It is a daemon that can provide valid access tokens from any number of configured OIDC Providers (OPs).

Once you have ``oidc-agent`` running, configure an account for your preferred OP. For example, you can generate an account configuration for the `EGI AAI <https://aai.egi.eu/oidc>`_  named ``egi`` as follows: 

.. code-block:: bash

  oidc-gen --pub --iss https://aai.egi.eu/oidc --scope "openid profile email offline_access entitlements eduperson_scoped_affiliation eduperson_unique_id" egi

Then you can retrieve an access token with:

.. code-block:: bash

  oidc-token egi

There are `oidc-agent gitbook pages <https://indigo-dc.gitbook.io/oidc-agent/user/oidc-gen/provider>`_ that provide detailed information for creating account configurations with many other OPs.

If you have another way to retrieve OIDC access tokens, don't worry. You can pass the token directly.


API calls
---------

In the following we assume the API at http://localhost:8080/. The Swagger UI, for interactive exploration, and to call and test your API directly from the browser, can be reached at http://localhost:8080/docs.

Let's take as an example your federated identity at `EGI Check-inEGI AAI <https://aai.egi.eu/oidc>`_, for which you generated an oidc-agent account as specified above. You can perform several operations to manage your local account corresponding to your EGI identity. Below, some examples and their output:

- deploy a local account:

.. code-block:: bash

  $ http http://localhost:8080/user/deploy  "Authorization: Bearer `oidc-token egi`"
  {
    "credentials": {
      "commandline": "ssh local_username001@localhost",
      "description": "Local SSH Test Service",
      "login_help": "Login via `mccli ssh {login_host}`.",
      "ssh_host": "localhost",
      "ssh_user": "local_username001"
    },
    "message": "User was created and was added to groups group1,group2.",
    "state": "deployed"
  }

- query the status of the local account, including your local username:
  
.. code-block:: bash

  $ http http://localhost:8080/user/get_status  "Authorization: Bearer `oidc-token egi`"
  {
    "message": "username local_username001",
    "state": "deployed"
  }

- verify if a given username matches the local account mapped to your remote identity
  
.. code-block:: bash

  $ http http://localhost:8080/verify_user\?username\=local_username001  "Authorization: Bearer `oidc-token egi`"
  {
    "state": "deployed",
    "verified": true
  }
  
- suspend your local account (e.g. if you suspect your account has been compromised):
  
.. code-block:: bash

  $ http http://localhost:8080/user/suspend "Authorization: Bearer `oidc-token egi`"
  {
    "message": "User 'c23***@https%3A%2F%2Faai.egi.eu%2Foidc%2F' was suspended.",
    "state": "suspended"
  }
  

The following `document <https://codebase.helmholtz.cloud/m-team/feudal/feudalAdapterLdf/-/blob/master/states.md>`_ gives a complete overview of the different states a local account can be in, as well as the actions that can be performed on a local account.
