from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseBadRequest
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from .models import Ad


@require_GET
def ad_click_redirect(request, pk):
	"""Record a click and redirect to the ad's target URL.

	Usage: /adverts/click/<pk>/
	"""
	ad = get_object_or_404(Ad, pk=pk)
	if not ad.target_url:
		return HttpResponseBadRequest('No target URL set for this ad')
	# increment click counter (uses F() inside model method)
	ad.click()
	return redirect(ad.target_url)


@csrf_exempt
def ad_impression_ping(request, pk):
	"""POST endpoint to record an impression for an ad; debounced by session/IP."""
	if request.method != 'POST':
		return JsonResponse({'error': 'POST required'}, status=405)

	ad = get_object_or_404(Ad, pk=pk)

	session_key = getattr(request.session, 'session_key', None)
	if not session_key:
		request.session.save()
		session_key = request.session.session_key

	requester_id = session_key or request.META.get('REMOTE_ADDR', 'anon')
	cache_key = f"ad_impression:{pk}:{requester_id}"

	if cache.get(cache_key):
		return JsonResponse({'message': 'already recorded recently'}, status=204)

	# Record impression
	try:
		ad.impression()
	except Exception:
		if hasattr(ad, 'increment_impression'):
			ad.increment_impression()

	cache.set(cache_key, 1, timeout=60)
	return JsonResponse({'message': 'impression recorded', 'impressions': getattr(ad, 'impressions', 0)})

