import os
import logging
from dotenv import load_dotenv
from ldap3 import Server, Connection, Tls, ALL, SUBTREE
import ssl
from datetime import datetime
import psycopg2.extras

# Get a logger that inherits the root configuration
logger = logging.getLogger(__name__)

# --- Import the db_utils module to use the connection pool ---
from jira_data_analysis import db_utils

class LdapUser:
    """A class to represent a user from LDAP."""
    def __init__(self, entry):
        # Extract attributes safely, providing default values
        self.account_name = entry.sAMAccountName.value if 'sAMAccountName' in entry else ''
        self.display_name = entry.displayName.value if 'displayName' in entry else ''
        self.email = entry.userPrincipalName.value.lower() if 'userPrincipalName' in entry else ''
        self.employee_id = entry.employeeID.value if 'employeeID' in entry else ''
        self.city = entry.l.value if 'l' in entry else ''
        self.country = entry.co.value if 'co' in entry else ''
        self.department = entry.department.value if 'department' in entry else ''
        self.distinguished_name = entry.distinguishedName.value if 'distinguishedName' in entry else ''
        self.manager = None # This will be populated later
        self.reports = [] # This will hold a list of LdapUser objects

    def is_manager(self) -> bool:
        """Checks if the user has any direct reports."""
        return len(self.reports) > 0
    
    def to_tuple(self):
        """Converts the object to a tuple for database operations."""
        manager_name = self.manager.display_name if self.manager else None
        manager_email = self.manager.email if self.manager else None
        return (
            self.employee_id, self.account_name, self.display_name, self.email,
            self.city, self.country, self.department, manager_name,
            manager_email, self.is_manager(), datetime.now()
        )

class LdapClient:
    """A client to connect and query the LDAP server."""
    def __init__(self):
        self.server_name = os.getenv('LDAP_SERVER', 'ldap.fyi.sas.com')
        self.port = int(os.getenv('LDAP_PORT', 3269))
        self.base_dn = os.getenv('LDAP_BASE_DN', 'DC=SAS,DC=com')
        self.user = os.getenv('LDAP_USER')
        self.password = os.getenv('LDAP_PASS')
        self.connection = None

    def connect(self):
        """Establishes and binds a connection to the LDAP server."""
        try:
            logger.info(f"⚙️ Connecting to LDAP server at {self.server_name}...")
            # Use TLS for a secure connection
            tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
            server = Server(self.server_name, port=self.port, use_ssl=True, tls=tls_config, get_info=ALL)
            self.connection = Connection(server, user=self.user, password=self.password, auto_bind=True)
            if self.connection.bind():
                logger.info("✅ Successfully connected and bound to LDAP server!")
                return True
            else:
                logger.error(f"❌ Failed to bind to LDAP server: {self.connection.result}")
                return False
        except Exception as e:
            logger.error(f"❌ An error occurred while connecting to LDAP: {e}")
            return False

    def close(self):
        """Closes the LDAP connection."""
        if self.connection:
            self.connection.unbind()
            logger.info("LDAP connection closed.")

    def get_user_by_email(self, email: str) -> LdapUser | None:
        """Searches for a single user by their email address (userPrincipalName)."""
        search_filter = f'(userPrincipalName={email})'
        attributes = ['sAMAccountName', 'displayName', 'userPrincipalName', 'employeeID', 'l', 'co', 'department', 'distinguishedName']
        
        self.connection.search(self.base_dn, search_filter, SUBTREE, attributes=attributes)
        
        if len(self.connection.entries) == 1:
            return LdapUser(self.connection.entries[0])
        elif len(self.connection.entries) > 1:
            logger.warning(f"Found multiple users with email '{email}'. Returning the first one.")
            return LdapUser(self.connection.entries[0])
        else:
            logger.error(f"No user found with email '{email}'.")
            return None

    def get_reports_for_user(self, manager: LdapUser, recursive: bool = True):
        """Recursively finds all direct and indirect reports for a given manager."""
        # Search for users whose 'manager' attribute matches the manager's distinguished name
        # Also filter out disabled accounts
        search_filter = f"(&(manager={manager.distinguished_name})(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
        attributes = ['sAMAccountName', 'displayName', 'userPrincipalName', 'employeeID', 'l', 'co', 'department', 'distinguishedName']
        
        self.connection.search(self.base_dn, search_filter, SUBTREE, attributes=attributes)
        
        for entry in self.connection.entries:
            report = LdapUser(entry)
            report.manager = manager # Set the manager for this report
            if recursive:
                # Recursively call to find sub-reports
                self.get_reports_for_user(report, recursive=True)
            manager.reports.append(report)

