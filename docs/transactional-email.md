# Personal-use transactional email

This application is for one person's private financial workspace. It does not need a commercial email platform, custom sending domain, bulk-mail service or public registration.

Use an existing personal email provider's authenticated SMTP service. For a Gmail account, use Google's SMTP relay with an app password.

## Gmail SMTP configuration

1. Use the personal Gmail address that should receive account verification and password-recovery messages.
2. Enable 2-Step Verification on that Google account. This is protection for the email provider account, not MFA in this application.
3. Create a Google App Password for this application. Do not use the normal Google account password.
4. Configure the application with:
   - EMAIL_ENABLED=true
   - SMTP_HOST=smtp.gmail.com
   - SMTP_PORT=465 (implicit TLS) or 587 (STARTTLS)
   - SMTP_USERNAME=your full Gmail address
   - SMTP_PASSWORD=Google app password
   - SMTP_FROM_EMAIL=your full Gmail address
   - SMTP_FROM_NAME=Financial Advisor
   - APP_PUBLIC_URL=the deployed HTTPS application URL
5. Store the app password in an IBM Code Engine secret. Never commit it to GitHub, a repository .env file, a Docker image, logs or chat.
6. Send a verification email to the same personal mailbox and confirm that the link opens the deployed application.
7. Keep email disabled until the test succeeds.

For a different email provider, use its official SMTP hostname, port and app-password/OAuth requirements. The adapter supports only TLS on port 465 or STARTTLS on port 587.

## Account workflow behavior

- New accounts are created as unverified.
- Verification links expire after 60 minutes and can be used once.
- Password-reset links expire after 30 minutes and can be used once.
- Only a keyed token digest is stored in Cloudant. The raw token is sent by email and is not stored.
- Password reset increments the account authentication version, invalidating previously issued access tokens.
- Password-reset responses do not disclose whether an email address belongs to an account.
- Existing accounts without an email_verified field remain compatible. New accounts must verify before login.
- If email delivery is unavailable during registration, the account remains unverified. After SMTP is configured, use the Resend verification email action on the sign-in page.

## Personal-use boundaries

- Keep account registration invitation-only.
- Do not add public sign-up or multi-user administration.
- MFA for this application, Redis infrastructure, commercial email infrastructure and bulk-mail features are out of scope.
- Never send bank statements, transaction details, balances or other financial records by email. Messages contain only account-action links.
