# google.google_sheets
# -----------------------------------------------------------
# Google Sheets REST API helper built on top of GoogleAuthProvider /
# GoogleOAuthClient / GoogleServiceAccountClient (any object that
# implements get_valid_access_token()).
# -----------------------------------------------------------

#import urllib
from google.auth import GoogleAuthProvider
from collections import OrderedDict

SHEETS_APPEND_URL = u"https://sheets.googleapis.com/v4/spreadsheets/%s/values/%s:append"
SHEETS_GET_URL = u"https://sheets.googleapis.com/v4/spreadsheets/%s/values/%s"
SHEETS_UPDATE_URL = u"https://sheets.googleapis.com/v4/spreadsheets/%s/values/%s"
SHEETS_CLEAR_URL  = u"https://sheets.googleapis.com/v4/spreadsheets/%s/values/%s:clear"

class GoogleSheetsClient(object):
	"""
	Simple Google Sheets client wrapper.
	
	Authentication:
	- Expects an auth client that exposes:
		get_valid_access_token() -> str
	- This can be:
		- GoogleAuthProvider (UDT UseSA toggle)
		- GoogleOAuthClient   (OAuth only)
		- GoogleServiceAccountClient (Service Account only)

	Responsibilities:
	- Manage spreadsheet ID
	- Append rows to a given range
	- Read rows from a given range
	- Update ranges
	- Clear ranges
	- Batch get / batch update
	- Header-based dictionary append helper
	"""

	def __init__(self, root_tag_path, spreadsheet_id):
		"""
		Args:
			root_tag_path    (str): Parent path to DataSet tag which holds Authentication information.
			spreadsheet_id(str): Google Sheets file ID.
		"""
		self.root_tag_path = root_tag_path
		self.spreadsheet_id = spreadsheet_id
		
	# ------------------------------------------------------------------
	# Internal helper
	# -----------------------------------------------------------------
	def _get_http_client_and_token(self):
		"""
		Internal helper to get a ready-to-use httpClient and valid access_token.
		"""
		authClient = GoogleAuthProvider(self.root_tag_path)
		token = authClient.get_valid_access_token()
		client = system.net.httpClient(timeout=10000)
		return client, token

	# ------------------------------------------------------------------
	# Basic values API: Spreadsheet Resource
	# -----------------------------------------------------------------
	def get_spreadsheet_resource(self):
		"""
		Fetch the Spreadsheet resource (sheets, properties, etc).
		
		Returns:
			dict: Raw JSON from spreadsheets.get.
		"""
		client, token = self._get_http_client_and_token()
		
		url = u"https://sheets.googleapis.com/v4/spreadsheets/%s" % self.spreadsheet_id
		
		resp = client.get(
			url=url,
			headers={u"Authorization": "Bearer %s" % token}
		)

		status = resp.getStatusCode()
		jsonResult = resp.getJson()

#		logger = system.util.getLogger("google-sheets-resource")
#		logger.info(u"GET RESOURCE status = %s" % status)
#		logger.info(u"GET RESOURCE result   = %s" % jsonResult)

		if status != 200:
			raise Exception(u"spreadsheets.get failed: %s %s" % (status, jsonResult))

		return jsonResult

	def get_sheet_name_id_map(self):
		"""
		Build a mapping: sheetName -> sheetId and sheetId -> sheetName.
		
		Returns:
			dict: {
				"byName": {"Sheet1": 0, "Sheet2": 123456789, ...},
				"byId": {0: "Sheet1", 123456789: "Sheet2", ...}
			}
		"""
		meta = self.get_spreadsheet_resource()
		sheets = meta.get("sheets", []) or []
		
		by_name = {}
		by_id = {}
		
		for sheet in sheets:
			props = sheet.get("properties", {}) or {}
			name = props.get("title")
			sid = props.get("sheetId")
			if name is not None and sid is not None:
				by_name[name] = sid
				by_id[int(sid)] = name
		
		return {"byName": by_name, "byId": by_id}
		
	# ------------------------------------------------------------------
	# Basic values API: append / get
	# ------------------------------------------------------------------
	def get_rows(self, range_a1):
		"""
		Retrieve rows from the Sheet.
		
		Args:
			range_a1 (str): A1 notation, (e.g. "Sheet1!A1:D100").
		
		Returns:
			list[list]: 2D list of values (e.g. {"A": ..., "B": ..., ...}).
		"""
		client, token = self._get_http_client_and_token()
		
