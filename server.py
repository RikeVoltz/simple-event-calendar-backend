import json
import uuid
from functools import partial
from http import cookies, server

import pymysql


def suppress_errors(handler):
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except pymysql.Error:
            return False

    return wrapper


class Handler(server.BaseHTTPRequestHandler):
    RESPONSE_ERROR_CODES_MAP = {
        'default': 405,
        'login': 404,
        'register': 400,
        'save_event': 400,
        'get_events': 400,
        'get_username': 404,
        'connect_to_db': 500,
    }

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

    def __init__(self, *args, **kwargs):
        self.sessions_dict = dict()
        self.HANDLERS_MAP = {'login': partial(Handler._check_credentials, self),
                             'register': partial(Handler._save_credentials, self),
                             'save_event': partial(Handler._save_event, self),
                             'get_username': partial(Handler._get_username, self),
                             'get_events': partial(Handler._get_events, self),
                             'connect_to_db': partial(Handler._connect_to_db, self)}
        request_result = self.HANDLERS_MAP['connect_to_db']()
        if not request_result:
            self._send_proper_response('connect_to_db', **request_result)
        self._create_events_table(self.cursor)
        self._create_users_table(self.cursor)
        super().__init__(*args, **kwargs)

    def __del__(self):
        self.connection.close()

    @suppress_errors
    def _connect_to_db(self):
        self.connection = pymysql.connect('localhost', 'root',
                                          'password', 'calendar', autocommit=True,
                                          cursorclass=pymysql.cursors.DictCursor)
        self.cursor = self.connection.cursor()
        return {'is_successful': True}

    @suppress_errors
    def _get_username(self, user_id, **_):
        self.cursor.execute(query="SELECT login FROM users WHERE id = %s",
                            args=[user_id])
        result = self.cursor.fetchall()
        if result:
            return {'is_successful': True, 'handler_result': json.dumps(result)}
        else:
            return {'is_successful': False}

    def _set_cookie(self, cookie_name, cookie_value):
        cookie = cookies.SimpleCookie()
        cookie[cookie_name] = cookie_value
        self.send_header('Set-Cookie', cookie.output(header=''))

    def _get_cookie(self, cookie_name):
        if "Cookie" in self.headers:
            cookie = cookies.SimpleCookie(self.headers["Cookie"])
            return cookie[cookie_name].value
        return None

    @suppress_errors
    def _check_credentials(self, login, password, **_):
        self.cursor.execute(query="SELECT id FROM users WHERE login = %s AND password = %s",
                            args=[login, password])
        result = self.cursor.fetchone()
        if result:
            guid = uuid.uuid4()
            self.sessions_dict[guid] = result['id']
            self._set_cookie('SESSION_ID', guid)
            return {'is_successful': True}
        else:
            return {'is_successful': False}

    @suppress_errors
    def _save_credentials(self, user, password, **_):
        self.cursor.execute(query="INSERT INTO users(login, password) VALUES (%s, %s)", args=[user, password])
        return {'is_successful': True}

    @suppress_errors
    def _save_event(self, name, date, time, duration, **_):
        self.cursor.execute(query="INSERT INTO events(name, date, time, duration) VALUES (%s, %s, %s, %s)",
                            args=[name, date, time, duration])
        return {'is_successful': True}

    @suppress_errors
    def _get_events(self, user_id, **_):
        self.cursor.execute(query="SELECT * FROM events WHERE owner=%s", args=[user_id])
        return {'is_successful': True, 'handler_result': json.dumps(self.cursor.fetchall())}

    def _send_proper_response(self, request_type='default', is_successful=True, handler_result=None):
        if is_successful:
            self.send_response(200, handler_result)
        else:
            self.send_response(self.RESPONSE_ERROR_CODES_MAP[request_type], handler_result)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def _validate_params(self, post_data):
        if post_data['type'] in ('login', 'register'):
            return all(key in post_data for key in ('login', 'password'))
        elif post_data['type'] == 'save_event':
            return all(key in post_data for key in ('name', 'date', 'time', 'duration'))
        elif post_data['type'] in ('get_events', 'get_username'):
            session_id = self._get_cookie('SESSION_ID')
            if session_id in self.sessions_dict:
                post_data['user_id'] = self.sessions_dict[session_id]
            return 'user_id' in post_data

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        if 'type' not in post_data or \
                post_data['type'] not in self.HANDLERS_MAP or \
                not self._validate_params(post_data):
            self._send_proper_response(is_successful=False)
        else:
            handler_result_data = self.HANDLERS_MAP[post_data['type']](**post_data)
            self._send_proper_response(post_data['type'], **handler_result_data)


def serve_on_port(port):
    s = server.ThreadingHTTPServer(("localhost", port), Handler)
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        s.shutdown()


if __name__ == '__main__':
    serve_on_port(5000)
