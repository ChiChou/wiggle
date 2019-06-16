from math import ceil

from django.shortcuts import render, redirect
from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseNotFound

from elasticsearch_dsl import Q, A
from elasticsearch import NotFoundError, RequestError

from libs.query import parse_query
from search.esmodels import MachO


def parse_boolean(value):
    lower = value.lower()
    if lower in ('yes', 'true'):
        return True

    if lower in ('no', 'false'):
        return False

    raise ValueError('invalid boolean value %s' % value)


def search(request):
    try:
        keyword = request.GET['q']
    except KeyError:
        return HttpResponseBadRequest('query should not be empty')

    args = parse_query(keyword)
    constraint = [Q('match', strings=keyword) for keyword in args['search']]
    show_fields = {}
    for key, value in args.items():
        if key == 'ent' or key == 'entitlement':
            def wrap(word):
                if "*" in word:
                    return Q('wildcard', ent_str=word)
                else:
                    return Q('match', ent_keys=word)

            constraint += [wrap(word) for word in value]
            show_fields['entitlement'] = True

        elif key in ('import', 'export', 'segment'):
            plural = key + 's'
            constraint += [Q('nested', path=plural, query=Q('match',
                                                            **{'%s.name' % plural: word})) for word in value]

        elif key == 'csflag':
            constraint += [Q('match', cs_flags_str=word) for word in value]

        elif key == 'path':
            constraint += [Q('match', path=word) for word in value]

        elif key in ('signed', 'apple', 'lv'):
            if len(value) > 1:
                raise HttpResponseBadRequest(
                    'expect only one %s filter' % key)  # not XSS
            constraint += [Q('match', **{key: parse_boolean(value.pop())})]

        elif key == 'lib':
            constraint += [Q('match', libraries=word) for word in value]

        elif key == 'codesign':
            constraint += [Q('term', **{key: word.lower()}) for word in value]
            show_fields[key] = True

    try:
        page_num = int(request.GET['page']) - 1
    except:
        page_num = 0

    if page_num < 0:
        return HttpResponseNotFound('invalid page')

    begin = page_num * settings.PER_PAGE
    end = begin + settings.PER_PAGE

    base_query = MachO.search()\
        .query(Q('bool', must=constraint)) \
        .highlight_options(order='score', encoder='html') \
        .highlight('ent_str') \
        .highlight('codesign')

    try:
        response = base_query.highlight('strings')[begin:end].execute()
    except RequestError:
        # bug workaround: "strings" length exceed the limit of highlight
        response = base_query[begin:end].execute()

    max_page = ceil(response.hits.total.value / settings.PER_PAGE)
    left = 1
    right = max_page + 1
    if max_page > 10:
        left = max(1, page_num - 5)
        right = min(left + 10, right)

    paginator = range(left, right)

    return render(request, 'search.html', dict(
        keyword=keyword,
        parsed=args,
        show_fields=show_fields,
        page=page_num + 1,
        max_page=max_page,
        paginator=paginator,
        took=response.took / 1000,
        response=response))


def detail(request, index, doc_id):
    try:
        doc = MachO.get(id=doc_id, index=index)
    except NotFoundError:
        return HttpResponseNotFound('Sorry, requested document was not found')

    return render(request, 'detail.html', dict(doc=doc))


def home(request):
    import random
    from django.conf import settings

    suggested = random.sample(settings.HOME_SUGGESTED_SEARCH, k=4)
    return render(request, 'home.html', { 'suggested': suggested})


def entitlements(request):
    keys_aggr = A('terms', field='ent_keys.raw', size=1024)
    search = MachO.search().query('match_all').extra(size=0)
    search.aggs.bucket('all_entitlement_names', keys_aggr)
    ents = search.execute().to_dict()
    return render(request, 'entitlements.html', dict(entitlements=ents))
