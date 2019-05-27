import shutil
import subprocess
import json

import r2pipe

FIELD_MAPPING = {
    # json
    'classes': 'icj',
    'libraries': 'ilj',
    'meta': 'iIj',
    'imports': 'iij',
    'exports': 'iEj',
    'segments': 'iSj',
    'entries': 'ieej'
}

HAS_STRINGS = bool(shutil.which('strings'))
HAS_CLASS_DUMP = bool(shutil.which('class-dump'))


def parse(path, entity):
    r2 = r2pipe.open(path, ['-2'])

    strings_failed = False
    if HAS_STRINGS:
        try:
            entity.strings = subprocess.check_output(
                ['strings', path]).decode('utf8')
        except:
            strings_failed = True

    if strings_failed or not HAS_STRINGS:  # fallback to r2 (much slower)
        entity.strings = '\n'.join([
            s.get('string')
            for s in json.loads(r2.cmd('izzj')).get('strings')])

    class_dump_failed = False
    if HAS_CLASS_DUMP:
        try:
            entity.classdump = subprocess.check_output(
                ['class-dump', path], stderr=subprocess.DEVNULL).decode('utf8')
        except:
            class_dump_failed = True

    if class_dump_failed or not HAS_CLASS_DUMP:
        entity.classdump = r2.cmd('icc')

    for key, cmd in FIELD_MAPPING.items():
        val = r2.cmd(cmd)
        if not val:
            continue
        obj = json.loads(val)
        setattr(entity, key, obj)
