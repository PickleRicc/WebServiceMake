import logging
import sys

workers = 4
bind = "0.0.0.0:10000"
timeout = 120
accesslog = '-'
errorlog = '-'
loglevel = 'debug'

# Ensure all output is captured
capture_output = True
enable_stdio_inheritance = True
