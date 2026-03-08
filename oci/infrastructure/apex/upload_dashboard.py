"""Upload dashboard HTML to ADW via ORDS REST SQL endpoint using base64."""
import requests
import os
import base64

ORDS_URL = "https://G95D3985BD0D2FD-PODACADEMY.adb.sa-saopaulo-1.oraclecloudapps.com/ords/mlmonitor/_/sql"
AUTH = ("MLMONITOR", "CreditRisk2026#ML")
HEADERS = {"Content-Type": "application/sql"}

html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Base64 encode to avoid & substitution issues
html_b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")

# Split base64 into chunks (safe size for VARCHAR2)
CHUNK_SIZE = 3000
chunks = [html_b64[i:i+CHUNK_SIZE] for i in range(0, len(html_b64), CHUNK_SIZE)]

print(f"HTML: {len(html)} bytes, Base64: {len(html_b64)}, Chunks: {len(chunks)}")

# First delete existing content
requests.post(ORDS_URL, auth=AUTH, headers=HEADERS,
    data="DELETE FROM dashboard_content")

# Insert empty CLOB
requests.post(ORDS_URL, auth=AUTH, headers=HEADERS,
    data="INSERT INTO dashboard_content (id, html_content) VALUES (1, EMPTY_CLOB())")
requests.post(ORDS_URL, auth=AUTH, headers=HEADERS, data="COMMIT")

# Build PL/SQL to decode base64 and write to CLOB in chunks
for i, chunk in enumerate(chunks):
    plsql = f"""DECLARE
  l_clob CLOB;
  l_raw RAW(32767);
  l_decoded VARCHAR2(32767);
BEGIN
  SELECT html_content INTO l_clob FROM dashboard_content WHERE id = 1 FOR UPDATE;
  l_raw := UTL_ENCODE.BASE64_DECODE(UTL_RAW.CAST_TO_RAW('{chunk}'));
  l_decoded := UTL_RAW.CAST_TO_VARCHAR2(l_raw);
  DBMS_LOB.WRITEAPPEND(l_clob, LENGTH(l_decoded), l_decoded);
  COMMIT;
END;"""

    resp = requests.post(ORDS_URL, auth=AUTH, headers=HEADERS, data=plsql.encode("utf-8"))
    result = resp.json()
    items = result.get("items", [])
    success = any("successfully" in str(it.get("response", "")) for it in items)
    error = any(it.get("errorCode") for it in items)

    if error:
        for it in items:
            if it.get("errorCode"):
                print(f"  Chunk {i+1}: ERROR - {it.get('errorDetails', '')[:150]}")
        break
    else:
        print(f"  Chunk {i+1}/{len(chunks)}: OK")

# Verify
resp2 = requests.post(ORDS_URL, auth=AUTH, headers=HEADERS,
    data="SELECT DBMS_LOB.GETLENGTH(html_content) AS len FROM dashboard_content WHERE id = 1")
result2 = resp2.json()
for item in result2.get("items", []):
    rs = item.get("resultSet", {})
    for row in rs.get("items", []):
        print(f"\nStored HTML length: {row.get('len', '?')} bytes")

# Now update the ORDS handler to serve the HTML
handler_sql = """BEGIN
  ORDS.DEFINE_HANDLER(
    p_module_name => 'dashboard',
    p_pattern     => '.',
    p_method      => 'GET',
    p_source_type => 'plsql/block',
    p_mimes_allowed => 'text/html',
    p_source      => '
DECLARE
  l_clob CLOB;
BEGIN
  OWA_UTIL.MIME_HEADER(''text/html'', FALSE);
  OWA_UTIL.HTTP_HEADER_CLOSE;
  SELECT html_content INTO l_clob FROM dashboard_content WHERE id = 1;
  HTP.P(l_clob);
END;'
  );
  COMMIT;
END;"""

resp3 = requests.post(ORDS_URL, auth=AUTH, headers=HEADERS, data=handler_sql.encode("utf-8"))
result3 = resp3.json()
for it in result3.get("items", []):
    if it.get("errorCode"):
        print(f"Handler ERROR: {it.get('errorDetails', '')[:200]}")
    elif "successfully" in str(it.get("response", "")):
        print("ORDS handler updated successfully!")
