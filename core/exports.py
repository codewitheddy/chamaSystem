"""
Shared CSV export helper.
Usage:
    return csv_response(filename, headers, rows)
where rows is an iterable of lists/tuples.
"""
import csv
from django.http import HttpResponse


def csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response
