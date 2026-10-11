"""Registered delivery event remains closed until its own worker is reviewed.

No common contact/search/model adapter can be substituted for delivery.
The original operation, authority and full liability remain for reconciliation.
"""
from ..registry import HandlerResult,register

@register('delivery.submit')
async def blocked_delivery(session,context,payload):
    return HandlerResult('blocked','delivery worker/provider connection is not selected')
