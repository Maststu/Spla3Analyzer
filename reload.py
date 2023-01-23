import sys
import yarr
import numpy

import socketserver

def proc_numpy(a):
    print(a)

def quit(retcode: int):
    sys.exit(retcode)

# server
socketserver.TCPServer.allow_reuse_address = True
yarr.yarr(('localhost', 8000), [proc_numpy, quit])