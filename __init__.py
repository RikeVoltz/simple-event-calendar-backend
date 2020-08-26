from server import run_server
from config import Config
import logging.config

if __name__ == '__main__':
    logging.config.fileConfig('logging.conf')
    try:
        config = Config('server.conf')
        run_server(config)
    except Exception as e:
        logging.critical('Invalid configuration: "{}"'.format(e))
        exit(1)
