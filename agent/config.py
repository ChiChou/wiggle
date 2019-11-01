'''
default configuration
'''

block_list = [
    # 
    '/System/Library/Frameworks/Ruby.framework',
    '/System/Library/Frameworks/Python.framework',
    '/System/Library/Frameworks/JavaVM.framework',

    # '/System/Library/PrivateFrameworks/Swift',

    # encrypted binaries
    # todo: https://osxbook.com/book/bonus/chapter7/binaryprotection/
    '/System/Library/CoreServices/Finder.app',

    # Kernel
    '/System/Library/PrelinkedKernels',

    # Xcode platform
    '/Applications/Xcode.app/Contents/Developer/Platforms',

    '/usr/lib/python2.7/',
    '/usr/lib/ruby',
    '/usr/libexec/apache2',
]

deprotect = '/usr/local/bin/deprotect'

from agent.config_user import *
