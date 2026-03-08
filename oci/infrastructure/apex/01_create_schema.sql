/*
 * Credit Risk ML Dashboard — Schema Setup
 * Run as ADMIN in SQL Developer Web or APEX SQL Workshop
 *
 * Creates:
 *   - MLMONITOR user/schema
 *   - APEX workspace mapped to MLMONITOR
 *   - Required privileges
 */

-- 1. Create schema user
BEGIN
  EXECUTE IMMEDIATE 'CREATE USER mlmonitor IDENTIFIED BY "CreditRisk2026#ML"
    DEFAULT TABLESPACE DATA
    QUOTA UNLIMITED ON DATA';
EXCEPTION WHEN OTHERS THEN
  IF SQLCODE = -1920 THEN NULL; -- user already exists
  ELSE RAISE;
  END IF;
END;
/

-- 2. Grant privileges
GRANT CREATE SESSION TO mlmonitor;
GRANT CREATE TABLE TO mlmonitor;
GRANT CREATE VIEW TO mlmonitor;
GRANT CREATE SEQUENCE TO mlmonitor;
GRANT CREATE PROCEDURE TO mlmonitor;
GRANT CREATE TRIGGER TO mlmonitor;

-- 3. Create APEX workspace
BEGIN
  APEX_INSTANCE_ADMIN.ADD_WORKSPACE(
    p_workspace      => 'MLMONITOR',
    p_primary_schema => 'MLMONITOR'
  );
EXCEPTION WHEN OTHERS THEN
  IF SQLCODE = -20001 THEN NULL; -- workspace exists
  ELSE RAISE;
  END IF;
END;
/

-- 4. Create APEX admin user for the workspace
BEGIN
  APEX_UTIL.SET_SECURITY_GROUP_ID(
    APEX_UTIL.FIND_SECURITY_GROUP_ID('MLMONITOR')
  );

  APEX_UTIL.CREATE_USER(
    p_user_name       => 'DASHADMIN',
    p_email_address   => 'wandersonlima20@gmail.com',
    p_web_password    => 'CreditRisk2026#ML',
    p_developer_privs => 'ADMIN:CREATE:DATA_LOADER:EDIT:HELP:MONITOR:SQL',
    p_change_password_on_first_use => 'N'
  );
EXCEPTION WHEN OTHERS THEN NULL;
END;
/
