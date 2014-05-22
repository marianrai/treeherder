from rest_framework import viewsets
from rest_framework.response import Response
from django.core import cache

from treeherder.webapp.api.utils import (UrlQueryFilter, with_jobs)

from treeherder.webapp.api.exceptions import ResourceNotFoundException

import urllib2
import gzip
import io
import logging

filesystem = cache.get_cache('filesystem')

class LogSliceView(viewsets.ViewSet):
    """
    This view serves slices of the log
    """

    def get_log_handle(self, url):
        """Hook to get a handle to the log with this url"""
        return urllib2.urlopen(url)

    @with_jobs
    def list(self, request, project, jm):
        """
        GET method implementation for log slicer

        Receives a line range and job_id and returns those lines
        """
        job_id = request.QUERY_PARAMS.get("job_id")

        filter = UrlQueryFilter({"job_id": job_id, "name": "Structured Log"})

        objs = jm.get_job_artifact_list(0, 1, filter.conditions)

        handle = None
        gz_file = None

        start_line = int(request.QUERY_PARAMS.get("start_line"))
        end_line = int(request.QUERY_PARAMS.get("end_line"))

        if objs:
            job = objs[0]

            try:

                url = job.get("blob").get("logurl")
                gz_file = filesystem.get(url)

                if not gz_file:
                    print('miss')
                    handle = self.get_log_handle(url)
                    gz_file = gzip.GzipFile(fileobj=io.BytesIO(handle.read()))
                    filesystem.set(url, gz_file.fileobj)
                else:
                    print('hit')
                    gz_file = gzip.GzipFile(fileobj=gz_file)

                lines = []

                for i, line in enumerate(gz_file):
                    if i < start_line or i >= end_line: continue
                    lines.append({"text": line, "index": i})

                return Response( lines )

            except Exception as e:
                logging.error(e)
                raise ResourceNotFoundException

            finally:
                if handle:
                    handle.close()
                if gz_file:
                    gz_file.close()

        else:
            return Response("job_artifact {0} not found".format(job_id), 404)
