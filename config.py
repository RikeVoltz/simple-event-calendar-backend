from localconfig import config


class Config:

    def __init__(self, filename):
        self.config = config
        self.config.read(filename)
        self._validate_params()

    def get_database_config(self):
        return dict(self.config.items('database'))

    def get_server_config(self):
        return dict(self.config.items('server'))

    def _validate_params(self):
        return self._validate_database_params() and self._validate_server_params()

    def _validate_database_params(self):
        return all(self.config.get('database', option) for option in ('host', 'user', 'password', 'db_name'))

    def _validate_server_params(self):
        return all(self.config.get('server', option) for option in ('host', 'port'))