#		encoded_range = urllib.quote(range_a1.encode("utf-8"))
		encoded_range = range_a1.strip()
		url = SHEETS_GET_URL % (self.spreadsheet_id, encoded_range)

		resp = client.get(
			url=url,
			headers={"Authorization": "Bearer %s" % token},
		)

		status = resp.getStatusCode()
		jsonResult = resp.getJson()

		if status != 200:
			raise Exception("Sheets GET failed: %s %s %s" % (url, status, jsonResult))

		values = jsonResult.get("values", []) or []
	
		result = []
#		for row in values:
#			row_dict = {}
#			for idx, cell in enumerate(row):
#				col_letter = _to_column_letters(idx + 1)  # 1→A, 2→B, ...
#				row_dict[col_letter] = cell
#			result.append(row_dict)
			
		for row in values:
			od = OrderedDict()
			for idx, cell in enumerate(row):
				col_letter = _to_column_letters(idx + 1)  # 1→A, 2→B, ...
				od[col_letter] = cell
			result.append(od)
			
		return result

	def append_rows(self, range_a1, values, value_input_option="USER_ENTERED"):
		"""
		Append one or more rows to the Sheet using values.append.
		
		Args:
			range_a1 (str): A1 notation, e.g. "Sheet1" or "Sheet1!A1".
							If only sheet name is given (e.g. "Sheet1"),
							rows are appended to the end of the sheet.
		    values (list[list]): 2D list, each inner list is a row.
		    value_input_option (str): "USER_ENTERED"(Numbers will stay as numbers, but strings may be converted to numbers, dates, etc.)
		    						 or "RAW"(not be parsed and will be stored as-is).
		
		Returns:
			dict: Parsed JSON response.
		"""
		client, token = self._get_http_client_and_token()
		
#		encoded_range = urllib.quote(range_a1.encode("utf-8"))		
		encoded_range = range_a1.strip()
		url = SHEETS_APPEND_URL % (self.spreadsheet_id, encoded_range)
		url += u"?valueInputOption=%s&insertDataOption=OVERWRITE" % value_input_option

		payload = {"values": values}
		body = system.util.jsonEncode(payload)
