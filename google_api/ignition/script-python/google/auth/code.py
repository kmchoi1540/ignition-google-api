# google.auth
# -----------------------------------------------------------
# Unified Google Authentication for Ignition (Jython)
# - OAuth Client (user-based)
# - Service Account (server-based)
#
# UDT Structure:
# [rootTagPath]
#   - Parameters (Project ID, Token URI, Auth URI, Scope, Redirect URI)
#   - ServiceAccount (DataSet: client_email, private_key, access_token, token_expiry)
#   - OAuthClient         (DataSet: client_id, client_secret, refresh_token, access_token, token_expiry)
#   - UseSA         (Boolean: True = Service Account, False = OAuth Client)
# -----------------------------------------------------------

import json
import urllib

from java.lang import String
from java.security import KeyFactory, Signature
from java.security.spec import PKCS8EncodedKeySpec
from java.util import Base64 as JBase64

GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# ===========================================================
# OAuth 2.0 (User-based)
# ===========================================================

class GoogleOAuthClient(object):
	"""
	OAuth 2.0 client (user account based).
	- DataSet: [root]/OAuthClient
	  columns: client_id, client_secret, refresh_token, access_token, token_expiry
	"""

	def __init__(self, root_tag_path):
		"""
		Args:
			root_tag_path    (str): Parent path to DataSet tag which holds Authentication information.
		"""
		self.root_tag_path = root_tag_path												# Modify with your enviroment
		self.tag_path = "%s/OAuthClient" % root_tag_path										# Modify with your enviroment
		
		cfg = system.tag.getConfiguration(root_tag_path)[0]["parameters"]				# Modify with your enviroment
		self.auth_uri = cfg["Auth URI"].value											# Modify with your enviroment
		self.redirect_uri = cfg["Redirect URI"].value									# Modify with your enviroment
		self.token_uri = cfg["Token URI"].value or GOOGLE_TOKEN_ENDPOINT				# Modify with your enviroment
		self.default_scope = cfg["Scope"].value											# Modify with your enviroment
		self.logger = system.util.getLogger("GoogleOAuthClient")

	# ------------------------------------------------------
	# DataSet helpers
	# ------------------------------------------------------

	def _read_dataset(self):
		"""
		Read the DataSet tag and return its first row as a dictionary.
		
		Expected DataSet columns:
			client_id, client_secret, refresh_token, access_token, token_expiry
			
		If the DataSet has no rows, it is initialized with a default row.
		"""
		result = system.tag.readBlocking([self.tag_path])[0]
		ds = result.value
		
		if ds is None or ds.rowCount == 0:
			default_row = [["", "", "", "", system.date.now()]]	# Manually modifiable values
			default_ds = system.dataset.toDataSet(
				["client_id", "client_secret", "refresh_token", "access_token", "token_expiry"],
				default_row,
			)
			system.tag.writeBlocking([self.tag_path], [default_ds])
			ds = default_ds

		row = ds[0]
		return {
			"client_id": row["client_id"],
			"client_secret": row["client_secret"],
			"refresh_token": row["refresh_token"],
			"access_token": row["access_token"],
			"token_expiry": row["token_expiry"],
			"_dataset": ds,
		}

	def _write_dataset(self, values):
		"""
		Update the first row of the DataSet tag using values from the given dict.
		
		Only keys that match existing column names are updated.
		
		Args:
			values (dict): May contain client_id, client_secret, refresh_token,
			access_token, token_expiry, _dataset.
		"""
		ds = values.get("_dataset")
		if ds is None:
			ds = system.tag.readBlocking([self.tag_path])[0].value

		col_names = list(ds.getColumnNames())
		updated_rows = []

		for row_index in range(ds.rowCount):
			row = list(ds[row_index])
			if row_index == 0:
				for idx, col in enumerate(col_names):
					if col in values:
						row[idx] = values[col]
			updated_rows.append(row)

		new_ds = system.dataset.toDataSet(col_names, updated_rows)
		system.tag.writeBlocking([self.tag_path], [new_ds])

	# ------------------------------------------------------
	# Public API
	# ------------------------------------------------------

	def build_authorize_url(self, scope=None, state=None):
		"""
		Build the Google OAuthClient authorization URL.
		
		Args:
			scope (str): Space-separated list of scopes.
				Example: "https://www.googleapis.com/auth/drive.file"
			state: (str or None): CSRF defense random Token
		
		Returns:
			str: Fully constructed authorization URL.
		"""
		info = self._read_dataset()
		client_id = info["client_id"]
		
		if not client_id:
			raise ValueError("client_id is empty in OAuthClient DataSet: %s" % self.tag_path)

		if not scope:
