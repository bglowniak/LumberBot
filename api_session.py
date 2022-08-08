import os
import requests

# original method would make a POST request to COD site login to set atkn and sso cookies
# this method now fails because Activision added a recaptcha to the login
# new method: manually log into browser and pull the required cookies from developer tools
# potential future workaround - use Selenium + 2captcha to login programmatically and set the cookies


class WarzoneApi():
    def __init__(self):
        self.session = requests.Session()
        self.atkn = os.getenv("atkn")
        self.sso = os.getenv("ACT_SSO_COOKIE")
        self.base_url = "https://my.callofduty.com/api/papi-client/"

        # requests will timeout otherwise
        self.user_agent_header = {
            "User-Agent": "Chrome/104.0.0.0"
        }

        # sets xsrf token cookie for future requests
        self.session.get('https://profile.callofduty.com/cod/login')

        if self.atkn is None or self.sso is None:
            raise RuntimeError("atkn and sso cookies must be set in .env by logging in on web browser")
        else:
            self.session.cookies.set("atkn", self.atkn, domain=".callofduty.com")
            self.session.cookies.set("ACT_SSO_COOKIE", self.sso, domain=".callofduty.com")

    # collect Warzone matches played in the last week.
    # start and end parameters don't actually work as expected
    def get_matches(self, username):
        req_url = f"crm/cod/v2/title/mw/platform/uno/gamer/{username}/matches/wz/start/0/end/0/details"
        api_data = self._api_call(req_url)
        if api_data["status"] != "success":
            raise Exception(f"API returned 200 status code but there was an unknown error. API responded with {api_data}")

        return api_data["data"]["matches"]

    # use match ID to get more detailed data/stats
    def get_match_details(self, match_id):
        req_url = f"crm/cod/v2/title/mw/platform/uno/fullMatch/wz/{match_id}/en"
        api_data = self._api_call(req_url)
        # TODO: similar checks to get matches?
        return api_data["data"]["allPlayers"]

    def _api_call(self, req_url):
        resp = self.session.get(self.base_url + req_url, headers=self.user_agent_header)
        if resp.status_code != 200:
            raise Exception(f"Unable to retrieve data from Warzone API. API responded with {resp.status_code}: {resp.text}")
        return resp.json()
