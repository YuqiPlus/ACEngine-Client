# Changelog

## 0.2.0

- MNet and ICAA17K use the managed private-asset and inference endpoints by default; an uploaded asset can be reused, and `legacy=True` explicitly selects the compatibility file endpoint.
- Preserve service request IDs, model fields, timings, costs and idempotency replay information. Expose lookup and recovery operations without automatic model POST retries or automatic endpoint fallback.
- Add formal IQA uploads, image/video task submission, polling, listing, cancellation and configuration. Waiting deadlines do not cancel or recreate tasks; retain partial/failed/cancelled distinctions and recovery context.
- Retain old API-Key construction and scoring methods; add `access_key_secret`, user-token authentication for managed endpoints, explicit errors, context-manager cleanup, additional scoring methods, and typed binary outputs.
- Correct image MIME handling and API-prefix normalization. Do not follow redirects, leak credentials in error details, or write binary output without an explicit request.
- Replace inaccurate uniform score examples with actual server contracts, clarify resource expiry and recovery, and add isolated HTTP protocol tests.
- Minimum Python version is now 3.9. The package remains `ace-engine-sdk`, imported as `ace_engine`.

Local verification on 2026-11-10: protocol tests passed on requests 2.25.1 and 2.34.2; actual shared-backend verification passed for private upload, MNet, ICAA17K, same-key replay, JWT status lookup, invalid-key rejection, the legacy contrast endpoint and an IQA exposure task. Wallet changes matched the ledger; the synthetic account, input assets and IQA outputs were removed. This does not establish availability of every optional algorithm or all video/metric combinations. Verification did not deploy services or upload to PyPI; package publication is a separate manual workflow.