#			scope = "https://www.googleapis.com/auth/drive.file"		# Only Drive files created/selected by the app
			scope = self.default_scope										# Almost all Google Cloud APIs

		params_dict = {
			"access_type": "offline",   # request refresh_token
			"response_type": "code",
			"client_id": client_id,
			"scope": scope,
			"redirect_uri": self.redirect_uri,
			"prompt": "consent",        # force consent screen
		}
		if state:
			params_dict["state"] = state
		params = urllib.urlencode(params_dict)
#		encoded = []
#		for k, v in params_dict.items():
#			encoded.append(u"%s=%s" % (k, v))
#
#		params = u"&".join(encoded)
		return u"%s?%s" % (self.auth_uri, params)

	def exchange_code_for_tokens(self, code):
		"""
		Exchange authorization code for access_token and refresh_token.
		
		Typically called from a WebDev callback.
		
		Args:
		    code (str): Authorization code from Google.
		
		Returns:
		    (str, str): (access_token, refresh_token)
		"""
		info = self._read_dataset()
		client_id = info["client_id"]
		client_secret = info["client_secret"]
		
		if not client_id or not client_secret:
			raise ValueError("client_id or client_secret is missing in OAuthClient DataSet")

		payload = {
			"code": code,
			"client_id": client_id,
			"client_secret": client_secret,
			"redirect_uri": self.redirect_uri,
			"grant_type": "authorization_code",
		}
		
		# dict → x-www-form-urlencoded string
		body = urllib.urlencode(payload)
		
		client = system.net.httpClient(
			timeout=10000          # ms
		)
		
		resp = client.post(
			url=self.token_uri,
			data=body,
			headers={"Content-Type": "application/x-www-form-urlencoded"},
		)

		status = resp.statusCode
		jsonResult = resp.json

		if status != 200:
			self.logger.error(u"OAuthClient token request failed: %s %s" % (status, jsonResult))
			raise Exception(u"Token exchange failed: %s %s" % (status, jsonResult))

		access_token = jsonResult.get("access_token", "")
		refresh_token = jsonResult.get("refresh_token", "")
		expires_in = int(jsonResult.get("expires_in", 0))
		
		now = system.date.now()
		expiry = system.date.addSeconds(now, expires_in - 60)	# 60s safety margin
		
		update = {
			"_dataset": info["_dataset"],
			"access_token": access_token,
			"token_expiry": expiry,
		}
		if refresh_token:
			update["refresh_token"] = refresh_token

		self._write_dataset(update)
		return access_token, refresh_token

	def refresh_access_token(self):
		"""
		Refresh the access_token using the stored refresh_token.
		
		Returns:
			str: Newly issued access_token.
		"""
		info = self._read_dataset()
		client_id = info["client_id"]
		client_secret = info["client_secret"]
		refresh_token = info["refresh_token"]

		if not refresh_token:
			raise ValueError("refresh_token is empty. Initial consent is required.")

		payload = {
			"client_id": client_id,
			"client_secret": client_secret,
			"refresh_token": refresh_token,
			"grant_type": "refresh_token",
		}

		body = urllib.urlencode(payload)
		client = system.net.httpClient(timeout=10000)

		resp = client.post(
			url=self.token_uri,
			data=body,
			headers={"Content-Type": "application/x-www-form-urlencoded"},
		)

		status = resp.statusCode
		jsonResult = resp.json

		if status != 200:
			raise Exception("Token refresh failed: %s %s" % (status, jsonResult))
		else:
			self.logger.info(u'%s' % (jsonResult))

		access_token = jsonResult.get("access_token", "")
		expires_in = int(jsonResult.get("expires_in", 0))

		now = system.date.now()
		expiry = system.date.addSeconds(now, expires_in - 60)

		update = {
			"_dataset": info["_dataset"],
			"access_token": access_token,
			"token_expiry": expiry,
		}
		self._write_dataset(update)
		return access_token

	def get_valid_access_token(self):
		"""
		Return a valid access token, refreshing it when necessary.
		
		Returns:
			str: Valid access_token string.
		"""
		info = self._read_dataset()
		token = info["access_token"]
		expiry = info["token_expiry"]
		now = system.date.now()

		if (not token) or (expiry is None) or expiry.before(now):
			return self.refresh_access_token()

		return token