#		logger = system.util.getLogger("google-sheets-append")
#		logger.info(u"POST url    = %s" % url)
#		logger.info(u"POST payload    = %s" % payload)
#		logger.info(u"POST body = %s" % body)
		resp = client.post(
			url=url,
			data=body,
			headers={
				"Authorization": "Bearer %s" % token,
				"Content-Type": "application/json",
			}
		)

		status = resp.getStatusCode()
		jsonResult = resp.getJson()

		if status not in (200, 201):
			raise Exception("Sheets APPEND failed: %s %s %s" % (url, status, jsonResult))

		return jsonResult
		
	def update_rows(self, range_a1, values, value_input_option="USER_ENTERED"):
		"""
		Overwrite values in a specific range using the Sheets 'values.update' API.
		
		Args:
			range_a1 (str): A1 notation, (e.g. "Sheet1!A2:B10").
			values   (list[list]): 2D list, each inner list is a row.
			value_input_option (str): "USER_ENTERED" or "RAW".
		
		Returns:
			dict: Parsed JSON response from the API.
		"""
		client, token = self._get_http_client_and_token()
		
		# Use the given A1 range as-is (no manual URL encoding).
		encoded_range = range_a1.strip()
		
		# Build URL for values.update
		url = SHEETS_UPDATE_URL % (self.spreadsheet_id, encoded_range)
		url += "?valueInputOption=%s" % value_input_option
		
		payload = {"values": values}
		body = system.util.jsonEncode(payload)
		
		logger = system.util.getLogger("google-sheets-update")
		logger.info(u"UPDATE url    = %s" % url)
		logger.info(u"UPDATE values = %s" % values)
		
		resp = client.put(
			url=url,
			data=body,
			headers={
				"Authorization": "Bearer %s" % token,
				"Content-Type": "application/json",
			}
		)

		status = resp.getStatusCode()
		text = resp.getText()
		logger.info(u"UPDATE status = %s" % status)
		logger.info(u"UPDATE body   = %s" % text)

		if status != 200:
			raise Exception("Sheets UPDATE failed: %s %s %s" % (url, status, text))

		return resp.getJson()
		
	def clear_rows(self, range_a1):
		"""
		Clear (empty) all values in the specified range using 'values.clear'.
		
		Args:
		    range_a1 (str): A1 notation, e.g. "Sheet1!A2:B100".
		
		Returns:
		    dict: Parsed JSON response from the API.
		"""
		client, token = self._get_http_client_and_token()
		
		encoded_range = range_a1.strip()
		url = SHEETS_CLEAR_URL % (self.spreadsheet_id, encoded_range)
		
		logger = system.util.getLogger("google-sheets-clear")
		logger.info(u"CLEAR url  = %s" % url)
		
		# values.clear expects an empty JSON body.
		body = system.util.jsonEncode({})
		
		resp = client.post(
			url=url,
			data=body,
			headers={
				"Authorization": "Bearer %s" % token,
				"Content-Type": "application/json",
			}
        	)

		status = resp.getStatusCode()
		text = resp.getText()
		logger.info(u"CLEAR status = %s" % status)
		logger.info(u"CLEAR body   = %s" % text)
		
		if status != 200:
			raise Exception("Sheets CLEAR failed: %s %s %s" % (url, status, text))
		
		return resp.getJson()

	def batch_get(self, ranges_a1, major_dimension="ROWS"):
		"""
		Read multiple ranges in a single API call using 'values.batchGet'.
		
		Args:
			ranges_a1 (list[str]): List of A1 ranges, e.g. ["Sheet1!A1:B10", "test!A1:C5"].
			major_dimension (str): "ROWS" or "COLUMNS".
		
		Returns:
			dict: {
				"range1": [[...], [...], ...],
				"range2": [[...], ...],
				...
			}
		"""
		client, token = self._get_http_client_and_token()
		
		# Build query params: ranges=...&ranges=...
		base_url = "https://sheets.googleapis.com/v4/spreadsheets/%s/values:batchGet" % self.spreadsheet_id
		
		# Manually build query string to avoid encoding issues
		params = ["majorDimension=%s" % major_dimension]
		for r in ranges_a1:
			params.append("ranges=%s" % r)
		
		url = base_url + "?" + "&".join(params)
		
		logger = system.util.getLogger("google-sheets-batch-get")
		logger.info(u"BATCH GET url = %s" % url)
		
		resp = client.get(
			url=url,
			headers={"Authorization": "Bearer %s" % token},
			timeout=10000,
		)
		
		status = resp.getStatusCode()
		text = resp.getText()
		
		logger.info(u"BATCH GET status = %s" % status)
		logger.info(u"BATCH GET body   = %s" % text)
		
		if status != 200:
			raise Exception("values.batchGet failed: %s %s" % (status, text))
		
		data = resp.getJson()
		value_ranges = data.get("valueRanges", []) or []
		
		result = {}
		for vr in value_ranges:
			rng = vr.get("range")
			vals = vr.get("values", [])
			if rng:
				result[rng] = vals

		return result
		
	def batch_update_values(self, data_items, value_input_option="USER_ENTERED"):
		"""
		Write values to multiple ranges in a single API call using 'values.batchUpdate'.
		
		Args:
			data_items (list[dict]): Each item:
				{
					"range": "Sheet1!A1:B2",
					"values": [[...], [...]]
				}
			value_input_option (str): "USER_ENTERED" or "RAW".
		
		Returns:
			dict: Parsed JSON response.
		"""
		client, token = self._get_http_client_and_token()
		
		url = "https://sheets.googleapis.com/v4/spreadsheets/%s/values:batchUpdate" % self.spreadsheet_id
		
		body_obj = {
			"valueInputOption": value_input_option,
			"data": data_items,
		}
		
		body = system.util.jsonEncode(body_obj)
		
		logger = system.util.getLogger("google-sheets-batch-update")
		logger.info(u"BATCH UPDATE url  = %s" % url)
		logger.info(u"BATCH UPDATE body = %s" % body)
		
		resp = client.post(
			url=url,
			data=body,
			headers={
				"Authorization": "Bearer %s" % token,
				"Content-Type": "application/json",
			},
			timeout=10000,
		)
		
		status = resp.getStatusCode()
		text = resp.getText()
		
		logger.info(u"BATCH UPDATE status = %s" % status)
		logger.info(u"BATCH UPDATE resp   = %s" % text)
		
		if status != 200:
			raise Exception("values.batchUpdate failed: %s %s" % (status, text))
		
		return resp.getJson()

	def get_dict_rows(self, sheet_name, header_row_index=1, start_row=2, end_row=None):
		"""
		Read rows as list[dict] using a header row.

		Args:
			sheet_name (str): Sheet name, e.g. "Sheet1".
			header_row_index (int): 1-based header row index.
			start_row (int): 1-based first data row index to read.
			end_row (int or None): 1-based last data row index. If None, read to ZZ.

		Returns:
			list[dict]: Each dict maps header -> cell value.
		"""
		logger = system.util.getLogger("google-sheets-get-dict")
		
		# 1) Read header (A,B,C,... dict)
		header_range = u"%s!A%d:ZZ%d" % (sheet_name, header_row_index, header_row_index)
		header_rows = self.get_rows(header_range)
		
		if header_rows and len(header_rows) > 0:
			header_dict = header_rows[0]											# e.g. OrderedDict("A": "col1", "B": "col2", ...)
