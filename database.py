import pymysql


def exit_on_error(message):
    def exit_on_error_decorator(func):
        def wrapper(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Database.Error as e:
                print("{}: error_code={}, exception='{}'".format(message, *e.args))
                exit(1)

        return wrapper

    return exit_on_error_decorator


class Database:
    Error = pymysql.Error

    @staticmethod
    def _create_events_table(cursor):
        cursor.execute(query="CREATE TABLE IF NOT EXISTS events ("
                             "id int AUTO_INCREMENT PRIMARY KEY NOT NULL,"
                             "owner int,"
                             "name varchar(15) NOT NULL, "
                             "date varchar(5) NOT NULL, "
                             "time varchar(4) NOT NULL, "
                             "duration int NOT NULL)")

    @staticmethod
    def _create_users_table(cursor):
        cursor.execute(query="CREATE TABLE IF NOT EXISTS users ("
                             "id int AUTO_INCREMENT PRIMARY KEY NOT NULL,"
                             "login varchar(15) UNIQUE NOT NULL, "
                             "password varchar(32) NOT NULL)")

    @exit_on_error("An error occurred while trying to connect to database")
    def _connect_to_db(self):
        connection = pymysql.connect('localhost', 'root',
                                     'password', 'calendar', autocommit=True,
                                     cursorclass=pymysql.cursors.DictCursor)
        return connection, connection.cursor()

    @exit_on_error("An error occurred while trying to create tables")
    def _create_tables(self):
        self._create_events_table(self.cursor)
        self._create_users_table(self.cursor)

    def __enter__(self):
        self.connection, self.cursor = self._connect_to_db()
        self._create_tables()

    def __exit__(self):
        self.connection.close()

    def execute(self, query, *args):
        self.cursor.execute(query=query, args=args)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()
