import requests


def post_internal_api(internal_api_url, internal_api_token, path: str, payload: dict):
    url = f"{internal_api_url}{path}"
    resp = requests.post(
        url, headers=_headers(internal_api_token), json=payload, timeout=10
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"POST {url} failed status={resp.status_code} body={resp.text}"
        )
    return resp


def _headers(internal_api_token):
    return {
        "Authorization": f"Bearer {internal_api_token}",
        "Content-Type": "application/json",
    }
