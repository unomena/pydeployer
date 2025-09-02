"""
Database management for deployments
"""
import logging
import psycopg2
from psycopg2 import sql
import pymysql
import subprocess
from django.conf import settings

logger = logging.getLogger('deployer')


class DatabaseManager:
    """Manages database operations for deployments"""
    
    def __init__(self):
        self.logger = logger
    
    def ensure_database(self, db_config, deployment=None):
        """
        Ensure database exists and is accessible
        
        Args:
            db_config: Database configuration from deploy yaml
            deployment: Deployment object for logging
            
        Returns:
            tuple: (success: bool, message: str)
        """
        engine = db_config.get('engine', 'postgresql')
        
        if engine == 'postgresql':
            return self._ensure_postgresql(db_config, deployment)
        elif engine == 'mysql':
            return self._ensure_mysql(db_config, deployment)
        elif engine == 'sqlite3':
            # SQLite doesn't need creation
            return True, "SQLite database will be created automatically"
        else:
            return False, f"Unsupported database engine: {engine}"
    
    def _ensure_postgresql(self, db_config, deployment=None):
        """Ensure PostgreSQL database exists"""
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 5432)
        db_name = db_config.get('name')
        db_user = db_config.get('user')
        db_password = db_config.get('password')
        create_if_missing = db_config.get('create_if_missing', True)
        test_connection = db_config.get('test_connection', True)
        
        if not all([db_name, db_user]):
            return False, "Database name and user are required"
        
        # First, test if we can connect to the database
        if test_connection:
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    database=db_name,
                    user=db_user,
                    password=db_password,
                    connect_timeout=5
                )
                conn.close()
                self._log(deployment, 'INFO', f"Successfully connected to database {db_name}")
                return True, f"Database {db_name} exists and is accessible"
            except psycopg2.OperationalError as e:
                if 'does not exist' in str(e):
                    if not create_if_missing:
                        return False, f"Database {db_name} does not exist and create_if_missing is False"
                    # Try to create the database
                    return self._create_postgresql_database(
                        host, port, db_name, db_user, db_password, deployment
                    )
                else:
                    # Connection error (wrong password, host, etc.)
                    return False, f"Cannot connect to database: {str(e)}"
        
        return True, "Database check skipped (test_connection=False)"
    
    def _create_postgresql_database(self, host, port, db_name, db_user, db_password, deployment=None):
        """Create PostgreSQL database"""
        try:
            # Try to connect to postgres database to create the new database
            # First try with provided credentials
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    database='postgres',
                    user=db_user,
                    password=db_password,
                    connect_timeout=5
                )
            except:
                # If that fails, try with postgres user (for local deployments)
                if host in ['localhost', '127.0.0.1']:
                    # Use sudo for local postgres
                    try:
                        cmd = ['sudo', '-u', 'postgres', 'psql', '-c', 
                               f"CREATE DATABASE {db_name} OWNER {db_user};"]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            self._log(deployment, 'INFO', f"Created database {db_name} using sudo")
                            return True, f"Database {db_name} created successfully"
                        else:
                            # Database might already exist
                            if 'already exists' in result.stderr:
                                return True, f"Database {db_name} already exists"
                            return False, f"Failed to create database: {result.stderr}"
                    except Exception as e:
                        return False, f"Failed to create database with sudo: {str(e)}"
                else:
                    # For remote databases, we can't create without proper credentials
                    return False, "Cannot create database on remote server without admin credentials"
            
            # If we got a connection, create the database
            conn.autocommit = True
            cur = conn.cursor()
            
            # Check if database exists
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (db_name,)
            )
            if cur.fetchone():
                conn.close()
                return True, f"Database {db_name} already exists"
            
            # Create database
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(db_name),
                    sql.Identifier(db_user)
                )
            )
            conn.close()
            
            self._log(deployment, 'INFO', f"Created database {db_name}")
            return True, f"Database {db_name} created successfully"
            
        except Exception as e:
            return False, f"Failed to create database: {str(e)}"
    
    def _ensure_mysql(self, db_config, deployment=None):
        """Ensure MySQL database exists"""
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 3306)
        db_name = db_config.get('name')
        db_user = db_config.get('user')
        db_password = db_config.get('password')
        create_if_missing = db_config.get('create_if_missing', True)
        test_connection = db_config.get('test_connection', True)
        
        if not all([db_name, db_user]):
            return False, "Database name and user are required"
        
        if test_connection:
            try:
                conn = pymysql.connect(
                    host=host,
                    port=port,
                    database=db_name,
                    user=db_user,
                    password=db_password,
                    connect_timeout=5
                )
                conn.close()
                self._log(deployment, 'INFO', f"Successfully connected to MySQL database {db_name}")
                return True, f"Database {db_name} exists and is accessible"
            except pymysql.err.OperationalError as e:
                if 'Unknown database' in str(e):
                    if not create_if_missing:
                        return False, f"Database {db_name} does not exist and create_if_missing is False"
                    # Try to create the database
                    return self._create_mysql_database(
                        host, port, db_name, db_user, db_password, deployment
                    )
                else:
                    return False, f"Cannot connect to database: {str(e)}"
        
        return True, "Database check skipped (test_connection=False)"
    
    def _create_mysql_database(self, host, port, db_name, db_user, db_password, deployment=None):
        """Create MySQL database"""
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=db_user,
                password=db_password,
                connect_timeout=5
            )
            cur = conn.cursor()
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
            conn.commit()
            conn.close()
            
            self._log(deployment, 'INFO', f"Created MySQL database {db_name}")
            return True, f"Database {db_name} created successfully"
            
        except Exception as e:
            return False, f"Failed to create database: {str(e)}"
    
    def build_database_url(self, db_config):
        """Build DATABASE_URL from config"""
        engine = db_config.get('engine', 'postgresql')
        
        if engine == 'sqlite3':
            db_name = db_config.get('name', 'db.sqlite3')
            return f"sqlite:///{db_name}"
        
        # Map engine names to URL schemes
        engine_map = {
            'postgresql': 'postgresql',
            'postgres': 'postgresql',
            'mysql': 'mysql',
            'mariadb': 'mysql'
        }
        
        scheme = engine_map.get(engine, engine)
        user = db_config.get('user')
        password = db_config.get('password')
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 5432 if 'postgres' in engine else 3306)
        name = db_config.get('name')
        
        if user and password:
            return f"{scheme}://{user}:{password}@{host}:{port}/{name}"
        elif user:
            return f"{scheme}://{user}@{host}:{port}/{name}"
        else:
            return f"{scheme}://{host}:{port}/{name}"
    
    def _log(self, deployment, level, message):
        """Log message to deployment and logger"""
        if deployment:
            from .models import DeploymentLog
            DeploymentLog.objects.create(
                deployment=deployment,
                level=level,
                message=message
            )
        
        if level == 'ERROR':
            self.logger.error(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        else:
            self.logger.info(message)