"""
backend/app/integrations/linkedin/linkedin_api.py
"""
import requests
from app.core.config import settings


class LinkedInClient:
    def get_user_urn(self) -> tuple[str | None, str | None]:
        if not settings.LINKEDIN_ACCESS_TOKEN:
            return None, "No LinkedIn access token provided."
        resp = requests.get("https://api.linkedin.com/v2/userinfo",
                           headers={"Authorization": f"Bearer {settings.LINKEDIN_ACCESS_TOKEN}"}, timeout=10)
        if resp.status_code != 200: 
            return None, f"HTTP {resp.status_code} - {resp.text[:100]}"
        return f"urn:li:person:{resp.json().get('sub')}", None

    def post_job(self, text: str) -> dict:
        urn, err = self.get_user_urn()
        if not urn: return {"success": False, "message": f"LinkedIn auth failed: {err}"}
        headers = {"Authorization": f"Bearer {settings.LINKEDIN_ACCESS_TOKEN}",
                   "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"}
        payload = {"author": urn, "lifecycleState": "PUBLISHED",
                   "specificContent": {"com.linkedin.ugc.ShareContent": {
                       "shareCommentary": {"text": text[:3000]}, "shareMediaCategory": "NONE"}},
                   "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}}
        resp = requests.post("https://api.linkedin.com/v2/ugcPosts", json=payload, headers=headers, timeout=15)
        return {"success": resp.status_code == 201, "message": "Posted" if resp.status_code == 201 else resp.text[:200]}
