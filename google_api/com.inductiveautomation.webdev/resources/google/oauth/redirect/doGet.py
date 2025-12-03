def doGet(request, session):
	# Web Dev Resource: /google/oauth/redirect
	# HTTP Method: doGet
	"""
	Google OAuth2 redirect/callback endpoint.
	
	Expected URL:
	  REDIRECT_URI?code=XXXX
	"""

	from google.auth import GoogleOAuthClient
	
	ROOT_OAUTH_TAG = "[default]Google"			# Modify with your enviroment
	logger = system.util.getLogger("GoogleOAuthRedirect")
	
	params = request.get("params", {})			# query string parameters
	logger.info("OAuth redirect params: %s" % params)
	
	code   = params.get("code")
	error  = params.get("error")
	state = params.get("state")
	servletResponse = request.get("servletResponse")	# may be None
	
	# 0) code, state 값이 list/tuple로 오는 경우 보정
	if isinstance(code, (list, tuple)):
		state = state[0]
	if isinstance(state, (list, tuple)):
		state = state[0]
		
	# 1) Google이 error를 보낸 경우
	if error:
		if servletResponse is not None:
			servletResponse.setStatus(400)
		html = (
			"<html><body>"
			"<h2>Google OAuth Error</h2>"
			"<p>error: %s</p>"
			"</body></html>" % error
		)
		return {"html": html}

	# 2) code 누락
	if not code:
		if servletResponse is not None:
			servletResponse.setStatus(400)
		html = (
			"<html><body>"
			"<h2>Missing authorization code.</h2>"
			"<p>Required query parameter 'code' was not found.</p>"
			"</body></html>"
		)
		return {"html": html}

	# 3) state 검증 (CSRF 방어 핵심)
	expected_state = session.get("google_oauth_state", None)
	if not state or not expected_state or state != expected_state:
		logger.warn(
			"Invalid or missing OAuth state. state=%s, expected=%s" %
			(state, expected_state)
		)
		if servletResponse is not None:
			servletResponse.setStatus(400)
		html = (
			"<html><body>"
			"<h2>Invalid OAuth state.</h2>"
			"<p>Security check failed. Please retry the login process.</p>"
			"</body></html>"
		)
		return {"html": html}

	# 4) state 한 번 쓰면 폐기 (재사용 방지)
	try:
		del session["google_oauth_state"]
	except KeyError:
		pass

	# 5) code 타입 보정
	if isinstance(code, (list, tuple)):
		code = code[0]

	client = GoogleOAuthClient(ROOT_OAUTH_TAG)

	try:
		# 3) code → access_token, refresh_token 교환 및 태그에 저장
		access_token, refresh_token = client.exchange_code_for_tokens(code)

		logger.info(
			"Google OAuth tokens updated successfully. "
			"access_token length=%d, has_refresh=%s"
			% (len(access_token or ""), bool(refresh_token))
		)

		if servletResponse is not None:
			servletResponse.setStatus(200)

		html = (
			"<html><body>"
			"<h2>Google account linked successfully.</h2>"
			"<p>You may now close this window and return to Ignition.</p>"
			"</body></html>"
		)
		return {"html": html}

	except Exception, e:
		logger.error("Error in Google OAuth redirect handler: %s" % e)
		if servletResponse is not None:
			servletResponse.setStatus(500)
		html = (
			"<html><body>"
			"<h2>Internal error in OAuth redirect.</h2>"
			"<p>Please check the Ignition gateway logs for details.</p>"
			"</body></html>"
		)
		return {"html": html}