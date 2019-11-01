import subprocess


# TODO: use ctypes to invoke SecCodeCheckValidity
def apple(filename):
    args = ['codesign', '-R=anchor apple', '-v', filename]
    status = subprocess.call(args, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    return status == 0


def codesign(filename):
    args = ['codesign', '-dvvv', filename]
    try:
        return subprocess.check_output(args, stderr=subprocess.STDOUT).decode('utf8')
    except:
        return ''


def deprotect(src, dst):
    from agent.config import deprotect as deprotect_path
    args = [deprotect_path, src, dst]
    status = subprocess.call(args, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    return status == 0


if __name__ == "__main__":
    print(apple('/bin/sh'))
    print(apple('/etc/passwd'))
    print(codesign('/bin/sh'))
    print(codesign('/etc/passwd'))
    print(deprotect('/System/Library/CoreServices/Finder.app/Contents/MacOS/Finder', '/tmp/Finder'))
