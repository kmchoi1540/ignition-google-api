def doGet(request, session):
	"""
	WebDev Resource: /google/oauth/start
	HTTP Method: GET
	
	Purpose:
		This endpoint initiates the Google OAuth 2.0 flow from Ignition.
		It generates a CSRF protection 'state', stores it in the Ignition session,
		builds the Google authorization URL, and redirects the user's browser to Google.
	
	Why this endpoint exists:
		- Google OAuth requires a 'state' value to prevent CSRF attacks.
		- Ignition WebDev cannot rely on cookies the same way normal web apps do,
			so we manually store the 'state' inside the WebDev session object.
		- After this function executes, the user's browser must be redirected
			to the Google Login/Consent Screen.
	"""

	# ----------------------------------------------------------
	# Imports
	# ----------------------------------------------------------
	from google.auth import GoogleOAuthClient
	import uuid
	
	# Path to your Google Authentication UDT root.
	# Must match the actual Tag structure in Ignition.
	ROOT_OAUTH_TAG = "[default]Google"
	
	# WebDev logger
	logger = system.util.getLogger("GoogleOAuthStart")

	# ----------------------------------------------------------
	# 1) Create unique state value for CSRF protection
	# ----------------------------------------------------------
	# The 'state' value is required by the OAuth 2.0 spec.
	#
	# Why we generate state:
	#   - When the user's browser is redirected to Google,
	#     Google will return the same 'state'.
	#   - At the redirect endpoint, we compare both values.
	#   - If mismatched → someone attempted CSRF or the flow is invalid.
	#
	# We store the state in Ignition's session object,
	# which persists across WebDev requests for the same user session.
	state = uuid.uuid4().hex
	session["google_oauth_state"] = state
	logger.info("Generated OAuth state: %s" % state)

	# ----------------------------------------------------------
	# 2) Build the Google Authorization URL with the 'state'
	# ----------------------------------------------------------
	# GoogleOAuthClient:
	#   - Reads client_id, client_secret, redirect_uri from the Tag dataset.
	#   - Builds a correct Google OAuth URL with:
	#       response_type=code
	#       client_id=...
	#       redirect_uri=...
	#       scope=...
	#       access_type=offline  (to get refresh_token)
	#       state=<generated_state>
	#
	# Passing the 'state' explicitly is essential for CSRF validation.
	client = GoogleOAuthClient(ROOT_OAUTH_TAG)
	auth_url = client.build_authorize_url(
		scope=None,    # Use default scope from the UDT parameter
		state=state    # CSRF protection value
	)

	# ----------------------------------------------------------
	# 3) Redirect to Google
	# ----------------------------------------------------------
	# IMPORTANT:
	#   - We MUST NOT use servletResponse.sendRedirect(),
	#     because WebDev may try to generate its own response afterwards,
	#     causing the "Committed" error.
	#
	#   - Instead, we return an HTML document that performs the redirect
	#     using JavaScript. This ensures:
	#         * WebDev sends only ONE response
	#         * No double-commit errors
	#         * Browser still navigates to Google
	#
	# The HTML also contains a backup <a> link for manual navigation.
	html = u"""
	<html>
	  <head>
	    <meta charset="utf-8" />
	    <title>Redirecting to Google OAuth…</title>

	    <!--
	      Auto-redirect using JavaScript.
	      This avoids servletResponse.sendRedirect() and therefore
	      prevents double-response commit issues in Ignition WebDev.
	    -->
	    <script type="text/javascript">
	      window.location.href = "%s";
	    </script>
	  </head>

	  <body style="font-family: Arial; padding: 20px;">
	    <p>
	      Redirecting to Google OAuth…<br/>
	      If it does not redirect automatically, click the link below:
	    </p>
	
	    <p>
	      <a href="%s">Continue to Google OAuth</a>
	    </p>
	  </body>
	</html>
	""" % (auth_url, auth_url)

	# WebDev returns exactly one response (HTML)
	return {"html": html}