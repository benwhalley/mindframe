import logging

import requests
from cacheback.decorators import cacheback
from decouple import config
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class LangfuseClient:
    def __init__(self, public_key, secret_key, base_url="https://langfuse.llemma.net"):
        self.auth = HTTPBasicAuth(public_key, secret_key)
        self.base_url = base_url.rstrip("/")
        # TODO SET THIS LONGER?
        self.timeout = 3  # seconds

    def get_session(self, session_id):
        url = f"{self.base_url}/api/public/sessions/{session_id}"
        resp = requests.get(url, auth=self.auth, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_trace(self, trace_id):
        url = f"{self.base_url}/api/public/traces/{trace_id}"
        resp = requests.get(url, auth=self.auth, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


@cacheback(lifetime=10)
def cost_for_session_usd(session_id: str) -> float:
    try:
        client = LangfuseClient(config("LANGFUSE_PUBLIC_KEY"), config("LANGFUSE_SECRET_KEY"))
        session = client.get_session(session_id)
        traces = session.get("traces", [])
        total_cost = 0.0
        for trace in traces:
            trace_data = client.get_trace(trace["id"])
            trace_cost = trace_data.get("totalCost")
            if trace_cost:
                total_cost += trace_cost
        return total_cost
    except Exception as e:
        logger.error(f"Error calculating cost for session {session_id}: {e}")
        return None


if False:
    cost = cost_for_session_usd("3e1b7859-f0b4-48d5-aca9-346f59f375ea")
    print(f"Total cost: ${cost:.4f}")