#			col_letters = sorted(header_dict.keys(), key=lambda x: (len(x), x))		# A..Z,AA..AZ...
			col_letters = list(header_dict.keys())									# preserve order
			columns = [header_dict[c] for c in col_letters]
		else:
			col_letters = []
			columns = []

		if not columns:
			logger.info(u"get_dict_rows: header not found, returning empty list.")
			return []

		# 2) Read data region using actual last header column letter
		last_col_letter = col_letters[-1]
		if end_row is None:
			data_range = u"%s!A%d:%s" % (sheet_name, start_row, last_col_letter)
		else:
			data_range = u"%s!A%d:%s%d" % (sheet_name, start_row, last_col_letter, end_row)

		data_rows = self.get_rows(data_range)  # list of dicts keyed by column letters # e.g. list[OrderedDict("A"->..., "B"->..., ...)]

		result = []
		
		for row_dict_letters in data_rows:
#			row_by_header = {}
			row_by_header = OrderedDict()
			for idx, header_name in enumerate(columns):
				col_letter = col_letters[idx]
				value = row_dict_letters.get(col_letter, u"")
				row_by_header[header_name] = value
			result.append(row_by_header)

		return result

	def append_dict_rows(self, sheet_name, header_row_index, dict_rows, add_t_stamp=True):
		"""
		Append rows to a sheet using dictionaries, automatically matching column names,
		and adding new columns when new keys appear.
		
		Args:
			sheet_name (str): Name of the sheet (e.g. "Sheet1" or "test").
			header_row_index (int): 1-based index of the header row (usually 1).
			dict_rows (list[dict]): Each dict mapping columnName -> value.
			add_t_stamp (bool): If True, add "t_stamp" column with current datetime.
		
		Returns:
			dict: Last append response from Sheets API.
		"""
		logger = system.util.getLogger("google-sheets-append-dict")
		
		# 1) Read the header row
		header_range = u"%s!A%d:ZZ%d" % (
			sheet_name,
			header_row_index,
			header_row_index,
		)

		header_rows = self.get_rows(header_range)  # list[{"A": "col1", "B": "col2", ...}]
		
		if header_rows and len(header_rows) > 0:
			header_dict = header_rows[0]
			# Order By A,B,...,Z,AA,...
			col_letters = sorted(header_dict.keys(), key=lambda x: (len(x), x))
			header_row = [header_dict[c] for c in col_letters]
		else:
			col_letters = []
			header_row = []
		
		columns = list(header_row)
		
		# Ensure "t_stamp" column exists if requested
		if add_t_stamp and "t_stamp" not in columns:
			columns.append("t_stamp")
		
		# 2) Build rows according to header columns, auto-expanding columns for new keys
		all_rows = []
		now = system.date.now().getTime()  # Store as Milliseconds; customize format if desired
		
		for d in dict_rows:
			row_dict = dict(d)  # shallow copy
			if add_t_stamp:
				row_dict["t_stamp"] = now
		
			# Ensure header has all keys
			for key in row_dict.keys():
				if key not in columns:
					columns.append(key)
		
			# Build row aligned to current columns
			row = [row_dict.get(col, "") for col in columns]
			all_rows.append(row)
		
		# 3) If we expanded columns beyond original header, update the header row via update_range
		if len(columns) > len(header_row):
			# compute end column letter (A, B, ..., Z, AA, AB, ..., ZZ) for simplicity up to 26*2
			col_letters_for_header = _to_column_letters(len(columns))

			header_update_range = u"%s!A%d:%s%d" % (
			    sheet_name,
			    header_row_index,
			    col_letters,
			    header_row_index,
			)
		
			self.update_range(header_update_range, [columns])
		
		# 4) Append the rows at the bottom of the sheet
		#    We use "sheetName" only (no row index), so Sheets appends at the end.
		append_range = u"%s" % sheet_name
		result = self.append_rows(append_range, all_rows)
