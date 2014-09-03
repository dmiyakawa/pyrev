# -*- coding: utf-8 -*-

from logging import getLogger, DEBUG

def _enable_logger(logger):
    from logging import StreamHandler
    handler = StreamHandler()
    handler.setLevel(DEBUG)
    logger.setLevel(DEBUG)
    logger.addHandler(handler)
    return logger

def _disable_logger(logger):
    from logging import NullHandler
    logger.addHandler(NullHandler())
    return logger

def setup_logger(name, debug):
    logger = getLogger(name)
    if debug:
        return _enable_logger(logger)
    else:
        return _disable_logger(logger)
