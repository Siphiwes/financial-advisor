# Transactional email service

This application requires transactional email for account verification, password recovery, MFA challenges and security notifications. Do not enable public registration or financial-data access until the delivery path has been configured and verified.

## Selected IBM Cloud service

Use **IBM Cloud Event Notifications** in the existing Frankfurt region (`eu-de`). IBM identifies Event Notifications as its preferred service for transactional enterprise email, including password resets and two-factor authentication. Use the custom-domain email capability, not the built-in IBM-domain destination, because application-generated messages need controlled content and a verified sender domain.

Official documentation:
- https://cloud.ibm.com/docs/event-notifications?topic=event-notifications-en-email-domains
- https://cloud.ibm.com/docs/event-notifications?topic=event-notifications-en-smtp-configurations

## IBM Cloud setup required

1. Create or select an Event Notifications instance in Frankfurt (`eu-de`) using a production-capable plan. The Lite plan is for evaluation and must not be used for production.
2. Add a sender domain controlled by the application owner.
3. Publish the SPF and DKIM DNS records supplied by Event Notifications and wait for verification.
4. Request and complete SMTP authorization for the domain.
5. Create a Context-Based Restriction (CBR) rule that permits the Code Engine application's egress network to reach the SMTP interface. Do not leave SMTP access open to all networks.
6. Create an SMTP configuration and a dedicated SMTP user. Prefer a Service ID API key as the SMTP password where supported.
7. Use the Frankfurt SMTP endpoint and TLS. Prefer implicit TLS on port 465 or STARTTLS on port 587. Never use plaintext SMTP.
8. Store the SMTP password/API key only in an IBM Cloud Secret Manager or Code Engine secret. Never place credentials in GitHub, source files, Docker build arguments, logs or chat.
9. Configure a sender address on the verified domain, such as `no-reply@<verified-domain>`. Do not use a fabricated or unverified sender address.
10. Send a real delivery verification message to an address controlled by the account owner. Confirm delivery, SPF/DKIM alignment and that the message is not rejected or classified as spam.

## Application configuration contract

The application email adapter will read these settings from the runtime environment:

- `EMAIL_ENABLED`: remains `false` until service setup and delivery verification are complete.
- `SMTP_HOST`: Frankfurt Event Notifications SMTP hostname.
- `SMTP_PORT`: `465` for implicit TLS or `587` for STARTTLS.
- `SMTP_USERNAME`: dedicated Event Notifications SMTP username.
- `SMTP_PASSWORD`: secret reference, never a literal committed value.
- `SMTP_FROM_EMAIL`: verified sender address on the configured domain.
- `SMTP_FROM_NAME`: application display name.
- `APP_PUBLIC_URL`: canonical HTTPS application URL used to build verification and recovery links.

The adapter must fail closed when email is required but configuration is missing or delivery fails. It must not log message bodies, credentials, verification tokens, reset tokens, MFA secrets or full recipient addresses.

## Security requirements for email workflows

- Generate cryptographically random, single-use verification and password-reset tokens.
- Store only a keyed hash of each token in Cloudant, never the raw token.
- Give tokens a short expiry and invalidate them after use or replacement.
- Rate-limit requests by account and observed peer address.
- Return generic responses from password-reset requests so account existence cannot be discovered.
- Do not activate a new account until its email address is verified.
- Do not allow password recovery to bypass MFA once MFA is enabled.
- Send a security notification after password changes, MFA changes and recovery completion.
- Keep email verification and recovery tokens separate from JWT access tokens.
- Avoid putting email addresses, account identifiers or secrets in URLs or application logs.
- Use HTTPS links and apply a restrictive Referrer-Policy.

## Release gate

Email verification, password recovery and MFA must remain disabled as production capabilities until:
- the Event Notifications instance and custom domain are configured;
- DNS and SMTP authorization are verified;
- the Code Engine network is allowed through CBR;
- credentials are stored as protected secret references;
- a real email delivery check succeeds; and
- the complete account lifecycle flows pass security review.

Do not use a test mailbox or synthetic financial records as a substitute for verifying the real delivery path. No bank statement or transaction data belongs in transactional email.
