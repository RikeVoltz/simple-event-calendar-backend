import logging.config
import pymysql

logger = logging.getLogger('database')


def exit_on_error(message):
    def exit_on_error_decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Database.Error as e:
                logger.critical("{}: error_code={}, exception='{}'".format(message, *e.args))
                exit(1)

        return wrapper

    return exit_on_error_decorator


class Database:
    Error = pymysql.Error

    def __init__(self, host, user, password, db_name):
        self.host = host
        self.user = user
        self.password = password
        self.db_name = db_name

    @staticmethod
    def _create_events_table(cursor):
        cursor.execute(query="CREATE TABLE IF NOT EXISTS events ("
                             "id int AUTO_INCREMENT PRIMARY KEY NOT NULL,"
                             "owner int,"
                             "name varchar(15) NOT NULL, "
                             "date varchar(15) NOT NULL, "
                             "time varchar(15) NOT NULL, "
                             "duration int NOT NULL)")

    @staticmethod
    def _create_users_table(cursor):
        cursor.execute(query="CREATE TABLE IF NOT EXISTS users ("
                             "id int AUTO_INCREMENT PRIMARY KEY NOT NULL,"
                             "login varchar(15) UNIQUE NOT NULL, "
                             "password varchar(32) NOT NULL)")

    @exit_on_error("An error occurred while trying to connect to database")
    def _connect_to_db(self):
        logger.info("Connecting to database...")
        connection = pymysql.connect(self.host, self.user,
                                     self.password, self.db_name, autocommit=True,
                                     cursorclass=pymysql.cursors.DictCursor)
        cursor = connection.cursor()
        return connection, cursor

    @exit_on_error("An error occurred while trying to create tables")
    def _create_tables(self):
        logger.info("Creating events and users tables (if needed)...")
        self._create_events_table(self.cursor)
        self._create_users_table(self.cursor)
        logger.info("User and events tables created")

    def __enter__(self):
        self.connection, self.cursor = self._connect_to_db()
        logger.info("Database connection established")
        self._create_tables()
        return self

    def __exit__(self, *_):
        self.connection.close()
        logger.info("Database connection closed")

    def execute(self, query, *args):
        logger.info("Executing query: '{}' with args: {}".format(query, args))
        self.cursor.execute(query=query, args=args)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()
