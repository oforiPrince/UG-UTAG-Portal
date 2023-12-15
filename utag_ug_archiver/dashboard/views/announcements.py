from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect



from dashboard.models import Executive, Event, News, Document, ExecutivePosition

from utag_ug_archiver.utils.decorators import MustLogin