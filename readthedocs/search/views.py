# -*- coding: utf-8 -*-

"""Search views."""
import collections
import logging
from pprint import pformat

from django.shortcuts import get_object_or_404, render

from readthedocs.builds.constants import LATEST
from readthedocs.projects.models import Project
from readthedocs.search.faceted_search import (
    AllSearch, ProjectSearch, PageSearch, DomainSearch, ALL_FACETS
)

log = logging.getLogger(__name__)
LOG_TEMPLATE = '(Elastic Search) [{user}:{type}] [{project}:{version}:{language}] {msg}'

UserInput = collections.namedtuple(
    'UserInput',
    (
        'query',
        'type',
        'project',
        'version',
        'taxonomy',
        'language',
        'doc_type',
        'index',
    ),
)


def elastic_search(request, project_slug=None):
    """
    Global user search on the dashboard

    This is for both the main search and project search.

    :param project_slug: Sent when the view is a project search
    """

    if project_slug:
        queryset = Project.objects.protected(request.user)
        project_obj = get_object_or_404(queryset, slug=project_slug)

    user_input = UserInput(
        query=request.GET.get('q'),
        type=request.GET.get('type', 'project'),
        project=project_slug or request.GET.get('project'),
        version=request.GET.get('version', LATEST),
        taxonomy=request.GET.get('taxonomy'),
        language=request.GET.get('language'),
        doc_type=request.GET.get('doc_type'),
        index=request.GET.get('index'),
    )

    results = ''
    facets = {}

    if user_input.query:
        kwargs = {}

        for avail_facet in ALL_FACETS:
            value = getattr(user_input, avail_facet, None)
            if value:
                kwargs[avail_facet] = value

        if user_input.type == 'project':
            search = ProjectSearch(
                query=user_input.query, user=request.user, **kwargs
            )

        elif user_input.type == 'domain':
            search = DomainSearch(
                query=user_input.query, user=request.user, **kwargs
            )

        elif user_input.type == 'file':
            search = PageSearch(
                query=user_input.query, user=request.user, **kwargs
            )

        elif user_input.type == 'all':
            search = AllSearch(
                query=user_input.query, user=request.user, **kwargs
            )

        results = search.execute()
        facets = results.facets

        log.info(
            LOG_TEMPLATE.format(
                user=request.user,
                project=user_input.project or '',
                type=user_input.type or '',
                version=user_input.version or '',
                language=user_input.language or '',
                msg=user_input.query or '',
            ),
        )

    # Make sure our selected facets are displayed even when they return 0 results
    for avail_facet in ALL_FACETS:
        value = getattr(user_input, avail_facet)
        if not value or avail_facet not in facets:
            continue
        if value not in [val[0] for val in facets[avail_facet]]:
            facets[avail_facet].insert(0, (value, 0, True))

    if results:
        if user_input.type == 'file':
            # Change results to turn newlines in highlight into periods
            # https://github.com/rtfd/readthedocs.org/issues/5168
            for result in results:
                if hasattr(result.meta.highlight, 'content'):
                    result.meta.highlight.content = [result.replace(
                        '\n', '. ') for result in result.meta.highlight.content]

        log.debug('Search results: %s', pformat(results.to_dict()))
        log.debug('Search facets: %s', pformat(results.facets.to_dict()))

    template_vars = user_input._asdict()
    template_vars.update({
        'results': results,
        'facets': facets,
    })

    if project_slug:
        template_vars.update({'project_obj': project_obj})

    return render(
        request,
        'search/elastic_search.html',
        template_vars,
    )
