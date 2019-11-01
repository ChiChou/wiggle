import pathlib
import os
import datetime
import logging
import plistlib
import tempfile

import lief

from agent.radare2 import parse as r2parse
from agent.codesign import CSFlags, parse_file as parse_codesign
from agent.external import apple, deprotect, codesign as check_codesign_cmd

def is_drm(o):
    TPM_ENCRYPTED = 8
    return any(s.flags & TPM_ENCRYPTED == TPM_ENCRYPTED for s in o.segments)


def add(abspath, context):
    filename = str(abspath)
    path = str(context.sysroot / abspath.relative_to(context.sysroot))

    Model = context.model
    if Model.objects.filter(path=path).exists():
        logging.warning('%s already exists', filename)
        return

    entity = Model()
    entity.raw_path = filename
    entity.path = path

    binary = lief.parse(filename)
    if not binary:
        return  # not an executable

    logging.info('file: %s', filename)

    with tempfile.TemporaryFile() as tmpfile:
        # lief
        if isinstance(binary, lief.MachO.Binary):
            parser = MachOParser(filename, context)
        else:
            raise NotImplementedError('Executable format unsupported yet %s' % binary.format)

        if is_drm(binary):
            deprotect(filename, tmpfile.name)
            filename = tmpfile.name
            parser = MachOParser(filename, context)

        parser.assign(entity)

        # radare2
        try:
            r2parse(filename, entity)
        except Exception as e:
            logging.error('Failed to decode radare2 output, file may be corrupted or unsupported')
            logging.error(e)
            return

    entity.save()
    return entity


class Parser(object):
    def __init__(self, path, context):
        self.path = path
        self.context = context
        self.binary = lief.parse(path)
        self.parser = None

    def assign(self, entity):
        # timestamp
        st = os.stat(self.path)
        entity.created = datetime.datetime.fromtimestamp(st.st_ctime)
        entity.modified = datetime.datetime.fromtimestamp(st.st_mtime)
        entity.added = datetime.datetime.now()

        self.parse_macho(entity)


class MachOParser(Parser):
    def parse_macho(self, entity):
        try:
            content = next(sect.content for sect in self.binary.sections if sect.name == '__info_plist')
            buf = bytes(content).rstrip(b'\x00')

            entity.info_plist_str = buf.decode('utf8')
            entity.info_plist = plistlib.loads(buf)

        except (plistlib.InvalidFileException, StopIteration):
            pass

        signature = parse_codesign(self.binary, self.path)
        if signature:
            entity.signed = True
            if signature.entitlement:
                entity.ent = signature.entitlement.as_dict()
                entity.ent_str = signature.entitlement.dump()
                entity.ent_keys = list(signature.entitlement.keys())

            entity.cs_flags = int(signature.flags)
            entity.cs_flags_str = str(signature.flags)
            entity.lv = CSFlags.kSecCodeSignatureLibraryValidation in signature.flags

            entity.apple = apple(self.path)
            entity.codesign = check_codesign_cmd(self.path)

        rpaths = [self.parse_rpath(cmd) for cmd in self.binary.commands
                  if cmd.command == lief.MachO.LOAD_COMMAND_TYPES.RPATH]
        entity.rpaths = rpaths

    def parse_rpath(self, cmd):
        path = cmd.path
        prefix = path[1:path.find('/')] if path.startswith('@') else ''
        return dict(path=path, prefix=prefix)
