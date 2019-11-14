import os
import logging
import json
import time

import coloredlogs

coloredlogs.install(level='DEBUG')

# mute ElasticSearch
tracer = logging.getLogger('elasticsearch')
tracer.setLevel(logging.CRITICAL)  # or desired level
tracer.addHandler(logging.FileHandler('indexer.log'))


COMMON_KEYS = ['raw_path', 'path', 'strings', 'libraries',
               'imports', 'exports', 'segments', 'entries', 'created',
               'modified', 'added']

MACHO_KEYS = COMMON_KEYS + [
    'classdump', 'rpaths', 'ent_str', 'ent_keys', 'cs_flags', 'lv',
    'signed', 'apple', 'codesign', 'info_plist_str']


class Storage(object):
    def __init__(self, index_name):
        self.index_name = index_name

    def migrate(self, throttle):
        from elasticsearch.helpers import bulk as bulk_save
        from elasticsearch.exceptions import ConnectionTimeout, ConnectionError
        from django.core.paginator import Paginator

        count = MachO.objects.count()
        logging.info('index: %s', self.index_name)
        logging.info('data count: %d', count)
        paginator = Paginator(MachO.objects.all().order_by('id'), 100)
        for index in paginator.page_range:
            page = paginator.page(index)
            try:
                inserted, errors = bulk_save(es_connection, map(
                    self.convert, page.object_list), raise_on_error=False)
            except (ConnectionTimeout, ConnectionError):
                logging.warning('connection failure, retry')
                time.sleep(throttle * 2)

                # throw this time
                inserted, errors = bulk_save(es_connection, map(
                    self.convert, page.object_list), raise_on_error=False)

            logging.info('bulk operation, page: %d/%d, successful: %d',
                         index, paginator.num_pages, inserted)

            for failed in errors:
                logging.error(failed)

            time.sleep(throttle)

    def convert(self, macho):
        meta = {'index': self.index_name}
        doc = MachODoc(meta=meta, **{key: getattr(macho, key)
                                     for key in MACHO_KEYS})

        doc.info = macho.meta
        # doc.classes = [Clazz(**clazz) for clazz in macho.classes]
        # todo: remove redundant serialize/deserialize
        doc.ent = json.dumps(macho.ent)
        # todo: use different splitter in scanner
        doc.cs_flags_str = macho.cs_flags_str.split(' | ')
        doc.info_plist = json.dumps(macho.info_plist)
        return doc.to_dict(include_meta=True)


if __name__ == '__main__':
    import sys
    if sys.platform != 'linux':
        logging.warn(
            'You need to run this script inside docker, or you will met unexpected problem')

    sys.path.append(os.getcwd())
    sys.path.append(os.path.join(os.getcwd(), 'web'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wiggle.settings')

    from search.esmodels import MachO as MachODoc, RPath, Clazz, connection as es_connection

    import django
    from django.conf import settings
    from django.core import management

    django.setup()

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('index', help='index name')
    parser.add_argument('db', help='path to SQLite3 archive')
    parser.add_argument('--throttle', type=float, default=0,
        help='seconds to sleep after every 100 records have been imported')
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print("Fatal error: %s does not exist" % args.db)
        sys.exit(1)

    settings.DATABASES['default']['NAME'] = args.db

    from search.models import MachO

    prefix = MachODoc.Index.name.replace('*', '')
    if args.index.startswith(prefix):
        index_name = args.index
    else:
        index_name = prefix + args.index

    index = MachODoc._index.as_template(index_name)
    index.save()

    storage = Storage(index_name)
    storage.migrate(args.throttle)
