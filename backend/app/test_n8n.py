import httpx

url = "https://saundaryafinalyear.app.n8n.cloud/webhook/rumour-verification"

payload = {
    "rumour": "Apple is going to acquire Disney.",
    "company": "Apple",
    "ticker": "Apple"
}
try:
    response = httpx.post(
        url,
        json=payload,
        timeout=60
    )

    print("Status:", response.status_code)
    print("Response:")
    print(response.text)

except Exception as e:
    print("ERROR:")
    print(type(e).__name__, str(e))