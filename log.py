import logging.handlers

logger = logging.getLogger('rhel-feeder')
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
file_handler = logging.FileHandler('rhel-feeder.log')
file_handler.setFormatter(formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical
