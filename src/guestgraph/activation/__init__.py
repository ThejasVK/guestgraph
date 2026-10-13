from .base import ActivationResult, Connector
from .google_ads import GoogleCustomerMatch
from .meta import MetaCustomAudience

CONNECTORS = {"meta": MetaCustomAudience, "google": GoogleCustomerMatch}

__all__ = ["ActivationResult", "Connector", "GoogleCustomerMatch", "MetaCustomAudience", "CONNECTORS"]