# ===========================================================
# Service Account (Server-based)
# ===========================================================

class GoogleServiceAccountClient(object):
	"""
	Service Account (server based).
	- DataSet: [root]/ServiceAccount
	  columns: client_email, private_key, access_token, token_expiry
	"""
	def __init__(self, root_tag_path):
		"""
		Args:
			root_tag_path    (str): Parent path to DataSet tag which holds Authentication information.
		"""
		self.root_tag_path = root_tag_path												# Modify with your enviroment
		self.tag_path = "%s/ServiceAccount" % root_tag_path								# Modify with your enviroment
		cfg = system.tag.getConfiguration(root_tag_path)[0]["parameters"]				# Modify with your enviroment
		self.scope = cfg["Scope"].value													# Modify with your enviroment
		self.token_uri = cfg["Token URI"].value or GOOGLE_TOKEN_ENDPOINT				# Modify with your enviroment
		self.logger = system.util.getLogger("GoogleServiceAccountClient")				# Modify with your enviroment

	# ------------------------------------------------------
	# DataSet helpers
	# ------------------------------------------------------
	def _read_dataset(self):
		result = system.tag.readBlocking([self.tag_path])[0]
		ds = result.value
		
		if ds is None or ds.rowCount == 0:
			default_row = [["", "", "", system.date.now()]]
			default_ds = system.dataset.toDataSet(
				["client_email", "private_key", "access_token", "token_expiry"],
				default_row,
			)
			system.tag.writeBlocking([self.tag_path], [default_ds])
			return default_ds

		row = ds[0]
		return {
			"client_email": row["client_email"],
			"private_key": row["private_key"],
			"access_token": row["access_token"],
			"token_expiry": row["token_expiry"],
			"_dataset": ds,
		}

	def _write_dataset(self, values):
		"""
		Update the first row of the DataSet tag using values from the given dict.
		
		Only keys that match existing column names are updated.
		
		Args:
			values (dict): May contain client_email, private_key,
			access_token, token_expiry, _dataset.
		"""
		ds = values.get("_dataset")
		if ds is None:
			ds = system.tag.readBlocking([self.tag_path])[0].value
		
		col_names = list(ds.getColumnNames())
		updated_rows = []
		
		for row_index in range(ds.rowCount):
			row = list(ds[row_index])
			if row_index == 0:
				for idx, col in enumerate(col_names):
					if col in values:
						row[idx] = values[col]
			updated_rows.append(row)

		new_ds = system.dataset.toDataSet(col_names, updated_rows)
		system.tag.writeBlocking([self.tag_path], [new_ds])

	# ------------------------------------------------------
	# JWT helpers
	# ------------------------------------------------------

	def _base64url_encode(self, b):
		encoder = JBase64.getUrlEncoder().withoutPadding()
		return encoder.encodeToString(b)

	def _load_private_key(self, private_key_pem):
		if not private_key_pem:
			raise ValueError("private_key is empty in ServiceAccount DataSet")
		lines = private_key_pem.replace("\\r", "").split("\\n")
		b64_lines = []
		for line in lines:
			line = line.strip()
			if (not line) or line.startswith("-----BEGIN") or line.startswith("-----END"):
				continue
			b64_lines.append(line)
		b64_str = "".join(b64_lines)
		
		decoder = JBase64.getDecoder()
		key_bytes = decoder.decode(b64_str)
		
		kf = KeyFactory.getInstance("RSA")
		spec = PKCS8EncodedKeySpec(key_bytes)
		privateKey = kf.generatePrivate(spec)
		return privateKey

	def _build_jwt_assertion(self, client_email, private_key_pem):
		if not client_email:
			raise ValueError("client_email is empty in ServiceAccount DataSet")
		if not self.scope:
			raise ValueError("Scope parameter is empty in UDT Parameters")

		privateKey = self._load_private_key(private_key_pem)
		
		now_ms = system.date.now().getTime()
		now_sec = now_ms / 1000
		exp_sec = now_sec + 3600
		
		header = {
			"alg": "RS256",
			"typ": "JWT",
		}
		claim_set = {
			"iss": client_email,
			"scope": self.scope,
			"aud": self.token_uri,
			"iat": int(now_sec),
			"exp": int(exp_sec),
		}
		
		header_json = json.dumps(header, separators=(",", ":"))
		claims_json = json.dumps(claim_set, separators=(",", ":"))
		
		header_b64 = self._base64url_encode(String(header_json).getBytes("UTF-8"))
		claims_b64 = self._base64url_encode(String(claims_json).getBytes("UTF-8"))

		signing_input_str = header_b64 + "." + claims_b64
		signing_input_bytes = String(signing_input_str).getBytes("UTF-8")

		sig = Signature.getInstance("SHA256withRSA")
		sig.initSign(privateKey)
		sig.update(signing_input_bytes)
		signature_bytes = sig.sign()
		
		signature_b64 = self._base64url_encode(signature_bytes)
		jwt_assertion = signing_input_str + "." + signature_b64
		return jwt_assertion
	
	# ------------------------------------------------------
	# Token request / refresh
	# ------------------------------------------------------

	def _request_access_token(self):
		info = self._read_dataset()
		client_email = info["client_email"]
		private_key = info["private_key"]
		
		assertion = self._build_jwt_assertion(client_email, private_key)
		
		params_dict = {
			"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
			"assertion": assertion,
		}
		
		params = urllib.urlencode(params_dict)
		
