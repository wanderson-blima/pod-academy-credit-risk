/*
 * ADW External Tables — Step 1: Setup OCI Credentials
 * Run as ADMIN in Database Actions > SQL Worksheet
 *
 * Prerequisites: OCI API key configured for the ADW user
 */

-- Create OCI credential for Object Storage access
BEGIN
  DBMS_CLOUD.CREATE_CREDENTIAL(
    credential_name => 'OCI_CRED',
    user_ocid       => '&user_ocid',
    tenancy_ocid    => '&tenancy_ocid',
    private_key      => '&api_key_content',
    fingerprint      => '&fingerprint'
  );
END;
/

-- Verify credential
SELECT credential_name, username, enabled
FROM all_credentials
WHERE credential_name = 'OCI_CRED';

-- Grant to MLMONITOR schema (for APEX dashboard access)
BEGIN
  DBMS_CLOUD.ENABLE_RESOURCE_PRINCIPAL();
EXCEPTION
  WHEN OTHERS THEN
    DBMS_OUTPUT.PUT_LINE('Resource Principal not available (Trial). Using API key auth.');
END;
/