#		logger.info(u"append_dict_rows completed: %s" % result)
		return result
		
	def update_dict_rows(self, sheet_name, header_row_index, start_row, dict_rows, add_t_stamp=False):
		"""
		Update a contiguous block of rows using dictionaries and a header row.
		Automatically expands header when new keys appear.

		Args:
			sheet_name (str): Sheet name, e.g. "Sheet1".
			header_row_index (int): 1-based header row index.
			start_row (int): 1-based first row to update.
			dict_rows (list[dict]): Each dict maps column name -> value.
			add_t_stamp (bool): If True, add/overwrite 't_stamp' column.

		Returns:
			dict: Sheets API response from values.update.
		"""
		logger = system.util.getLogger("google-sheets-update-dict")

		# 1) Read header
		header_range = u"%s!A%d:ZZ%d" % (sheet_name, header_row_index, header_row_index)
		header_rows = self.get_rows(header_range)

		if header_rows and len(header_rows) > 0:
			header_dict = header_rows[0]
			col_letters = sorted(header_dict.keys(), key=lambda x: (len(x), x))
			header_row = [header_dict[c] for c in col_letters]
		else:
			col_letters = []
			header_row = []
	
		columns = list(header_row)

		if add_t_stamp and "t_stamp" not in columns:
			columns.append("t_stamp")

		# 2) Merge keys from dict_rows
		now = system.date.now().getTime()  # Store as Milliseconds; customize format if desired
		rows_values = []

		for d in dict_rows:
			row_dict = dict(d)
			if add_t_stamp:
				row_dict["t_stamp"] = now

			for key in row_dict.keys():
				if key not in columns:
					columns.append(key)

			row = [row_dict.get(col, u"") for col in columns]
			rows_values.append(row)

		# 3) If header expanded, write it back
		if len(columns) > len(header_row):
			col_letters_for_header = _to_column_letters(len(columns))
			header_update_range = u"%s!A%d:%s%d" % (
				sheet_name,
				header_row_index,
				col_letters_for_header,
				header_row_index,
			)
			self.update_rows(header_update_range, [columns])

		# 4) Update data block
		end_row = start_row + len(rows_values) - 1
		col_letters_for_data = _to_column_letters(len(columns))
		update_range = u"%s!A%d:%s%d" % (
			sheet_name,
			start_row,
			col_letters_for_data,
			end_row,
		)

#		logger.info(u"UPDATE_DICT range = %s" % update_range)
		return self.update_rows(update_range, rows_values)

	def clear_dict_rows(self, sheet_name, header_row_index, start_row, end_row):
		"""
		Clear rows using header width (A..last header column).

		Args:
			sheet_name (str): Sheet name, e.g. "Sheet1".
			header_row_index (int): 1-based header row index (to detect last column).
			start_row (int): 1-based first data row to clear.
			end_row (int): 1-based last data row to clear.

		Returns:
			dict: Sheets API response from values.clear.
		"""
		logger = system.util.getLogger("google-sheets-clear-dict")

		# 1) Read header to know how many columns are in use
		header_range = u"%s!A%d:ZZ%d" % (sheet_name, header_row_index, header_row_index)
		header_rows = self.get_rows(header_range)
		
		if header_rows and len(header_rows) > 0:
			header_dict = header_rows[0]
			columns = [header_dict[c] for c in sorted(header_dict.keys(), key=lambda x: (len(x), x))]
		else:
			columns = []

		if not columns:
			# no header ⇒ nothing to clear for dict-based region
			logger.info(u"clear_dict_rows: no header found, skipping.")
			return {}

		col_letters = _to_column_letters(len(columns))
		clear_range = u"%s!A%d:%s%d" % (
			sheet_name,
			start_row,
			col_letters,
			end_row,
		)

		logger.info(u"CLEAR_DICT range = %s" % clear_range)
		return self.clear_rows(clear_range)


# ----------------------------------------------------------------------
# Helper to convert column index to Excel-style letters
# ----------------------------------------------------------------------		
def _to_column_letters(n):
	"""
	Convert 1-based column index to Excel-style column letters.
	Example:
		1 -> "A"
		26 -> "Z"
		27 -> "AA"
		28 -> "AB"
	Supports up to 702 ("ZZ"), which is typically enough.
	"""
	n = int(n)
	letters = []
	while n > 0:
		n, rem = divmod(n - 1, 26)					# n: quotient, rem: remainder
		letters.insert(0, chr(ord("A") + rem))		# eg. ord("A") -> 65, chr(65 + 1) -> "B", n==28 -> letters = [] -> [B] -> [AB]
	return "".join(letters)