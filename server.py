import json
import logging
import uuid
from functools import partial
from http import cookies, server

from database import Database

logger = logging.getLogger('server')


def suppress_errors(handler):
    def wrapper(*args, **kwargs):
        try:
            return handler(*args, **kwargs)
        except Database.Error as e:
            logger.error("{}: error_code={}, exception='{}'".format(handler.__name__, *e.args))
            return {'is_successful': False}

    return wrapper


class Handler(server.BaseHTTPRequestHandler):
    RESPONSE_ERROR_CODES_MAP = {
        'default': 405,
        'login': 404,
        'register': 400,
        'save_event': 400,
        'get_events': 400,
        'get_username': 404,
    }

    def __init__(self, db, sessions_dict, *args, **kwargs):
        self.database = db
        self.sessions_dict = sessions_dict
        self.HANDLERS_MAP = {'login': partial(Handler._check_credentials, self),
                             'register': partial(Handler._save_credentials, self),
                             'save_event': partial(Handler._save_event, self),
                             'get_username': partial(Handler._get_username, self),
                             'get_events': partial(Handler._get_events, self)}
        super().__init__(*args, **kwargs)

    def __del__(self):
        self.connection.close()

    @suppress_errors
    def _get_username(self, user_id, **_):
        self.database.execute("SELECT login FROM users WHERE id = %s", user_id)
        logger.info("Trying to get username for user with id={}...".format(user_id))
        result = self.database.fetchall()
        if result:
            logger.info("User with id={} has username={}".format(user_id, result['login']))
            return {'is_successful': True, 'handler_result': json.dumps(result['login'])}
        else:
            logger.warning("User with id={} not found".format(user_id))
            return {'is_successful': False}

    def _set_cookie(self, cookie_name, cookie_value):
        cookie = cookies.SimpleCookie()
        cookie[cookie_name] = cookie_value
        self.send_header('Set-Cookie', cookie.output(header=''))

    def _get_cookie(self, cookie_name):
        if "Cookie" in self.headers:
            cookie = cookies.SimpleCookie(self.headers["Cookie"])
            if cookie_name in cookie:
                logger.info("Cookie with name={} has value={}".format(cookie_name, cookie[cookie_name].value))
                return cookie[cookie_name].value
        logger.warning("Cookie with name={} not found".format(cookie_name))
        return None

    @suppress_errors
    def _check_credentials(self, login, password, **_):
        self.database.execute("SELECT id FROM users WHERE login = %s AND password = %s", login, password)
        result = self.database.fetchone()
        if result:
            guid = str(uuid.uuid4())
            self.sessions_dict[guid] = result['id']
            self._set_cookie('SESSION_ID', guid)
            logger.info("User with id={} successfully logged in, assigned SESSION_ID={}".format(result['id'], guid))
            return {'is_successful': True}
        else:
            logger.warning("User with id={} not found".format(result['id']))
            return {'is_successful': False}

    @suppress_errors
    def _save_credentials(self, login, password, **_):
        self.database.execute("INSERT INTO users(login, password) VALUES (%s, %s)", login, password)
        logger.info("User with login={} successfully registered".format(login))
        return {'is_successful': True}

    @suppress_errors
    def _save_event(self, name, date, time, duration, user_id, **_):
        self.database.execute("INSERT INTO events(name, date, time, duration, owner) VALUES (%s, %s, %s, %s, %s)",
                              name, date, time, duration, user_id)
        logger.info(
            "Event with name={}, date={}, time={}, duration={} "
            "for user with id={} successfully saved".format(name, date, time, duration, user_id))
        return {'is_successful': True}

    @suppress_errors
    def _get_events(self, user_id, **_):
        self.database.execute("SELECT * FROM events WHERE owner=%s", user_id)
        logger.info("Events for user with id={} successfully received".format(user_id))
        return {'is_successful': True, 'handler_result': json.dumps(self.database.fetchall())}

    def _send_proper_response(self, request_type='default', is_successful=True, handler_result=None):
        if is_successful:
            self.send_response(200)
        else:
            self.send_response(self.RESPONSE_ERROR_CODES_MAP[request_type])
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        if handler_result:
            self.wfile.write(handler_result.encode('utf-8'))

    def _validate_params(self, post_data):
        mandatory_params = []
        if post_data['type'] in ('login', 'register'):
            mandatory_params = ['login', 'password']
        elif post_data['type'] in ('save_event', 'get_events', 'get_username'):
            if post_data['type'] == 'save_event':
                mandatory_params = ['name', 'date', 'time', 'duration']
            session_id = self._get_cookie('SESSION_ID')
            if session_id in self.sessions_dict:
                post_data['user_id'] = self.sessions_dict[session_id]
            mandatory_params.append('user_id')
        return all(key in post_data for key in mandatory_params)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        if 'type' not in post_data or \
                post_data['type'] not in self.HANDLERS_MAP or \
                not self._validate_params(post_data):
            logger.error("Request params({}) are invalid".format(post_data))
            self._send_proper_response(is_successful=False)
        else:
            handler_result_data = self.HANDLERS_MAP[post_data['type']](**post_data)
            self._send_proper_response(post_data['type'], **handler_result_data)


def run_server(config):
    server_config = config.get_server_config()
    db_config = config.get_database_config()
    with Database(**db_config) as database:
        s = server.ThreadingHTTPServer((server_config['host'], server_config['port']),
                                       partial(Handler, database, dict()))
        try:
            logger.info("Starting server on port {}...".format(server_config['port']))
            s.serve_forever()
        except KeyboardInterrupt:
            s.shutdown()
            logger.info("Server shut down")