def flatten_reports(user: LdapUser, exclude_list: set) -> list:
    """Recursively flattens the reporting structure into a list for CSV export."""
    flat_list = []
    
    # Check if the current user's email is in the exclude list (case-insensitive)
    if user.email.lower() not in exclude_list:
        flat_list.append(user)
        for report in user.reports:
            flat_list.extend(flatten_reports(report, exclude_list))
            
    return flat_list

def sync_ldap_data_to_db(db_pool, all_users: list):
    """Synchronizes the fetched LDAP user data with the PostgreSQL database."""
    if not all_users:
        logger.info("No LDAP users to sync. Database operations will be skipped.")
        return

    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            # 1. Fetch existing records from the database
            logger.info("Fetching existing records from tbl_ldap_hierarchy...")
            cursor.execute("SELECT employee_id, account_name, display_name, email, city, country, department, manager_name, manager_email, is_manager FROM tbl_ldap_hierarchy")
            # Create a dictionary for easy lookup: {employee_id: (all_other_fields...)}
            db_users = {row[0]: row[1:] for row in cursor.fetchall()}
            logger.info(f"Found {len(db_users)} records in the database.")

            # 2. Compare LDAP data with DB data to find differences
            ldap_users_map = {user.employee_id: user for user in all_users if user.employee_id}
            
            to_insert = []
            to_update = []
            
            for ldap_id, ldap_user in ldap_users_map.items():
                ldap_tuple = ldap_user.to_tuple()[1:] # Exclude employee_id for comparison
                if ldap_id not in db_users:
                    to_insert.append(ldap_user.to_tuple())
                elif ldap_tuple[:-1] != db_users[ldap_id]: # Compare all fields except the timestamp
                    to_update.append(ldap_user.to_tuple())

            # 3. Find records to delete (in DB but not in latest LDAP fetch)
            to_delete = set(db_users.keys()) - set(ldap_users_map.keys())

            # 4. Perform bulk database operations
            if to_insert:
                logger.info(f"Inserting {len(to_insert)} new records...")
                insert_query = """
                    INSERT INTO tbl_ldap_hierarchy (
                        employee_id, account_name, display_name, email, city, country, 
                        department, manager_name, manager_email, is_manager, last_updated
                    ) VALUES %s
                """
                psycopg2.extras.execute_values(cursor, insert_query, to_insert)

            if to_update:
                logger.info(f"Updating {len(to_update)} existing records...")
                update_query = """
                    UPDATE tbl_ldap_hierarchy SET
                        account_name = v.account_name, display_name = v.display_name, email = v.email,
                        city = v.city, country = v.country, department = v.department,
                        manager_name = v.manager_name, manager_email = v.manager_email,
                        is_manager = v.is_manager, last_updated = v.last_updated
                    FROM (VALUES %s) AS v(
                        employee_id, account_name, display_name, email, city, country, 
                        department, manager_name, manager_email, is_manager, last_updated
                    )
                    WHERE tbl_ldap_hierarchy.employee_id = v.employee_id;
                """
                psycopg2.extras.execute_values(cursor, update_query, to_update)

            if to_delete:
                logger.info(f"Deleting {len(to_delete)} obsolete records...")
                # Use a tuple for the WHERE IN clause
                delete_query = "DELETE FROM tbl_ldap_hierarchy WHERE employee_id IN %s"
                cursor.execute(delete_query, (tuple(to_delete),))

            if not any([to_insert, to_update, to_delete]):
                logger.info("No changes detected. Database is already up-to-date.")

            conn.commit()
            logger.info("Database synchronization complete.")

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Database synchronization failed: {e}")
    finally:
        db_pool.putconn(conn)


def main():
    """Main function to execute the LDAP report generation."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))
    
    include_emails_str = os.getenv('LDAP_INCLUDE_EMAILS')
    exclude_emails_str = os.getenv('LDAP_EXCLUDE_EMAILS', '')
    
    if not include_emails_str:
        logger.error("❌ LDAP_INCLUDE_EMAILS environment variable is not set. Aborting.")
        return

    include_list = [email.strip() for email in include_emails_str.split(',')]
    exclude_list = {email.strip().lower() for email in exclude_emails_str.split(',')}

    client = LdapClient()
    if not client.connect():
        return

    all_reports_flat = []
    for email in include_list:
        manager = client.get_user_by_email(email)
        if manager:
            logger.info(f"Fetching report structure for {manager.display_name}...")
            client.get_reports_for_user(manager, recursive=True)
            all_reports_flat.extend(flatten_reports(manager, exclude_list))

    client.close()
    
    # --- NEW: Get the database connection pool and sync the data ---
    db_pool = db_utils.get_connection_pool()
    sync_ldap_data_to_db(db_pool, all_reports_flat)

if __name__ == "__main__":
    main()
