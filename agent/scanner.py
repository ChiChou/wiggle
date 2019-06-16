import os
import pathlib
import logging

from agent.importer import add


class Scanner(object):
    def __init__(self, directories, model, sysroot='/', block_list=None):
        self.directories = map(pathlib.Path, directories)
        self.sysroot = pathlib.Path(sysroot)
        self.model = model

        if block_list == None:
            self.block_list = []
        else:
            self.block_list = set(map(pathlib.Path, block_list))

    def run(self):
        for path in self.directories:
            try:
                self.scan(path)
            except (PermissionError, FileNotFoundError):
                logging.warning('Unable to read directory %s', path)

    def scan(self, cwd):
        from django.db import IntegrityError

        for blocked in self.block_list:
            if blocked == cwd or blocked in cwd.parents:
                return

        for child in cwd.iterdir():
            if child.is_dir():
                try:
                    self.scan(child)
                except PermissionError:
                    logging.warning('Unable to read directory %s', child)
            elif child.is_symlink():
                # TODO: better solution for symlink
                continue
            elif child.is_file():
                try:
                    add(child, self)
                except IntegrityError as e:
                    logging.error('Path %s may already exists\n(%s)', child, e)
                except PermissionError:
                    logging.warning('Unable to read file %s\n(%s)', child, e)
                except NotImplementedError as e:
                    logging.error('Unsupported file %s\n(%s)', child, e)
