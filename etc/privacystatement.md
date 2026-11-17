# motley-cue privacy policy

## Description of the service

The service **motley-cue** is a service for mapping OIDC identities to local identities.

## What personal data is processed and why

Users of the motley-cue service use it to map their OIDC identities to local identities. This is done by the user providing an OIDC access token to the service, and the service provisioning and providing a local identity to the user, if the user is authorised. The user can then use the local identity to access services that are protected by the service.

Therefore, motley-cue receives these tokens and requests information about the user from the OIDC provider. The following scopes requested from the OIDC provider, if supported by the OP:

- openid
- profile
- email
- entitlements
- eduperson_assurance

Example of information released by Google when asked for the OpenID Scope:

- subject
- issuer
- name
- family_name
- given_name
- picture

The email address is used to identify the user, and the name and preferred_username are used to provide a better user experience (e.g. for user-friendly local usernames). The assurance and entitlements are used to authorise the user. motley-cue stores the user's subject and issuer in the local user database (e.g. `/etc/passwd` or LDAP), to be able to retrieve the OIDC identity mapped to the local identity.

When one-time passwords are enabled, tokens larger than 1kB are stored in a database, to be able to verify the token later. The tokens are stored encrypted, and are only decrypted when the user provides the one-time password to the service, after which they are immediately deleted.

When the approval flow is enabled, the user's information is stored in a database, and is used to send the site administrator an email with the user's information, so that the site administrator can approve the user's request. The user's information is deleted once the user is approved or denied.

Usage of the motley-cue service generates logs, which are retained. These records contain:

- The network (IP) address from which you access motley-cue
- The user agent used to connect to the motley-cue service
- Time and date of access
- Details of actions you perform

This data is necessary to ensure that the motley-cue service is reliable and secure, and are used for assisting in the analysis of reported problems and responding to security incidents.

The legal basis for processing the personal data is legitimate interest, Article 6.1(f), [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj).

## Disclosure of personal data

The collected personal data is only accessible to the authorised personnel of this service, and then only for reasons outlined above. Personal data is not regularly disclosed to third parties.

## Data retention

The user may ask to be removed from the service by interacting with the contact person for the service. Access logs are deleted after 12 months.

## How to access, rectify and delete the personal data

For the data retained and processed by motley-cue, you may use the service contact (provided below) to access or rectify information. To rectify the data released by an OpenID provider, contact the providers' operators.

## Data protection code of conduct

Personal data will be protected according to the [Code of Conduct for Service Providers](https://www.geant.org/uri/Pages/dataprotection-code-of-conduct.aspx), a common standard for the research and higher education sector to protect the user's privacy.

## Contact Information

Service Operator: {{privacy_contact}}