#		encoded = []
#		for k, v in params_dict.items():
#			encoded_pairs.append(u"%s=%s" % (k, v))
#		params = u"&".join(encoded)
		
		client = system.net.httpClient(timeout=10000)
		resp = client.post(
			url=self.token_uri,
			data=params,
			headers={"Content-Type": "application/x-www-form-urlencoded"},
		)
		
		status = resp.statusCode
		jsonResult = resp.json
		
		if status != 200:
			self.logger.error(u"ServiceAccount token request failed: %s %s" % (status, jsonResult))
			raise Exception(u"ServiceAccount token request failed: HTTP %s" % status)
		else:
			self.logger.info(u'%s' % (jsonResult))
		
		access_token = jsonResult.get("access_token", "")
		expires_in = int(jsonResult.get("expires_in", 3600))
		
		now = system.date.now()
		expiry = system.date.addSeconds(now, expires_in - 60)
		
		update = {
			"_dataset": info["_dataset"],
			"access_token": access_token,
			"token_expiry": expiry,
		}
		self._write_dataset(update)
		return access_token

	def get_valid_access_token(self):
		info = self._read_dataset()
		token = info["access_token"]
		expiry = info["token_expiry"]
		now = system.date.now()
		
		if (not token) or (expiry is None) or expiry.before(now):
			return self._request_access_token()

		return token

## debug
#from google.auth import GoogleServiceAccountClient
#
#rootPath = "[default]Google"
#client = GoogleServiceAccountClient(rootPath)
#token = client.get_valid_access_token()
#
#http = system.net.httpClient(timeout=10000)
#resp = http.get(
#    u"https://oauth2.googleapis.com/tokeninfo?access_token=%s" % token
#)
#
#print "STATUS:", resp.getStatusCode()
#print "JSON:", resp.getJson()

# ===========================================================
# Unified Provider (UseSA Boolean Choice)
# ===========================================================

class GoogleAuthProvider(object):
	"""
	Automatically scan UseSA(Boolean) of UDT
	- True  → Service Account
	- False → OAuth Client
	and return the access token.
	"""

	def __init__(self, root_tag_path):
		self.root_tag_path = root_tag_path
		self.oauth_client = GoogleOAuthClient(root_tag_path)
		self.sa_client = GoogleServiceAccountClient(root_tag_path)

	def get_valid_access_token(self):												# Modify with your enviroment
		use_sa = system.tag.readBlocking(										# Modify with your enviroment
			[u"%s/UseSA" % self.root_tag_path]									# Modify with your enviroment
		)[0].value																# Modify with your enviroment

		# debug: https://oauth2.googleapis.com/tokeninfo?access_token=		
		if use_sa:
			return self.sa_client.get_valid_access_token()
		else:
			return self.oauth_client.get_valid_access_token()


	