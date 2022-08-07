import json
import time
import logging

logger = logging.getLogger(__name__)

# most of the code in this file is no longer needed because of changes to Activision authentication (added captcha)
# leaving it in case they ever revert back

# takes in a session object and attempts to set the required cookies to make WZ API calls
def authenticate_warzone_api(session, atkn, sso):
    # AUTHENTICATING WARZONE API NO LONGER WORKS DUE TO CAPTCHA ADDED BY ACTIVISION
    # original method below (would authenticate to set the atkn and sso cookies)
    '''
    data = {'email': self.cod_email, 'password': self.cod_pw, 'remember_me': 'true', '_csrf': session.cookies['XSRF-TOKEN']}
        
    1. device_id method:
    # how to regenerate device_id and auth_token if needed
    #device_id = hex(random.getrandbits(128)).lstrip("0x")
    #payload =  {"deviceId": device_id}
    #resp = s.post('https://profile.callofduty.com/cod/mapp/registerDevice', json=payload)
    #auth_token = resp.json()['data']['authHeader']
        
    headers = {
        "Authorization": f"Bearer {self.auth_token}",
        "x_cod_device_id" : self.device_id,
    }

    response = session.post('https://profile.callofduty.com/cod/mapp/login', headers=headers, json=data)
        
    2. normal method
    response = session.post('https://profile.callofduty.com/do_login?new_SiteId=cod', params=data)
        
    if response.status_code == 200 and response.json()["success"] == True:
        logger.info("API Session successfully authenticated")
    else:
        logger.error(f"API session unable to be established. API returned {response.text}")
        raise Exception("API authentication failure")
    '''

    # sets xsrf token
    session.get('https://profile.callofduty.com/cod/login')

    # new method: manually log in and pull the required cookies from developer tools (smdh)
    if atkn is None or sso is None:
        logger.error("atkn and sso cookies must be set in .env by logging in on web browser")
        raise RuntimeError("API authentication failure")
    else:
        session.cookies.set("atkn", atkn, domain=".callofduty.com")
        session.cookies.set("ACT_SSO_COOKIE", sso, domain=".callofduty.com")

# helper function for session authentication. Retries 3 times in case of failure.
def authenticate_session(session, atkn, sso):
    connecting = True
    attempts = 0
    while connecting and attempts < 3:
        try:
            authenticate_warzone_api(session, atkn, sso)
            connecting = False
        except:
            attempts += 1
            if attempts < 3: time.sleep(5) # space out attempts

    return (attempts != 3)