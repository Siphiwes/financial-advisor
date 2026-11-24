# IBM watsonx.ai setup for personal use

The application already includes an IBM watsonx.ai chat integration. Do not build a second integration or send financial data to a different provider.

## IBM Cloud setup

1. Open IBM Cloud and select the existing Frankfurt (eu-de) region.
2. Open the existing watsonx.ai service instance, or create one if it does not exist.
3. Create or select one watsonx.ai project for this personal application.
4. Open the project's Developer access page.
5. Record the project ID and service endpoint.
6. Create an IBM Cloud API key for the application. Store it as a protected Code Engine secret, not in GitHub.
7. In the watsonx.ai Resource hub or API, select a model that is available in eu-de and supports the text chat task.
8. Record the exact API model ID. Do not guess the model ID from its display name.
9. Record the API version date used when validating the integration.

IBM documentation:
- API prerequisites and Developer access: https://www.ibm.com/docs/en/watsonx/saas?topic=solutions-rest-api
- Chat API: https://www.ibm.com/docs/en/watsonx/saas?topic=code-chat
- Supported foundation models: https://www.ibm.com/docs/en/watsonx/saas?topic=solutions-supported-models
- List available models and model IDs: https://www.ibm.com/docs/en/watsonx/saas?topic=models-get-model-information-code

## Application settings

Configure these in Code Engine using secret references where applicable:

- WATSONX_APIKEY: IBM Cloud API key, secret reference only.
- WATSONX_PROJECT_ID: project ID from Developer access.
- WATSONX_URL: the project endpoint, expected to be the Frankfurt service endpoint if the project is in eu-de.
- WATSONX_MODEL_ID: exact API model ID that supports text chat in the selected region.
- WATSONX_API_VERSION: API version date in YYYY-MM-DD format, matching the date used when validating the code.

The existing integration obtains a short-lived IAM bearer token, caches it in application memory, and calls the watsonx.ai text chat endpoint. It does not require a separately stored IAM token.

## Personal-use AI controls

- Keep FINANCIAL_AI_ENABLED=false until the project, credentials, model and API version are configured.
- Keep FINANCIAL_DATA_ENABLED=false until the personal-use data release checks are complete.
- The application asks for explicit consent before sharing a financial summary or one selected transaction.
- The chat integration receives an aggregate summary, not raw bank statement files or full transaction history.
- Category suggestions receive only the selected transaction fields and allowed category names.
- Never send online banking passwords, PINs, full account numbers, statement files or authentication tokens to watsonx.ai.
- Monitor IBM Cloud usage and billing. Model inference may incur charges.

## Activation sequence

1. Configure the watsonx.ai settings as Code Engine secrets/environment references.
2. Keep FINANCIAL_AI_ENABLED=false.
3. Deploy the application with the configuration.
4. Confirm the application starts and authentication works.
5. Enable FINANCIAL_AI_ENABLED only after a successful non-financial smoke request and a reviewed consent-based request.
6. Check the IBM Cloud usage and billing view after the first real request.
