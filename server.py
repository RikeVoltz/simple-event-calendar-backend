import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import pymysql

REQUEST_TYPES = ('login', 'register', 'save_event')


class Handler(BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        try:
            self.connection = pymysql.connect('localhost', 'root',
                                              'password', 'calendar', autocommit=True)
            self.cursor = self.connection.cursor()
        except pymysql.OperationalError:
            self.send_response(500)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            raise
        self.cursor.execute(query="CREATE TABLE IF NOT EXISTS users ("
                                  "ID int AUTO_INCREMENT PRIMARY KEY NOT NULL,"
                                  "login varchar(15) UNIQUE NOT NULL, "
                                  "password varchar(32) NOT NULL)")
        self.cursor.execute(query="CREATE TABLE IF NOT EXISTS events ("
                                  "ID int AUTO_INCREMENT PRIMARY KEY NOT NULL,"
                                  "owner int,"
                                  "name varchar(15) NOT NULL, "
                                  "date varchar(5) NOT NULL, "
                                  "time varchar(4) NOT NULL, "
                                  "duration int NOT NULL)")
        super().__init__(*args, **kwargs)

    def __del__(self):
        self.connection.close()

    def check_credentials(self, user, password):
        try:
            self.cursor.execute(query="SELECT COUNT(*) FROM users WHERE login = %s AND password = %s",
                                args=[user, password])
            return self.cursor.fetchone()[0]
        except pymysql.Error:
            return False

    def save_credentials(self, user, password):
        try:
            self.cursor.execute(query="INSERT INTO users(login, password) VALUES (%s, %s)", args=[user, password])
            return True
        except pymysql.Error as e:
            print(e)
        return False

    def save_event(self, name, date, time, duration):
        try:
            self.cursor.execute(query="INSERT INTO events(name, date, time, duration) VALUES (%s, %s, %s, %s)", args=[name, date, time, duration])
            return True
        except pymysql.Error as e:
            print(e)
        return False

    def send_proper_response(self, request_result, request_type):
        if request_result:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
        else:
            if request_type == 'login':
                self.send_response(404)
                self.send_header('Access-Control-Allow-Origin', '*')
            if request_type in ('register', 'save_event'):
                self.send_response(400)
                self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    @staticmethod
    def verify_post_data_params(post_data):
        if post_data['type'] in ('login', 'register'):
            return 'login' in post_data and 'password' in post_data
        elif post_data['type'] == 'save_event':
            return 'name' in post_data and 'date' in post_data and \
                   'time' in post_data and 'duration' in post_data

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        if 'type' not in post_data or post_data['type'] not in REQUEST_TYPES:
            self.send_response(403)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
        else:
            request_result = False
            self.verify_post_data_params(post_data)
            if post_data['type'] == 'login':
                request_result = self.check_credentials(post_data['login'], post_data['password'])
            elif post_data['type'] == 'register':
                request_result = self.save_credentials(post_data['login'], post_data['password'])
            elif post_data['type'] == 'save_event':
                request_result = self.save_event(post_data['name'], post_data['date'],
                                                 post_data['time'], post_data['duration'])
            self.send_proper_response(request_result, post_data['type'])


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def serve_on_port(port):
    server = ThreadingHTTPServer(("localhost", port), Handler)
    server.serve_forever()


serve_on_port(5000)

